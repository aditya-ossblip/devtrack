/**
 * "Your three for today": which of your open issues to do next, and why.
 *
 * Pure, so the ranking can be tested without React or a server. It only reads
 * fields every issue already carries - due date, priority, points, state - so
 * there is nothing to set up for it to work.
 *
 * The order, most important first:
 *   1. Overdue, most overdue first.
 *   2. Priority.
 *   3. Due soonest (no due date sorts last).
 *   4. Already started before not started - finish what you began.
 *   5. Bigger before smaller.
 */

const PRIORITY_RANK = { highest: 0, high: 1, medium: 2, low: 3, lowest: 4 }
const PRIORITY_WORDS = { highest: 'highest priority', high: 'high priority' }
const DAY = 24 * 60 * 60 * 1000

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

/** Whole days from `today` to an ISO date (yyyy-mm-dd). Negative means past. */
export function daysUntil(isoDate, today = new Date()) {
  if (!isoDate) return null
  const [y, m, d] = isoDate.slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return null
  return Math.round((new Date(y, m - 1, d) - startOfDay(today)) / DAY)
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

/** One short line saying why this issue is on the list. */
export function focusReason(issue, days) {
  const parts = []
  if (issue.overdue) {
    // The server decides "overdue" in UTC; the count is local. Around midnight
    // they can disagree by a day, and "0 days overdue" would read as a bug.
    parts.push(`${plural(Math.max(1, -(days ?? -1)), 'day')} overdue`)
  } else if (days === 0) parts.push('due today')
  else if (days === 1) parts.push('due tomorrow')
  else if (days != null && days > 1 && days <= 7) parts.push(`due in ${days} days`)

  if (PRIORITY_WORDS[issue.priority]) parts.push(PRIORITY_WORDS[issue.priority])
  if (issue.stateCategory === 'in_progress') parts.push('already started')
  if (issue.storyPoints) parts.push(plural(issue.storyPoints, 'point'))

  return parts.slice(0, 3).join(' · ') || 'Next on your list'
}

/**
 * Returns `{ picks, remaining }`: up to `limit` issues with a `reason` each,
 * and how many more open issues are yours beyond those.
 */
export function pickFocus(issues, userId, { today = new Date(), limit = 3 } = {}) {
  if (userId == null) return { picks: [], remaining: 0 }

  const mine = issues
    .filter((issue) => issue.assigneeId === userId && issue.stateCategory !== 'done')
    .map((issue) => ({ issue, days: daysUntil(issue.dueDate, today) }))

  const key = ({ issue, days }) => [
    issue.overdue ? 0 : 1,
    issue.overdue ? (days ?? 0) : 0,
    PRIORITY_RANK[issue.priority] ?? 2,
    days ?? Number.MAX_SAFE_INTEGER,
    issue.stateCategory === 'in_progress' ? 0 : 1,
    -(issue.storyPoints || 0),
  ]

  mine.sort((a, b) => {
    const ka = key(a)
    const kb = key(b)
    for (let i = 0; i < ka.length; i += 1) if (ka[i] !== kb[i]) return ka[i] - kb[i]
    return a.issue.id - b.issue.id
  })

  return {
    picks: mine.slice(0, limit).map(({ issue, days }) => ({ issue, reason: focusReason(issue, days) })),
    remaining: Math.max(0, mine.length - limit),
  }
}
