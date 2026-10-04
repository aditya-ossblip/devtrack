import React, { useCallback, useEffect, useState } from 'react'

import { api, errorMessage } from '../api/client.js'
import { useAuth } from '../state/AuthContext.jsx'
import ActivityFeed from './ActivityFeed.jsx'
import Attachments from './Attachments.jsx'
import { ISSUE_TYPES, PRIORITIES, TypeMark } from './issueMeta.jsx'

/**
 * The issue detail panel. Every field saves on change or blur — there is no
 * Save button, because a panel with one invites half-finished edits that get
 * lost when it closes.
 */
export default function IssueDrawer({ issueId, states, members, onClose, onChanged, onDeleted }) {
  const { user } = useAuth()
  const [issue, setIssue] = useState(null)
  const [allowed, setAllowed] = useState([])
  // Opened from a page that has no project context (My tasks), the drawer
  // fetches the issue's own project's columns and people itself.
  const [ownStates, setOwnStates] = useState([])
  const [ownMembers, setOwnMembers] = useState([])
  const [error, setError] = useState('')
  const [draftDescription, setDraftDescription] = useState(null)
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [canManage, setCanManage] = useState(false)
  const [tab, setTab] = useState('comments')
  const [attachmentCount, setAttachmentCount] = useState(0)
  // Bumped to force the history to refetch. The log grows as a side effect of
  // edits made in this very panel, so a version number is simpler than trying
  // to predict which changes wrote a row.
  const [historyVersion, setHistoryVersion] = useState(0)

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/issues/${issueId}`)
      setIssue(data.issue)
      setAllowed(data.allowedStateIds)
      setCanManage(Boolean(data.canManage))
      setAttachmentCount(data.issue.attachmentCount ?? 0)
    } catch (err) {
      setError(errorMessage(err, 'Could not load that issue.'))
    }
  }, [issueId])

  useEffect(() => {
    load()
  }, [load])

  const needsOwnLookups = !states?.length || !members?.length
  useEffect(() => {
    if (!issue?.projectId || !needsOwnLookups) return
    Promise.all([
      api.get(`/projects/${issue.projectId}`),
      api.get(`/projects/${issue.projectId}/members`),
    ])
      .then(([projectRes, memberRes]) => {
        setOwnStates(projectRes.data.states)
        setOwnMembers(memberRes.data.members)
      })
      .catch(() => {
        /* the selects fall back to showing just the current value */
      })
  }, [issue?.projectId, needsOwnLookups])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const patch = useCallback(
    async (changes) => {
      setError('')
      setBusy(true)
      try {
        const { data } = await api.patch(`/issues/${issueId}`, changes)
        setIssue((current) => ({ ...data.issue, comments: current?.comments ?? [] }))
        setHistoryVersion((n) => n + 1)
        onChanged?.(data.issue)
      } catch (err) {
        setError(errorMessage(err, 'Could not save that change.'))
        load() // pull the server's truth back so the panel isn't lying
      } finally {
        setBusy(false)
      }
    },
    [issueId, onChanged, load]
  )

  /**
   * Pull the comments on their own.
   *
   * The issue payload carries them, but a panel can sit open for a long time
   * while other people are typing into the same issue. Refetching just the
   * thread leaves the fields alone — reloading the whole issue would discard
   * whatever half-finished edit is sitting in an input.
   */
  const refreshComments = useCallback(async () => {
    try {
      const { data } = await api.get(`/issues/${issueId}/comments`)
      setIssue((current) => (current ? { ...current, comments: data.comments } : current))
    } catch {
      /* the thread already on screen is still the best we have */
    }
  }, [issueId])

  async function addComment(e) {
    e.preventDefault()
    const body = comment.trim()
    if (!body) return

    setComment('')
    try {
      const { data } = await api.post(`/issues/${issueId}/comments`, { body })
      setIssue((current) => ({ ...current, comments: [...(current.comments ?? []), data.comment] }))
      setHistoryVersion((n) => n + 1)
    } catch (err) {
      setComment(body) // give them their text back
      setError(errorMessage(err, 'Could not post that comment.'))
    }
  }

  async function deleteComment(commentId) {
    try {
      await api.delete(`/issues/${issueId}/comments/${commentId}`)
      setIssue((current) => ({
        ...current,
        comments: current.comments.filter((c) => c.id !== commentId),
      }))
      setHistoryVersion((n) => n + 1)
    } catch (err) {
      setError(errorMessage(err, 'Could not delete that comment.'))
    }
  }

  async function deleteIssue() {
    try {
      await api.delete(`/issues/${issueId}`)
      onDeleted?.(issueId)
      onClose()
    } catch (err) {
      setError(errorMessage(err, 'Could not delete that issue.'))
    }
  }

  if (!issue) {
    return (
      <>
        <div className="drawer-backdrop" onClick={onClose} />
        <aside className="drawer">
          <div className="app-loading">
            <div className="spinner" />
          </div>
        </aside>
      </>
    )
  }

  const description = draftDescription ?? issue.description
  const stateOptions = states?.length ? states : ownStates
  const memberOptions = members?.length ? members : ownMembers

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={`${issue.key} details`}>
        <div className="drawer-head">
          <TypeMark type={issue.type} />
          <span className="issue-key">{issue.key}</span>
          {busy && <span className="muted" style={{ fontSize: 11 }}>Saving…</span>}
          <div className="panel-action row">
            <button type="button" className="btn-icon" onClick={deleteIssue} aria-label="Delete issue" title="Delete issue">
              🗑
            </button>
            <button type="button" className="btn-icon" onClick={onClose} aria-label="Close">
              ✕
            </button>
          </div>
        </div>

        <div className="drawer-body">
          {error && (
            <div className="banner banner--error" role="alert">
              {error}
            </div>
          )}

          <textarea
            className="drawer-title"
            rows={2}
            defaultValue={issue.title}
            onBlur={(e) => {
              const title = e.target.value.trim()
              if (title && title !== issue.title) patch({ title })
            }}
            aria-label="Issue title"
          />

          <div className="detail-grid">
            <span className="detail-label">Status</span>
            <div className="detail-value">
              <select
                className="select"
                value={issue.stateId}
                onChange={(e) => patch({ stateId: Number(e.target.value) })}
              >
                {stateOptions.map((state) => (
                  <option
                    key={state.id}
                    value={state.id}
                    disabled={state.id !== issue.stateId && !allowed.includes(state.id)}
                  >
                    {state.name}
                  </option>
                ))}
              </select>
            </div>

            <span className="detail-label">Assignee</span>
            <div className="detail-value">
              <select
                className="select"
                value={issue.assigneeId ?? ''}
                onChange={(e) => patch({ assigneeId: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">Unassigned</option>
                {memberOptions.map((member) => (
                  <option key={member.id} value={member.id}>
                    {member.name}
                  </option>
                ))}
              </select>
            </div>

            <span className="detail-label">Type</span>
            <div className="detail-value">
              <select className="select" value={issue.type} onChange={(e) => patch({ type: e.target.value })}>
                {ISSUE_TYPES.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            <span className="detail-label">Priority</span>
            <div className="detail-value">
              <select
                className="select"
                value={issue.priority}
                onChange={(e) => patch({ priority: e.target.value })}
              >
                {PRIORITIES.map((priority) => (
                  <option key={priority.id} value={priority.id}>
                    {priority.label}
                  </option>
                ))}
              </select>
            </div>

            <span className="detail-label">Points</span>
            <div className="detail-value">
              <input
                type="number"
                min="0"
                max="100"
                className="input"
                defaultValue={issue.storyPoints ?? ''}
                onBlur={(e) =>
                  patch({ storyPoints: e.target.value === '' ? null : Number(e.target.value) })
                }
                aria-label="Story points"
              />
            </div>

            <span className="detail-label">Due</span>
            <div className="detail-value">
              <input
                type="date"
                className="input"
                defaultValue={issue.dueDate ?? ''}
                onChange={(e) => patch({ dueDate: e.target.value || null })}
                aria-label="Due date"
              />
            </div>

            <span className="detail-label">Labels</span>
            <div className="detail-value">
              <input
                className="input"
                defaultValue={issue.labels.join(', ')}
                placeholder="auth, backend"
                onBlur={(e) =>
                  patch({ labels: e.target.value.split(',').map((l) => l.trim()).filter(Boolean) })
                }
                aria-label="Labels, comma separated"
              />
            </div>
          </div>

          <div className="subsection-title">Description</div>
          {draftDescription === null ? (
            <div
              className={`description-box${issue.description ? '' : ' is-empty'}`}
              role="button"
              tabIndex={0}
              onClick={() => setDraftDescription(issue.description)}
              onKeyDown={(e) => e.key === 'Enter' && setDraftDescription(issue.description)}
            >
              {issue.description || 'Add a description…'}
            </div>
          ) : (
            <div style={{ marginBottom: 20 }}>
              <textarea
                className="textarea"
                autoFocus
                value={description}
                onChange={(e) => setDraftDescription(e.target.value)}
              />
              <div className="row" style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => {
                    patch({ description: draftDescription })
                    setDraftDescription(null)
                  }}
                >
                  Save
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setDraftDescription(null)}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="tabs tabs--drawer" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'comments'}
              className={`tab${tab === 'comments' ? ' is-active' : ''}`}
              onClick={() => {
                setTab('comments')
                refreshComments()
              }}
            >
              Comments
              {issue.comments?.length > 0 && <span className="tab-count">{issue.comments.length}</span>}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'files'}
              className={`tab${tab === 'files' ? ' is-active' : ''}`}
              onClick={() => setTab('files')}
            >
              Files
              {attachmentCount > 0 && <span className="tab-count">{attachmentCount}</span>}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'history'}
              className={`tab${tab === 'history' ? ' is-active' : ''}`}
              onClick={() => setTab('history')}
            >
              History
            </button>
          </div>

          {tab === 'files' && (
            <Attachments
              issueId={issueId}
              canManage={canManage}
              onChanged={() => {
                setHistoryVersion((n) => n + 1)
                api
                  .get(`/issues/${issueId}/attachments`)
                  .then(({ data }) => setAttachmentCount(data.attachments.length))
                  .catch(() => {
                    /* the badge is cosmetic */
                  })
              }}
            />
          )}

          {tab === 'history' && (
            <ActivityFeed
              key={historyVersion}
              source={`/issues/${issueId}/activity`}
              emptyText="Nothing has happened to this issue yet."
            />
          )}

          {tab === 'comments' && (
            <>
          {issue.comments?.map((entry) => (
            <div className="comment" key={entry.id}>
              <div className="avatar avatar-sm">{entry.authorInitials}</div>
              <div className="grow">
                <div className="comment-head">
                  <span className="comment-author">{entry.authorName}</span>
                  <span className="comment-time">{entry.time}</span>
                  {entry.authorId === user?.id && (
                    <button
                      type="button"
                      className="comment-delete"
                      onClick={() => deleteComment(entry.id)}
                    >
                      Delete
                    </button>
                  )}
                </div>
                <div className="comment-body">{entry.body}</div>
              </div>
            </div>
          ))}

          <form className="comment-form" onSubmit={addComment}>
            <div className="avatar avatar-sm">{user?.initials}</div>
            <div className="grow">
              <textarea
                className="textarea"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Leave a comment…"
                aria-label="New comment"
              />
              <button
                type="submit"
                className="btn btn-secondary btn-sm"
                style={{ marginTop: 8 }}
                disabled={!comment.trim()}
              >
                Comment
              </button>
            </div>
          </form>
            </>
          )}

          <p className="muted" style={{ fontSize: 11, marginTop: 20 }}>
            {issue.reporterName && `Reported by ${issue.reporterName}. `}
            Created {new Date(issue.createdAt).toLocaleDateString()}.
          </p>
        </div>
      </aside>
    </>
  )
}
