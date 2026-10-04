"""Recording what happened, and paging what is returned.

Both of these are small enough to inline at each call site, and both are the
kind of thing that drifts if you do. One writer and one pager means the log
reads consistently and every list endpoint answers the same shape.
"""

from flask import request

from .extensions import db
from .models import ACTIVITY_VERBS, Activity

MAX_PER_PAGE = 100
DEFAULT_PER_PAGE = 50


def record(verb, *, project_id, actor=None, issue=None, field=None,
           before=None, after=None, before_ref=None, after_ref=None,
           subject=None, commit=False):
    """Append one row to the activity log.

    Deliberately forgiving about its arguments and strict about its verb: an
    unknown verb is a programming mistake and should surface in tests, but a
    missing issue or actor just means less detail in one row.

    `before_ref` / `after_ref` carry ids beside the human-readable names, for
    the callers whose values are rows that can later be renamed.
    """
    if verb not in ACTIVITY_VERBS:
        raise ValueError(f'Unknown activity verb: {verb}')

    def trim(value):
        if value is None:
            return None
        text = str(value)
        return text if len(text) <= 200 else text[:197] + '...'

    entry = Activity(
        project_id=project_id,
        issue_id=issue.id if issue is not None else None,
        actor_id=actor.id if actor is not None else None,
        verb=verb,
        field=field,
        from_value=trim(before),
        to_value=trim(after),
        from_ref=before_ref,
        to_ref=after_ref,
        subject=trim(subject if subject is not None else (
            f'{issue.key} {issue.title}' if issue is not None else ''
        )) or '',
    )
    db.session.add(entry)
    if commit:
        db.session.commit()
    return entry


def page_args():
    """Read ?page= and ?perPage= from the query string, clamped."""
    try:
        page = max(int(request.args.get('page', 1)), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get('perPage', DEFAULT_PER_PAGE))
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE
    return page, max(1, min(per_page, MAX_PER_PAGE))


def paginate(query, serialise=lambda row: row.to_dict()):
    """Run a query for one page and describe where that page sits.

    Returns (items, meta). `meta` carries total and hasMore so a caller can
    render "showing 50 of 214" without a second request - the thing that makes
    people give up on pagination and fetch everything.
    """
    page, per_page = page_args()
    total = db.session.scalar(
        db.select(db.func.count()).select_from(query.subquery())
    ) or 0

    rows = db.session.scalars(query.limit(per_page).offset((page - 1) * per_page)).all()

    return [serialise(row) for row in rows], {
        'page': page,
        'perPage': per_page,
        'total': total,
        'pages': max(1, (total + per_page - 1) // per_page),
        'hasMore': page * per_page < total,
    }


def paginate_list(items, serialise=lambda row: row.to_dict()):
    """The same contract for an already-materialised list."""
    page, per_page = page_args()
    total = len(items)
    start = (page - 1) * per_page
    window = items[start:start + per_page]

    return [serialise(row) for row in window], {
        'page': page,
        'perPage': per_page,
        'total': total,
        'pages': max(1, (total + per_page - 1) // per_page),
        'hasMore': start + per_page < total,
    }
