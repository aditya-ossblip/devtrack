from .analytics_routes import bp as analytics_bp
from .attachment_routes import bp as attachment_bp
from .auth_routes import bp as auth_bp
from .issue_routes import bp as issue_bp
from .notification_routes import bp as notification_bp
from .project_routes import bp as project_bp
from .sprint_routes import bp as sprint_bp
from .user_routes import bp as user_bp

BLUEPRINTS = (
    auth_bp,
    user_bp,
    project_bp,
    issue_bp,
    sprint_bp,
    notification_bp,
    analytics_bp,
    attachment_bp,
)


def register_blueprints(app):
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)
