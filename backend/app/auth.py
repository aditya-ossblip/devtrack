from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from .errors import ApiError
from .extensions import db
from .models import Project, ProjectMember, User


def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(user.id),  # PyJWT requires `sub` to be a string
        'role': user.role,
        'iat': now,
        'exp': now + timedelta(seconds=current_app.config['JWT_EXPIRES_SECONDS']),
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm=current_app.config['JWT_ALGORITHM'])


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=[current_app.config['JWT_ALGORITHM']],
        )
    except jwt.ExpiredSignatureError:
        raise ApiError('Your session has expired. Please sign in again.', 401)
    except jwt.InvalidTokenError:
        raise ApiError('Invalid session. Please sign in again.', 401)


def _user_from_request() -> User:
    header = request.headers.get('Authorization', '')
    scheme, _, token = header.partition(' ')
    if scheme.lower() != 'bearer' or not token:
        raise ApiError('Sign in to continue.', 401)

    payload = decode_token(token)
    user = db.session.get(User, int(payload['sub']))
    if user is None:
        raise ApiError('That account no longer exists.', 401)
    return user


def token_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        g.current_user = _user_from_request()
        return view(*args, **kwargs)

    return wrapper


def current_user() -> User:
    user = getattr(g, 'current_user', None)
    if user is None:
        raise ApiError('Sign in to continue.', 401)
    return user


# --------------------------------------------------------------------------
# Project-scoped permissions
#
# Site role (admin/manager/developer) decides what you may do generally;
# project role decides what you may do inside one project. The effective role
# is whichever is stronger, so a site admin is never locked out of a project
# they own.
# --------------------------------------------------------------------------

RANK = {'developer': 0, 'manager': 1, 'admin': 2}


def project_role(user: User, project: Project) -> str:
    """Which role this user holds *on this project*, or 'none'.

    The only source of project access, deliberately. There is no site-wide
    override and no global role that reaches in here: DevTrack is used by
    unrelated people whose projects share one database, so "runs the server"
    must not mean "admin of your project". Whoever deployed this is not a
    member of your team unless you added them.

    `User.role` is display only. It used to grant access everywhere, which was
    fine when the only users were one team of four and is a privacy hole the
    moment strangers can sign up.
    """
    if project.lead_id == user.id:
        return 'admin'
    membership = db.session.get(ProjectMember, (project.id, user.id))
    if membership is None:
        return 'none'
    return membership.role if membership.role in RANK else 'developer'


def require_project(project_id, minimum: str = 'developer') -> Project:
    """Load a project the current user may act on, or raise.

    Non-membership raises 404 rather than 403: whether a project exists is
    itself information, and a 403 would confirm it.
    """
    user = current_user()
    project = db.session.get(Project, int(project_id)) if project_id else None
    if project is None:
        raise ApiError('That project does not exist.', 404)

    role = project_role(user, project)
    if role == 'none':
        raise ApiError('That project does not exist.', 404)
    if RANK[role] < RANK[minimum]:
        raise ApiError('You do not have permission to do that.', 403)
    return project


def require_project_by_key(key: str, minimum: str = 'developer') -> Project:
    project = db.session.scalar(db.select(Project).filter_by(key=(key or '').upper()))
    if project is None:
        raise ApiError('That project does not exist.', 404)
    return require_project(project.id, minimum)


def can_manage(user: User, project: Project) -> bool:
    return RANK.get(project_role(user, project), -1) >= RANK['manager']


def can_edit_issue(user: User, issue) -> bool:
    """Managers and leads edit anything; developers only their own issues."""
    if can_manage(user, issue.project):
        return True
    return issue.assignee_id == user.id or issue.reporter_id == user.id


def requires_role(*roles: str):
    """Site-role guard, for routes with no project in scope."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if current_user().role not in roles:
                raise ApiError('You do not have permission to do that.', 403)
            return view(*args, **kwargs)

        return wrapper

    return decorator
