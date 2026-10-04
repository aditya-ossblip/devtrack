import React from 'react'

/** One place that knows how an issue's type, priority and labels look. */

export const ISSUE_TYPES = [
  { id: 'epic', label: 'Epic', mark: 'E' },
  { id: 'story', label: 'Story', mark: 'S' },
  { id: 'task', label: 'Task', mark: 'T' },
  { id: 'bug', label: 'Bug', mark: 'B' },
  { id: 'subtask', label: 'Subtask', mark: 'st' },
]

export const PRIORITIES = [
  { id: 'highest', label: 'Highest', mark: '⬆⬆' },
  { id: 'high', label: 'High', mark: '⬆' },
  { id: 'medium', label: 'Medium', mark: '=' },
  { id: 'low', label: 'Low', mark: '⬇' },
  { id: 'lowest', label: 'Lowest', mark: '⬇⬇' },
]

const TYPE_BY_ID = Object.fromEntries(ISSUE_TYPES.map((t) => [t.id, t]))
const PRIORITY_BY_ID = Object.fromEntries(PRIORITIES.map((p) => [p.id, p]))

export function TypeMark({ type }) {
  const meta = TYPE_BY_ID[type] ?? TYPE_BY_ID.task
  return (
    <span className={`type-mark type-${meta.id}`} title={meta.label}>
      <span className="sr-only">{meta.label}</span>
      <span aria-hidden="true">{meta.mark}</span>
    </span>
  )
}

export function PriorityMark({ priority }) {
  const meta = PRIORITY_BY_ID[priority] ?? PRIORITY_BY_ID.medium
  return (
    <span className={`priority-mark priority-${meta.id}`} title={`${meta.label} priority`}>
      <span className="sr-only">{meta.label} priority</span>
      <span aria-hidden="true">{meta.mark}</span>
    </span>
  )
}

export function typeLabel(type) {
  return (TYPE_BY_ID[type] ?? TYPE_BY_ID.task).label
}

export function priorityLabel(priority) {
  return (PRIORITY_BY_ID[priority] ?? PRIORITY_BY_ID.medium).label
}
