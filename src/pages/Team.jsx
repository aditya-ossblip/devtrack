import React, { useState } from 'react'

import Empty from '../components/Empty.jsx'
import MemberPicker from '../components/MemberPicker.jsx'
import Modal from '../components/Modal.jsx'
import ProjectEmpty from '../components/ProjectEmpty.jsx'
import Topbar from '../components/Topbar.jsx'
import { useAuth } from '../state/AuthContext.jsx'
import { useMembers } from '../state/useMembers.js'
import { useProjects } from '../state/ProjectContext.jsx'

const ROLES = [
  { id: 'admin', label: 'Admin', hint: 'Everything, including deleting the project' },
  { id: 'manager', label: 'Manager', hint: 'Manage issues, members and the workflow' },
  { id: 'developer', label: 'Developer', hint: 'Create issues; edit their own' },
]

export default function Team() {
  const { user } = useAuth()
  const { project, projectId, status: projectStatus } = useProjects()
  const { members, error, addMember, removeMember, changeRole } = useMembers(projectId)
  const [adding, setAdding] = useState(false)

  if (projectStatus === 'empty') return <ProjectEmpty />

  const isLead = project?.leadId === user?.id
  const canManage = isLead || user?.role === 'admin' || user?.role === 'manager'

  return (
    <>
      <Topbar
        title="Team"
        subtitle={`${members.length} on ${project?.name ?? 'this project'}`}
      >
        {canManage && (
          <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
            + Add people
          </button>
        )}
      </Topbar>

      <div className="app-content">
        {error && (
          <div className="banner banner--error" role="alert">
            {error}
          </div>
        )}

        <div className="panel">
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Person</th>
                  <th>Role on this project</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {members.map((member) => {
                  const isProjectLead = member.id === project?.leadId
                  return (
                    <tr key={member.id}>
                      <td>
                        <div className="row-gap-3">
                          <div className="avatar">{member.initials}</div>
                          <div>
                            <div className="strong">
                              {member.name}
                              {member.id === user?.id && <span className="muted"> · you</span>}
                            </div>
                            <div className="list-sub">{member.title || member.role}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        {canManage && !isProjectLead ? (
                          <select
                            className="select"
                            style={{ width: 150 }}
                            value={(member.projectRole ?? 'Developer').toLowerCase()}
                            onChange={(e) => changeRole(member.id, e.target.value)}
                            aria-label={`Role for ${member.name}`}
                          >
                            {ROLES.map((role) => (
                              <option key={role.id} value={role.id}>
                                {role.label}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <span className={`badge badge-${(member.projectRole ?? 'developer').toLowerCase()}`}>
                            {isProjectLead ? 'Project lead' : member.projectRole}
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {canManage && !isProjectLead && (
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => removeMember(member.id)}
                          >
                            Remove
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {members.length === 0 && (
            <Empty mark="◍" title="Nobody here yet">
              Add the people you are working with so issues can be assigned to them.
            </Empty>
          )}
        </div>

        <div className="panel" style={{ marginTop: 16 }}>
          <div className="panel-head">
            <h2 className="panel-title">What each role can do</h2>
          </div>
          <div className="panel-body">
            {ROLES.map((role) => (
              <div className="list-row" key={role.id} style={{ padding: '10px 0' }}>
                <span className={`badge badge-${role.id}`}>{role.label}</span>
                <span className="muted">{role.hint}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {adding && (
        <AddMembersModal
          existing={members.map((m) => m.id)}
          onClose={() => setAdding(false)}
          onAdd={addMember}
        />
      )}
    </>
  )
}

function AddMembersModal({ existing, onClose, onAdd }) {
  const [selected, setSelected] = useState([])
  const [role, setRole] = useState('developer')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function submit(e) {
    e.preventDefault()
    if (selected.length === 0) {
      setError('Pick at least one person.')
      return
    }

    setSaving(true)
    setError('')
    for (const person of selected) {
      const result = await onAdd({ userId: person.id, role })
      if (!result.ok) {
        setError(result.error)
        setSaving(false)
        return
      }
    }
    setSaving(false)
    onClose()
  }

  return (
    <Modal
      title="Add people to this project"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="add-members" className="btn btn-primary" disabled={saving}>
            {saving ? 'Adding…' : `Add ${selected.length || ''}`.trim()}
          </button>
        </>
      }
    >
      <form id="add-members" onSubmit={submit}>
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}

        <div className="field">
          <span className="field-label">Who</span>
          <MemberPicker selected={selected} onChange={setSelected} exclude={existing} />
        </div>

        <div className="field">
          <label className="field-label" htmlFor="add-role">
            Join as
          </label>
          <select id="add-role" className="select" value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label} — {option.hint}
              </option>
            ))}
          </select>
        </div>

        <div className="field-hint">
          Only people with a DevTrack account appear here. Ask anyone missing to sign up first.
        </div>
      </form>
    </Modal>
  )
}
