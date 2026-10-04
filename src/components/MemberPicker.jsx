import React, { useEffect, useRef, useState } from 'react'

import { api } from '../api/client.js'

/**
 * Add someone by their email address.
 *
 * Not a search over everyone, on purpose. DevTrack is signed up for by people
 * who do not know each other, and a substring search would let anyone signed
 * in page through the whole user directory or check whether a given address
 * has an account. The server only answers a complete address, so this asks
 * for one.
 *
 * The cost is real — you have to know the address rather than half-remember a
 * name — and it is the right trade once the accounts are not all your
 * colleagues.
 */
export default function MemberPicker({ selected = [], onChange, exclude = [] }) {
  const [term, setTerm] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const timer = useRef(null)

  const looksComplete = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(term.trim())

  useEffect(() => {
    // Nothing is sent until the address is whole — a partial one would be
    // refused anyway, and not asking is better than asking and being told no.
    if (!looksComplete) {
      setResults([])
      setLoading(false)
      return undefined
    }

    clearTimeout(timer.current)
    timer.current = setTimeout(async () => {
      setLoading(true)
      try {
        const { data } = await api.get('/users', { params: { q: term.trim() } })
        setResults(data.users)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 220)

    return () => clearTimeout(timer.current)
  }, [term, looksComplete])

  const excluded = new Set(exclude)
  const selectedIds = new Set(selected.map((u) => u.id))
  const visible = results.filter((user) => !excluded.has(user.id))

  function toggle(user) {
    onChange(
      selectedIds.has(user.id)
        ? selected.filter((u) => u.id !== user.id)
        : [...selected, user]
    )
  }

  return (
    <div>
      <input
        className="input"
        value={term}
        onChange={(e) => setTerm(e.target.value)}
        type="email"
        placeholder="their.email@example.com"
        aria-label="Email address of the person to add"
      />

      <div className="picker-results" style={{ marginTop: 8 }}>
        {loading && visible.length === 0 && <div className="picker-row muted">Looking…</div>}

        {!loading && visible.length === 0 && (
          <div className="picker-row muted">
            {!term
              ? 'Type the full email address of the person you want to add.'
              : !looksComplete
                ? 'Keep going — this needs a complete email address.'
                : `No account here uses ${term.trim()}. They need to sign up first.`}
          </div>
        )}

        {visible.map((user) => (
          <button
            type="button"
            key={user.id}
            className={`picker-row${selectedIds.has(user.id) ? ' is-selected' : ''}`}
            onClick={() => toggle(user)}
            aria-pressed={selectedIds.has(user.id)}
          >
            <div className="avatar avatar-sm">{user.initials}</div>
            <div className="grow">
              <div className="picker-name">{user.name}</div>
              <div className="picker-meta">{user.title || 'No job title set'}</div>
            </div>
            {selectedIds.has(user.id) && <span className="picker-check">✓</span>}
          </button>
        ))}
      </div>

      {selected.length > 0 && (
        <div className="picker-selected">
          {selected.map((user) => (
            <span className="picker-tag" key={user.id}>
              <span className="avatar avatar-sm">{user.initials}</span>
              {user.name}
              <button type="button" onClick={() => toggle(user)} aria-label={`Remove ${user.name}`}>
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
