from flask import jsonify
from sqlalchemy.exc import OperationalError, ProgrammingError
from werkzeug.exceptions import HTTPException

from .extensions import db


class ApiError(Exception):
    """An error with a message meant for a human to read.

    Login.jsx renders `error` from the response verbatim, so every message
    raised here should read like a sentence, not a status code.
    """

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        # Whatever the request had half-changed is thrown away, so a refused
        # edit (say, a title that is too long) cannot be written by the next
        # thing that happens to flush the session.
        db.session.rollback()
        return jsonify(error=error.message), error.status

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        # Keeps 404s and 405s as JSON, so the frontend never has to parse an
        # HTML error page out of an axios rejection.
        return jsonify(error=error.description), error.code

    # Two decorators rather than a tuple: Flask's errorhandler takes one
    # exception class or one status code, never a tuple of them.
    @app.errorhandler(OperationalError)
    @app.errorhandler(ProgrammingError)
    def handle_schema_drift(error):
        """The database does not have the columns the models expect.

        Almost always one thing: a model changed and `db upgrade` has not run.
        Left alone this surfaces as a generic 500, and every page just says it
        could not do the thing — which sends people hunting through their own
        code for a bug that is really an unapplied migration.
        """
        detail = str(getattr(error, 'orig', error))
        app.logger.error('Database schema does not match the models: %s', detail)

        lowered = detail.lower()
        # SQLite, MySQL and Postgres each word it differently.
        if ('no such column' in lowered or 'unknown column' in lowered
                or ('column' in lowered and 'does not exist' in lowered)):
            return jsonify(
                error=(
                    'The database is missing a column the app expects. '
                    'Stop the API and run: npm run db:migrate -- -m "sync" '
                    'then npm run db:upgrade'
                )
            ), 503

        return jsonify(error='The database rejected that request.'), 503

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        app.logger.exception('Unhandled error: %s', error)
        if app.config.get('DEBUG') or app.config.get('TESTING'):
            raise error
        return jsonify(error='Something went wrong on our end.'), 500
