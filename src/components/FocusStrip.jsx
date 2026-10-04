import React from 'react'

import { PriorityMark, TypeMark } from './issueMeta.jsx'

const COUNT_WORDS = ['', 'one thing', 'two', 'three']

/**
 * "Your three for today" - the top of the board.
 *
 * What to work on next, each with the reason it was picked, so the ranking is
 * never a mystery. The switch beside it decides whether the board underneath
 * dims everyone else's cards (Just me) or shows them all (Everyone).
 */
export default function FocusStrip({ picks, remaining, mode, onMode, onOpen, firstName, othersDimmed = 0 }) {
  const heading = picks.length
    ? `Your ${COUNT_WORDS[picks.length] ?? picks.length} for today${firstName ? `, ${firstName}` : ''}`
    : `Nothing on your plate${firstName ? `, ${firstName}` : ''}`

  return (
    <section className="focus-strip" aria-label="Your focus for today">
      <header className="focus-head">
        <h2 className="focus-title">{heading}</h2>
        <span className="focus-hint" aria-live="polite">
          {mode === 'me'
            ? `Board below: your cards, ${othersDimmed} other${othersDimmed === 1 ? '' : 's'} dimmed`
            : 'Board below: everyone\'s cards'}
        </span>
        <div className="seg" role="group" aria-label="Whose cards to highlight on the board">
          <button type="button" aria-pressed={mode === 'me'} onClick={() => onMode('me')}>
            Just me
          </button>
          <button type="button" aria-pressed={mode === 'all'} onClick={() => onMode('all')}>
            Everyone
          </button>
        </div>
      </header>

      {picks.length > 0 ? (
        <div className="focus-cards">
          {picks.map(({ issue, reason }, index) => (
            <button
              type="button"
              key={issue.id}
              className={`focus-card${issue.overdue ? ' is-overdue' : ''}`}
              onClick={() => onOpen(issue)}
              aria-label={`${index + 1}. ${issue.key}: ${issue.title}. ${reason}`}
            >
              <span className="focus-num" aria-hidden="true">{index + 1}</span>
              <span className="focus-card-title">{issue.title}</span>
              <span className="focus-reason">{reason}</span>
              <span className="focus-meta">
                <TypeMark type={issue.type} />
                <span className="issue-key">{issue.key}</span>
                <PriorityMark priority={issue.priority} />
                {issue.stateName && <span className="focus-state">{issue.stateName}</span>}
              </span>
            </button>
          ))}
        </div>
      ) : (
        <p className="focus-empty">
          Nothing is assigned to you right now. Pick something from <b>To do</b> and assign it to
          yourself, or switch to <b>Everyone</b> to see the whole board.
        </p>
      )}

      {remaining > 0 && (
        <p className="focus-more">
          + {remaining} more of yours on the board below
        </p>
      )}
    </section>
  )
}
