from datetime import date

from flask import Blueprint, jsonify, request

from ..auth import can_edit_issue, can_manage, current_user, require_project, token_required
from ..errors import ApiError
from ..events import broadcast, notify
from ..extensions import db
from ..history import paginate, record
from ..models import (
    ISSUE_TYPES,
    PRIORITIES,
    Activity,
    Comment,
    Issue,
    Notification,
    Sprint,
    User,
    WorkflowState,
    allowed_transitions,
)

bp = Blueprint('issues', __name__, url_prefix='/api/issues')


def _parse_due_date(value):
    if value in (None, ''):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ApiError('Due date must look like 2026-09-20.')


def _next_position(project_id: int, state_id: int) -> int:
    highest = db.session.scalar(
        db.select(db.func.max(Issue.position)).filter_by(project_id=project_id, state_id=state_id)
    )
    return (highest or 0) + 1


def _load_issue(issue_id: int) -> Issue:
    issue = db.session.get(Issue, issue_id)
    if issue is None:
        raise ApiError('That issue does not exist.', 404)
    require_project(issue.project_id)
    return issue


def _notify_assignment(issue: Issue, actor: User) -> None:
    if not issue.assignee_id or issue.assignee_id == actor.id:
        return
    notification = Notification(
        user_id=issue.assignee_id,
        project_id=issue.project_id,
        issue_id=issue.id,
        type='assigned',
        text=f'{actor.name} assigned {issue.key} to you: {issue.title}',
    )
    db.session.add(notification)
    db.session.commit()
    notify('notification:new', {'notification': notification.to_dict()}, issue.assignee_id)


@bp.get('')
@token_required
def list_issues():
    """Cross-project issue search — what My tasks and the backlog both use.

    Filters: projectId, assigneeId ("me" allowed), type, priority, sprintId
    ("backlog" for unassigned), category, epicId, q.
    """
    user = current_user()
    args = request.args

    query = db.select(Issue).join(WorkflowState, Issue.state_id == WorkflowState.id)

    if args.get('projectId'):
        project = require_project(args['projectId'])
        query = query.filter(Issue.project_id == project.id)
    else:
        # Without a project filter, only show issues from projects they're on.
        from ..models import Project, ProjectMember

        if user.role != 'admin':
            query = query.filter(
                Issue.project_id.in_(
                    db.select(ProjectMember.project_id).filter(ProjectMember.user_id == user.id)
                )
            )

    assignee = args.get('assigneeId')
    if assignee == 'me':
        query = query.filter(Issue.assignee_id == user.id)
    elif assignee == 'none':
        query = query.filter(Issue.assignee_id.is_(None))
    elif assignee and assignee.isdigit():
        query = query.filter(Issue.assignee_id == int(assignee))

    if args.get('type'):
        query = query.filter(Issue.type == args['type'])
    if args.get('priority'):
        query = query.filter(Issue.priority == args['priority'])
    if args.get('category'):
        query = query.filter(WorkflowState.category == args['category'])
    if args.get('epicId'):
        query = query.filter(Issue.epic_id == int(args['epicId']))

    sprint = args.get('sprintId')
    if sprint == 'backlog':
        query = query.filter(Issue.sprint_id.is_(None))
    elif sprint and sprint.isdigit():
        query = query.filter(Issue.sprint_id == int(sprint))

    term = (args.get('q') or '').strip()
    if term:
        like = f'%{term}%'
        query = query.filter(db.or_(Issue.title.ilike(like), Issue.key.ilike(like)))

    query = query.order_by(WorkflowState.position, Issue.position, Issue.id)
    issues, meta = paginate(query)
    return jsonify(issues=issues, meta=meta)


@bp.post('')
@token_required
def create_issue():
    user = current_user()
    data = request.get_json(silent=True) or {}

    project = require_project(data.get('projectId'))

    title = (data.get('title') or '').strip()
    if not title:
        raise ApiError('Give the issue a title.')

    issue_type = (data.get('type') or 'task').lower()
    if issue_type not in ISSUE_TYPES:
        raise ApiError(f"Type must be one of: {', '.join(ISSUE_TYPES)}.")

    priority = (data.get('priority') or 'medium').lower()
    if priority not in PRIORITIES:
        raise ApiError(f"Priority must be one of: {', '.join(PRIORITIES)}.")

    if data.get('stateId'):
        state = db.session.get(WorkflowState, int(data['stateId']))
        if state is None or state.project_id != project.id:
            raise ApiError('That column is not on this board.', 404)
    else:
        state = project.states[0]

    assignee_id = data.get('assigneeId')
    if assignee_id is not None and db.session.get(User, assignee_id) is None:
        raise ApiError('That assignee does not exist.', 404)

    issue = Issue(
        key=project.next_issue_key(),
        project_id=project.id,
        title=title,
        description=(data.get('description') or '').strip(),
        type=issue_type,
        priority=priority,
        state_id=state.id,
        assignee_id=assignee_id,
        reporter_id=user.id,
        epic_id=data.get('epicId'),
        sprint_id=data.get('sprintId'),
        story_points=data.get('storyPoints'),
        due_date=_parse_due_date(data.get('dueDate')),
        position=_next_position(project.id, state.id),
    )
    issue.set_labels(data.get('labels'))

    db.session.add(issue)
    db.session.flush()
    record('issue.created', project_id=project.id, actor=user, issue=issue,
           after=state.name)
    db.session.commit()

    broadcast('issue:created', {'issue': issue.to_dict()}, project.id)
    _notify_assignment(issue, user)
    return jsonify(issue=issue.to_dict()), 201


@bp.get('/<int:issue_id>')
@token_required
def get_issue(issue_id: int):
    issue = _load_issue(issue_id)
    user = current_user()
    return jsonify(
        issue=issue.to_dict(with_comments=True),
        allowedStateIds=allowed_transitions(issue.project, issue.state_id),
        # So the panel can hide controls the server would refuse anyway. The
        # server still checks on every call - this only spares people a button
        # that answers 403.
        canManage=can_manage(user, issue.project),
        canEdit=can_edit_issue(user, issue),
    )


@bp.patch('/<int:issue_id>')
@token_required
def update_issue(issue_id: int):
    user = current_user()
    issue = _load_issue(issue_id)

    if not can_edit_issue(user, issue):
        raise ApiError('You can only change issues assigned to you.', 403)

    data = request.get_json(silent=True) or {}
    previous_state_id = issue.state_id
    previous_state_name = issue.state.name if issue.state else None
    new_state = None
    moved = False
    edits = []   # (field, before, after) for the log

    if 'stateId' in data:
        state = db.session.get(WorkflowState, int(data['stateId']))
        if state is None or state.project_id != issue.project_id:
            raise ApiError('That column is not on this board.', 404)
        if state.id != issue.state_id:
            if state.id not in allowed_transitions(issue.project, issue.state_id):
                raise ApiError(
                    f'This workflow does not allow moving from {issue.state.name} to {state.name}.',
                    422,
                )
            if state.wip_limit and len(state.issues) >= state.wip_limit:
                raise ApiError(
                    f'{state.name} is at its limit of {state.wip_limit}. Finish something first.',
                    422,
                )
            # Assigning through the relationship, not the raw id: setting
            # `state_id` alone leaves `issue.state` pointing at the old row
            # until the session flushes, and the log below reads that.
            issue.state = state
            issue.position = _next_position(issue.project_id, state.id)
            new_state = state
            moved = True

    if 'title' in data:
        title = (data['title'] or '').strip()
        if not title:
            raise ApiError('An issue cannot have an empty title.')
        if title != issue.title:
            edits.append(('title', issue.title, title))
        issue.title = title
    if 'description' in data:
        description = (data['description'] or '').strip()
        if description != issue.description:
            edits.append(('description', None, None))
        issue.description = description
    if 'type' in data:
        if data['type'] not in ISSUE_TYPES:
            raise ApiError(f"Type must be one of: {', '.join(ISSUE_TYPES)}.")
        if data['type'] != issue.type:
            edits.append(('type', issue.type, data['type']))
        issue.type = data['type']
    if 'priority' in data:
        if data['priority'] not in PRIORITIES:
            raise ApiError(f"Priority must be one of: {', '.join(PRIORITIES)}.")
        if data['priority'] != issue.priority:
            edits.append(('priority', issue.priority, data['priority']))
        issue.priority = data['priority']
    if 'storyPoints' in data:
        points = data['storyPoints'] or None
        if points != issue.story_points:
            edits.append(('storyPoints', issue.story_points, points))
        issue.story_points = points
    if 'labels' in data:
        issue.set_labels(data['labels'])
    if 'dueDate' in data:
        issue.due_date = _parse_due_date(data['dueDate'])
    if 'epicId' in data:
        issue.epic_id = data['epicId'] or None
    if 'sprintId' in data:
        issue.sprint_id = data['sprintId'] or None

    reassigned = False
    if 'assigneeId' in data:
        # Reassigning is a management action, including on an issue you are
        # already holding: handing work to someone else is a scheduling
        # decision, not an edit. See the permission table in README.md.
        if not can_manage(user, issue.project):
            raise ApiError('Only a manager or the project lead can reassign an issue.', 403)
        assignee_id = data['assigneeId']
        if assignee_id is not None and db.session.get(User, assignee_id) is None:
            raise ApiError('That assignee does not exist.', 404)
        reassigned = assignee_id != issue.assignee_id
        if reassigned:
            previous_assignee = issue.assignee.name if issue.assignee else 'Unassigned'
            new_assignee = db.session.get(User, assignee_id).name if assignee_id else 'Unassigned'
        issue.assignee_id = assignee_id

    # The log is written before the commit so a failed write takes the history
    # with it - a log that records changes that did not happen is worse than
    # no log.
    if moved:
        record('issue.moved', project_id=issue.project_id, actor=user, issue=issue,
               field='status', before=previous_state_name, after=new_state.name,
               before_ref=previous_state_id, after_ref=new_state.id)
    for field, before, after in edits:
        record('issue.updated', project_id=issue.project_id, actor=user, issue=issue,
               field=field, before=before, after=after)
    if reassigned:
        record('issue.assigned', project_id=issue.project_id, actor=user, issue=issue,
               field='assignee', before=previous_assignee, after=new_assignee)

    db.session.commit()
    payload = issue.to_dict()

    if moved:
        broadcast(
            'issue:moved',
            {
                'issueId': issue.id,
                'fromStateId': previous_state_id,
                'toStateId': issue.state_id,
                'issue': payload,
            },
            issue.project_id,
        )
        if issue.state and issue.state.category == 'done':
            _announce_completion(issue, user)
    else:
        broadcast('issue:updated', {'issue': payload}, issue.project_id)

    if reassigned:
        _notify_assignment(issue, user)

    return jsonify(issue=payload)


@bp.delete('/<int:issue_id>')
@token_required
def delete_issue(issue_id: int):
    issue = _load_issue(issue_id)
    if not can_manage(current_user(), issue.project):
        raise ApiError('Only a manager or the project lead can delete an issue.', 403)

    project_id = issue.project_id
    record('issue.deleted', project_id=project_id, actor=current_user(), issue=None,
           subject=f'{issue.key} {issue.title}')
    db.session.delete(issue)
    db.session.commit()

    broadcast('issue:deleted', {'issueId': issue_id}, project_id)
    return '', 204


def _announce_completion(issue: Issue, actor: User) -> None:
    text = f'{actor.name.split()[0]} completed {issue.key}: {issue.title}'
    recipients = [m.user for m in issue.project.memberships if m.user_id != actor.id]

    created = []
    for person in recipients:
        notification = Notification(
            user_id=person.id,
            project_id=issue.project_id,
            issue_id=issue.id,
            type='done',
            text=text,
        )
        db.session.add(notification)
        created.append((person.id, notification))

    db.session.commit()
    for user_id, notification in created:
        notify('notification:new', {'notification': notification.to_dict()}, user_id)


@bp.get('/<int:issue_id>/activity')
@token_required
def issue_activity(issue_id: int):
    """Everything that has happened to one issue, newest first."""
    issue = _load_issue(issue_id)
    query = (
        db.select(Activity)
        .filter(Activity.issue_id == issue.id)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
    )
    entries, meta = paginate(query)
    return jsonify(activity=entries, meta=meta)


# --------------------------------------------------------------------------
# Comments
# --------------------------------------------------------------------------

@bp.get('/<int:issue_id>/comments')
@token_required
def list_comments(issue_id: int):
    issue = _load_issue(issue_id)
    return jsonify(comments=[comment.to_dict() for comment in issue.comments])


@bp.post('/<int:issue_id>/comments')
@token_required
def add_comment(issue_id: int):
    user = current_user()
    issue = _load_issue(issue_id)

    body = ((request.get_json(silent=True) or {}).get('body') or '').strip()
    if not body:
        raise ApiError('Write something first.')

    comment = Comment(issue_id=issue.id, author_id=user.id, body=body)
    db.session.add(comment)
    record('comment.added', project_id=issue.project_id, actor=user, issue=issue)
    db.session.commit()

    broadcast(
        'comment:created',
        {'issueId': issue.id, 'comment': comment.to_dict()},
        issue.project_id,
    )

    # Tell the assignee somebody is talking about their issue.
    if issue.assignee_id and issue.assignee_id != user.id:
        notification = Notification(
            user_id=issue.assignee_id,
            project_id=issue.project_id,
            issue_id=issue.id,
            type='comment',
            text=f'{user.name} commented on {issue.key}',
        )
        db.session.add(notification)
        db.session.commit()
        notify('notification:new', {'notification': notification.to_dict()}, issue.assignee_id)

    return jsonify(comment=comment.to_dict()), 201


@bp.delete('/<int:issue_id>/comments/<int:comment_id>')
@token_required
def delete_comment(issue_id: int, comment_id: int):
    user = current_user()
    issue = _load_issue(issue_id)

    comment = db.session.get(Comment, comment_id)
    if comment is None or comment.issue_id != issue.id:
        raise ApiError('That comment does not exist.', 404)
    if comment.author_id != user.id and not can_manage(user, issue.project):
        raise ApiError('You can only delete your own comments.', 403)

    db.session.delete(comment)
    record('comment.deleted', project_id=issue.project_id, actor=user, issue=issue)
    db.session.commit()
    broadcast('comment:deleted', {'issueId': issue.id, 'commentId': comment_id}, issue.project_id)
    return '', 204
