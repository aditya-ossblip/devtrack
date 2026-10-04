import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { api, errorMessage } from '../api/client.js'
import { onSocketReady } from '../api/socket.js'

/**
 * Pure move: returns a new columns array with `issueId` appended to
 * `targetStateId` and removed from wherever it was. Returns the input
 * unchanged when the move is a no-op or the ids do not resolve, so React
 * skips the re-render.
 */
export function moveIssueInColumns(columns, issueId, targetStateId) {
  const id = Number(issueId)
  const source = columns.find((col) => col.issues.some((issue) => issue.id === id))
  const target = columns.find((col) => col.id === Number(targetStateId))
  if (!source || !target || source.id === target.id) return columns

  const issue = source.issues.find((item) => item.id === id)

  return columns.map((col) => {
    if (col.id === source.id) {
      return { ...col, issues: col.issues.filter((item) => item.id !== id) }
    }
    if (col.id === target.id) {
      return {
        ...col,
        issues: [...col.issues, { ...issue, stateId: col.id, stateName: col.name, stateCategory: col.category }],
      }
    }
    return col
  })
}

/** Replace an issue wherever it sits, moving it if its state changed. */
export function upsertIssueInColumns(columns, issue) {
  const without = columns.map((col) => ({
    ...col,
    issues: col.issues.filter((item) => item.id !== issue.id),
  }))

  const target = without.find((col) => col.id === issue.stateId)
  if (!target) return columns // belongs to a column this board isn't showing

  return without.map((col) =>
    col.id === target.id
      ? {
          ...col,
          issues: [...col.issues, issue].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)),
        }
      : col
  )
}

export function removeIssueFromColumns(columns, issueId) {
  const id = Number(issueId)
  if (!columns.some((col) => col.issues.some((issue) => issue.id === id))) return columns
  return columns.map((col) => ({ ...col, issues: col.issues.filter((i) => i.id !== id) }))
}

/**
 * Single owner of board state.
 *
 * Loads the board, applies moves optimistically and rolls them back if the
 * server refuses, and folds in socket events from other people. The stats
 * derive from the same array, so they can never disagree with the columns.
 */
export function useBoard(projectId, { sprintId } = {}) {
  const [columns, setColumns] = useState([])
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState('')
  const columnsRef = useRef(columns)
  columnsRef.current = columns

  const load = useCallback(async () => {
    if (!projectId) return
    setStatus('loading')
    try {
      const params = sprintId ? { sprintId } : {}
      const { data } = await api.get(`/projects/${projectId}/board`, { params })
      setColumns(data.columns)
      setStatus('ready')
      setError('')
    } catch (err) {
      setError(errorMessage(err, 'Could not load the board.'))
      setStatus('error')
    }
  }, [projectId, sprintId])

  useEffect(() => {
    load()
  }, [load])

  const moveIssue = useCallback(async (issueId, targetStateId) => {
    const snapshot = columnsRef.current
    const optimistic = moveIssueInColumns(snapshot, issueId, targetStateId)
    if (optimistic === snapshot) return // no-op move, nothing to persist

    setColumns(optimistic)
    setError('')

    try {
      const { data } = await api.patch(`/issues/${issueId}`, { stateId: Number(targetStateId) })
      // Take the server's copy: it carries the authoritative position and the
      // recomputed `overdue` flag.
      setColumns((current) => upsertIssueInColumns(current, data.issue))
    } catch (err) {
      setColumns(snapshot) // put the card back where it was
      setError(errorMessage(err, 'Could not move that issue.'))
    }
  }, [])

  const applyIssue = useCallback((issue) => {
    setColumns((current) => upsertIssueInColumns(current, issue))
  }, [])

  const dropIssue = useCallback((issueId) => {
    setColumns((current) => removeIssueFromColumns(current, issueId))
  }, [])

  // Live updates from everyone else working the same board.
  useEffect(() => {
    if (!projectId) return undefined

    return onSocketReady((socket) => {
      socket.emit('join_project', { projectId })

      const onUpsert = (payload) => payload?.issue && applyIssue(payload.issue)
      const onDeleted = (payload) => dropIssue(payload?.issueId)
      const onWorkflow = () => load()

      socket.on('issue:created', onUpsert)
      socket.on('issue:moved', onUpsert)
      socket.on('issue:updated', onUpsert)
      socket.on('issue:deleted', onDeleted)
      socket.on('workflow:changed', onWorkflow)

      return () => {
        socket.emit('leave_project', { projectId })
        socket.off('issue:created', onUpsert)
        socket.off('issue:moved', onUpsert)
        socket.off('issue:updated', onUpsert)
        socket.off('issue:deleted', onDeleted)
        socket.off('workflow:changed', onWorkflow)
      }
    })
  }, [projectId, applyIssue, dropIssue, load])

  const stats = useMemo(() => {
    const all = columns.flatMap((col) => col.issues)
    const byCategory = (category) =>
      columns.filter((col) => col.category === category).flatMap((col) => col.issues)

    const done = byCategory('done')
    const inProgress = byCategory('in_progress')

    return {
      total: all.length,
      notStarted: byCategory('todo').length,
      inProgress: inProgress.length,
      overdue: all.filter((issue) => issue.overdue).length,
      done: done.length,
      donePct: all.length ? Math.round((done.length / all.length) * 100) : 0,
      points: all.reduce((sum, issue) => sum + (issue.storyPoints || 0), 0),
      pointsDone: done.reduce((sum, issue) => sum + (issue.storyPoints || 0), 0),
    }
  }, [columns])

  return { columns, moveIssue, applyIssue, dropIssue, stats, status, error, reload: load }
}
