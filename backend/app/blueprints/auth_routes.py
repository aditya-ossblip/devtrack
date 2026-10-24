import hashlib
import secrets
from datetime import timedelta
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from ..auth import create_token, current_user, token_required
from ..errors import ApiError
from ..extensions import db
from ..models import PasswordReset, User, utcnow

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

MIN_PASSWORD = 8


def _json() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError('Expected a JSON body.')
    return data


GOOGLE_ONLY = 'This site only signs people in with Google. Use the Google button.'


def password_sign_in(view):
    """Refuse the email-and-password routes when PASSWORD_SIGN_IN is off.

    Checked on the server, not just hidden in the page: a form that is merely
    not drawn can still be posted to by anyone with curl.
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_app.config.get('PASSWORD_SIGN_IN', False):
            raise ApiError(GOOGLE_ONLY, 403)
        return view(*args, **kwargs)

    return wrapper


@bp.post('/register')
@password_sign_in
def register():
    data = _json()
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    title = (data.get('title') or '').strip()

    if not name or not email or not password:
        raise ApiError('Name, email and password are all required.')
    if '@' not in email or '.' not in email.split('@')[-1]:
        raise ApiError('That does not look like an email address.')
    if len(password) < MIN_PASSWORD:
        raise ApiError(f'Use a password of at least {MIN_PASSWORD} characters.')

    # Everyone signs up the same. There used to be a first-user-is-admin rule
    # and a client-supplied `role`; both are gone. The first was meaningless
    # once a global role stopped granting project access, and the second let
    # anyone register themselves as an admin by adding a field to the request.
    role = 'developer'

    if db.session.scalar(db.select(User).filter_by(email=email)) is not None:
        raise ApiError('An account with that email already exists.', 409)

    user = User(name=name, email=email, role=role, title=title)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify(user=user.to_private_dict(), token=create_token(user)), 201


@bp.get('/config')
def public_config():
    """The handful of settings the sign-in page needs before anyone is signed in.

    Serving the Google client ID from here rather than baking it into the
    frontend build means there is one place to configure it — `backend/.env` —
    and a checkout with no Google setup simply renders no Google button.
    """
    return jsonify(
        googleClientId=current_app.config.get('GOOGLE_CLIENT_ID', ''),
        passwordSignIn=bool(current_app.config.get('PASSWORD_SIGN_IN', False)),
    )


@bp.post('/google')
def sign_in_with_google():
    """Trade a Google ID token for a DevTrack one.

    The token arrives from the browser, so nothing in it is trusted until
    Google's signature has been checked against their published keys. That
    check also covers the audience (this app's client ID) and the expiry, so a
    token minted for some other site cannot be replayed here.

    After that, the account is matched on Google's `sub` — a stable id that
    survives an address change — and only falls back to email for the first
    sign-in, which is safe because `email_verified` is required.
    """
    client_id = current_app.config.get('GOOGLE_CLIENT_ID', '')
    if not client_id:
        raise ApiError('Google sign-in is not configured on this server.', 501)

    credential = (_json().get('credential') or '').strip()
    if not credential:
        raise ApiError('No Google credential was sent.')

    # Imported here rather than at module scope: Google sign-in is optional,
    # and a missing package must not stop the whole app from starting.
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
    except ImportError:
        current_app.logger.error('GOOGLE_CLIENT_ID is set but google-auth is not installed.')
        raise ApiError('Google sign-in is not available on this server.', 501)

    try:
        claims = google_id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
            # Server clocks drift; ten seconds is enough to absorb it without
            # meaningfully widening the window a stolen token is usable in.
            clock_skew_in_seconds=10,
        )
    except ValueError as exc:
        # One message for a bad signature, the wrong audience, an expired
        # token and a malformed one alike. Which check failed is not something
        # the caller needs, and saying so helps only an attacker.
        current_app.logger.warning('Rejected a Google credential: %s', exc)
        raise ApiError('That Google sign-in could not be verified. Try again.', 401)

    if claims.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
        raise ApiError('That Google sign-in could not be verified. Try again.', 401)
    if not claims.get('email_verified'):
        raise ApiError('Verify your email address with Google before signing in.', 403)

    sub = (claims.get('sub') or '').strip()
    email = (claims.get('email') or '').strip().lower()
    name = (claims.get('name') or '').strip() or email.split('@')[0]
    if not sub or not email:
        raise ApiError('That Google sign-in could not be verified. Try again.', 401)

    user = db.session.scalar(db.select(User).filter_by(google_sub=sub))

    if user is None:
        user = db.session.scalar(db.select(User).filter_by(email=email))
        if user is not None:
            if user.google_sub and user.google_sub != sub:
                # Two Google accounts claiming one address. Refuse rather than
                # silently re-point the link.
                raise ApiError('That email is already linked to a different Google account.', 409)
            # First Google sign-in for an account that was created with a
            # password. Link them; the password keeps working.
            user.google_sub = sub
        else:
            user = User(
                name=name,
                email=email,
                role='developer',
                google_sub=sub,
            )
            # No password is set: this account signs in through Google until
            # its owner chooses one in Settings.
            db.session.add(user)

    db.session.commit()
    return jsonify(token=create_token(user), user=user.to_private_dict())


@bp.post('/login')
@password_sign_in
def login():
    data = _json()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    user = db.session.scalar(db.select(User).filter_by(email=email))
    # One message for both cases, so the response cannot be used to find out
    # which addresses have accounts.
    if user is None or not user.check_password(password):
        raise ApiError('Invalid email or password.', 401)

    return jsonify(token=create_token(user), user=user.to_private_dict())


@bp.get('/me')
@token_required
def me():
    return jsonify(user=current_user().to_private_dict())


@bp.patch('/me')
@token_required
def update_me():
    user = current_user()
    data = _json()

    if 'name' in data:
        name = (data['name'] or '').strip()
        if not name:
            raise ApiError('Your name cannot be empty.')
        user.name = name
    if 'title' in data:
        user.title = (data['title'] or '').strip()

    if 'password' in data:
        if not current_app.config.get('PASSWORD_SIGN_IN', False):
            raise ApiError(GOOGLE_ONLY, 403)
        # An account created through Google has no password to confirm. It can
        # set one — that is how you stop depending on Google — but only while
        # it genuinely has none; once set, the old one is required as usual.
        if user.has_password and not user.check_password(data.get('currentPassword') or ''):
            raise ApiError('That is not your current password.', 403)
        if len(data['password']) < MIN_PASSWORD:
            raise ApiError(f'Use a password of at least {MIN_PASSWORD} characters.')
        user.set_password(data['password'])

    db.session.commit()
    return jsonify(user=user.to_private_dict())


# --------------------------------------------------------------------------
# Forgotten passwords
#
# There is no mail server, so the link has to travel some other way. In debug
# the API hands it straight back and the frontend shows it; anywhere else it
# is written to the log for an admin to pass on. What does NOT change between
# the two is the response the caller sees - it is identical whether or not the
# address exists, so this endpoint cannot be used to find out who has an
# account here.
# --------------------------------------------------------------------------

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


@bp.post('/forgot')
@password_sign_in
def forgot_password():
    data = _json()
    email = (data.get('email') or '').strip().lower()
    if not email:
        raise ApiError('Enter the email address on the account.')

    user = db.session.scalar(db.select(User).filter_by(email=email))
    payload = {'sent': True}

    if user is not None:
        # Any earlier request is spent the moment a new one is made, so a
        # link someone left in a chat window stops working.
        for old in db.session.scalars(
            db.select(PasswordReset).filter(
                PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)
            )
        ).all():
            old.used_at = utcnow()

        token = secrets.token_urlsafe(32)
        ttl = current_app.config['RESET_TOKEN_TTL_SECONDS']
        db.session.add(PasswordReset(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=utcnow() + timedelta(seconds=ttl),
        ))
        db.session.commit()

        current_app.logger.info('Password reset requested for %s: /reset?token=%s', email, token)
        if current_app.config['RESET_RETURN_TOKEN']:
            payload['token'] = token
            payload['expiresInMinutes'] = ttl // 60

    return jsonify(payload)


@bp.post('/reset')
@password_sign_in
def reset_password():
    data = _json()
    token = (data.get('token') or '').strip()
    password = data.get('password') or ''

    if not token:
        raise ApiError('That reset link is incomplete.')
    if len(password) < MIN_PASSWORD:
        raise ApiError(f'Use a password of at least {MIN_PASSWORD} characters.')

    entry = db.session.scalar(
        db.select(PasswordReset).filter_by(token_hash=_hash_token(token))
    )
    if entry is None or not entry.is_usable:
        # One message for expired, used and never-existed alike.
        raise ApiError('That reset link has expired or already been used.', 400)

    entry.user.set_password(password)
    entry.used_at = utcnow()
    db.session.commit()

    # Signed straight in: the alternative is asking someone to type the
    # password they just chose, thirty seconds later.
    return jsonify(token=create_token(entry.user), user=entry.user.to_private_dict())
