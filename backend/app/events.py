"""Socket.IO layer.

Live updates are an enhancement on a working REST API: every change is written
and broadcast by the HTTP route, and the socket only carries the news. If the
socket is down the app still works, it just stops updating other people's
screens by itself.
"""

import logging

from flask import request
from flask_socketio import emit, join_room, leave_room
from sqlalchemy import event
from sqlalchemy.orm import Session

from .auth import decode_token, project_role
from .extensions import db, socketio
from .models import Activity, User

# Which user each live connection belongs to, keyed by Socket.IO's session id.
# This cannot live on flask.g: Flask-SocketIO gives every event its own app
# context, so anything put on g in `connect` is gone by the time `join_project`
# runs. Kept in memory on purpose - a connection only exists while the server
# is up, and every client reconnects (and re-authenticates) after a restart.
_socket_users: dict[str, int] = {}


def project_room(project_id) -> str:
    return f'project:{project_id}'


def _origin_sid():
    """The socket that caused this change, read from the X-Socket-Id header.

    The frontend sends its socket id on every request once connected. Skipping
    it on the broadcast stops the mover's own card from jumping: they already
    applied the change optimistically.
    """
    return request.headers.get('X-Socket-Id') or None


def broadcast(event: str, payload: dict, project_id) -> None:
    socketio.emit(event, payload, to=project_room(project_id), skip_sid=_origin_sid())


def notify(event: str, payload: dict, user_id) -> None:
    socketio.emit(event, payload, to=f'user:{user_id}')


def handle_connect(auth=None):
    """Authenticate the socket itself — a room join must not be open to anyone.

    The client passes its JWT in the connect payload:
        io('/', { auth: { token } })
    """
    token = (auth or {}).get('token') if isinstance(auth, dict) else None
    if not token:
        return False  # refuse the connection

    try:
        payload = decode_token(token)
        user = db.session.get(User, int(payload['sub']))
    except Exception:
        return False

    if user is None:
        return False

    _socket_users[request.sid] = user.id
    join_room(f'user:{user.id}')
    emit('connected', {'userId': user.id})
    return True


def handle_join_project(data):
    project_id = (data or {}).get('projectId')
    user_id = _socket_users.get(request.sid)
    if project_id is None or user_id is None:
        return

    user = db.session.get(User, user_id)
    if user is None:
        return

    from .models import Project

    project = db.session.get(Project, int(project_id))
    if project is None or project_role(user, project) == 'none':
        emit('error', {'error': 'You do not have access to that project.'})
        return

    join_room(project_room(project_id))
    emit('joined_project', {'projectId': int(project_id)})


def handle_leave_project(data):
    project_id = (data or {}).get('projectId')
    if project_id is not None:
        leave_room(project_room(project_id))


def handle_disconnect(*_reason):
    _socket_users.pop(request.sid, None)


def init_socket_handlers(sio):
    """Attach the handlers to the server `sio` currently has.

    Called from create_app after socketio.init_app. Decorating the functions
    with @socketio.on instead would bind them to whichever server existed when
    this module was first imported - fine for one running app, but every later
    create_app (each test builds a fresh one) got a server with no handlers at
    all, which accepted any connection, token or not, and ignored join_project.
    """
    sio.on_event('connect', handle_connect)
    sio.on_event('join_project', handle_join_project)
    sio.on_event('leave_project', handle_leave_project)
    sio.on_event('disconnect', handle_disconnect)


# --------------------------------------------------------------------------
# Live activity feed
#
# Every change is already written to the `activities` table by the route that
# makes it (see history.record). These three hooks send each new row to the
# project's room once its transaction has actually committed, so the feed can
# never show something that was rolled back - and because the row is in the
# database first, a client that was offline (or a server that restarted) loses
# nothing: the panel reloads the stored history and then follows along live.
# --------------------------------------------------------------------------

_PENDING = 'devtrack.activity_out'
_log = logging.getLogger(__name__)


@event.listens_for(Session, 'after_flush')
def _collect_activity(session, _flush_context):
    # After the INSERT, so the row has its id and timestamp. no_autoflush stops
    # loading the actor's name from trying to start a second flush mid-flush.
    with session.no_autoflush:
        for obj in session.new:
            if not isinstance(obj, Activity):
                continue
            try:
                payload = obj.to_dict()
                # The row was built with actor_id, not the relationship, so
                # `actor` is not loaded yet at this point. The user is already
                # in the session (they are the one making the change), so this
                # is a lookup in memory, not a query.
                if obj.actor_id and payload.get('actorName') == 'Someone':
                    actor = session.get(User, obj.actor_id)
                    if actor is not None:
                        payload['actorName'] = actor.name
                        payload['actorInitials'] = actor.initials
                session.info.setdefault(_PENDING, []).append(payload)
            except Exception:  # a missed broadcast must never break a save
                _log.exception('Could not prepare a live activity update')


@event.listens_for(Session, 'after_commit')
def _send_activity(session):
    for payload in session.info.pop(_PENDING, []):
        try:
            socketio.emit('activity:new', {'activity': payload},
                          to=project_room(payload['projectId']))
        except Exception:
            _log.exception('Could not send a live activity update')


@event.listens_for(Session, 'after_rollback')
def _drop_activity(session):
    session.info.pop(_PENDING, None)
