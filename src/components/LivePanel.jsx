import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { api, errorMessage } from '../api/client.js'
import { getSocket, onSocketReady } from '../api/socket.js'
import { describeActivity } from './ActivityFeed.jsx'

const SHOWN = 40
// Changes by the same person this close together read as one burst of work,
// so they share a single name and avatar - the way Discord stacks messages.
const GROUP_GAP_MS = 10 * 60 * 1000

/** The server stores UTC without a zone marker; read it as UTC. */
function parseUtc(iso) {
  if (!iso) return null
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

function sameDay(a, b) {
  return a && b && a.toDateString() === b.toDateString()
}

function clock(date, now) {
  if (!date) return ''
  const seconds = Math.max(0, Math.round((now - date) / 1000))
  if (seconds < 45) return 'just now'
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function dayLabel(date, now) {
  if (!date) return 'Earlier'
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (sameDay(date, now)) return 'Today'
  if (sameDay(date, yesterday)) return 'Yesterday'
  return date.toLocaleDateString([], { day: 'numeric', month: 'long', year: 'numeric' })
}

/** "DEV-5 Write API documentation" -> ["DEV-5", "Write API documentation"] */
function splitSubject(subject) {
  const match = /^([A-Z][A-Z0-9]*-\d+)\s*(.*)$/.exec(subject || '')
  return match ? [match[1], match[2]] : [null, subject || '']
}

/**
 * One short line per change, naming the issue by its key so every line has
 * the same shape. The issue's title is in the tooltip, not the line - that is
 * what keeps the column narrow and aligned.
 */
function shortLine(entry) {
  const [key] = splitSubject(entry.subject)
  const K = key ? <span className="lp-key">{key}</span> : <>an issue</>
  const v = (text) => <b>{text}</b>
  const { verb, from: before, to: after, field } = entry

  switch (verb) {
    case 'issue.created': return <>created {K}</>
    case 'issue.deleted': return <>deleted {K}</>
    case 'issue.moved': return <>moved {K} to {v(after)}</>
    case 'issue.assigned':
      if (after === 'Unassigned') return <>unassigned {K}</>
      return <>assigned {K} to {v(after)}</>
    case 'issue.updated': return <>changed {field === 'storyPoints' ? 'points' : field || 'details'} on {K}</>
    case 'comment.added': return <>commented on {K}</>
    case 'comment.deleted': return <>deleted a comment on {K}</>
    case 'attachment.added': return key ? <>attached {v(after)} to {K}</> : <>uploaded {v(after)}</>
    case 'attachment.deleted': return key ? <>removed {v(before)} from {K}</> : <>deleted {v(before)}</>
    default: return describeActivity(entry)
  }
}

/** Plain-text version of an entry for its tooltip. */
function fullText(entry) {
  const [key, title] = splitSubject(entry.subject)
  const parts = [entry.actorName, entry.verb.replace('.', ' ')]
  if (entry.from || entry.to) parts.push(`${entry.from ?? ''} → ${entry.to ?? ''}`)
  if (key) parts.push(`${key}${title ? `: ${title}` : ''}`)
  return parts.join(' · ')
}

/** Newest-first entries -> day blocks -> groups by the same person. */
function arrange(entries, now) {
  const days = []
  for (const entry of entries) {
    const at = parseUtc(entry.createdAt)
    const label = dayLabel(at, now)
    let day = days[days.length - 1]
    if (!day || day.label !== label) {
      day = { label, groups: [] }
      days.push(day)
    }
    const group = day.groups[day.groups.length - 1]
    const last = group?.entries[group.entries.length - 1]
    if (group && group.actorId === entry.actorId && last?.at && at && last.at - at <= GROUP_GAP_MS) {
      group.entries.push({ ...entry, at })
    } else {
      day.groups.push({ actorId: entry.actorId, entries: [{ ...entry, at }] })
    }
  }
  return days
}

/**
 * The right-hand panel: who is on the project, and what just happened.
 *
 * The activity is the stored history, so changes made while you were away -
 * or while the server was off overnight - are all there when you open the
 * board. New changes then arrive over the live connection, and if that drops
 * (a server restart, a laptop waking up) the history is reloaded when it comes
 * back, so nothing in the gap is missed.
 */
export default function LivePanel({ projectId, userId, members = [], myIssueIds, onActivity }) {
  const [entries, setEntries] = useState([])
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState('')
  const [live, setLive] = useState(() => Boolean(getSocket()?.connected))
  const [now, setNow] = useState(() => new Date())
  const onActivityRef = useRef(onActivity)
  onActivityRef.current = onActivity

  const load = useCallback(async () => {
    if (!projectId) return
    try {
      const { data } = await api.get(`/projects/${projectId}/activity`, { params: { perPage: SHOWN } })
      setEntries(data.activity)
      setStatus('ready')
      setError('')
    } catch (err) {
      setStatus('error')
      setError(errorMessage(err, 'Could not load recent activity.'))
    }
  }, [projectId])

  useEffect(() => {
    setStatus('loading')
    setEntries([])
    load()
  }, [load])

  // Relative times ("4 min ago") would otherwise freeze where they started.
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!projectId) return undefined
    let firstRun = true

    return onSocketReady((socket) => {
      setLive(true)
      if (!firstRun) load() // a reconnect: catch up on the gap
      firstRun = false

      const onNew = (payload) => {
        const entry = payload?.activity
        if (!entry || entry.projectId !== projectId) return
        setEntries((current) =>
          current.some((item) => item.id === entry.id) ? current : [entry, ...current].slice(0, SHOWN)
        )
        setNow(new Date())
        onActivityRef.current?.(entry)
      }
      const onDown = () => setLive(false)

      socket.on('activity:new', onNew)
      socket.on('disconnect', onDown)
      return () => {
        socket.off('activity:new', onNew)
        socket.off('disconnect', onDown)
      }
    })
  }, [projectId, load])

  const days = useMemo(() => arrange(entries, now), [entries, now])
  const byId = useMemo(() => new Map(members.map((m) => [m.id, m])), [members])

  return (
    <aside className="live-panel" aria-label="Members and recent activity">
      <header className="lp-head">
        <span className={`lp-status${live ? ' is-live' : ''}`}>
          <i aria-hidden="true" />
          {live ? 'Live' : 'Reconnecting…'}
        </span>
      </header>

      {members.length > 0 && (
        <section className="lp-section">
          <h2 className="lp-label">Members — {members.length}</h2>
          <ul className="lp-members">
            {members.map((member) => (
              <li key={member.id} className="lp-member">
                <div className="avatar avatar-sm">{member.initials}</div>
                <span className="lp-member-name">
                  {member.id === userId ? `${member.name} (you)` : member.name}
                </span>
                {member.projectRole && <span className="lp-role">{member.projectRole}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="lp-section lp-activity">
        <h2 className="lp-label">Activity{entries.length ? ` — ${entries.length}` : ''}</h2>

        {status === 'loading' && <p className="lp-note">Loading…</p>}
        {status === 'error' && (
          <div className="lp-note">
            <p>{error}</p>
            <button type="button" className="btn btn-ghost btn-sm" onClick={load}>Try again</button>
          </div>
        )}
        {status === 'ready' && entries.length === 0 && (
          <p className="lp-note">
            Nothing has happened here yet. Moves, comments and uploads appear as they happen.
          </p>
        )}

        {days.map((day) => (
          <div key={day.label} className="lp-day">
            <div className="lp-day-rule"><span>{day.label}</span></div>
            {day.groups.map((group) => {
              const first = group.entries[0]
              const isMe = group.actorId === userId
              const name = isMe ? 'You' : (byId.get(group.actorId)?.name ?? first.actorName)
              return (
                <div className="lp-group" key={first.id}>
                  <div className="avatar avatar-sm" title={first.actorName}>{first.actorInitials}</div>
                  <div className="lp-group-body">
                    <div className="lp-who">
                      <b>{name}</b>
                      <time dateTime={first.at?.toISOString()}>{clock(first.at, now)}</time>
                    </div>
                    <ul className="lp-acts">
                      {group.entries.map((entry) => {
                        const yours = !isMe && entry.issueId != null && myIssueIds.has(entry.issueId)
                        return (
                          <li key={entry.id} className={`lp-act${yours ? ' is-yours' : ''}`} title={fullText(entry)}>
                            {shortLine(entry)}
                            {yours && <span className="lp-tag">yours</span>}
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                </div>
              )
            })}
          </div>
        ))}
      </section>
    </aside>
  )
}
