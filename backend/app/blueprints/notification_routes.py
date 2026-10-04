from flask import Blueprint, jsonify

from ..auth import current_user, token_required
from ..errors import ApiError
from ..extensions import db
from ..history import paginate
from ..models import Notification, utcnow

bp = Blueprint('notifications', __name__, url_prefix='/api/notifications')


@bp.get('')
@token_required
def list_notifications():
    user = current_user()
    rows, meta = paginate(
        db.select(Notification)
        .filter_by(user_id=user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
    )

    unread = db.session.scalar(
        db.select(db.func.count(Notification.id)).filter(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
    )
    return jsonify(notifications=rows, unread=unread or 0, meta=meta)


@bp.patch('/<int:notification_id>/read')
@token_required
def mark_read(notification_id: int):
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user().id:
        raise ApiError('That notification does not exist.', 404)

    if notification.read_at is None:
        notification.read_at = utcnow()
        db.session.commit()
    return '', 204


@bp.post('/read-all')
@token_required
def mark_all_read():
    user = current_user()
    unread = db.session.scalars(
        db.select(Notification).filter(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
    ).all()

    for notification in unread:
        notification.read_at = utcnow()
    db.session.commit()
    return jsonify(marked=len(unread))
