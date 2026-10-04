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


def _database_url() -> str:
    """MySQL when DATABASE_URL is set, otherwise a local SQLite file.

    The SQLite default exists so `python run.py` works on a fresh clone with no
    database server installed. Production and the shared dev database should
    both set DATABASE_URL.
    """
    url = os.getenv('DATABASE_URL', '').strip()
    if url:
        return url
    INSTANCE_DIR.mkdir(exist_ok=True)
    return f"sqlite:///{INSTANCE_DIR / 'devtrack.db'}"


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-not-for-deployment')
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Recycle before MySQL's default wait_timeout (8h) drops the connection,
    # and check liveness on checkout so a slept laptop does not 500.
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 3600}

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

    # --- Attachments ----------------------------------------------------
    # Uploads live beside the database, outside the source tree, so a deploy
    # never serves them as static files by accident.
    UPLOAD_DIR = INSTANCE_DIR / 'uploads'
    MAX_UPLOAD_BYTES = int(os.getenv('MAX_UPLOAD_BYTES', str(25 * 1024 * 1024)))
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
    # somehow. In debug the API returns it directly so the flow is testable;
    # anywhere else it is logged and the response says nothing.
    RESET_RETURN_TOKEN = os.getenv('RESET_RETURN_TOKEN', '1') == '1'

    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')
        if origin.strip()
    ]


class TestConfig(Config):
    TESTING = True
    UPLOAD_DIR = INSTANCE_DIR / 'test-uploads'
    MAX_UPLOAD_BYTES = 64 * 1024   # small, so a test can exceed it cheaply
    MAX_CONTENT_LENGTH = 1024 * 1024
    RESET_RETURN_TOKEN = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}

    # Fixed, but a real 32-byte key: RFC 7518 wants at least that for HS256,
    # and PyJWT warns on anything shorter. Tests should exercise the same key
    # size production uses.
    SECRET_KEY = 'devtrack-test-key-0123456789abcdef'

    # Fast on purpose. Never outside tests: one PBKDF2 round is no protection
    # at all if a password file ever leaks.
    PASSWORD_HASH_METHOD = 'pbkdf2:sha256:1'
