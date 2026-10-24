# Running DevTrack

**Shortcut:** `npm run setup` from the project root does all of section 1 and
`npm install` in one go, on any OS. The manual steps are below.

Two processes: the Flask API on :5001 and the Vite dev server on :5173. Vite
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
`backend/instance/devtrack.db`, so you can run everything before Postgres is
installed. Section 3 moves you onto Postgres.

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

Check it is up: <http://127.0.0.1:5001/api/health> should return
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

```bash
# pane 1 — the API
npm run api

# pane 2 — the frontend
npm run dev
```

`npm run api` calls the virtualenv's Python by path (`.venv\Scripts\python.exe`
on Windows, `.venv/bin/python` on macOS/Linux), so nothing needs activating —
which also sidesteps PowerShell's execution-policy block on `Activate.ps1`.

To get the editor to pick the right interpreter for IntelliSense and debugging:
`Ctrl+Shift+P` → **Python: Select Interpreter** → choose the one under
`backend\.venv\Scripts\python.exe`. After that, any new terminal activates the
venv on its own and plain `python run.py` works from `backend/`.

## 3. Postgres

DevTrack runs on Postgres, on your computer and on the live site. SQLite is
only the fallback that lets a fresh clone start before Postgres is installed.

### Install it

**Windows** (Command Prompt):

```
winget install -e --id PostgreSQL.PostgreSQL.17
```

The installer asks for a password for the `postgres` superuser. Keep it; you
need it once, below. Then open a **new** Command Prompt so `psql` is on PATH
(or use `"C:\Program Files\PostgreSQL\17\bin\psql.exe"`).

**macOS** (Terminal, with Homebrew):

```
brew install postgresql@17
brew services start postgresql@17
echo 'export PATH="$(brew --prefix postgresql@17)/bin:$PATH"' >> ~/.zprofile
```

Open a new Terminal window afterwards.

### Create DevTrack's user and databases

Windows: `psql -U postgres` (enter the superuser password).
macOS: `psql postgres` (Homebrew makes you the superuser, no password).

```sql
CREATE ROLE devtrack LOGIN PASSWORD 'pick-a-password';
CREATE DATABASE devtrack OWNER devtrack;
CREATE DATABASE devtrack_test OWNER devtrack;
\q
```

Then in `backend/.env`:

```
DATABASE_URL=postgresql://devtrack:pick-a-password@localhost:5432/devtrack
TEST_DATABASE_URL=postgresql://devtrack:pick-a-password@localhost:5432/devtrack_test
```

### Build the schema, and bring your old data across

```
npm run db:upgrade
npm run db:copy-sqlite
```

`db:copy-sqlite` copies everything from `backend/instance/devtrack.db` into the
empty Postgres database in one go and leaves the SQLite file untouched as a
backup. Skip it on a fresh install; run `npm run seed` instead for the demo
account. Restart `npm run api` and you are on Postgres.

The migrations folder is already in the repo, so never run `db init`. After a
model change: `npm run db:migrate -- -m "what changed"`, then
`npm run db:upgrade`, and commit the new file in `migrations/versions/`.

### On the live site

Hosts (Render, Railway, Neon, Supabase) give you a URL starting `postgres://`
or `postgresql://`. Paste it into `DATABASE_URL` as it is; the app adds the
driver itself. Also set `DEVTRACK_ENV=production`, a fresh `SECRET_KEY` and
`GOOGLE_CLIENT_ID`. In production the app refuses to start if any of those is
missing, password sign-in and reset links are off, and Google is the only way
in.

## 4. Tests

```bash
npm test               # in-memory SQLite, nothing to install
npm run test:postgres  # the same suite on TEST_DATABASE_URL
```

`npm test` needs no server running. Run `test:postgres` before deploying:
Postgres enforces column lengths and types that SQLite ignores, so it catches
problems SQLite lets through. It empties `devtrack_test` as it goes, so never
point TEST_DATABASE_URL at your real database. It covers
login, JWT and password reset, the board response shape, issue moves and
workflow transitions, sprints, attachments, pagination, the live activity feed,
the derived `overdue` flag, and every row of the permission table.

## Troubleshooting

**"Cannot reach the server. Is the backend running?"** — this message means Vite could not proxy to :5001. Start the backend first.

**macOS: the login page says it can't reach the server while the backend is
running** — something else is answering on the API's port. The usual one is
AirPlay Receiver, which holds port 5000 on macOS 12+ and replies 403 to
everything; that is why DevTrack uses 5001. Check with
`lsof -nP -iTCP:5001 -sTCP:LISTEN` — the only listener should be Python. If
5001 is taken too, start the API with `PORT=5002 npm run api` and Vite with
`VITE_API_TARGET=http://127.0.0.1:5002 npm run dev`.

**Windows: `npm : File ...\npm.ps1 cannot be loaded because running scripts is
disabled on this system`** — PowerShell on a fresh Windows install blocks npm's
PowerShell wrapper. `npm run api` and `npm run dev` work in **Command Prompt**,
which is why the project's `.vscode/settings.json` makes VS Code open Command
Prompt terminals on Windows. In PowerShell, either type `npm.cmd run api` /
`npm.cmd run dev`, or allow scripts for your own account once with
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. macOS and Linux are
unaffected.

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
thought you had switched to Postgres. `.env` is now loaded at the top of
`config.py`, before any setting is read. If it ever comes back, check that
`backend/.env` exists and that nothing moved the `load_dotenv()` call.

**`InsecureKeyLengthWarning` from PyJWT** — HS256 signing keys should be at
least 32 bytes (RFC 7518 §3.2); a short key is easier to brute-force. The real
`SECRET_KEY` in `.env` is 64 hex characters, so the running app was never
affected — only the test config had a short one, and that is fixed. If you see
this warning again, whatever key is in play is too short: regenerate it with
`python -c "import secrets; print(secrets.token_hex(32))"`.
