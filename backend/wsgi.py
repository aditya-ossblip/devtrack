"""Production entry point (Render, or any Linux host).

    gunicorn -w 1 --threads 50 -b 0.0.0.0:$PORT wsgi:app

One worker process with many threads: Flask-SocketIO's threading mode needs
every live connection in the same process, and the free plan has one small
CPU anyway. Development still uses `npm run api` (run.py).
"""

from app import create_app

app = create_app()
