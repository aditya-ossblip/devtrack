import React, { useCallback, useEffect, useState } from 'react'

import { api, errorMessage } from '../api/client.js'

/**
 * The activity log, as sentences.
 *
 * `describeActivity` is exported so the phrasing can be tested on its own:
 * it is the part with a branch per verb, and a missing case shows up as a
 * blank row rather than an error.
 *
 * The server stores the shape of a change — verb, field, before, after — and
 * nothing about how to phrase it. That split is deliberate: a stored sentence
 * would be frozen in whatever wording and language it was written in, and
 * could not be filtered on. Turning rows into English is this file's whole job.
 */

const FIELD_LABELS = {
  title: 'the title',
  description: 'the description',
  type: 'the type',
  priority: 'the priority',
  storyPoints: 'the points',
  status: 'the status',
  assignee: 'the assignee',
}

function value(text) {
  return <b className="activity-value">{text}</b>
}

export function describeActivity(entry) {
  const { verb, field, from: before, to: after } = entry

  switch (verb) {
    case 'issue.created':
      return <>created this issue</>
    case 'issue.deleted':
      return <>deleted this issue</>
    case 'issue.moved':
      return (
        <>
          moved it from {value(before ?? 'nowhere')} to {value(after)}
        </>
      )
    case 'issue.assigned':
      if (after === 'Unassigned') return <>unassigned it from {value(before)}</>
      if (before === 'Unassigned') return <>assigned it to {value(after)}</>
      return (
        <>
          reassigned it from {value(before)} to {value(after)}
        </>
      )
    case 'issue.updated': {
      // Descriptions are long and often multi-line; quoting one here would
      // swamp every other row in the feed.
      if (field === 'description') return <>edited the description</>
      const label = FIELD_LABELS[field] ?? field
      if (before == null && after == null) return <>changed {label}</>
      if (before == null) return <>set {label} to {value(after)}</>
      if (after == null) return <>cleared {label}</>
      return (
        <>
          changed {label} from {value(before)} to {value(after)}
        </>
      )
    }
    case 'comment.added':
      return <>commented</>
    case 'comment.deleted':
      return <>deleted a comment</>
    case 'member.added':
      return <>added {value(after)} to the project</>
    case 'member.removed':
      return <>removed {value(before)} from the project</>
    case 'member.role_changed':
      return (
        <>
          changed {value(entry.subject || 'a member')} from {value(before)} to {value(after)}
        </>
      )
    case 'sprint.started':
      return <>started {value(after ?? entry.subject)}</>
    case 'sprint.completed':
      return <>completed {value(after ?? entry.subject)}</>
    case 'attachment.added':
      return <>attached {value(after)}</>
    case 'attachment.deleted':
      return <>removed {value(before)}</>
    default:
      // A verb added to the backend and not yet to this list should degrade to
      // something readable rather than a blank row.
      return <>{verb.replace('.', ' ')}</>
  }
}

/** Whether the entry's own text already names what it acted on. */
const NAMES_ITS_SUBJECT = new Set([
  'member.added',
  'member.removed',
  'member.role_changed',
  'sprint.started',
  'sprint.completed',
])

export default function ActivityFeed({ source, showSubject = false, emptyText = 'Nothing yet.' }) {
  const [entries, setEntries] = useState([])
  const [meta, setMeta] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const fetchPage = useCallback(
    async (page) => {
      const { data } = await api.get(source, { params: { page, perPage: 25 } })
      return data
    },
    [source]
  )

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchPage(1)
      .then((data) => {
        if (cancelled) return
        setEntries(data.activity)
        setMeta(data.meta)
        setError('')
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err, 'Could not load the history.'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [fetchPage])

  async function loadMore() {
    try {
      const data = await fetchPage((meta?.page ?? 1) + 1)
      setEntries((current) => [...current, ...data.activity])
      setMeta(data.meta)
    } catch (err) {
      setError(errorMessage(err, 'Could not load more history.'))
    }
  }

  if (loading) return <p className="muted">Loading…</p>
  if (error) {
    return (
      <div className="banner banner--error" role="alert">
        {error}
      </div>
    )
  }
  if (!entries.length) return <p className="muted">{emptyText}</p>

  return (
    <div className="activity">
      {entries.map((entry) => (
        <div className="activity-row" key={entry.id}>
          <div className="avatar avatar-sm" title={entry.actorName}>
            {entry.actorInitials}
          </div>
          <div className="grow">
            <div className="activity-line">
              <span className="activity-actor">{entry.actorName}</span> {describeActivity(entry)}
              {showSubject && entry.subject && !NAMES_ITS_SUBJECT.has(entry.verb) && (
                <span className="activity-subject"> — {entry.subject}</span>
              )}
            </div>
            <div className="activity-time" title={entry.createdAt}>
              {entry.time}
            </div>
          </div>
        </div>
      ))}

      {meta?.hasMore && (
        <button type="button" className="btn btn-ghost btn-sm" onClick={loadMore}>
          Show older ({meta.total - entries.length} more)
        </button>
      )}
    </div>
  )
}
