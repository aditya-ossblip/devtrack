# DevTrack vs Jira — a feature-by-feature comparison

Prepared for the DevTrack team · September 2026
Compared against Jira Software Cloud as of the 2026 Summer Release.

---

## How to read this

Jira is a twenty-year-old product with a full-time staff and a 3,000-app marketplace.
DevTrack is a four-person college project written in one term. A list of everything
Jira has and DevTrack doesn't would be long, true, and useless.

So each row below gets one of four verdicts:

| Verdict | Meaning |
|---|---|
| **Match** | DevTrack does the same job. It may look different; the outcome is the same. |
| **Simplified** | DevTrack does the useful 80% and drops the configuration around it. Usually on purpose. |
| **Missing** | A real gap. The "cost" column says roughly what closing it would take. |
| **Not applicable** | Only matters at a scale DevTrack does not target (enterprise admin, billing, compliance). |

The honest summary is at the bottom. Read that first if you're short on time.

---

## 1. Work items

| Feature | Jira | DevTrack | Verdict |
|---|---|---|---|
| Issue types | Epic, Story, Task, Bug, Sub-task, plus custom types per project | Epic, Story, Task, Bug, Sub-task — fixed list | **Simplified** |
| Issue key | `PROJ-123`, auto-incrementing per project | `DEV-14`, same scheme, key derived from project name | **Match** |
| Title, description | Rich text (ADF) with @mentions, tables, code blocks, images | Plain text, click-to-edit | **Simplified** |
| Priority | 5 levels, configurable | 5 levels: Lowest → Highest, fixed | **Match** |
| Story points | Yes, estimation field | Yes, 0–100 | **Match** |
| Labels | Yes, free-text, autocompleted | Yes, comma-separated | **Match** |
| Due dates | Yes, plus start dates | Due date, with derived `overdue` | **Simplified** |
| Assignee | One assignee, plus a Reporter | One assignee, plus a Reporter | **Match** |
| Epic link | Issues roll up to an epic | Issues roll up to an epic, progress bar on the Backlog | **Match** |
| Sub-task hierarchy | Real parent/child with its own rollup | Sub-task is a *type*, but there is no parent link between issues | **Missing** — 1 column + UI, ~half a day |
| Custom fields | Unlimited, 20+ field types, per-project schemes | None | **Missing** — large; needs a schema-in-a-schema |
| Issue links | "blocks", "relates to", "duplicates", etc. | None | **Missing** — 1 join table, ~a day |
| Attachments | Yes, with preview | **Yes** — allowlisted extensions, 8 MB cap, generated filenames | **Match** |
| Comments | Rich text, @mentions, reactions, internal comments | Plain text, delete your own | **Simplified** |
| Watchers / voting | Yes | No | **Missing** — small, low value at 4 people |
| Work logging / time tracking | Yes, with estimates vs actuals | No | **Missing** — medium |

## 2. Boards

| Feature | Jira | DevTrack | Verdict |
|---|---|---|---|
| Kanban board | Yes | Yes, drag and drop | **Match** |
| Configurable columns | Yes, per board | Yes, add/rename/reorder/delete in Settings | **Match** |
| Column → status category | To Do / In Progress / Done, drives reports | Same three categories, drives every report | **Match** |
| WIP limits | Yes, per column | Yes, per column, enforced server-side | **Match** |
| Swimlanes | By assignee, epic, priority, query | No | **Missing** — presentational, ~a day |
| Card customisation | Choose which fields show on a card | Fixed card layout | **Simplified** |
| Quick filters | Saved JQL chips above the board | Filters exist on the API; the board does not expose them | **Missing** — the backend is already there |
| Board per team | Multiple boards over one project | One board per project | **Simplified** |
| Backlog view | Separate backlog with sprint sections | Same shape: sprint sections above, backlog below | **Match** |
| Drag from backlog to sprint | Yes, drag | Tick issues, then send to a sprint | **Simplified** |

## 3. Workflow

| Feature | Jira | DevTrack | Verdict |
|---|---|---|---|
| Custom statuses | Yes | Yes | **Match** |
| Transition rules | Yes, a directed graph per workflow | **Yes** — a from/to matrix in Settings, enforced on the server | **Match** |
| Transition conditions | "only the assignee", "only if a field is set" | No — transitions are allowed or not, full stop | **Simplified** |
| Transition validators / post-functions | Yes, scriptable | No | **Missing** — this is where Jira gets genuinely deep |
| Workflow schemes shared across projects | Yes | Each project owns its workflow | **Simplified** |
| Resolution field | Separate from status | Status category *is* the resolution | **Simplified** — deliberate; see note below |

> **Note on "Done".** Jira separates *status* from *resolution*, which is why a Jira
> issue can sit in a Done column and still be unresolved. DevTrack collapses the two:
> a column's **category** decides whether work in it counts as finished, so renaming
> "Done" to "Shipped" changes nothing about the reports. Fewer concepts, one fewer
> way to be wrong.

## 4. Sprints

| Feature | Jira | DevTrack | Verdict |
|---|---|---|---|
| Create, name, goal, dates | Yes | Yes | **Match** |
| Start / complete a sprint | Yes | Yes | **Match** |
| Incomplete work carries over | Yes, prompts where to send it | Yes, returns to backlog, counted in the log | **Match** |
| Edit / delete a sprint | Yes | **Yes** (active sprints must be completed first) | **Match** |
| Multiple parallel sprints | Premium feature | One active sprint per project | **Simplified** |
| Sprint reports | Burndown, velocity, sprint report | Burndown and velocity | **Simplified** |
| Capacity planning | Premium/Enterprise, added Summer 2026 | No | **Not applicable** |

## 5. Search and filtering

| Feature | Jira | DevTrack | Verdict |
|---|---|---|---|
| Query language | JQL — a real query language with functions and saved filters | `GET /api/issues?projectId=&assigneeId=me&type=&priority=&category=&sprintId=backlog&epicId=&q=` | **Simplified** |
| Natural-language search | Yes (Rovo) | No | **Not applicable** |
| Text search | Full-text across everything | `q=` substring match on title | **Simplified** |
| Saved filters / dashboards | Yes, shareable | No | **Missing** — medium |
| "My work" view | Yes | **Yes** — the My tasks page | **Match** |

## 6. Reporting

| Feature | Jira | DevTrack | Verdict |
|---|---|---|---|
| Burndown | Yes | Yes, ideal vs actual | **Match** |
| Velocity | Yes | Yes, committed vs completed per sprint | **Match** |
| Work breakdown by status / type / priority / assignee | Yes | Yes, all four | **Match** |
| Completed per day | Yes (control chart, cumulative flow) | **Yes** — read from the activity log, so it counts *transitions* | **Match** |
| Cumulative flow diagram | Yes | No | **Missing** — the log now has the data; it's a rendering job |
| Cycle time / lead time | Yes | No — but every transition is timestamped, so it is derivable | **Missing** — ~a day on top of the log |
| Custom dashboards with gadgets | Yes | Fixed Analytics page | **Simplified** |

## 7. Collaboration and history

| Feature | Jira | DevTrack | Verdict |
|---|---|---|---|
| Activity / history on an issue | Yes | **Yes** — every field change, move, comment and attachment | **Match** |
| Project-wide activity stream | Yes | **Yes** — on Analytics, filterable by verb, actor and issue | **Match** |
| Notifications in-app | Yes | Yes, on assignment | **Simplified** |
| Email notifications | Yes, configurable schemes | No mail server at all | **Missing** — needs SMTP, not code |
| @mentions | Yes | No | **Missing** — small |
| Real-time collaborative updates | Yes | **Yes** — Socket.IO, and the sender is skipped on broadcast | **Match** |

## 8. Permissions and administration

| Feature | Jira | DevTrack | Verdict |
|---|---|---|---|
| Roles | Configurable project roles + global permission schemes | Three: Developer, Manager, Admin | **Simplified** |
| Per-project role | Yes | Yes, set per member | **Match** |
| Who can edit an issue | Fully configurable | Managers and leads edit anything; developers edit issues they report or are assigned | **Simplified** |
| Who can reassign | Configurable | Managers and leads only — including on your own issue | **Simplified** |
| Permissions enforced server-side | Yes | Yes, on every route, with tests | **Match** |
| Project visibility | Public / private / restricted | Members only. Non-membership returns **404, not 403** | **Match** |
| Delete a project | Yes | **Yes** — admin only, type-the-name confirmation | **Match** |
| Audit log | Yes, Premium | The activity log covers project events | **Simplified** |
| SSO / SAML / SCIM | Yes | No | **Not applicable** |
| Data residency, compliance | Yes | No | **Not applicable** |

## 9. Accounts

| Feature | Jira | DevTrack | Verdict |
|---|---|---|---|
| Sign up | Yes | Yes | **Match** |
| Sign in | Yes | Yes, JWT | **Match** |
| Edit your own profile | Yes | **Yes** — name, job title, password | **Match** |
| Forgotten password | Yes, emailed link | **Yes** — single-use, hashed, 1-hour token. Returned in the response in debug because there is no mail server | **Simplified** |
| Avatars | Uploaded images | Generated initials | **Simplified** |
| 2FA | Yes | No | **Missing** — meaningful for a real deployment |

## 10. Platform

| Feature | Jira | DevTrack | Verdict |
|---|---|---|---|
| REST API | Huge, versioned, documented | ~50 endpoints, consistent shapes | **Simplified** |
| Webhooks | Yes | No | **Missing** — small |
| Automation rules | Yes, no-code, and natural-language since 2026 | No | **Missing** — large |
| Marketplace / apps | 3,000+ | No | **Not applicable** |
| Git integration | Branch/commit/PR linked to issues | No | **Missing** — medium, and the obvious next feature |
| Mobile app | Yes | Responsive web only | **Simplified** |
| Import / export | CSV, JSON, other trackers | No | **Missing** — small |
| Pagination on list endpoints | Yes | **Yes** — `page` / `perPage`, with `total` and `hasMore` | **Match** |

---

## UI: how the two actually differ

This is the part most visible in a demo, so it's worth separating from features.

**What is the same shape.** Both put a persistent left sidebar against a content
area, with a top bar that carries the page title, search and a create button.
Both use a column board with draggable cards, a backlog as a vertical list with
sprint sections above it, and a detail panel rather than a separate page for an
issue. Anyone who has used Jira can drive DevTrack without being told where things
are — that was the point.

**Where DevTrack is deliberately different.**

- **Three colours, not a palette.** DevTrack is black, white and Lime 400, with red
  reserved for exactly two things: destructive actions and overdue work. Jira carries
  a full blue-based colour system with separate hues for statuses, priorities, issue
  types and labels. In DevTrack those are encoded by *lightness* instead — priority
  reads as weight, workflow category as grey → white → lime. The result is quieter
  and much stricter; the cost is that a chart cannot lean on hue, which is why every
  chart carries a legend and direct value labels.
- **Dark only.** Lime on white measures 1.5:1 contrast. Rather than ship a broken
  light mode, there isn't one. Jira offers light, dark and system.
- **One board per project.** Jira's project sidebar lists boards, backlogs,
  timelines, reports, forms, pages and shortcuts. DevTrack's sidebar lists seven
  fixed destinations. Less to learn; nothing to configure.
- **No modal for the issue.** Both use a side drawer. DevTrack's saves on blur with
  no Save button; Jira's has explicit confirm on some fields and auto-save on others.
- **The sidebar is animated metal.** A liquid-mercury gradient, transform-only so it
  costs nothing. Jira's is flat. This is pure personality, and worth defending as such.

**Where Jira is better and it should be admitted.** Jira's board is denser and
survives 300 issues on screen; DevTrack has not been tested at that size. Jira's
inline editing reaches more fields. Jira's empty states teach the product; DevTrack's
mostly just say the list is empty. And Jira's typography scale has been tuned over
many years — DevTrack's IBM Plex setup is good but it is a first draft.

---

## The honest summary

**DevTrack covers the core of Jira's agile workflow.** Projects, members and roles;
a configurable board with real workflow restrictions and WIP limits; a backlog and
sprints with start/complete and carry-over; issues with types, priorities, points,
labels, epics, due dates, comments, attachments and a full change history; four
reports; live updates; and permissions enforced on the server rather than hidden in
the UI. That is a genuinely working project management tool, not a mock-up.

**The three real gaps, in the order they'd hurt:**

1. **Custom fields.** This is the single biggest structural difference. Jira's whole
   business is that every team can shape an issue to their process. DevTrack's issue
   shape is fixed in `models.py`. Closing this properly means a schema-in-a-schema and
   is easily the largest remaining feature.
2. **Issue links and true sub-task parenting.** Cheap to add — one join table each —
   and both are things people notice missing within an hour of real use.
3. **Automation.** Jira's "when X then Y" rules are why large teams stay. This is a
   large feature and a reasonable one to declare out of scope.

**Three things DevTrack does that are defensible as better, not just smaller:**

- **Status category, not resolution.** One concept where Jira has two, and no way to
  land in a Done column while being unresolved.
- **404 on non-membership, not 403.** Whether a project exists is itself information.
  Jira leaks this in places.
- **The activity log is the source of truth for reports.** The completed-per-day
  figure counts recorded transitions, not `updated_at`, so renaming a finished issue
  does not count as finishing it twice. Jira gets this right too — but plenty of
  trackers don't, and it's worth pointing out that DevTrack does it on purpose.

**What to say if someone asks "why not just use Jira?"** Because Jira's power is its
configurability, and configurability is a cost you pay every day whether you use it
or not. DevTrack is the opinionated version: one board, one workflow, three roles,
three colours. For a team of four, that is not a compromise — it's the design.

---

## Sources

- [Jira Software — Features (Atlassian)](https://www.atlassian.com/software/jira/features)
- [Introducing the Jira 2026 Summer Release (Atlassian Community)](https://community.atlassian.com/forums/Jira-articles/Introducing-the-Jira-2026-Summer-Release-%EF%B8%8F/ba-p/3268349)
- [Jira Backlog Software (Atlassian)](https://www.atlassian.com/software/jira/features/backlog-software)
- [Introducing Atlassian's new navigation (Atlassian Blog)](https://www.atlassian.com/blog/announcements/introducing-new-navigation)
- [Jira Issue Types: A Complete Guide for 2026 (Atlassian Community)](https://community.atlassian.com/forums/App-Central-articles/Jira-Issue-Types-A-Complete-Guide-for-2026/ba-p/2928042)
- [Enhanced Jira Software backlog and board (Atlassian Community)](https://community.atlassian.com/forums/Jira-articles/Enhanced-Jira-board-and-backlog/ba-p/2331946)

DevTrack figures in this document were read from the source at
`backend/app/` and `src/`, not from memory.
