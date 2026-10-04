import React, { useCallback, useEffect, useMemo, useState } from 'react'

import { api, errorMessage } from '../api/client.js'
import Empty from '../components/Empty.jsx'
import IssueDrawer from '../components/IssueDrawer.jsx'
import Topbar from '../components/Topbar.jsx'
import { PriorityMark, TypeMark } from '../components/issueMeta.jsx'
import { useNotifications } from '../state/useNotifications.js'

const GROUPS = [
  { id: 'in_progress', label: 'In progress' },
  { id: 'todo', label: 'To do' },
  { id: 'done', label: 'Done' },
]

export default function MyTasks() {
  const [issues, setIssues] = useState([])
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState('')
  const [openId, setOpenId] = useState(null)
  const { notifications, unread, markAllRead, markRead } = useNotifications()

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/issues', { params: { assigneeId: 'me' } })
      setIssues(data.issues)
      setStatus('ready')
    } catch (err) {
      setError(errorMessage(err, 'Could not load your issues.'))
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const grouped = useMemo(() => {
    const buckets = Object.fromEntries(GROUPS.map((g) => [g.id, []]))
    for (const issue of issues) {
      const key = issue.stateCategory ?? 'todo'
      if (buckets[key]) buckets[key].push(issue)
    }
    // Overdue first, then by due date, then by priority order on the card.
    for (const list of Object.values(buckets)) {
      list.sort((a, b) => {
        if (a.overdue !== b.overdue) return a.overdue ? -1 : 1
        if (a.dueDate && b.dueDate) return a.dueDate.localeCompare(b.dueDate)
        if (a.dueDate) return -1
        if (b.dueDate) return 1
        return 0
      })
    }
    return buckets
  }, [issues])

  const overdue = issues.filter((i) => i.overdue).length

  return (
    <>
      <Topbar
        title="My tasks"
        subtitle={`${issues.length} assigned to you${overdue ? ` · ${overdue} overdue` : ''}`}
      />

      <div className="app-content">
        {error && (
          <div className="banner banner--error" role="alert">
            <span>{error}</span>
            <button type="button" className="banner-action" onClick={load}>
              Retry
            </button>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(280px, 1fr)', gap: 16, alignItems: 'start' }}>
          <div className="stack">
            {status === 'ready' && issues.length === 0 && (
              <div className="panel">
                <Empty mark="☑" title="Nothing assigned to you">
                  When someone assigns you an issue it shows up here, sorted so anything overdue
                  is at the top.
                </Empty>
              </div>
            )}

            {GROUPS.map((group) =>
              grouped[group.id].length === 0 ? null : (
                <section className="panel" key={group.id}>
                  <div className="panel-head">
                    <span className={`column-dot dot-${group.id}`} aria-hidden="true" />
                    <h2 className="panel-title">{group.label}</h2>
                    <span className="column-count panel-action">{grouped[group.id].length}</span>
                  </div>

                  {grouped[group.id].map((issue) => (
                    <button
                      type="button"
                      className="list-row"
                      key={issue.id}
                      onClick={() => setOpenId(issue.id)}
                    >
                      <TypeMark type={issue.type} />
                      <span className="issue-key">{issue.key}</span>
                      <div className="list-main">
                        <div className="list-title">{issue.title}</div>
                        <div className="list-sub">{issue.stateName}</div>
                      </div>
                      {issue.overdue && <span className="flag-overdue">Overdue</span>}
                      {issue.dueDate && !issue.overdue && (
                        <span className="muted" style={{ fontSize: 12 }}>
                          {new Date(issue.dueDate).toLocaleDateString(undefined, {
                            month: 'short',
                            day: 'numeric',
                          })}
                        </span>
                      )}
                      <PriorityMark priority={issue.priority} />
                      {issue.storyPoints != null && (
                        <span className="points-pill">{issue.storyPoints}</span>
                      )}
                    </button>
                  ))}
                </section>
              )
            )}
          </div>

          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Notifications</h2>
              {unread > 0 && (
                <button type="button" className="btn btn-ghost btn-sm panel-action" onClick={markAllRead}>
                  Mark all read
                </button>
              )}
            </div>

            {notifications.length === 0 ? (
              <Empty mark="◔" title="All quiet">
                You will hear about assignments, comments and completed work here.
              </Empty>
            ) : (
              notifications.map((item) => (
                <button
                  type="button"
                  className="list-row"
                  key={item.id}
                  onClick={() => {
                    if (!item.read) markRead(item.id)
                    if (item.issueId) setOpenId(item.issueId)
                  }}
                  style={{ opacity: item.read ? 0.6 : 1 }}
                >
                  <span className={`column-dot dot-${item.read ? 'todo' : 'in_progress'}`} aria-hidden="true" />
                  <div className="list-main">
                    <div style={{ fontSize: 13, lineHeight: 1.45 }}>{item.text}</div>
                    <div className="list-sub">{item.time}</div>
                  </div>
                </button>
              ))
            )}
          </section>
        </div>
      </div>

      {openId && (
        <IssueDrawer
          issueId={openId}
          states={[]}
          members={[]}
          onClose={() => setOpenId(null)}
          onChanged={load}
          onDeleted={load}
        />
      )}
    </>
  )
}
