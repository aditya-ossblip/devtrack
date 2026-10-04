# DevTrack — Phase 2: backend wiring plan

> **Status: implemented.** This document was the plan; the code in `backend/`
> and `src/` now follows it. Kept as the API reference — if you change an
> endpoint, change it here too. See SETUP.md to run it.

Frontend is React 18 + Vite 8 (`devtrack-frontend`). Backend is Flask +
SQLAlchemy + MySQL, JWT auth, Flask-SocketIO for live updates. This document is
the contract between the two — build the API to match and the frontend changes
stay inside four files.

---

## 1. Data model

Four tables, mirroring the shapes already in `src/data/mockData.js`.

| Table | Columns |
| --- | --- |
| `users` | `id` PK, `name`, `email` UNIQUE, `password_hash`, `role` (`admin` \| `manager` \| `developer`), `title`, `created_at` |
| `projects` | `id` PK, `name`, `description`, `owner_id` FK→users, `created_at` |
| `project_members` | `project_id` FK, `user_id` FK, `role`, PK(`project_id`,`user_id`) |
| `tasks` | `id` PK, `project_id` FK, `title`, `description`, `status` (`todo` \| `progress` \| `done`), `tag` (`UI` \| `DB` \| `Backend` \| `Frontend`), `assignee_id` FK→users NULL, `due_date` DATE NULL, `position` INT, `created_at`, `updated_at` |
| `notifications` | `id` PK, `user_id` FK, `type` (`done` \| `deadline` \| `member` \| `overdue`), `text`, `read_at` NULL, `created_at` |

Notes that matter to the frontend:

- `status` uses the frontend's column ids exactly (`todo` / `progress` /
  `done`). Do not rename these — `DOT_CLASS`, `COLUMN_LABELS` and
  `moveTaskInColumns` all key off them.
- `position` is an integer ordering within a status. The board appends on drop,
  so a move is `status = :new_status, position = MAX(position)+1`.
- `overdue` is **not** stored. It is derived: `due_date < CURDATE() AND status
  != 'done'`. Serialize it as a boolean on the task so the card can render the
  flag without doing date math.

---

## 2. REST contract

Base path `/api`. All responses JSON. All routes except `/auth/login` and
`/auth/register` require `Authorization: Bearer <jwt>`.

### Auth

```
POST /api/auth/register   { name, email, password }        -> 201 { user }
POST /api/auth/login      { email, password }              -> 200 { token, user }
GET  /api/auth/me                                          -> 200 { user }
```

`token` is a JWT with `sub` = user id, `role` claim, 24h expiry.
Wrong credentials return `401 { "error": "Invalid email or password." }` —
`Login.jsx` shows `error` verbatim, so keep these human-readable.

### Users / team

```
GET  /api/users                     -> 200 { users: [ { id, name, initials, role, title } ] }
GET  /api/projects/:id/members      -> 200 { members: [...same shape...] }
```

`initials` is computed server-side (first letter of first + last name, upper).
`TeamPanel` and the avatars render it directly.

### Projects

```
GET  /api/projects                  -> 200 { projects: [ { id, name, description, taskCounts } ] }
POST /api/projects                  -> 201 { project }        (admin, manager)
GET  /api/projects/:id              -> 200 { project }
```

### Tasks — the one the board depends on

```
GET   /api/projects/:id/tasks       -> 200 { columns: [ { id, title, status, tasks: [task] } ] }
POST  /api/tasks                    -> 201 { task }
PATCH /api/tasks/:id                -> 200 { task }
DELETE /api/tasks/:id               -> 204
```

`GET .../tasks` returns the board **already grouped into columns**, in the exact
shape `useBoard` seeds its state with:

```json
{
  "columns": [
    { "id": "todo",     "title": "To do",       "status": "todo",
      "tasks": [ { "id": 101, "title": "Design login page UI", "tag": "UI",
                   "assignee": "DD", "assigneeId": 4, "status": "todo",
                   "dueDate": "2026-09-20", "overdue": false } ] },
    { "id": "progress", "title": "In progress", "status": "progress", "tasks": [] },
    { "id": "done",     "title": "Done",        "status": "done",     "tasks": [] }
  ]
}
```

Always return all three columns, even when empty — the board renders the
"Drop a task here" placeholder off `tasks.length === 0`.

`PATCH /api/tasks/:id` accepts a partial task; the board only ever sends
`{ "status": "done" }`.

### Notifications

```
GET   /api/notifications            -> 200 { notifications: [ { id, type, text, time } ] }
PATCH /api/notifications/:id/read   -> 204
```

`time` is a pre-formatted relative string ("10 mins ago") — that is what
`NotificationsPanel` prints. Send `createdAt` alongside it if the frontend
should ever reformat client-side.

---

## 3. Role-based access

| Action | admin | manager | developer |
| --- | --- | --- | --- |
| Create/delete project | yes | yes | no |
| Add/remove members | yes | yes | no |
| Create task | yes | yes | yes |
| Edit any task | yes | yes | assigned only |
| Move task status | yes | yes | assigned only |
| Delete task | yes | yes | no |

Enforce in a `@requires_role` decorator on the Flask side. The frontend should
*also* hide the actions a user cannot take, but the server is the boundary —
never trust the hidden button.

---

## 4. Socket.IO events

Namespace `/`, room per project (`project:<id>`). Client joins after auth.

| Event | Direction | Payload |
| --- | --- | --- |
| `join_project` | client → server | `{ projectId }` |
| `task:created` | server → client | `{ task }` |
| `task:moved` | server → client | `{ taskId, fromStatus, toStatus, position }` |
| `task:updated` | server → client | `{ task }` |
| `task:deleted` | server → client | `{ taskId }` |
| `notification:new` | server → client | `{ notification }` |

The mover's own socket should be excluded from the broadcast (`skip_sid`) —
they already applied the change optimistically, and re-applying it makes the
card jump.

---

## 5. Frontend changes, file by file

**`src/api/client.js`** (new)

```js
import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('devtrack.token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('devtrack.token')
      window.location.assign('/login')
    }
    return Promise.reject(error)
  }
)
```

**`vite.config.js`** — proxy the API in dev so there is no CORS setup:

```js
server: {
  port: 5173,
  proxy: { '/api': 'http://localhost:5000', '/socket.io': { target: 'http://localhost:5000', ws: true } }
}
```

**`src/state/useBoard.js`** — the only file where the board changes:

- `useEffect` on mount: `api.get('/projects/1/tasks')` → `setColumns(data.columns)`
- `moveTask`: keep the optimistic `moveTaskInColumns(prev, ...)`, then
  `api.patch(`/tasks/${taskId}`, { status })`; on rejection restore the
  snapshot taken before the update and surface an error.
- Subscribe to `task:*` events and apply them with the same pure helpers.
- `metrics` needs no change — it already derives from `columns`.

**`src/pages/Login.jsx`** — replace the `setTimeout` stand-in:

```js
const { data } = await api.post('/auth/login', { email, password })
localStorage.setItem('devtrack.token', data.token)
navigate('/')
```

The `catch` already renders `error.response?.data?.error` shaped messages.

**`src/App.jsx`** — replace `const isAuthenticated = true` with an
`AuthContext` that reads the stored token on mount, calls `GET /api/auth/me` to
validate it, and exposes `{ user, login, logout }`. Wrap protected routes in a
`<RequireAuth>` element rather than a bare ternary, so new routes inherit it.

**`src/data/mockData.js`** — delete once every panel reads from the API. Until
then keep it as the fallback for `npm run dev` without a backend running.

---

## 6. Suggested build order

1. Flask app factory, MySQL connection, models, Alembic migration.
2. `/auth/register` + `/auth/login` returning a real JWT → wire `Login.jsx`.
   This is the first end-to-end slice and proves the proxy and token storage.
3. `GET /projects/:id/tasks` → replace the mock seed in `useBoard`.
4. `PATCH /tasks/:id` → make drag-and-drop persist.
5. `/users`, `/notifications` → the two side panels.
6. Role decorator + tests for the permission table above.
7. Socket.IO last — it is an enhancement on a working REST app, not a
   prerequisite.

Each step leaves the app running, which matters if this is being demoed.
