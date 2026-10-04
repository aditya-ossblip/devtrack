"""Development entry point.

    python run.py

Use socketio.run rather than app.run: the plain Flask server does not know
about the WebSocket handshake, so live updates silently fall back to polling.
"""

import os

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == '__main__':
    debug = os.getenv('FLASK_DEBUG', '1') == '1'

    # The Werkzeug auto-reloader and Flask-SocketIO's dev server do not get on
    # under Windows: the server prints its whole startup banner and then the
    # process exits, leaving the port closed and the frontend proxy returning
    # 502. Reloading is a convenience; staying up is not. Set
    # FLASK_USE_RELOADER=1 to opt back in if it behaves on your machine —
    # otherwise restart the server by hand after changing backend code.
    use_reloader = os.getenv('FLASK_USE_RELOADER', '0') == '1'

    socketio.run(
        app,
        host=os.getenv('HOST', '127.0.0.1'),
        port=int(os.getenv('PORT', '5000')),
        debug=debug,
        use_reloader=use_reloader,
        allow_unsafe_werkzeug=True,  # dev server only
    )
