import React, { useEffect, useRef } from 'react'

import { api } from '../api/client.js'

const GSI_SRC = 'https://accounts.google.com/gsi/client'

/** Load Google's script once, however many buttons ask for it. */
let scriptPromise = null
function loadGsi() {
  if (scriptPromise) return scriptPromise
  scriptPromise = new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve()
      return
    }
    const el = document.createElement('script')
    el.src = GSI_SRC
    el.async = true
    el.defer = true
    el.onload = () => resolve()
    el.onerror = () => reject(new Error('blocked'))
    document.head.appendChild(el)
  })
  return scriptPromise
}

/**
 * "Sign in with Google".
 *
 * Reports what happened through `onStatus` so the page around it can decide
 * what to show instead: 'ready', 'unconfigured' (no client ID on the server),
 * 'server-down' (our own API did not answer) or 'unreachable' (Google's script
 * was blocked, or the machine is offline). The first request goes to our
 * server, not Google — so when it fails, blaming Google sends people looking
 * in the wrong place. Sign-in is Google-only by
 * design, but a page that can only ever fail is not a design — so the caller
 * needs to know which of those it is.
 *
 * The button is drawn by Google's own script and cannot be restyled; their
 * branding terms require it. `filled_black` is the closest of their themes to
 * this palette.
 *
 * What comes back is an ID token — not a password, not an access token. It
 * goes straight to our backend, which verifies Google's signature on it
 * before trusting a single field inside.
 */
export default function GoogleButton({ onCredential, onStatus, text = 'continue_with' }) {
  const holder = useRef(null)
  // Hold the latest callbacks without re-running the effect, which would make
  // Google draw a second button on top of the first.
  const handlers = useRef({ onCredential, onStatus })
  handlers.current = { onCredential, onStatus }

  useEffect(() => {
    let cancelled = false
    const report = (status) => {
      if (!cancelled) handlers.current.onStatus?.(status)
    }

    async function start() {
      let clientId = ''
      try {
        const { data } = await api.get('/auth/config')
        clientId = data.googleClientId || ''
      } catch {
        report('server-down')
        return
      }
      if (cancelled) return
      if (!clientId) {
        report('unconfigured')
        return
      }

      try {
        await loadGsi()
      } catch {
        report('unreachable')
        return
      }
      if (cancelled || !holder.current) return

      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: (response) => handlers.current.onCredential?.(response.credential),
      })

      window.google.accounts.id.renderButton(holder.current, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        shape: 'rectangular',
        text,
        logo_alignment: 'center',
        width: holder.current.clientWidth || 340,
      })

      report('ready')
    }

    start()
    return () => {
      cancelled = true
    }
  }, [text])

  return <div className="auth-google" ref={holder} />
}
