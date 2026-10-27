import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / 'instance'

# This MUST run before the Config class body below, because those are
# module-level assignments: os.getenv() is evaluated the moment this module is
# imported. Loading .env any later — from create_app(), say — is too late, and
# the app silently runs on the fallbacks instead of your settings.
load_dotenv(BASE_DIR / '.env')


def _flag(name: str, default: bool) -> bool:
    """Read an on/off setting. Accepts 1/0, true/false, yes/no, on/off."""
    raw = os.getenv(name, '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def normalise_database_url(url: str) -> str:
    """Point every Postgres URL at the psycopg 3 driver.

    Hosts hand out `postgres://...` (Heroku, Render) or `postgresql://...`
    (Neon, Supabase, Railway). SQLAlchemy 2 refuses the first spelling outright
    and reads the second as "use psycopg2", which is not installed. Rewriting
    both here means the URL a host gives you can be pasted into DATABASE_URL
    exactly as it is.
    """
    url = url.strip()
    for prefix in ('postgres://', 'postgresql://'):
        if url.startswith(prefix):
            return 'postgresql+psycopg://' + url[len(prefix):]
    return url


def _database_url() -> str:
    """DATABASE_URL when set (Postgres, or MySQL), otherwise a local SQLite file.

    Postgres is the real database, locally and in production. The SQLite
    fallback only exists so a fresh clone can start before Postgres is
    installed; it is not something to launch on.
    """
    url = os.getenv('DATABASE_URL', '').strip()
    if url:
        return normalise_database_url(url)
    INSTANCE_DIR.mkdir(exist_ok=True)
    return f"sqlite:///{INSTANCE_DIR / 'devtrack.db'}"


def engine_options(url: str) -> dict:
    """Connection settings for the database at `url`.

    Recycle before MySQL's default wait_timeout (8h) drops the connection, and
    check liveness on checkout so a slept laptop does not 500.

    Postgres sessions are pinned to UTC. Every timestamp here is a UTC instant
    stored in a column without a time zone, and Postgres converts an aware
    datetime to the *session's* zone before dropping the offset. A server set
    up on a machine in India defaults to Asia/Kolkata, which shifted every
    stored time by 5h30 and kept expired reset links alive for hours.
    """
    options = {'pool_pre_ping': True, 'pool_recycle': 3600}
    if url.startswith('postgresql'):
        options['connect_args'] = {'options': '-c timezone=UTC'}
    return options


# 'development' on your own computer, 'production' on the live server. The
# safe choice for everything below depends on which one this is, so the
# defaults follow it and the .env file only has to say where it is running.
ENVIRONMENT = os.getenv('DEVTRACK_ENV', 'development').strip().lower()
IS_PRODUCTION = ENVIRONMENT == 'production'


class Config:
    ENVIRONMENT = ENVIRONMENT
    IS_PRODUCTION = IS_PRODUCTION

    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-not-for-deployment')
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = engine_options(SQLALCHEMY_DATABASE_URI)

    JWT_EXPIRES_SECONDS = int(os.getenv('JWT_EXPIRES_SECONDS', '86400'))
    JWT_ALGORITHM = 'HS256'

    # Werkzeug's default (scrypt) is deliberately expensive, which is the point
    # in production and a problem in tests: every fixture hashes four
    # passwords, and the suite ends up slow enough that people Ctrl+C it.
    PASSWORD_HASH_METHOD = os.getenv('PASSWORD_HASH_METHOD', 'scrypt')

    # --- Google sign-in --------------------------------------------------
    # The client ID is public: it ships inside the page and Google expects it
    # to. There is deliberately no client secret here — the ID-token flow does
    # not use one, because the token is verified against Google's public keys
    # rather than exchanged at a token endpoint. Empty means the button never
    # appears and /api/auth/google refuses.
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '').strip()

    # Email-and-password accounts. Off in production: there, Google is the
    # only way in, which means every address is one Google has verified and
    # there are no passwords to leak, guess or reset. On in development, so
    # the demo account works before Google is set up. PASSWORD_SIGN_IN=1 or 0
    # in .env overrides either default.
    PASSWORD_SIGN_IN = _flag('PASSWORD_SIGN_IN', default=not IS_PRODUCTION)

    # --- Attachments ----------------------------------------------------
    # Uploads live beside the database, outside the source tree, so a deploy
    # never serves them as static files by accident.
    UPLOAD_DIR = INSTANCE_DIR / 'uploads'
    MAX_UPLOAD_BYTES = int(os.getenv('MAX_UPLOAD_BYTES', str(10 * 1024 * 1024)))
    # Total file space per project. Keeps every team inside the free 1 GB of
    # the live bucket, and turns "the bucket is full" into a clear message
    # for one project instead of failed uploads for everyone.
    PROJECT_STORAGE_BYTES = int(os.getenv('PROJECT_STORAGE_BYTES', str(100 * 1024 * 1024)))

    # Where files go: 'local' (UPLOAD_DIR, for your own computer) or 's3' (any
    # S3-compatible bucket: Supabase Storage on the live site). See storage.py.
    STORAGE_BACKEND = os.getenv('STORAGE_BACKEND', 'local').strip().lower()
    S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL', '').strip()
    S3_REGION = os.getenv('S3_REGION', '').strip()
    S3_BUCKET = os.getenv('S3_BUCKET', '').strip()
    S3_ACCESS_KEY_ID = os.getenv('S3_ACCESS_KEY_ID', '').strip()
    S3_SECRET_ACCESS_KEY = os.getenv('S3_SECRET_ACCESS_KEY', '').strip()
    # Flask's own guard, so an oversized body is refused before it is read
    # into memory rather than after.
    MAX_CONTENT_LENGTH = MAX_UPLOAD_BYTES + (1024 * 1024)

    # An allowlist, not a blocklist. A blocklist is a list of the attacks
    # somebody already thought of.
    ALLOWED_UPLOAD_EXTENSIONS = {
        # images
        'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg',
        # documents
        'pdf', 'doc', 'docx', 'odt', 'txt', 'md', 'rtf',
        # decks and sheets
        'ppt', 'pptx', 'odp', 'xls', 'xlsx', 'ods', 'csv',
        # archives
        'zip',
        # code and data
        'json', 'log', 'sql', 'py', 'js', 'jsx', 'html', 'css',
    }

    # --- Password reset --------------------------------------------------
    RESET_TOKEN_TTL_SECONDS = int(os.getenv('RESET_TOKEN_TTL_SECONDS', '3600'))
    # With no mail server wired up, the reset link has to reach the user
    # somehow. In development the API returns it directly so the flow is
    # testable. Never in production: handing the link to whoever asks would let
    # anyone take over any account by typing its email address.
    RESET_RETURN_TOKEN = (not IS_PRODUCTION) and _flag('RESET_RETURN_TOKEN', default=True)

    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')
        if origin.strip()
    ]


class TestConfig(Config):
    TESTING = True
    UPLOAD_DIR = INSTANCE_DIR / 'test-uploads'
    MAX_UPLOAD_BYTES = 64 * 1024   # small, so a test can exceed it cheaply
    PROJECT_STORAGE_BYTES = 160 * 1024
    STORAGE_BACKEND = 'local'
    MAX_CONTENT_LENGTH = 1024 * 1024
    RESET_RETURN_TOKEN = True
    # In-memory SQLite by default: fast, and nothing to install. `npm run
    # test:postgres` runs the same suite against TEST_DATABASE_URL instead, so
    # anything Postgres is stricter about (string lengths, types) shows up
    # before it reaches the live site. That database is emptied by every test.
    if os.getenv('DEVTRACK_TEST_ON_POSTGRES') == '1':
        SQLALCHEMY_DATABASE_URI = normalise_database_url(os.getenv('TEST_DATABASE_URL', ''))
        SQLALCHEMY_ENGINE_OPTIONS = engine_options(SQLALCHEMY_DATABASE_URI)
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        SQLALCHEMY_ENGINE_OPTIONS = {}
    PASSWORD_SIGN_IN = True

    # Fixed, but a real 32-byte key: RFC 7518 wants at least that for HS256,
    # and PyJWT warns on anything shorter. Tests should exercise the same key
    # size production uses.
    SECRET_KEY = 'devtrack-test-key-0123456789abcdef'

    # Fast on purpose. Never outside tests: one PBKDF2 round is no protection
    # at all if a password file ever leaks.
    PASSWORD_HASH_METHOD = 'pbkdf2:sha256:1'
