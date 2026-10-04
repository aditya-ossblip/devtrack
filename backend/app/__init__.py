from flask import Flask, jsonify

# .env is loaded inside config.py, which must happen before its settings are
# read at import time. Do not move it here.
from .config import Config
from .errors import register_error_handlers
from .extensions import cors, db, migrate, socketio


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(
        app,
        resources={r'/api/*': {'origins': app.config['CORS_ORIGINS']}},
        supports_credentials=False,
    )
    socketio.init_app(app, cors_allowed_origins=app.config['CORS_ORIGINS'] or '*')

    # Imported for their side effects: model registration and socket handlers.
    from . import events, models  # noqa: F401
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
