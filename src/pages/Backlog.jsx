import React, { useCallback, useEffect, useState } from 'react'

import { api, errorMessage } from '../api/client.js'
import Empty from '../components/Empty.jsx'
import IssueDrawer from '../components/IssueDrawer.jsx'
import Modal from '../components/Modal.jsx'
import NewIssueModal from '../components/NewIssueModal.jsx'
import ProjectEmpty from '../components/ProjectEmpty.jsx'
import Topbar from '../components/Topbar.jsx'
import { PriorityMark, TypeMark } from '../components/issueMeta.jsx'
import { useMembers } from '../state/useMembers.js'
import { useProjects } from '../state/ProjectContext.jsx'

export default function Backlog() {
  const { project, projectId, status: projectStatus } = useProjects()
  const { members } = useMembers(projectId)

  const [sprints, setSprints] = useState([])
  const [issues, setIssues] = useState([])
  const [states, setStates] = useState([])
  const [error, setError] = useState('')
  const [openId, setOpenId] = useState(null)
  const [composing, setComposing] = useState(false)
  const [planning, setPlanning] = useState(null)
  const [selected, setSelected] = useState(() => new Set())

  const load = useCallback(async () => {
    if (!projectId) return
    try {
      const [sprintRes, issueRes, projectRes] = await Promise.all([
        api.get(`/projects/${projectId}/sprints`),
        api.get('/issues', { params: { projectId } }),
        api.get(`/projects/${projectId}`),
      ])
      setSprints(sprintRes.data.sprints)
      setIssues(issueRes.data.issues)
      setStates(projectRes.data.states)
      setError('')
    } catch (err) {
      setError(errorMessage(err, 'Could not load the backlog.'))
    }
  }, [projectId])

  useEffect(() => {
    load()
  }, [load])

  if (projectStatus === 'empty') return <ProjectEmpty />

  const backlog = issues.filter((issue) => !issue.sprintId && issue.type !== 'epic')
  const epics = issues.filter((issue) => issue.type === 'epic')

  function toggle(id) {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function moveToSprint(sprintId) {
    try {
      await api.post(`/sprints/${sprintId}/issues`, { issueIds: [...selected] })
      setSelected(new Set())
      load()
    } catch (err) {
      setError(errorMessage(err, 'Could not move those issues.'))
    }
  }

  async function sprintAction(sprint, action) {
    try {
      await api.post(`/sprints/${sprint.id}/${action}`)
      load()
    } catch (err) {
      setError(errorMessage(err, `Could not ${action} the sprint.`))
    }
  }

  async function deleteSprint(sprint) {
    // Say what happens to the work, not just to the sprint. Deleting a sprint
    // returns its issues to the backlog rather than destroying them, and
    // people hesitate over this button because they assume otherwise.
    const count = issues.filter((issue) => issue.sprintId === sprint.id).length
    const warning = count
      ? `Delete ${sprint.name}? Its ${count} issue${count === 1 ? '' : 's'} go back to the backlog — nothing is lost.`
      : `Delete ${sprint.name}?`
    if (!window.confirm(warning)) return

    try {
      await api.delete(`/sprints/${sprint.id}`)
      load()
    } catch (err) {
      setError(errorMessage(err, 'Could not delete the sprint.'))
    }
  }

  return (
    <>
      <Topbar title="Backlog" subtitle={project?.name} members={members}>
        <button type="button" className="btn btn-secondary" onClick={() => setPlanning({})}>
          + New sprint
        </button>
        <button type="button" className="btn btn-primary" onClick={() => setComposing(true)}>
          + New issue
        </button>
      </Topbar>

      <div className="app-content">
        {error && (
          <div className="banner banner--error" role="alert">
            <span>{error}</span>
            <button type="button" className="banner-action" onClick={load}>
              Retry
            </button>
          </div>
        )}

        {selected.size > 0 && (
          <div className="banner banner--info">
            <span>
              {selected.size} issue{selected.size === 1 ? '' : 's'} selected
            </span>
            <div className="row panel-action">
              {sprints
                .filter((s) => s.state !== 'completed')
                .map((sprint) => (
                  <button
                    type="button"
                    className="banner-action"
                    key={sprint.id}
                    onClick={() => moveToSprint(sprint.id)}
                  >
                    → {sprint.name}
                  </button>
                ))}
              <button type="button" className="banner-action" onClick={() => setSelected(new Set())}>
                Clear
              </button>
            </div>
          </div>
        )}

        <div className="stack">
          {sprints
            .filter((sprint) => sprint.state !== 'completed')
            .map((sprint) => {
              const sprintIssues = issues.filter((issue) => issue.sprintId === sprint.id)
              return (
                <section className="panel" key={sprint.id}>
                  <div className="panel-head">
                    <h2 className="panel-title">{sprint.name}</h2>
                    <span className={`badge badge-${sprint.state === 'active' ? 'admin' : 'developer'}`}>
                      {sprint.state === 'active' ? 'Active' : 'Planned'}
                    </span>
                    <span className="muted" style={{ fontSize: 12 }}>
                      {sprintIssues.length} issues · {sprint.points} points
                    </span>
                    <div className="row panel-action">
                      {sprint.state === 'future' && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => sprintAction(sprint, 'start')}
                        >
                          Start sprint
                        </button>
                      )}
                      {sprint.state === 'active' && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => sprintAction(sprint, 'complete')}
                        >
                          Complete sprint
                        </button>
                      )}
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => setPlanning(sprint)}
                      >
                        Edit
                      </button>
                      {/* An active sprint has to be completed first — the
                          server refuses it, and offering the button anyway
                          would just produce an error people cannot act on. */}
                      {sprint.state !== 'active' && (
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm btn-ghost-danger"
                          onClick={() => deleteSprint(sprint)}
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </div>

                  {sprint.goal && (
                    <div className="panel-body" style={{ paddingBottom: 0 }}>
                      <span className="muted">Goal: {sprint.goal}</span>
                    </div>
                  )}

                  {sprintIssues.length === 0 ? (
                    <Empty mark="≡" title="Nothing planned in yet">
                      Tick issues in the backlog below, then send them here.
                    </Empty>
                  ) : (
                    sprintIssues.map((issue) => (
                      <IssueRow key={issue.id} issue={issue} onOpen={() => setOpenId(issue.id)} />
                    ))
                  )}
                </section>
              )
            })}

          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Backlog</h2>
              <span className="muted" style={{ fontSize: 12 }}>
                {backlog.length} issues
              </span>
            </div>

            {backlog.length === 0 ? (
              <Empty mark="≡" title="Backlog is empty">
                Everything is either in a sprint or done. Create an issue to add to the pile.
              </Empty>
            ) : (
              backlog.map((issue) => (
                <IssueRow
                  key={issue.id}
                  issue={issue}
                  selectable
                  checked={selected.has(issue.id)}
                  onToggle={() => toggle(issue.id)}
                  onOpen={() => setOpenId(issue.id)}
                />
              ))
            )}
          </section>

          {epics.length > 0 && (
            <section className="panel">
              <div className="panel-head">
                <h2 className="panel-title">Epics</h2>
              </div>
              {epics.map((epic) => {
                const children = issues.filter((issue) => issue.epicId === epic.id)
                const done = children.filter((issue) => issue.stateCategory === 'done').length
                return (
                  <button
                    type="button"
                    className="list-row"
                    key={epic.id}
                    onClick={() => setOpenId(epic.id)}
                  >
                    <TypeMark type="epic" />
                    <span className="issue-key">{epic.key}</span>
                    <div className="list-main">
                      <div className="list-title">{epic.title}</div>
                      <div className="list-sub">
                        {children.length} issues · {done} done
                      </div>
                    </div>
                    <div className="project-progress" style={{ width: 100, marginBottom: 0 }}>
                      <i
                        className="seg-done"
                        style={{ width: children.length ? `${(done / children.length) * 100}%` : '0%' }}
                      />
                      <i className="seg-todo" style={{ flex: 1 }} />
                    </div>
                  </button>
                )
              })}
            </section>
          )}
        </div>
      </div>

      {composing && (
        <NewIssueModal
          projectId={projectId}
          states={states}
          members={members}
          onClose={() => setComposing(false)}
          onCreated={load}
        />
      )}

      {planning && (
        <SprintModal
          projectId={projectId}
          sprint={planning.id ? planning : null}
          onClose={() => setPlanning(null)}
          onSaved={load}
        />
      )}

      {openId && (
        <IssueDrawer
          issueId={openId}
          states={states}
          members={members}
          onClose={() => setOpenId(null)}
          onChanged={load}
          onDeleted={load}
        />
      )}
    </>
  )
}

function IssueRow({ issue, selectable, checked, onToggle, onOpen }) {
  return (
    <div className="list-row">
      {selectable && (
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          aria-label={`Select ${issue.key}`}
        />
      )}
      <TypeMark type={issue.type} />
      <span className="issue-key">{issue.key}</span>
      <button type="button" className="list-main" style={{ textAlign: 'left' }} onClick={onOpen}>
        <div className="list-title">{issue.title}</div>
        <div className="list-sub">{issue.stateName}</div>
      </button>
      {issue.overdue && <span className="flag-overdue">Overdue</span>}
      <PriorityMark priority={issue.priority} />
      {issue.storyPoints != null && <span className="points-pill">{issue.storyPoints}</span>}
      {issue.assignee ? (
        <div className="avatar avatar-sm" title={issue.assigneeName}>
          {issue.assignee}
        </div>
      ) : (
        <div className="avatar avatar-sm avatar-empty">–</div>
      )}
    </div>
  )
}

/**
 * Plan a sprint, or change one that already exists.
 *
 * One form for both. The fields are identical and the only difference is which
 * request it sends, so splitting it would mean two copies of the same layout
 * drifting apart the first time a field is added.
 */
function SprintModal({ projectId, sprint, onClose, onSaved }) {
  const editing = Boolean(sprint)
  const [form, setForm] = useState({
    name: sprint?.name ?? '',
    goal: sprint?.goal ?? '',
    startDate: sprint?.startDate ?? '',
    endDate: sprint?.endDate ?? '',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const set = (key) => (e) => setForm((current) => ({ ...current, [key]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setSaving(true)
    const body = {
      name: form.name.trim(),
      goal: form.goal.trim(),
      startDate: form.startDate || null,
      endDate: form.endDate || null,
    }

    try {
      if (editing) {
        // PATCH treats a missing key as "leave it alone", so an empty name on
        // an edit would blank a sprint that already has one.
        if (!body.name) delete body.name
        await api.patch(`/sprints/${sprint.id}`, body)
      } else {
        await api.post(`/projects/${projectId}/sprints`, body)
      }
      await onSaved()
      onClose()
    } catch (err) {
      setError(errorMessage(err, `Could not ${editing ? 'save' : 'create'} the sprint.`))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title={editing ? `Edit ${sprint.name}` : 'New sprint'}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="new-sprint" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving…' : editing ? 'Save sprint' : 'Create sprint'}
          </button>
        </>
      }
    >
      <form id="new-sprint" onSubmit={submit}>
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}

        <div className="field">
          <label className="field-label" htmlFor="sprint-name">
            Name
          </label>
          <input
            id="sprint-name"
            className="input"
            autoFocus
            value={form.name}
            onChange={set('name')}
            placeholder={editing ? '' : 'Leave blank to number it automatically'}
          />
        </div>

        <div className="field">
          <label className="field-label" htmlFor="sprint-goal">
            Sprint goal
          </label>
          <textarea
            id="sprint-goal"
            className="textarea"
            value={form.goal}
            onChange={set('goal')}
            placeholder="One sentence on what this sprint is for."
          />
        </div>

        <div className="field-row">
          <div className="field">
            <label className="field-label" htmlFor="sprint-start">
              Starts
            </label>
            <input id="sprint-start" type="date" className="input" value={form.startDate} onChange={set('startDate')} />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="sprint-end">
              Ends
            </label>
            <input id="sprint-end" type="date" className="input" value={form.endDate} onChange={set('endDate')} />
          </div>
        </div>

        <div className="field-hint">
          Dates drive the burndown chart. You can start the sprint without them and fill them in later.
        </div>
      </form>
    </Modal>
  )
}
