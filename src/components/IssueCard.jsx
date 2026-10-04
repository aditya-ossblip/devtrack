import React from 'react'

import { PriorityMark, TypeMark } from './issueMeta.jsx'

export default function IssueCard({
  issue,
  isDragging,
  dimmed = false,
  fresh = false,
  onDragStart,
  onDragEnd,
  onOpen,
}) {
  return (
    <article
      className={`issue-card${isDragging ? ' is-dragging' : ''}${dimmed ? ' is-dimmed' : ''}${fresh ? ' is-fresh' : ''}`}
      draggable
      onDragStart={(e) => onDragStart?.(e, issue)}
      onDragEnd={onDragEnd}
      onClick={() => onOpen?.(issue)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen?.(issue)
        }
      }}
      role="button"
      tabIndex={0}
      aria-label={`${issue.key}: ${issue.title}`}
    >
      {issue.epicKey && (
        <div className="issue-card-epic" title={issue.epicTitle}>
          {issue.epicTitle || issue.epicKey}
        </div>
      )}

      <div className="issue-card-title">{issue.title}</div>

      {issue.labels?.length > 0 && (
        <div className="issue-card-labels">
          {issue.labels.slice(0, 3).map((label) => (
            <span className="chip chip-label" key={label}>
              {label}
            </span>
          ))}
        </div>
      )}

      <div className="issue-card-foot">
        <TypeMark type={issue.type} />
        <span className="issue-key">{issue.key}</span>
        <PriorityMark priority={issue.priority} />

        {issue.overdue && <span className="flag-overdue">Overdue</span>}

        {issue.commentCount > 0 && (
          <span className="issue-card-meta" title={`${issue.commentCount} comments`}>
            <span aria-hidden="true">💬</span>
            {issue.commentCount}
          </span>
        )}

        {issue.storyPoints != null && <span className="points-pill">{issue.storyPoints}</span>}

        {issue.assignee ? (
          <div className="avatar avatar-sm" title={issue.assigneeName}>
            {issue.assignee}
          </div>
        ) : (
          <div className="avatar avatar-sm avatar-empty" title="Unassigned">
            –
          </div>
        )}
      </div>
    </article>
  )
}
