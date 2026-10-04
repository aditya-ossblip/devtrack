import React, { useCallback, useEffect, useState } from 'react'

import { useNavigate } from 'react-router-dom'

import { api, errorMessage } from '../api/client.js'
import Modal from '../components/Modal.jsx'
import ProjectEmpty from '../components/ProjectEmpty.jsx'
import Topbar from '../components/Topbar.jsx'
import { useAuth } from '../state/AuthContext.jsx'
import { useProjects } from '../state/ProjectContext.jsx'

const CATEGORIES = [
  { id: 'todo', label: 'To do' },
  { id: 'in_progress', label: 'In progress' },
  { id: 'done', label: 'Done' },
]

export default function Settings() {
  const { project, projectId, status: projectStatus, reload } = useProjects()
  const navigate = useNavigate()
  const [states, setStates] = useState([])
  const [transitions, setTransitions] = useState([])
  const [restricted, setRestricted] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const [details, setDetails] = useState({ name: '', description: '' })
  const [newColumn, setNewColumn] = useState({ name: '', category: 'todo' })
  const [role, setRole] = useState('developer')
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const load = useCallback(async () => {
    if (!projectId) return
    try {
      const [projectRes, workflowRes] = await Promise.all([
        api.get(`/projects/${projectId}`),
        api.get(`/projects/${projectId}/workflow`),
      ])
      setStates(workflowRes.data.states)
      setTransitions(workflowRes.data.transitions)
      setRestricted(workflowRes.data.transitions.length > 0)
      setDetails({
        name: projectRes.data.project.name,
        description: projectRes.data.project.description,
      })
      setRole(projectRes.data.role)
      setError('')
    } catch (err) {
      setError(errorMessage(err, 'Could not load project settings.'))
    }
  }, [projectId])

  useEffect(() => {
    load()
  }, [load])

  function flash(message) {
    setSaved(message)
    setTimeout(() => setSaved(''), 2500)
  }

  async function saveDetails(e) {
    e.preventDefault()
    try {
      await api.patch(`/projects/${projectId}`, details)
      await reload()
      flash('Project details saved.')
    } catch (err) {
      setError(errorMessage(err, 'Could not save.'))
    }
  }

  async function addColumn(e) {
    e.preventDefault()
    if (!newColumn.name.trim()) return
    try {
      await api.post(`/projects/${projectId}/states`, newColumn)
      setNewColumn({ name: '', category: 'todo' })
      load()
    } catch (err) {
      setError(errorMessage(err, 'Could not add the column.'))
    }
  }

  async function patchColumn(stateId, changes) {
    try {
      await api.patch(`/projects/${projectId}/states/${stateId}`, changes)
      load()
    } catch (err) {
      setError(errorMessage(err, 'Could not update the column.'))
    }
  }

  async function deleteColumn(stateId) {
    try {
      await api.delete(`/projects/${projectId}/states/${stateId}`)
      load()
    } catch (err) {
      setError(errorMessage(err, 'Could not delete the column.'))
    }
  }

  function isAllowed(fromId, toId) {
    if (!restricted) return true
    return transitions.some((t) => t.fromStateId === fromId && t.toStateId === toId)
  }

  async function saveTransitions(pairs) {
    try {
      const { data } = await api.put(`/projects/${projectId}/transitions`, { transitions: pairs })
      setTransitions(data.transitions)
      flash('Workflow rules saved.')
    } catch (err) {
      setError(errorMessage(err, 'Could not save the workflow rules.'))
    }
  }

  function toggleTransition(fromId, toId) {
    const exists = isAllowed(fromId, toId)
    const pairs = exists
      ? transitions.filter((t) => !(t.fromStateId === fromId && t.toStateId === toId))
      : [...transitions, { fromStateId: fromId, toStateId: toId }]
    saveTransitions(pairs.map((t) => ({ fromStateId: t.fromStateId, toStateId: t.toStateId })))
  }

  async function toggleRestricted(next) {
    setRestricted(next)
    if (!next) {
      await saveTransitions([]) // empty rule set means "allow every move"
    } else {
      // Seed with the obvious left-to-right flow plus staying put, so turning
      // this on does not immediately block everyone.
      const pairs = []
      states.forEach((state, index) => {
        if (states[index + 1]) pairs.push({ fromStateId: state.id, toStateId: states[index + 1].id })
        if (states[index - 1]) pairs.push({ fromStateId: state.id, toStateId: states[index - 1].id })
      })
      await saveTransitions(pairs)
    }
  }

  const noProject = projectStatus === 'empty'

  return (
    <>
      <Topbar title="Settings" subtitle={project?.name} />

      <div className="app-content">
        {error && (
          <div className="banner banner--error" role="alert">
            {error}
          </div>
        )}
        {saved && <div className="banner banner--info">{saved}</div>}

        {/* One stack, so every panel keeps the same gap. Your own account
            comes first: it is the one thing on this page that works before
            you have joined a project. */}
        <div className="stack">
          <ProfilePanel onSaved={flash} onError={setError} />

          {noProject && <ProjectEmpty />}

          {noProject ? null : (
            <>
          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Details</h2>
            </div>
            <div className="panel-body">
              <form onSubmit={saveDetails}>
                <div className="field">
                  <label className="field-label" htmlFor="set-name">
                    Name
                  </label>
                  <input
                    id="set-name"
                    className="input"
                    value={details.name}
                    onChange={(e) => setDetails((d) => ({ ...d, name: e.target.value }))}
                  />
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="set-desc">
                    Description
                  </label>
                  <textarea
                    id="set-desc"
                    className="textarea"
                    value={details.description}
                    onChange={(e) => setDetails((d) => ({ ...d, description: e.target.value }))}
                  />
                </div>
                <button type="submit" className="btn btn-primary">
                  Save details
                </button>
              </form>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Board columns</h2>
              <span className="muted panel-action" style={{ fontSize: 12 }}>
                The board is these columns, in this order
              </span>
            </div>

            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Column</th>
                    <th>Counts as</th>
                    <th>WIP limit</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {states.map((state, index) => (
                    <tr key={state.id}>
                      <td>
                        <div className="row">
                          <span className={`column-dot dot-${state.category}`} aria-hidden="true" />
                          <input
                            className="input"
                            style={{ width: 180 }}
                            defaultValue={state.name}
                            onBlur={(e) =>
                              e.target.value.trim() !== state.name &&
                              patchColumn(state.id, { name: e.target.value.trim() })
                            }
                            aria-label={`Name of column ${state.name}`}
                          />
                        </div>
                      </td>
                      <td>
                        <select
                          className="select"
                          style={{ width: 140 }}
                          value={state.category}
                          onChange={(e) => patchColumn(state.id, { category: e.target.value })}
                          aria-label={`Category of ${state.name}`}
                        >
                          {CATEGORIES.map((category) => (
                            <option key={category.id} value={category.id}>
                              {category.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <input
                          type="number"
                          min="0"
                          className="input"
                          style={{ width: 80 }}
                          defaultValue={state.wipLimit ?? ''}
                          placeholder="—"
                          onBlur={(e) =>
                            patchColumn(state.id, {
                              wipLimit: e.target.value === '' ? null : Number(e.target.value),
                            })
                          }
                          aria-label={`WIP limit for ${state.name}`}
                        />
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="row" style={{ justifyContent: 'flex-end' }}>
                          <button
                            type="button"
                            className="btn-icon"
                            disabled={index === 0}
                            onClick={() => {
                              patchColumn(state.id, { position: state.position - 1 })
                              patchColumn(states[index - 1].id, { position: state.position })
                            }}
                            aria-label={`Move ${state.name} left`}
                          >
                            ←
                          </button>
                          <button
                            type="button"
                            className="btn-icon"
                            disabled={index === states.length - 1}
                            onClick={() => {
                              patchColumn(state.id, { position: state.position + 1 })
                              patchColumn(states[index + 1].id, { position: state.position })
                            }}
                            aria-label={`Move ${state.name} right`}
                          >
                            →
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => deleteColumn(state.id)}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="panel-body">
              <form className="row-gap-3" onSubmit={addColumn}>
                <input
                  className="input"
                  style={{ width: 200 }}
                  value={newColumn.name}
                  onChange={(e) => setNewColumn((c) => ({ ...c, name: e.target.value }))}
                  placeholder="New column name"
                  aria-label="New column name"
                />
                <select
                  className="select"
                  style={{ width: 140 }}
                  value={newColumn.category}
                  onChange={(e) => setNewColumn((c) => ({ ...c, category: e.target.value }))}
                  aria-label="New column category"
                >
                  {CATEGORIES.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.label}
                    </option>
                  ))}
                </select>
                <button type="submit" className="btn btn-secondary">
                  Add column
                </button>
              </form>
              <p className="field-hint">
                “Counts as” is what reports use. Rename columns freely — Done still means done
                because of this setting, not the name.
              </p>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Workflow rules</h2>
              <label className="row panel-action" style={{ gap: 8, fontSize: 13 }}>
                <input
                  type="checkbox"
                  checked={restricted}
                  onChange={(e) => toggleRestricted(e.target.checked)}
                />
                Restrict which moves are allowed
              </label>
            </div>

            <div className="panel-body">
              {!restricted ? (
                <p className="muted">
                  Every move is allowed. Turn on restrictions to require issues to follow the
                  workflow — useful when a review step keeps getting skipped.
                </p>
              ) : (
                <>
                  <div className="table-scroll">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>From ↓ / To →</th>
                          {states.map((state) => (
                            <th key={state.id}>{state.name}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {states.map((from) => (
                          <tr key={from.id}>
                            <td className="strong">{from.name}</td>
                            {states.map((to) => (
                              <td key={to.id} style={{ textAlign: 'center' }}>
                                {from.id === to.id ? (
                                  <span className="muted">—</span>
                                ) : (
                                  <input
                                    type="checkbox"
                                    checked={isAllowed(from.id, to.id)}
                                    onChange={() => toggleTransition(from.id, to.id)}
                                    aria-label={`Allow ${from.name} to ${to.name}`}
                                  />
                                )}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="field-hint">
                    A blocked move is refused by the server, not just hidden in the UI.
                  </p>
                </>
              )}
            </div>
          </section>

          {/* Only shown to people the server would actually let through. The
              check below is the one that counts; this just avoids offering a
              button that answers 403. */}
          {role === 'admin' && (
            <section className="panel panel--danger">
              <div className="panel-head">
                <h2 className="panel-title">Danger zone</h2>
              </div>
              <div className="panel-body">
                <p className="muted" style={{ marginBottom: 12 }}>
                  Deleting <b>{details.name}</b> removes its board, its {states.length} columns,
                  every issue, sprint, comment and attachment in it, and its history. There is no
                  undo and no export.
                </p>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => setConfirmingDelete(true)}
                >
                  Delete this project
                </button>
              </div>
            </section>
          )}
            </>
          )}
        </div>
      </div>

      {confirmingDelete && (
        <DeleteProjectModal
          projectId={projectId}
          name={details.name}
          onClose={() => setConfirmingDelete(false)}
          onDeleted={async () => {
            await reload()
            navigate('/projects')
          }}
        />
      )}
    </>
  )
}

/**
 * Your own account.
 *
 * Name and title save together; the password is its own form because it needs
 * the current one, and because mixing the two means a failed password check
 * silently throws away an edited name.
 */
function ProfilePanel({ onSaved, onError }) {
  const { user, updateUser } = useAuth()
  const [profile, setProfile] = useState({ name: '', title: '' })
  const [passwords, setPasswords] = useState({ currentPassword: '', password: '', confirm: '' })
  const [passwordError, setPasswordError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (user) setProfile({ name: user.name ?? '', title: user.title ?? '' })
  }, [user])

  async function saveProfile(e) {
    e.preventDefault()
    setBusy(true)
    try {
      const { data } = await api.patch('/auth/me', profile)
      updateUser(data.user)
      onSaved('Profile saved.')
    } catch (err) {
      onError(errorMessage(err, 'Could not save your profile.'))
    } finally {
      setBusy(false)
    }
  }

  async function changePassword(e) {
    e.preventDefault()
    setPasswordError('')

    if (passwords.password !== passwords.confirm) {
      setPasswordError('The two new passwords do not match.')
      return
    }

    setBusy(true)
    try {
      await api.patch('/auth/me', {
        currentPassword: passwords.currentPassword,
        password: passwords.password,
      })
      setPasswords({ currentPassword: '', password: '', confirm: '' })
      onSaved('Password changed.')
    } catch (err) {
      setPasswordError(errorMessage(err, 'Could not change your password.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2 className="panel-title">Your profile</h2>
        <span className="muted panel-action" style={{ fontSize: 12 }}>
          {user?.email}
        </span>
      </div>

      <div className="panel-body">
        <form onSubmit={saveProfile}>
          <div className="field-row">
            <div className="field">
              <label className="field-label" htmlFor="me-name">
                Name
              </label>
              <input
                id="me-name"
                className="input"
                value={profile.name}
                onChange={(e) => setProfile((p) => ({ ...p, name: e.target.value }))}
              />
              <p className="field-hint">This is the name on your avatar and on everything you touch.</p>
            </div>
            <div className="field">
              <label className="field-label" htmlFor="me-title">
                Job title
              </label>
              <input
                id="me-title"
                className="input"
                value={profile.title}
                onChange={(e) => setProfile((p) => ({ ...p, title: e.target.value }))}
                placeholder="Backend developer"
              />
              <p className="field-hint">Optional. Shown on the team page.</p>
            </div>
          </div>
          <button type="submit" className="btn btn-primary" disabled={busy || !profile.name.trim()}>
            Save profile
          </button>
        </form>

        <hr className="rule" />

        <form onSubmit={changePassword}>
          <div className="subsection-title" style={{ marginTop: 0 }}>
            Change password
          </div>
          {passwordError && (
            <div className="form-error" role="alert">
              {passwordError}
            </div>
          )}
          <div className="field-row field-row--3">
            <div className="field">
              <label className="field-label" htmlFor="me-current">
                Current password
              </label>
              <input
                id="me-current"
                type="password"
                className="input"
                autoComplete="current-password"
                value={passwords.currentPassword}
                onChange={(e) => setPasswords((p) => ({ ...p, currentPassword: e.target.value }))}
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="me-new">
                New password
              </label>
              <input
                id="me-new"
                type="password"
                className="input"
                autoComplete="new-password"
                value={passwords.password}
                onChange={(e) => setPasswords((p) => ({ ...p, password: e.target.value }))}
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="me-confirm">
                Repeat it
              </label>
              <input
                id="me-confirm"
                type="password"
                className="input"
                autoComplete="new-password"
                value={passwords.confirm}
                onChange={(e) => setPasswords((p) => ({ ...p, confirm: e.target.value }))}
              />
            </div>
          </div>
          <button
            type="submit"
            className="btn btn-secondary"
            disabled={busy || !passwords.currentPassword || !passwords.password}
          >
            Change password
          </button>
        </form>
      </div>
    </section>
  )
}

/**
 * Deleting a project takes everything in it with it, so the confirmation is
 * deliberately awkward: the name has to be typed out. A Yes/No dialog on an
 * irreversible action is muscle memory by the second week.
 */
function DeleteProjectModal({ projectId, name, onClose, onDeleted }) {
  const [typed, setTyped] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const matches = typed.trim() === name

  async function submit(e) {
    e.preventDefault()
    if (!matches) return
    setBusy(true)
    try {
      await api.delete(`/projects/${projectId}`)
      await onDeleted()
    } catch (err) {
      setError(errorMessage(err, 'Could not delete the project.'))
      setBusy(false)
    }
  }

  return (
    <Modal
      title="Delete this project?"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            form="delete-project"
            className="btn btn-danger"
            disabled={!matches || busy}
          >
            {busy ? 'Deleting…' : 'Delete project'}
          </button>
        </>
      }
    >
      <form id="delete-project" onSubmit={submit}>
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}
        <p style={{ marginBottom: 12 }}>
          This deletes every issue, sprint, comment, attachment and history entry in{' '}
          <b>{name}</b>. It cannot be undone.
        </p>
        <div className="field">
          <label className="field-label" htmlFor="confirm-name">
            Type <b>{name}</b> to confirm
          </label>
          <input
            id="confirm-name"
            className="input"
            autoFocus
            autoComplete="off"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
          />
        </div>
      </form>
    </Modal>
  )
}
