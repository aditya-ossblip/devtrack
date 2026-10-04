from flask import Blueprint, jsonify, request

from ..auth import token_required
from ..extensions import db
from ..models import User

bp = Blueprint('users', __name__, url_prefix='/api/users')


@bp.get('')
@token_required
def find_user():
    """Find one person by their full email address, to add them to a project.

    An exact match, never a listing. A substring search across every account
    lets anyone signed in page through the whole user directory, or check
    whether a particular address has an account here — which is nobody's
    business but its owner's. You can add someone whose address you already
    know; you cannot go fishing for one.

    The empty result is the same whether the address is unknown or simply
    mistyped, so this cannot be used to confirm who is registered.
    """
    term = (request.args.get('q') or '').strip().lower()

    # Nothing that is not a whole address gets a query at all.
    whole_address = '@' in term and not term.startswith('@') and not term.endswith('@')
    person = (
        db.session.scalar(db.select(User).filter(db.func.lower(User.email) == term))
        if whole_address else None
    )

    # The same `meta` envelope every other list endpoint returns, so a caller
    # never has to special-case this one. There is only ever a single page;
    # `exact` says so, for anything that cares to look.
    found = 1 if person is not None else 0
    return jsonify(
        users=[person.to_dict()] if person is not None else [],
        meta={'page': 1, 'perPage': 1, 'total': found, 'pages': 1,
              'hasMore': False, 'exact': True},
    )
