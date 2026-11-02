import React, { useEffect, useState } from 'react'

import { API_ORIGIN } from '../api/client.js'
import { LogoMark } from './Logo.jsx'

/**
 * Wait for the API before showing the app.
 *
 * On the free hosting plan the API goes to sleep after 15 quiet minutes and
 * takes up to a minute to wake. Without this, the first visitor after a quiet
 * spell would see sign-in fail or be signed out. Instead they see a short
 * "waking up" screen while this keeps asking, then the app as normal.
 *
 * Only when the API is on another address (the live site). In development the
 * API is on this machine and never sleeps, so this renders straight through.
 */
const SHOW_AFTER_MS = 1500 // a normal answer comes back faster than this
const GIVE_UP_AFTER_MS = 150_000

export default function ServerWake({ children }) {
  const [state, setState] = useState(API_ORIGIN ? 'checking' : 'ready')

  useEffect(() => {
    if (!API_ORIGIN) return undefined
    let cancelled = false
    const started = Date.now()
    const slow = setTimeout(() => !cancelled && setState((s) => (s === 'checking' ? 'waking' : s)), SHOW_AFTER_MS)

    async function poll() {
      while (!cancelled) {
        try {
          const response = await fetch(`${API_ORIGIN}/api/health`, { cache: 'no-store' })
          if (response.ok) {
            if (!cancelled) setState('ready')
            return
          }
        } catch {
          /* still asleep, or the network blinked: ask again */
        }
        if (Date.now() - started > GIVE_UP_AFTER_MS) {
          if (!cancelled) setState('down')
          return
        }
        await new Promise((resolve) => setTimeout(resolve, 3000))
      }
    }

    poll()
    return () => {
      cancelled = true
      clearTimeout(slow)
    }
  }, [])

  if (state === 'ready') return children
  if (state === 'checking') return null

  return (
    <div className="server-wake" role="status" aria-live="polite">
      <LogoMark size={38} />
      {state === 'waking' ? (
        <>
          <h1>Waking up the server…</h1>
          <p>DevTrack sleeps when nobody is using it. This takes up to a minute, once.</p>
          <div className="server-wake-bar" aria-hidden="true" />
        </>
      ) : (
        <>
          <h1>DevTrack is not answering</h1>
          <p>The server did not wake up. Try again in a few minutes.</p>
          <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
            Try again
          </button>
        </>
      )}
    </div>
  )
}
