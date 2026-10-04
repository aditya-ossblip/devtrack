import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client.js'
import Empty from '../components/Empty.jsx'
import FocusStrip from '../components/FocusStrip.jsx'
import IssueCard from '../components/IssueCard.jsx'
import IssueDrawer from '../components/IssueDrawer.jsx'
import LivePanel from '../components/LivePanel.jsx'
import NewIssueModal from '../components/NewIssueModal.jsx'
import Topbar from '../components/Topbar.jsx'
import { useAuth } from '../state/AuthContext.jsx'
import { useBoard } from '../state/useBoard.js'
import { pickFocus } from '../state/focus.js'
import { useMembers } from '../state/useMembers.js'
import { useProjects } from '../state/ProjectContext.jsx'
import ProjectEmpty from '../components/ProjectEmpty.jsx'
import '../styles/board-live.css'

const FOCUS_MODE_KEY = 'devtrack.focusMode'
const FRESH_MS = 2600

function readFocusMode() {
  try {
    return localStorage.getItem(FOCUS_MODE_KEY) === 'all' ? 'all' : 'me'
  } catch {
    return 'me'
  }
}

export default function Board() {
  const { project, projectId, status: projectStatus } = useProjects()
  const [sprintFilter, setSprintFilter] = useState('all')
  const [sprints, setSprints] = useState([])

  const { columns, moveIssue, applyIssue, dropIssue, stats, status, error, reload } = useBoard(
    projectId,
    { sprintId: sprintFilter === 'all' ? undefined : sprintFilter }
  )
  const { members } = useMembers(projectId)

  const [dragId, setDragId] = useState(null)
  const [dropTarget, setDropTarget] = useState(null)
  const [openIssueId, setOpenIssueId] = useState(null)
  const [composing, setComposing] = useState(null)

  const { user } = useAuth()
  const [focusMode, setFocusMode] = useState(readFocusMode)
  const [fresh, setFresh] = useState(() => new Set())
  const freshTimers = useRef([])

  const allIssues = useMemo(() => columns.flatMap((col) => col.issues), [columns])
  const focus = useMemo(() => pickFocus(allIssues, user?.id), [allIssues, user?.id])
  const myIssueIds = useMemo(
    () => new Set(allIssues.filter((issue) => issue.assigneeId === user?.id).map((issue) => issue.id)),
    [allIssues, user?.id]
  )

  function chooseFocusMode(mode) {
    setFocusMode(mode)
    try {
      localStorage.setItem(FOCUS_MODE_KEY, mode)
    } catch {
      /* private window or blocked storage: the choice just won't be remembered */
    }
  }

  // A card someone just changed glows for a moment.
  const markFresh = useCallback((entry) => {
    const id = entry?.issueId
    if (!id) return
    setFresh((current) => new Set(current).add(id))
    freshTimers.current.push(
      setTimeout(() => {
        setFresh((current) => {
          const next = new Set(current)
          next.delete(id)
          return next
        })
      }, FRESH_MS)
    )
  }, [])

  useEffect(() => () => freshTimers.current.forEach(clearTimeout), [])

  useEffect(() => {
    if (!projectId) return
    api
      .get(`/projects/${projectId}/sprints`)
      .then(({ data }) => setSprints(data.sprints))
      .catch(() => setSprints([]))
  }, [projectId])

  if (projectStatus === 'empty') return <ProjectEmpty />

  const states = columns.map((col) => ({ id: col.id, name: col.name, category: col.category }))
  const activeSprint = sprints.find((s) => s.state === 'active')

  function handleDrop(e, stateId) {
    e.preventDefault()
    // Prefer the id carried on the event: it survives cases where React state
    // was never set (a drag started in another window, or a re-render).
    const carried = Number(e.dataTransfer.getData('text/plain'))
    const issueId = Number.isFinite(carried) && carried > 0 ? carried : dragId
    if (issueId) moveIssue(issueId, stateId)
    setDragId(null)
    setDropTarget(null)
  }

  return (
    <>
      <Topbar title={project?.name ?? 'Board'} subtitle={project?.key} members={members}>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setComposing({ stateId: columns[0]?.id })}
          disabled={!columns.length}
        >
          + New issue
        </button>
      </Topbar>

      <div className="board-shell">
        <div className="app-content">
          <FocusStrip
            picks={focus.picks}
            remaining={focus.remaining}
            mode={focusMode}
            onMode={chooseFocusMode}
            othersDimmed={allIssues.length - myIssueIds.size}
            onOpen={(issue) => setOpenIssueId(issue.id)}
            firstName={user?.name?.split(' ')[0]}
          />

          {error && (
            <div className="banner banner--error" role="alert">
              <span>{error}</span>
              <button type="button" className="banner-action" onClick={reload}>
                Retry
              </button>
            </div>
          )}

          <div className="stat-row">
            <Stat label="Issues" value={stats.total} note={`${stats.notStarted} not started`} />
            <Stat
              label="In progress"
              value={stats.inProgress}
              note={stats.overdue ? `${stats.overdue} overdue` : 'On track'}
              tone={stats.overdue ? 'danger' : 'neutral'}
            />
            <Stat label="Done" value={stats.done} note={`${stats.donePct}% complete`} tone="positive" pct={stats.donePct} />
            <Stat
              label="Story points"
              value={stats.points}
              note={`${stats.pointsDone} delivered`}
              tone="neutral"
            />
          </div>

          <div className="board-toolbar">
            <label className="row" style={{ gap: 8 }}>
              <span className="muted" style={{ fontSize: 12.5 }}>Showing</span>
              <select
                className="select"
                style={{ width: 'auto' }}
                value={sprintFilter}
                onChange={(e) => setSprintFilter(e.target.value)}
                aria-label="Filter by sprint"
              >
                <option value="all">All issues</option>
                {activeSprint && <option value="active">Active sprint · {activeSprint.name}</option>}
                {sprints
                  .filter((s) => s.state !== 'active')
                  .map((sprint) => (
                    <option key={sprint.id} value={sprint.id}>
                      {sprint.name}
                    </option>
                  ))}
              </select>
            </label>
            {activeSprint && sprintFilter === 'active' && activeSprint.goal && (
              <span className="muted" style={{ fontSize: 12.5 }}>Goal: {activeSprint.goal}</span>
            )}
          </div>

          {status === 'loading' && columns.length === 0 ? (
            <div className="app-loading" style={{ minHeight: 240 }}>
              <div className="spinner" />
            </div>
          ) : (
            <div className="board">
              {columns.map((col) => {
                const overLimit = col.wipLimit && col.issues.length > col.wipLimit
                return (
                  <section
                    key={col.id}
                    className={`column${dropTarget === col.id ? ' is-drop-target' : ''}${overLimit ? ' is-over-limit' : ''}`}
                    onDragOver={(e) => {
                      e.preventDefault()
                      e.dataTransfer.dropEffect = 'move'
                      if (dropTarget !== col.id) setDropTarget(col.id)
                    }}
                    onDragLeave={() => setDropTarget((c) => (c === col.id ? null : c))}
                    onDrop={(e) => handleDrop(e, col.id)}
                    aria-label={col.name}
                  >
                    <header className="column-head">
                      <span className={`column-dot dot-${col.category}`} aria-hidden="true" />
                      <span className="column-name">{col.name}</span>
                      <span className="column-count">{col.issues.length}</span>
                      {col.wipLimit && <span className="column-limit">/ {col.wipLimit}</span>}
                    </header>

                    <div className="column-body">
                      {col.issues.map((issue) => (
                        <IssueCard
                          key={issue.id}
                          issue={issue}
                          isDragging={dragId === issue.id}
                          dimmed={focusMode === 'me' && issue.assigneeId !== user?.id}
                          fresh={fresh.has(issue.id)}
                          onDragStart={(e, item) => {
                            setDragId(item.id)
                            e.dataTransfer.effectAllowed = 'move'
                            e.dataTransfer.setData('text/plain', String(item.id))
                          }}
                          onDragEnd={() => {
                            setDragId(null)
                            setDropTarget(null)
                          }}
                          onOpen={(item) => setOpenIssueId(item.id)}
                        />
                      ))}

                      {col.issues.length === 0 && <div className="column-empty">Drop an issue here</div>}
                    </div>

                    <button
                      type="button"
                      className="column-add"
                      onClick={() => setComposing({ stateId: col.id })}
                    >
                      + Add issue
                    </button>
                  </section>
                )
              })}

              {columns.length === 0 && status === 'ready' && (
                <Empty mark="▦" title="This board has no columns">
                  Add one in project settings and the board appears here.
                </Empty>
              )}
            </div>
          )}
        </div>

        <LivePanel
          projectId={projectId}
          userId={user?.id}
          members={members}
          myIssueIds={myIssueIds}
          onActivity={markFresh}
        />
      </div>

      {composing && (
        <NewIssueModal
          projectId={projectId}
          states={states}
          members={members}
          defaultStateId={composing.stateId}
          sprintId={sprintFilter === 'active' ? activeSprint?.id : undefined}
          onClose={() => setComposing(null)}
          onCreated={applyIssue}
        />
      )}

      {openIssueId && (
        <IssueDrawer
          issueId={openIssueId}
          states={states}
          members={members}
          onClose={() => setOpenIssueId(null)}
          onChanged={applyIssue}
          onDeleted={dropIssue}
        />
      )}
    </>
  )
}

function Stat({ label, value, note, tone = 'neutral', pct }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className={`stat-note stat-note--${tone}`}>{note}</div>
      {pct != null && (
        <div className="stat-bar">
          <span style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  )
}
