"""Reporting. Every number here is computed from issues at request time —
nothing is cached or denormalised, so a report can never disagree with a board.
"""

from collections import defaultdict
from datetime import datetime, time, timedelta

from flask import Blueprint, jsonify, request

from ..auth import require_project, token_required
from ..extensions import db
from ..models import PRIORITIES, Activity, Issue, Sprint, today_utc

bp = Blueprint('analytics', __name__, url_prefix='/api/projects')


@bp.get('/<int:project_id>/analytics')
@token_required
def project_analytics(project_id: int):
    project = require_project(project_id)
    issues = project.issues
    # UTC, to match how every Activity row is stamped. See models.today_utc.
    today = today_utc()

    by_state = defaultdict(int)
    by_type = defaultdict(int)
    by_priority = defaultdict(int)
    by_assignee = defaultdict(lambda: {'total': 0, 'done': 0, 'overdue': 0})

    done_total = 0
    overdue_total = 0
    points_total = 0
    points_done = 0

    for issue in issues:
        category = issue.state.category if issue.state else 'todo'
        by_state[issue.state.name if issue.state else 'Unknown'] += 1
        by_type[issue.type] += 1
        by_priority[issue.priority] += 1

        name = issue.assignee.name if issue.assignee else 'Unassigned'
        bucket = by_assignee[name]
        bucket['total'] += 1

        points_total += issue.story_points or 0
        if category == 'done':
            done_total += 1
            bucket['done'] += 1
            points_done += issue.story_points or 0
        if issue.is_overdue:
            overdue_total += 1
            bucket['overdue'] += 1

    # Completion over the last 14 days, read from the activity log.
    #
    # This used to approximate from Issue.updated_at, which moves for any edit
    # at all - so renaming a finished issue counted as finishing it again, and
    # an issue finished twice (moved back, then forward) counted once. The log
    # records the actual transitions, so this is now exact.
    window_start = today - timedelta(days=13)
    completed_by_day = {(window_start + timedelta(days=n)).isoformat(): 0 for n in range(14)}

    # Matched by id, not by name. A column renamed after the fact would
    # otherwise erase every completion recorded under its old name.
    done_ids = {state.id for state in project.states if state.category == 'done'}
    done_names = {state.name for state in project.states if state.category == 'done'}
    moves = db.session.scalars(
        db.select(Activity).filter(
            Activity.project_id == project.id,
            Activity.verb == 'issue.moved',
            Activity.created_at >= datetime.combine(window_start, time.min),
        )
    ).all()

    for move in moves:
        # Rows written before ids were logged only have the name to go on.
        landed_in_done = (
            move.to_ref in done_ids if move.to_ref is not None
            else move.to_value in done_names
        )
        if not landed_in_done:
            continue
        key = move.created_at.date().isoformat()
        if key in completed_by_day:
            completed_by_day[key] += 1

    return jsonify(
        totals={
            'issues': len(issues),
            'done': done_total,
            'overdue': overdue_total,
            'completionPct': round(done_total / len(issues) * 100) if issues else 0,
            'storyPoints': points_total,
            'storyPointsDone': points_done,
            'members': len(project.memberships),
        },
        byState=[
            {'name': state.name, 'category': state.category, 'count': by_state.get(state.name, 0)}
            for state in project.states
        ],
        byType=[{'name': key, 'count': value} for key, value in sorted(by_type.items())],
        byPriority=[
            {'name': name, 'count': by_priority.get(name, 0)} for name in PRIORITIES
        ],
        byAssignee=sorted(
            [{'name': name, **data} for name, data in by_assignee.items()],
            key=lambda row: -row['total'],
        ),
        completedByDay=[
            {'date': day, 'count': count} for day, count in sorted(completed_by_day.items())
        ],
    )


@bp.get('/<int:project_id>/burndown')
@token_required
def sprint_burndown(project_id: int):
    """Points remaining per day across the active (or requested) sprint."""
    project = require_project(project_id)

    sprint_id = request.args.get('sprintId')
    if sprint_id and sprint_id.isdigit():
        sprint = db.session.get(Sprint, int(sprint_id))
        if sprint is None or sprint.project_id != project.id:
            sprint = None
    else:
        sprint = db.session.scalar(
            db.select(Sprint).filter_by(project_id=project.id, state='active')
        )

    if sprint is None or not sprint.start_date or not sprint.end_date:
        return jsonify(sprint=None, points=[])

    total = sum(issue.story_points or 0 for issue in sprint.issues)
    span = max((sprint.end_date - sprint.start_date).days, 1)

    rows = []
    for offset in range(span + 1):
        day = sprint.start_date + timedelta(days=offset)
        remaining = total
        for issue in sprint.issues:
            finished = (
                issue.state
                and issue.state.category == 'done'
                and issue.updated_at
                and issue.updated_at.date() <= day
            )
            if finished:
                remaining -= issue.story_points or 0
        rows.append(
            {
                'date': day.isoformat(),
                'ideal': round(total - (total / span) * offset, 1),
                'remaining': remaining if day <= today_utc() else None,
            }
        )

    return jsonify(sprint=sprint.to_dict(), points=rows)


@bp.get('/<int:project_id>/velocity')
@token_required
def velocity(project_id: int):
    """Points completed per finished sprint — the last eight."""
    project = require_project(project_id)
    completed = [s for s in project.sprints if s.state == 'completed']
    completed.sort(key=lambda s: s.completed_at or s.created_at)

    return jsonify(
        sprints=[
            {
                'name': sprint.name,
                'committed': sum(i.story_points or 0 for i in sprint.issues),
                'completed': sum(
                    i.story_points or 0
                    for i in sprint.issues
                    if i.state and i.state.category == 'done'
                ),
            }
            for sprint in completed[-8:]
        ]
    )
