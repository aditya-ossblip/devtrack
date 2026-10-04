import re

from flask import Blueprint, jsonify, request

from ..auth import current_user, project_role, require_project, token_required
from ..errors import ApiError
from ..events import broadcast, notify
from ..extensions import db
from ..history import paginate, record
from ..models import (
    ROLES,
    STATE_CATEGORIES,
    Activity,
    Notification,
    Project,
    ProjectMember,
    Sprint,
    User,
    WorkflowState,
    WorkflowTransition,
    build_board,
)

bp = Blueprint('projects', __name__, url_prefix='/api/projects')

KEY_PATTERN = re.compile(r'^[A-Z][A-Z0-9]{1,9}$')


def _suggest_key(name: str) -> str:
    """"Payments Revamp" -> "PR"; "DevTrack" -> "DEV"."""
    words = [w for w in re.split(r'[^A-Za-z0-9]+', name) if w]
    if len(words) >= 2:
        candidate = ''.join(word[0] for word in words)[:10]
    else:
        candidate = (words[0][:3] if words else 'PRJ')
    return candidate.upper() or 'PRJ'


def _unique_key(base: str) -> str:
    key = base
    suffix = 1
    while db.session.scalar(db.select(Project).filter_by(key=key)) is not None:
        suffix += 1
        key = f'{base[:8]}{suffix}'
    return key


@bp.get('')
@token_required
def list_projects():
    user = current_user()
    # Projects you lead, plus projects you were added to. Nothing else, for
    # anybody — there is no account on this server that sees every project.
    query = (
        db.select(Project)
        .filter(
            db.or_(
                Project.lead_id == user.id,
                Project.id.in_(
                    db.select(ProjectMember.project_id).filter(ProjectMember.user_id == user.id)
                ),
            )
        )
        .order_by(Project.created_at.desc())
    )

    projects = db.session.scalars(query).all()
    return jsonify(projects=[project.to_dict() for project in projects])


@bp.post('')
@token_required
def create_project():
    """Create a project and everything it needs to be usable immediately.

    One request sets up the project, its default workflow, its lead's
    membership and any invited members — so a new user goes from signing up to
    a working board without a setup checklist.
    """
    user = current_user()
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    if not name:
        raise ApiError('Give the project a name.')

    key = (data.get('key') or '').strip().upper() or _suggest_key(name)
    if not KEY_PATTERN.match(key):
        raise ApiError('A project key is 2–10 characters, letters and digits, starting with a letter.')
    if db.session.scalar(db.select(Project).filter_by(key=key)) is not None:
        if data.get('key'):
            raise ApiError(f'The key {key} is already taken.', 409)
        key = _unique_key(key)

    project = Project(
        key=key,
        name=name,
        description=(data.get('description') or '').strip(),
        lead_id=user.id,
    )
    db.session.add(project)
    db.session.flush()

    project.install_default_workflow()
    db.session.add(ProjectMember(project_id=project.id, user_id=user.id, role='admin'))

    invited = []
    for member_id in data.get('memberIds') or []:
        if int(member_id) == user.id:
            continue
        member = db.session.get(User, int(member_id))
        if member is None:
            continue
        db.session.add(
            ProjectMember(project_id=project.id, user_id=member.id, role='developer')
        )
        invited.append(member)

    for member in invited:
        db.session.add(
            Notification(
                user_id=member.id,
                project_id=project.id,
                type='member',
                text=f'{user.name} added you to {project.name}',
            )
        )
        record('member.added', project_id=project.id, actor=user,
               after=member.name, subject=member.name)

    db.session.commit()

    for member in invited:
        notify('notification:new', {'projectId': project.id}, member.id)

    return jsonify(project=project.to_dict()), 201


@bp.get('/<int:project_id>')
@token_required
def get_project(project_id: int):
    project = require_project(project_id)
    return jsonify(
        project=project.to_dict(),
        states=[state.to_dict() for state in project.states],
        role=project_role(current_user(), project),
    )


@bp.patch('/<int:project_id>')
@token_required
def update_project(project_id: int):
    project = require_project(project_id, minimum='manager')
    data = request.get_json(silent=True) or {}

    if 'name' in data:
        name = (data['name'] or '').strip()
        if not name:
            raise ApiError('A project cannot have an empty name.')
        project.name = name
    if 'description' in data:
        project.description = (data['description'] or '').strip()

    db.session.commit()
    return jsonify(project=project.to_dict())


@bp.delete('/<int:project_id>')
@token_required
def delete_project(project_id: int):
    project = require_project(project_id, minimum='admin')
    db.session.delete(project)
    db.session.commit()
    return '', 204


# --------------------------------------------------------------------------
# Members
# --------------------------------------------------------------------------

@bp.get('/<int:project_id>/members')
@token_required
def list_members(project_id: int):
    project = require_project(project_id)
    members = sorted(project.memberships, key=lambda m: m.user.name)
    return jsonify(members=[membership.to_dict() for membership in members])


@bp.post('/<int:project_id>/members')
@token_required
def add_member(project_id: int):
    """Add someone by id, or by email if they are not registered yet."""
    project = require_project(project_id, minimum='manager')
    actor = current_user()
    data = request.get_json(silent=True) or {}

    user = None
    if data.get('userId'):
        user = db.session.get(User, int(data['userId']))
    elif data.get('email'):
        email = data['email'].strip().lower()
        user = db.session.scalar(db.select(User).filter_by(email=email))
        if user is None:
            raise ApiError(f'Nobody is registered with {email}. Ask them to sign up first.', 404)

    if user is None:
        raise ApiError('Pick someone to add.')

    role = (data.get('role') or 'developer').lower()
    if role not in ROLES:
        raise ApiError('That is not a valid role.')

    existing = db.session.get(ProjectMember, (project.id, user.id))
    if existing is not None:
        existing.role = role
    else:
        db.session.add(ProjectMember(project_id=project.id, user_id=user.id, role=role))
        db.session.add(
            Notification(
                user_id=user.id,
                project_id=project.id,
                type='member',
                text=f'{actor.name} added you to {project.name}',
            )
        )

    record('member.added', project_id=project.id, actor=actor,
           after=user.name, subject=user.name)
    db.session.commit()
    broadcast('member:added', {'member': user.to_dict()}, project.id)
    return jsonify(member=db.session.get(ProjectMember, (project.id, user.id)).to_dict()), 201


@bp.patch('/<int:project_id>/members/<int:user_id>')
@token_required
def update_member(project_id: int, user_id: int):
    project = require_project(project_id, minimum='manager')
    membership = db.session.get(ProjectMember, (project.id, user_id))
    if membership is None:
        raise ApiError('That person is not on this project.', 404)

    role = (request.get_json(silent=True) or {}).get('role', '').lower()
    if role not in ROLES:
        raise ApiError('That is not a valid role.')
    if user_id == project.lead_id and role != 'admin':
        raise ApiError('The project lead has to stay an admin. Change the lead first.')

    before = membership.role
    membership.role = role
    record('member.role_changed', project_id=project.id, actor=current_user(),
           field='role', before=before, after=role, subject=membership.user.name)
    db.session.commit()
    return jsonify(member=membership.to_dict())


@bp.delete('/<int:project_id>/members/<int:user_id>')
@token_required
def remove_member(project_id: int, user_id: int):
    project = require_project(project_id, minimum='manager')
    if user_id == project.lead_id:
        raise ApiError('The project lead cannot be removed. Change the lead first.')

    membership = db.session.get(ProjectMember, (project.id, user_id))
    if membership is None:
        raise ApiError('That person is not on this project.', 404)

    record('member.removed', project_id=project.id, actor=current_user(),
           before=membership.user.name, subject=membership.user.name)
    db.session.delete(membership)
    db.session.commit()
    broadcast('member:removed', {'userId': user_id}, project.id)
    return '', 204


# --------------------------------------------------------------------------
# Board and workflow
# --------------------------------------------------------------------------

@bp.get('/<int:project_id>/board')
@token_required
def project_board(project_id: int):
    """The board: the project's workflow states, each carrying its issues."""
    project = require_project(project_id)

    sprint_id = request.args.get('sprintId')
    issues = project.issues
    if sprint_id == 'active':
        active = db.session.scalar(
            db.select(Sprint).filter_by(project_id=project.id, state='active')
        )
        issues = [i for i in issues if active and i.sprint_id == active.id]
    elif sprint_id and sprint_id.isdigit():
        issues = [i for i in issues if i.sprint_id == int(sprint_id)]

    return jsonify(columns=build_board(project, issues))


@bp.get('/<int:project_id>/activity')
@token_required
def project_activity(project_id: int):
    """Everything that has happened on this project, newest first.

    Filterable by `verb` and by `actorId`, so "what did Rohan change this
    week" and "every move" are both one request.
    """
    project = require_project(project_id)

    query = db.select(Activity).filter(Activity.project_id == project.id)
    if request.args.get('verb'):
        query = query.filter(Activity.verb == request.args['verb'])
    if request.args.get('actorId', '').isdigit():
        query = query.filter(Activity.actor_id == int(request.args['actorId']))
    if request.args.get('issueId', '').isdigit():
        query = query.filter(Activity.issue_id == int(request.args['issueId']))

    query = query.order_by(Activity.created_at.desc(), Activity.id.desc())
    entries, meta = paginate(query)
    return jsonify(activity=entries, meta=meta)


@bp.get('/<int:project_id>/workflow')
@token_required
def get_workflow(project_id: int):
    project = require_project(project_id)
    return jsonify(
        states=[state.to_dict() for state in project.states],
        transitions=[t.to_dict() for t in project.transitions],
    )


@bp.post('/<int:project_id>/states')
@token_required
def add_state(project_id: int):
    project = require_project(project_id, minimum='manager')
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    if not name:
        raise ApiError('Give the column a name.')

    category = (data.get('category') or 'todo').lower()
    if category not in STATE_CATEGORIES:
        raise ApiError(f"Category must be one of: {', '.join(STATE_CATEGORIES)}.")

    state = WorkflowState(
        project_id=project.id,
        name=name,
        category=category,
        position=len(project.states),
        wip_limit=data.get('wipLimit'),
    )
    db.session.add(state)
    db.session.commit()

    broadcast('workflow:changed', {'projectId': project.id}, project.id)
    return jsonify(state=state.to_dict()), 201


@bp.patch('/<int:project_id>/states/<int:state_id>')
@token_required
def update_state(project_id: int, state_id: int):
    project = require_project(project_id, minimum='manager')
    state = db.session.get(WorkflowState, state_id)
    if state is None or state.project_id != project.id:
        raise ApiError('That column does not exist.', 404)

    data = request.get_json(silent=True) or {}
    if 'name' in data:
        name = (data['name'] or '').strip()
        if not name:
            raise ApiError('A column cannot have an empty name.')
        state.name = name
    if 'category' in data:
        if data['category'] not in STATE_CATEGORIES:
            raise ApiError(f"Category must be one of: {', '.join(STATE_CATEGORIES)}.")
        state.category = data['category']
    if 'wipLimit' in data:
        state.wip_limit = data['wipLimit'] or None
    if 'position' in data:
        state.position = int(data['position'])

    db.session.commit()
    broadcast('workflow:changed', {'projectId': project.id}, project.id)
    return jsonify(state=state.to_dict())


@bp.delete('/<int:project_id>/states/<int:state_id>')
@token_required
def delete_state(project_id: int, state_id: int):
    project = require_project(project_id, minimum='manager')
    state = db.session.get(WorkflowState, state_id)
    if state is None or state.project_id != project.id:
        raise ApiError('That column does not exist.', 404)
    if len(project.states) <= 1:
        raise ApiError('A board needs at least one column.')
    if state.issues:
        raise ApiError(
            f'{state.name} still has {len(state.issues)} issue(s). Move them first.'
        )

    db.session.delete(state)
    db.session.commit()
    broadcast('workflow:changed', {'projectId': project.id}, project.id)
    return '', 204


@bp.put('/<int:project_id>/transitions')
@token_required
def set_transitions(project_id: int):
    """Replace the whole rule set. An empty list means "allow every move"."""
    project = require_project(project_id, minimum='manager')
    data = request.get_json(silent=True) or {}
    pairs = data.get('transitions') or []

    valid_ids = {state.id for state in project.states}
    for transition in project.transitions:
        db.session.delete(transition)

    for pair in pairs:
        from_id, to_id = int(pair.get('fromStateId', 0)), int(pair.get('toStateId', 0))
        if from_id not in valid_ids or to_id not in valid_ids:
            raise ApiError('A transition refers to a column that is not on this board.')
        db.session.add(
            WorkflowTransition(project_id=project.id, from_state_id=from_id, to_state_id=to_id)
        )

    db.session.commit()
    broadcast('workflow:changed', {'projectId': project.id}, project.id)
    return jsonify(transitions=[t.to_dict() for t in project.transitions])
