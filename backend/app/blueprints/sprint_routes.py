from datetime import date, datetime, timezone

from flask import Blueprint, jsonify, request

from ..auth import require_project, token_required
from ..errors import ApiError
from ..events import broadcast
from ..auth import current_user
from ..extensions import db
from ..history import record
from ..models import Issue, Sprint, today_utc

bp = Blueprint('sprints', __name__, url_prefix='/api')


def _parse_date(value):
    if value in (None, ''):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ApiError('Dates must look like 2026-09-20.')


def _load_sprint(sprint_id: int, minimum: str = 'developer') -> Sprint:
    sprint = db.session.get(Sprint, sprint_id)
    if sprint is None:
        raise ApiError('That sprint does not exist.', 404)
    require_project(sprint.project_id, minimum=minimum)
    return sprint


@bp.get('/projects/<int:project_id>/sprints')
@token_required
def list_sprints(project_id: int):
    project = require_project(project_id)
    order = {'active': 0, 'future': 1, 'completed': 2}
    sprints = sorted(project.sprints, key=lambda s: (order.get(s.state, 3), -s.id))
    return jsonify(sprints=[sprint.to_dict() for sprint in sprints])


@bp.post('/projects/<int:project_id>/sprints')
@token_required
def create_sprint(project_id: int):
    project = require_project(project_id, minimum='manager')
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    if not name:
        # Jira's own convention: "DEV Sprint 3".
        name = f'{project.key} Sprint {len(project.sprints) + 1}'

    sprint = Sprint(
        project_id=project.id,
        name=name,
        goal=(data.get('goal') or '').strip(),
        start_date=_parse_date(data.get('startDate')),
        end_date=_parse_date(data.get('endDate')),
    )
    db.session.add(sprint)
    db.session.commit()

    broadcast('sprint:changed', {'projectId': project.id}, project.id)
    return jsonify(sprint=sprint.to_dict()), 201


@bp.patch('/sprints/<int:sprint_id>')
@token_required
def update_sprint(sprint_id: int):
    sprint = _load_sprint(sprint_id, minimum='manager')
    data = request.get_json(silent=True) or {}

    if 'name' in data:
        name = (data['name'] or '').strip()
        if not name:
            raise ApiError('A sprint needs a name.')
        sprint.name = name
    if 'goal' in data:
        sprint.goal = (data['goal'] or '').strip()
    if 'startDate' in data:
        sprint.start_date = _parse_date(data['startDate'])
    if 'endDate' in data:
        sprint.end_date = _parse_date(data['endDate'])

    db.session.commit()
    broadcast('sprint:changed', {'projectId': sprint.project_id}, sprint.project_id)
    return jsonify(sprint=sprint.to_dict())


@bp.post('/sprints/<int:sprint_id>/start')
@token_required
def start_sprint(sprint_id: int):
    sprint = _load_sprint(sprint_id, minimum='manager')

    if sprint.state != 'future':
        raise ApiError('Only a future sprint can be started.')
    # One active sprint at a time, as in Jira's simple board.
    running = db.session.scalar(
        db.select(Sprint).filter_by(project_id=sprint.project_id, state='active')
    )
    if running is not None:
        raise ApiError(f'{running.name} is still running. Complete it first.', 409)
    if not sprint.issues:
        raise ApiError('Add some issues to the sprint before starting it.')

    sprint.state = 'active'
    if sprint.start_date is None:
        sprint.start_date = today_utc()

    record('sprint.started', project_id=sprint.project_id, actor=current_user(),
           after=sprint.name, subject=sprint.name)
    db.session.commit()
    broadcast('sprint:changed', {'projectId': sprint.project_id}, sprint.project_id)
    return jsonify(sprint=sprint.to_dict())


@bp.post('/sprints/<int:sprint_id>/complete')
@token_required
def complete_sprint(sprint_id: int):
    """Finish a sprint; unfinished issues roll to the next one or the backlog."""
    sprint = _load_sprint(sprint_id, minimum='manager')
    if sprint.state != 'active':
        raise ApiError('Only the active sprint can be completed.')

    move_to = (request.get_json(silent=True) or {}).get('moveUnfinishedTo')
    target_id = None
    if move_to:
        target = db.session.get(Sprint, int(move_to))
        if target is None or target.project_id != sprint.project_id:
            raise ApiError('That sprint does not exist.', 404)
        target_id = target.id

    carried = 0
    for issue in list(sprint.issues):
        if issue.state and issue.state.category == 'done':
            continue
        issue.sprint_id = target_id
        carried += 1

    sprint.state = 'completed'
    sprint.completed_at = datetime.now(timezone.utc)
    if sprint.end_date is None:
        sprint.end_date = today_utc()

    record('sprint.completed', project_id=sprint.project_id, actor=current_user(),
           after=sprint.name, subject=f'{sprint.name} ({carried} carried over)')
    db.session.commit()
    broadcast('sprint:changed', {'projectId': sprint.project_id}, sprint.project_id)
    return jsonify(sprint=sprint.to_dict(), carriedOver=carried)


@bp.delete('/sprints/<int:sprint_id>')
@token_required
def delete_sprint(sprint_id: int):
    sprint = _load_sprint(sprint_id, minimum='manager')
    if sprint.state == 'active':
        raise ApiError('Complete the sprint before deleting it.')

    project_id = sprint.project_id
    for issue in list(sprint.issues):
        issue.sprint_id = None

    db.session.delete(sprint)
    db.session.commit()
    broadcast('sprint:changed', {'projectId': project_id}, project_id)
    return '', 204


@bp.post('/sprints/<int:sprint_id>/issues')
@token_required
def move_issues_into_sprint(sprint_id: int):
    """Bulk move from the backlog into a sprint (and back out with null)."""
    sprint = _load_sprint(sprint_id)
    ids = (request.get_json(silent=True) or {}).get('issueIds') or []

    moved = 0
    for issue_id in ids:
        issue = db.session.get(Issue, int(issue_id))
        if issue is None or issue.project_id != sprint.project_id:
            continue
        issue.sprint_id = sprint.id
        moved += 1

    db.session.commit()
    broadcast('sprint:changed', {'projectId': sprint.project_id}, sprint.project_id)
    return jsonify(moved=moved)
