# DevTrack

Issue tracking and sprint planning for small development teams — a Jira-style
tracker built on React + Vite and a Flask + SQLAlchemy API, with JWT and Google
sign-in, per-project roles, configurable workflows and live updates over
Socket.IO.

- **Setup, Postgres and troubleshooting:** [SETUP.md](SETUP.md)
- **Original API contract and design notes:** [PHASE2.md](PHASE2.md)
- **How it compares to Jira, feature by feature:** [docs/devtrack-vs-jira.md](docs/devtrack-vs-jira.md)

## Features

- **Projects with keys** — each project gets a key (`DEV`), and issues are
  numbered from it (`DEV-14`).
- **Issues** — epic, story, task, bug and sub-task types; five priority levels;
  story points, labels, due dates, assignee and reporter; comments and
  per-issue activity history.
- **Board** — drag-and-drop Kanban with optimistic moves that roll back if the
  server refuses.
- **Configurable workflow** — columns are rows in `workflow_states`, not code.
  Rename, reorder, add or remove states, and restrict which transitions are
  allowed. Each state belongs to a category (`todo`, `in_progress`, `done`) so
  reports keep working whatever the columns are called.
- **Backlog and sprints** — plan future sprints, start and complete them, with
  epic progress on the backlog.
- **Analytics** — project breakdowns, sprint burndown and velocity.
- **My tasks** — everything assigned to you across projects, with a "three for
  today" strip that ranks what to do next (overdue → priority → due soonest →
  already started → bigger first).
- **Files** — project files and issue attachments, checked against an
  extension allowlist and a size limit.
- **Live updates** — board changes, notifications and a project activity feed
  push to everyone viewing the project.
- **Accounts** — Sign in with Google on the live site. Email/password (with
  reset) is kept for local development and the demo account.

## Tech stack

| Layer | |
| --- | --- |
| Frontend | React 18, React Router 7, Vite 8, axios, socket.io-client |
| Backend | Flask 3, Flask-SQLAlchemy / SQLAlchemy 2, Flask-Migrate (Alembic), Flask-SocketIO, PyJWT, google-auth |
| Database | Postgres (psycopg 3); SQLite fallback for a first run |
| Tests | pytest, against in-memory SQLite or Postgres (`npm run test:postgres`) |

## Quick start (Windows, macOS, Linux)

You need Node 20.19+ or 22.12+ and Python 3.10+.

```bash
npm run setup     # installs everything, writes backend/.env, builds the database, creates the demo account
```

It is safe to run again; each step skips what is already done.

Then run each of these in its own terminal:

```bash
npm run api    # Flask + Socket.IO on http://127.0.0.1:5001
npm run dev    # Vite on http://localhost:5173
```

Open <http://localhost:5173> and sign in as `aditya@devtrack.local` /
`devtrack123`. The seed creates **only this account and no demo project** on
purpose: creating a project, adding people and shaping the board is the flow
being tested. `python backend/seed.py --email you@gmail.com` moves the demo
account to your Google address, so your first Google sign-in lands in it.

For manual setup, macOS/Linux and Postgres, see [SETUP.md](SETUP.md).

### npm scripts

| Script | Does |
| --- | --- |
| `setup` | One-time install: packages, virtualenv, `.env`, database, demo account |
| `dev` / `build` / `preview` | Vite dev server, production build, preview the build |
| `api` | Start the backend (`backend/run.py`) |
| `test` | Run the pytest suite |
| `seed` | Create the demo account |
| `db:upgrade` / `db:migrate` / `db:downgrade` / `db:history` | Flask-Migrate commands |

The backend scripts go through `scripts/backend.mjs`, which finds the
virtualenv's Python on Windows (`.venv\Scripts\python.exe`) or macOS/Linux
(`.venv/bin/python`), so the same commands work on every system.

## Configuration

Settings live in `backend/.env`. Copy them from
[backend/.env.example](backend/.env.example); never commit the real file.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEVTRACK_ENV` | `development` | `production` on the live server: Google-only sign-in, no reset links, refuses to start on unsafe settings |
| `SECRET_KEY` | insecure dev value | Signs JWTs. Use 32+ random bytes. |
| `DATABASE_URL` | SQLite at `backend/instance/devtrack.db` | Postgres, e.g. `postgresql://devtrack:pass@localhost:5432/devtrack`. A host's `postgres://` URL works as it is. |
| `TEST_DATABASE_URL` | unset | A separate Postgres database for `npm run test:postgres` (it gets emptied) |
| `JWT_EXPIRES_SECONDS` | `86400` | Login lifetime |
| `CORS_ORIGINS` | `http://localhost:5173` | Only needed when not going through the Vite proxy |
| `MAX_UPLOAD_BYTES` | 25 MB if unset; `.env.example` sets 8 MB | Largest attachment |
| `RESET_TOKEN_TTL_SECONDS` | `3600` | Password reset link lifetime |
| `RESET_RETURN_TOKEN` | `1` | Return the reset link in the API response (there is no mail server). Always off in production. |
| `PASSWORD_SIGN_IN` | on in development, off in production | Email-and-password accounts. Refused on the server when off. |
| `GOOGLE_CLIENT_ID` | empty | Sign in with Google. Required in production, where it is the only way in. |

## Project layout

```
.                         frontend (Vite root)
├── src/
│   ├── api/              axios client, Socket.IO connection
│   ├── pages/            Board, Backlog, Projects, MyTasks, Files, Team,
│   │                     Analytics, Settings, Login, Register
│   ├── components/       AppLayout, Sidebar, Topbar, IssueCard, IssueDrawer,
│   │                     NewIssueModal, ActivityFeed, LivePanel, FocusStrip,
│   │                     Attachments, charts, GoogleButton, …
│   ├── state/            AuthContext, ProjectContext, useBoard, useMembers,
│   │                     useNotifications, focus.js
│   └── styles/           theme.css (design tokens), app.css, board-live.css
├── backend/
│   ├── app/
│   │   ├── models.py     User, Project, ProjectMember, WorkflowState,
│   │   │                 WorkflowTransition, Sprint, Issue, Comment,
│   │   │                 Notification, Activity, Attachment, PasswordReset
│   │   ├── auth.py       JWT, @token_required, project-role checks
│   │   ├── events.py     Socket.IO rooms, broadcasts, live activity feed
│   │   ├── history.py    writes activity rows
│   │   └── blueprints/   auth, users, projects, issues, sprints,
│   │                     attachments, notifications, analytics
│   ├── migrations/       Alembic migrations
│   ├── tests/            pytest suite
│   ├── seed.py           demo account
│   └── run.py            dev server entry point
├── docs/                 Jira comparison
├── setup.ps1             one-shot Windows setup
└── refresh.ps1           helper script
```

## API overview

Everything is under `/api` and returns JSON. All routes except register, login,
Google sign-in, forgot/reset password and `/api/health` need
`Authorization: Bearer <jwt>`.

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/register` · `POST /auth/login` · `POST /auth/google` · `GET/PATCH /auth/me` · `POST /auth/forgot` · `POST /auth/reset` · `GET /auth/config` |
| Projects | `GET/POST /projects` · `GET/PATCH/DELETE /projects/:id` · `GET /projects/:id/board` · `GET /projects/:id/activity` |
| Members | `GET/POST /projects/:id/members` · `PATCH/DELETE /projects/:id/members/:userId` |
| Workflow | `GET /projects/:id/workflow` · `POST /projects/:id/states` · `PATCH/DELETE /projects/:id/states/:stateId` · `PUT /projects/:id/transitions` |
| Issues | `GET/POST /issues` · `GET/PATCH/DELETE /issues/:id` · `GET /issues/:id/activity` · `GET/POST /issues/:id/comments` · `DELETE /issues/:id/comments/:commentId` |
| Sprints | `GET/POST /projects/:id/sprints` · `PATCH/DELETE /sprints/:id` · `POST /sprints/:id/start` · `POST /sprints/:id/complete` · `POST /sprints/:id/issues` |
| Files | `GET/POST /projects/:id/files` · `GET/POST /issues/:id/attachments` · `GET/DELETE /attachments/:id` |
| Analytics | `GET /projects/:id/analytics` · `GET /projects/:id/burndown` · `GET /projects/:id/velocity` |
| Other | `GET /users` · `GET /notifications` · `PATCH /notifications/:id/read` · `POST /notifications/read-all` · `GET /health` |

## Permissions

Access is **per project**. The global `User.role` is only shown in the UI. It
grants nothing, so whoever runs the server is not automatically an admin of
anyone's project.

A project's lead is its admin. Everyone else gets the role they were added
with. Non-members get a `404` rather than a `403`, so they can't even confirm
the project exists.

| Action | admin | manager | developer |
| --- | --- | --- | --- |
| View project, board, analytics, files | yes | yes | yes |
| Create issues, comment, upload files | yes | yes | yes |
| Edit or move an issue | any | any | ones they are assigned to or reported |
| Reassign or delete issues | yes | yes | no |
| Delete others' comments or attachments | yes | yes | no |
| Edit project, manage members, workflow and sprints | yes | yes | no |
| Delete the project | yes | no | no |

The frontend hides actions you can't take, but every rule is checked again on
the server. A hidden button is a convenience, not security.

## Design notes

- **One source of board state.** `useBoard` loads the board, applies moves
  optimistically and computes the counts from the same data, so the counts
  can't drift from the columns.
- **Live updates are an extra.** Every change is written and broadcast by the
  HTTP route; the socket only carries the news. If it drops, the app still
  works. Requests carry `X-Socket-Id` so the sender is skipped on broadcast,
  which keeps the mover's own card from jumping.
- **Activity is broadcast after commit.** Activity rows are sent to the room
  only once their transaction commits, so the feed never shows a rolled-back
  change. A client that reconnects reloads the stored history.
- **`overdue` is never stored.** It is computed from the due date and state on
  every read, so it can't go out of date.

## Tests

```powershell
npm test
```

136 test functions covering auth and JWT, password reset, permissions, projects,
workflow and transitions, issues, sprints, attachments, pagination, the
activity feed and Socket.IO. No running server is needed.

## Team

Built and maintained by Aditya Kundu.
