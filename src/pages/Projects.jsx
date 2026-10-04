import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api, errorMessage } from '../api/client.js'
import Empty from '../components/Empty.jsx'
import MemberPicker from '../components/MemberPicker.jsx'
import Modal from '../components/Modal.jsx'
import Topbar from '../components/Topbar.jsx'
import { useAuth } from '../state/AuthContext.jsx'
import { useProjects } from '../state/ProjectContext.jsx'

function suggestKey(name) {
  const words = name.split(/[^A-Za-z0-9]+/).filter(Boolean)
  if (words.length >= 2) return words.map((w) => w[0]).join('').slice(0, 10).toUpperCase()
  return (words[0] ?? '').slice(0, 3).toUpperCase()
}

export default function Projects() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const { projects, selectProject, reload } = useProjects()
  const [creating, setCreating] = useState(false)

  return (
    <>
      <Topbar title="Projects" subtitle={`${projects.length} project${projects.length === 1 ? '' : 's'}`}>
        <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
          + New project
        </button>
      </Topbar>

      <div className="app-content">
        {projects.length === 0 ? (
          <Empty
            mark="◈"
            title="No projects yet"
            action={
              <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
                Create your first project
              </button>
            }
          >
            A project holds a board, a backlog and a team. You can invite people while you
            create it, or add them later from the Team page.
          </Empty>
        ) : (
          <div className="project-grid">
            {projects.map((project) => {
              const counts = project.issueCounts ?? {}
              const total = project.issueTotal || 0
              const pct = (key) => (total ? (counts[key] / total) * 100 : 0)

              return (
                <button
                  type="button"
                  className="project-card"
                  key={project.id}
                  onClick={() => {
                    selectProject(project.id)
                    navigate('/board')
                  }}
                >
                  <div className="project-card-head">
                    <span className="project-key">{project.key}</span>
                    <div className="grow">
                      <div className="project-name">{project.name}</div>
                      <div className="list-sub">Led by {project.leadName}</div>
                    </div>
                  </div>

                  <p className="project-desc">
                    {project.description || 'No description yet.'}
                  </p>

                  <div className="project-progress" aria-hidden="true">
                    <i className="seg-done" style={{ width: `${pct('done')}%` }} />
                    <i className="seg-in_progress" style={{ width: `${pct('in_progress')}%` }} />
                    <i className="seg-todo" style={{ width: `${pct('todo')}%` }} />
                  </div>

                  <div className="project-foot">
                    <span>{total} issues</span>
                    <span>·</span>
                    <span>{counts.done ?? 0} done</span>
                    <span>·</span>
                    <span>{project.memberCount} member{project.memberCount === 1 ? '' : 's'}</span>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {creating && (
        <NewProjectModal
          currentUser={user}
          onClose={() => setCreating(false)}
          onCreated={async (project) => {
            await reload()
            selectProject(project.id)
            navigate('/board')
          }}
        />
      )}
    </>
  )
}

function NewProjectModal({ currentUser, onClose, onCreated }) {
  const [name, setName] = useState('')
  const [key, setKey] = useState('')
  const [keyTouched, setKeyTouched] = useState(false)
  const [description, setDescription] = useState('')
  const [members, setMembers] = useState([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  function handleName(value) {
    setName(value)
    // The key follows the name until they edit it themselves.
    if (!keyTouched) setKey(suggestKey(value))
  }

  async function submit(e) {
    e.preventDefault()
    if (!name.trim()) {
      setError('Give the project a name.')
      return
    }

    setSaving(true)
    setError('')
    try {
      const { data } = await api.post('/projects', {
        name: name.trim(),
        key: key.trim().toUpperCase(),
        description: description.trim(),
        memberIds: members.map((m) => m.id),
      })
      await onCreated(data.project)
      onClose()
    } catch (err) {
      setError(errorMessage(err, 'Could not create the project.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="New project"
      wide
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="new-project" className="btn btn-primary" disabled={saving}>
            {saving ? 'Creating…' : 'Create project'}
          </button>
        </>
      }
    >
      <form id="new-project" onSubmit={submit}>
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}

        <div className="field-row">
          <div className="field">
            <label className="field-label" htmlFor="project-name">
              Project name
            </label>
            <input
              id="project-name"
              className="input"
              autoFocus
              value={name}
              onChange={(e) => handleName(e.target.value)}
              placeholder="DevTrack v2"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="project-key">
              Key
            </label>
            <input
              id="project-key"
              className="input"
              value={key}
              onChange={(e) => {
                setKeyTouched(true)
                setKey(e.target.value.toUpperCase())
              }}
              placeholder="DEV"
              maxLength={10}
            />
            <div className="field-hint">Prefixes every issue: {key || 'DEV'}-1, {key || 'DEV'}-2…</div>
          </div>
        </div>

        <div className="field">
          <label className="field-label" htmlFor="project-desc">
            What is this project about?
          </label>
          <textarea
            id="project-desc"
            className="textarea"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="One or two sentences on the goal, so anyone joining knows what they've walked into."
          />
        </div>

        <div className="field">
          <span className="field-label">Add your team</span>
          <div className="field-hint" style={{ marginTop: 0, marginBottom: 8 }}>
            You are the lead. Anyone you add here joins as a developer — change roles later on the
            Team page. People need a DevTrack account before they can be added.
          </div>
          <MemberPicker selected={members} onChange={setMembers} exclude={[currentUser?.id]} />
        </div>

        <div className="field-hint">
          Your board starts with To do, In progress, In review and Done. Rename or add columns in
          project settings.
        </div>
      </form>
    </Modal>
  )
}
