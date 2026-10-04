from flask_cors import CORS
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()

# async_mode is left to Flask-SocketIO: it picks eventlet or gevent when they
# are installed and falls back to threading, which is fine for development.
socketio = SocketIO(cors_allowed_origins='*')
