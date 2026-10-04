import React, { useState } from 'react'
import { Link } from 'react-router-dom'

import GoogleButton from './GoogleButton.jsx'
import { LogoMark } from './Logo.jsx'
import { useAuth } from '../state/AuthContext.jsx'

/**
 * The whole of sign-in and sign-up.
 *
 * Google is the only way in. With Google holding the identity there is no
 * meaningful difference between the two actions — it either finds the account
 * or creates it — so this is one component and the two routes differ only in
 * what they say.
 *
 * The password form still exists, but only appears when Google *cannot* work:
 * no client ID on the server, or their script blocked. Shipping a screen whose
 * single control is guaranteed to fail is how a team locks itself out of its
 * own app, and the demo account has to stay reachable while Google is being
 * set up.
 */
export default function SignInPanel({ mode = 'signin', onDone }) {
  const { login, loginWithGoogle, isChecking } = useAuth()

  const [status, setStatus] = useState('loading')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const signingUp = mode === 'signup'
  const needsFallback = status === 'unconfigured' || status === 'unreachable'
  const serverDown = status === 'server-down'

  async function handleGoogle(credential) {
    setError('')
    setBusy(true)
    const result = await loginWithGoogle(credential)
    setBusy(false)
    if (result.ok) onDone()
    else setError(result.error)
  }

  async function handlePassword(e) {
    e.preventDefault()
    setError('')
    if (!email || !password) {
      setError('Enter your email and password.')
      return
    }
    setBusy(true)
    const result = await login(email, password)
    setBusy(false)
    if (result.ok) onDone()
    else setError(result.error)
  }

  return (
    <div className="auth-form">
      <LogoMark size={38} className="auth-mark" />
      <h1 className="auth-title">
        {signingUp ? 'Create your account' : 'Welcome to DevTrack'}
      </h1>
      <p className="auth-lede">
        {signingUp
          ? 'Sign up with Google. Your name and email come across; nothing else does.'
          : 'Sign in with the Google account your team knows you by.'}
      </p>

      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}

      <GoogleButton
        onCredential={handleGoogle}
        onStatus={setStatus}
        text={signingUp ? 'signup_with' : 'continue_with'}
      />

      {status === 'loading' && <p className="auth-waiting">Loading sign-in…</p>}

      {/* Our own API did not answer. A password form here would only fail
          with a vaguer message, so it is not shown until the server is back. */}
      {serverDown && (
        <div className="auth-fallback">
          <p className="auth-fallback-note">
            <b>Can’t reach the DevTrack server.</b> It may be restarting —
            try again in a moment.
            {import.meta.env.DEV && (
              <>
                {' '}Running locally? Start the API with <code>npm run api</code>{' '}
                in the left terminal.
              </>
            )}
          </p>
          <button
            className="btn btn-primary auth-submit"
            type="button"
            onClick={() => window.location.reload()}
          >
            Try again
          </button>
        </div>
      )}

      {needsFallback && (
        <div className="auth-fallback">
          <p className="auth-fallback-note">
            {status === 'unconfigured' ? (
              <>
                <b>Google sign-in is not set up on this server yet.</b> Add a
                client ID to <code>backend/.env</code> as{' '}
                <code>GOOGLE_CLIENT_ID</code> and restart the API. Until then,
                sign in with a password.
              </>
            ) : (
              <>
                <b>Google could not be reached.</b> You are offline, or a
                blocker is stopping their script. Sign in with a password
                instead.
              </>
            )}
          </p>

          <form onSubmit={handlePassword}>
            <div className="field">
              <label className="field-label" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                disabled={busy || isChecking}
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                disabled={busy || isChecking}
              />
            </div>
            <button
              className="btn btn-primary auth-submit"
              type="submit"
              disabled={busy || isChecking}
            >
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>
      )}

      <p className="auth-switch">
        {signingUp ? (
          <>
            Already here? <Link to="/login">Sign in</Link>
          </>
        ) : (
          <>
            First time? <Link to="/register">Create an account</Link>
          </>
        )}
      </p>

      <p className="auth-legal">
        DevTrack stores your name, your email and the work you are assigned
        &mdash; nothing else. It never asks Google for anything beyond that, and
        never posts anywhere on your behalf.
      </p>
    </div>
  )
}
