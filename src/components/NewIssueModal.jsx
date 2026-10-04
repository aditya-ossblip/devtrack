import React, { useState } from 'react'

import { api, errorMessage } from '../api/client.js'
import Modal from './Modal.jsx'
import { ISSUE_TYPES, PRIORITIES } from './issueMeta.jsx'

export default function NewIssueModal({ projectId, states = [], members = [], defaultStateId, sprintId, onClose, onCreated }) {
  const [form, setForm] = useState({
    title: '',
    description: '',
    type: 'task',
    priority: 'medium',
    stateId: defaultStateId ?? states[0]?.id ?? '',
    assigneeId: '',
    storyPoints: '',
    dueDate: '',
    labels: '',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const set = (key) => (e) => setForm((current) => ({ ...current, [key]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    if (!form.title.trim()) {
      setError('Give the issue a title.')
      return
    }

    setSaving(true)
    setError('')
    try {
      const { data } = await api.post('/issues', {
        projectId,
        title: form.title.trim(),
        description: form.description.trim(),
        type: form.type,
        priority: form.priority,
        stateId: Number(form.stateId) || undefined,
        assigneeId: form.assigneeId ? Number(form.assigneeId) : null,
        storyPoints: form.storyPoints === '' ? null : Number(form.storyPoints),
        dueDate: form.dueDate || null,
        labels: form.labels.split(',').map((l) => l.trim()).filter(Boolean),
        sprintId: sprintId ?? null,
      })
      onCreated?.(data.issue)
      onClose()
    } catch (err) {
      setError(errorMessage(err, 'Could not create the issue.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="New issue"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="new-issue" className="btn btn-primary" disabled={saving}>
            {saving ? 'Creating…' : 'Create issue'}
          </button>
        </>
      }
    >
      <form id="new-issue" onSubmit={submit}>
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}

        <div className="field">
          <label className="field-label" htmlFor="issue-title">
            Title
          </label>
          <input
            id="issue-title"
            className="input"
            autoFocus
            value={form.title}
            onChange={set('title')}
            placeholder="What needs doing?"
          />
        </div>

        <div className="field-row">
          <div className="field">
            <label className="field-label" htmlFor="issue-type">
              Type
            </label>
            <select id="issue-type" className="select" value={form.type} onChange={set('type')}>
              {ISSUE_TYPES.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="field-label" htmlFor="issue-priority">
              Priority
            </label>
            <select id="issue-priority" className="select" value={form.priority} onChange={set('priority')}>
              {PRIORITIES.map((priority) => (
                <option key={priority.id} value={priority.id}>
                  {priority.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label className="field-label" htmlFor="issue-state">
              Status
            </label>
            <select id="issue-state" className="select" value={form.stateId} onChange={set('stateId')}>
              {states.map((state) => (
                <option key={state.id} value={state.id}>
                  {state.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="field-label" htmlFor="issue-assignee">
              Assignee
            </label>
            <select id="issue-assignee" className="select" value={form.assigneeId} onChange={set('assigneeId')}>
              <option value="">Unassigned</option>
              {members.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label className="field-label" htmlFor="issue-points">
              Story points
            </label>
            <input
              id="issue-points"
              type="number"
              min="0"
              max="100"
              className="input"
              value={form.storyPoints}
              onChange={set('storyPoints')}
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="issue-due">
              Due date
            </label>
            <input id="issue-due" type="date" className="input" value={form.dueDate} onChange={set('dueDate')} />
          </div>
        </div>

        <div className="field">
          <label className="field-label" htmlFor="issue-labels">
            Labels
          </label>
          <input
            id="issue-labels"
            className="input"
            value={form.labels}
            onChange={set('labels')}
            placeholder="auth, backend"
          />
          <div className="field-hint">Comma separated.</div>
        </div>

        <div className="field">
          <label className="field-label" htmlFor="issue-desc">
            Description
          </label>
          <textarea
            id="issue-desc"
            className="textarea"
            value={form.description}
            onChange={set('description')}
            placeholder="Context, acceptance criteria, links…"
          />
        </div>
      </form>
    </Modal>
  )
}
