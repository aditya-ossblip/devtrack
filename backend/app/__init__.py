from flask import Flask, jsonify

# .env is loaded inside config.py, which must happen before its settings are
# read at import time. Do not move it here.
from .config import Config
from .errors import register_error_handlers
from .extensions import cors, db, migrate, socketio


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)
    _refuse_unsafe_production(app)

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(
        app,
        resources={r'/api/*': {'origins': app.config['CORS_ORIGINS']}},
        supports_credentials=False,
    )
    socketio.init_app(app, cors_allowed_origins=app.config['CORS_ORIGINS'] or '*')

    # Imported for their side effects: model registration and socket handlers.
    from . import events, lengths, models  # noqa: F401

    lengths.install()
    from .blueprints import register_blueprints

    events.init_socket_handlers(socketio)

    register_blueprints(app)
    register_error_handlers(app)
    _warn_if_schema_is_behind(app)

    @app.get('/api/health')
    def health():
        return jsonify(status='ok')

    @app.cli.command('seed')
    def seed_command():
        """flask --app run:app seed — load the demo project."""
        from seed import seed

        seed()

    return app



def _refuse_unsafe_production(app) -> None:
    """Stop at startup rather than run a live site on development settings.

    Each of these is easy to forget when moving to a host, and each one fails
    quietly: a guessable signing key lets anyone forge a login, and a SQLite
    file on most hosts is wiped on every deploy, taking everyone's work with it.
    """
    if not app.config.get('IS_PRODUCTION'):
        return

    problems = []
    key = app.config.get('SECRET_KEY') or ''
    if key in ('dev-only-not-for-deployment', 'change-me-before-anyone-else-runs-this') or len(key) < 32:
        problems.append('SECRET_KEY must be set to a long random value (64 hex characters).')
    if str(app.config.get('SQLALCHEMY_DATABASE_URI', '')).startswith('sqlite'):
        problems.append('DATABASE_URL must point at Postgres; SQLite is for local development only.')
    if not app.config.get('GOOGLE_CLIENT_ID') and not app.config.get('PASSWORD_SIGN_IN'):
        problems.append('GOOGLE_CLIENT_ID is empty, so nobody would be able to sign in.')

    if problems:
        raise RuntimeError(
            'DEVTRACK_ENV=production, but the settings are not safe to go live with:\n  - '
            + '\n  - '.join(problems)
        )


def _warn_if_schema_is_behind(app) -> None:
    """Compare the live database against the models, and say so loudly.

    The failure this prevents is miserable to diagnose from the outside: the
    app boots, the pages render, and every request that touches the changed
    table returns a 500 that the UI reports as "could not sign in". The cause
    is not in the code at all. One glance at the terminal should be enough.
    """
    from sqlalchemy import inspect

    with app.app_context():
        try:
            inspector = inspect(db.engine)
            present = set(inspector.get_table_names())
        except Exception:
            return  # no database yet; seed.py already explains that case

        if not present:
            return

        missing = []
        for table in db.metadata.sorted_tables:
            if table.name not in present:
                missing.append(f'{table.name} (whole table)')
                continue
            have = {column['name'] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in have:
                    missing.append(f'{table.name}.{column.name}')

        if not missing:
            return

        app.logger.error(
            '\n'
            '  ' + '=' * 68 + '\n'
            '  THE DATABASE IS BEHIND THE MODELS\n'
            '  ' + '=' * 68 + '\n'
            '  Missing: %s\n'
            '\n'
            '  Requests touching these will fail with a 503 until you run,\n'
            '  with this API stopped:\n'
            '\n'
            '      npm run db:migrate -- -m "sync"\n'
            '      npm run db:upgrade\n'
            '  ' + '=' * 68,
            ', '.join(missing),
        )
