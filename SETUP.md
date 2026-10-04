# Running DevTrack

Two processes: the Flask API on :5000 and the Vite dev server on :5173. Vite
proxies `/api` and `/socket.io` through to Flask, so the browser only ever
talks to one origin and there is no CORS setup to get wrong.

## 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
copy .env.example .env        # Windows   (cp on macOS/Linux)
```

Open `.env` and set a real `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Leave `DATABASE_URL` blank to start — the app falls back to a SQLite file at
`backend/instance/devtrack.db`, so you can run everything before MySQL exists.

Create the schema, add the demo account and start the API:

```bash
flask --app run:app db upgrade
python seed.py
python run.py
```

The schema comes from the migrations in `migrations/versions/`; `seed.py`
refuses to run until they have been applied.

`seed.py` creates a single account, `aditya@devtrack.local` with the password
`devtrack123`, and no project — creating one is the first thing to try. To
see developer restrictions, register a second account, add it to your project
as a developer and sign in as it. `python seed.py --email you@gmail.com` moves
the demo account onto your Google address, and `--reset` empties every table
first.

Check it is up: <http://localhost:5000/api/health> should return
`{"status":"ok"}`.

## 2. Frontend

In a second terminal, from the project root:

```bash
npm install
npm run dev
```

<http://localhost:5173> — you should land on the login page.

## Running it from the VS Code / Antigravity terminal

Open the `Devtrack` folder in the editor, then open a terminal (`Ctrl` + `` ` ``)
and split it so you have two panes. From the project root, no `cd` needed:

```powershell
# pane 1 — the API
.\backend\.venv\Scripts\python.exe backend\run.py

# pane 2 — the frontend
npm run dev
```

Calling the virtualenv's `python.exe` by path avoids activating it, which
sidesteps PowerShell's execution-policy block on `Activate.ps1` entirely.

To get the editor to pick the right interpreter for IntelliSense and debugging:
`Ctrl+Shift+P` → **Python: Select Interpreter** → choose the one under
`backend\.venv\Scripts\python.exe`. After that, any new terminal activates the
venv on its own and plain `python run.py` works from `backend/`.

## 3. Switching to MySQL

```sql
CREATE DATABASE devtrack CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'devtrack'@'localhost' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON devtrack.* TO 'devtrack'@'localhost';
```

Then in `backend/.env`:

```
DATABASE_URL=mysql+pymysql://devtrack:your-password@localhost:3306/devtrack
```

Build the schema in MySQL from the existing migrations and add the demo
account:

```bash
cd backend
flask --app run:app db upgrade
python seed.py
```

The migrations folder is already in the repo, so do not run `db init`. After a
model change, run `db migrate -m "what changed"` and then `db upgrade` (or
`npm run db:migrate` / `npm run db:upgrade` from the root), and commit the new
file in `migrations/versions/`.

## 4. Tests

```bash
cd backend
pytest
```

The suite runs against in-memory SQLite and needs no server running. It covers
login, JWT and password reset, the board response shape, issue moves and
workflow transitions, sprints, attachments, pagination, the live activity feed,
the derived `overdue` flag, and every row of the permission table.

## Troubleshooting

**"Cannot reach the server. Is the backend running?"** — this message means Vite could not proxy to :5000. Start the backend first.

**Vite refuses to start** — Vite 8 needs Node 20.19+ or 22.12+. Check with
`node -v`.

**The backend prints its startup banner and then the prompt comes back** —
the process exited instead of serving, and the frontend will show 502s or
"Cannot reach the server". This was the Werkzeug auto-reloader clashing with
Flask-SocketIO on Windows; `run.py` now starts with the reloader off, so the
server stays up. The cost is that backend code changes need a manual restart
(`Ctrl+C`, run it again). To try the reloader again: `$env:FLASK_USE_RELOADER=1`
before starting.

**Live updates don't arrive** — everything still works over REST; only other
people's changes stop appearing by themselves. Confirm the backend was started
with `python run.py` (which uses `socketio.run`) and not `flask run`, which
does not speak WebSocket.

**Login always fails** — if you changed `SECRET_KEY` after signing in, old
tokens no longer validate. Clear site data, or just sign in again.

**`InsecureKeyLengthWarning` saying the key is 27 bytes** — 27 is the length
of the `dev-only-not-for-deployment` fallback in `config.py`, so seeing that
number means `.env` was not loaded and every setting fell back to its default
— including `DATABASE_URL`, which would silently keep you on SQLite after you
thought you had switched to MySQL. `.env` is now loaded at the top of
`config.py`, before any setting is read. If it ever comes back, check that
`backend/.env` exists and that nothing moved the `load_dotenv()` call.

**`InsecureKeyLengthWarning` from PyJWT** — HS256 signing keys should be at
least 32 bytes (RFC 7518 §3.2); a short key is easier to brute-force. The real
`SECRET_KEY` in `.env` is 64 hex characters, so the running app was never
affected — only the test config had a short one, and that is fixed. If you see
this warning again, whatever key is in play is too short: regenerate it with
`python -c "import secrets; print(secrets.token_hex(32))"`.
