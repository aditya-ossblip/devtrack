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
        # Not 5000: macOS's AirPlay Receiver holds that port. vite.config.js
        # proxies to 5001 — change both together, or set PORT and
        # VITE_API_TARGET.
        port=int(os.getenv('PORT', '5001')),
        debug=debug,
        use_reloader=use_reloader,
        # Werkzeug's in-browser debugger wraps the whole server, Socket.IO
        # included. When a live connection closes, the WebSocket layer ends it
        # by raising ConnectionError on purpose; the debugger mistakes that for
        # a crash, logs a 500 with a traceback and writes an error page down
        # the already-closed socket (which is what makes Vite print
        # "ws proxy error: write ECONNABORTED"). This is a JSON API behind a
        # proxy, so the debugger page was never reachable anyway; real errors
        # still print their traceback in this terminal.
        use_debugger=False,
        allow_unsafe_werkzeug=True,  # dev server only
    )
