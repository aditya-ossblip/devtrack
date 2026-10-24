import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import GoogleButton from './GoogleButton.jsx'
import { LogoMark } from './Logo.jsx'
import { useAuth } from '../state/AuthContext.jsx'
import { getAuthConfig } from '../state/authConfig.js'

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
  const { login, register, loginWithGoogle, isChecking } = useAuth()

  const [status, setStatus] = useState('loading')
  const [statusDetail, setStatusDetail] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  // Whether this server accepts email-and-password accounts at all. Off on
  // the live site, where Google is the only way in; null until known.
  const [passwordSignIn, setPasswordSignIn] = useState(null)

  useEffect(() => {
    let cancelled = false
    getAuthConfig()
      .then((config) => !cancelled && setPasswordSignIn(config.passwordSignIn))
      .catch(() => {}) // the Google button reports the server being down
    return () => {
      cancelled = true
    }
  }, [])

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
    // On the sign-up page this form creates the account. It used to sign in
    // here too, so without Google nobody could register at all — every new
    // address was rejected as a wrong password.
    if (signingUp && !name.trim()) {
      setError('Enter your name.')
      return
    }
    if (!email || !password) {
      setError('Enter your email and password.')
      return
    }
    if (signingUp && password.length < 8) {
      setError('Use a password of at least 8 characters.')
      return
    }
    setBusy(true)
    const result = signingUp
      ? await register({ name: name.trim(), email, password })
      : await login(email, password)
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
        onStatus={(next, detail) => {
          setStatus(next)
          setStatusDetail(detail)
        }}
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
                {/* Something answered, but it was not Flask: another
                    program holds the port the dev proxy points at. */}
                {statusDetail && statusDetail !== 502 && statusDetail !== 504 && (
                  <>
                    {' '}The API address answered with HTTP {statusDetail}, so
                    another program may be using its port — see
                    {' '}<code>vite.config.js</code>.
                  </>
                )}
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

      {needsFallback && passwordSignIn === false && (
        <div className="auth-fallback">
          <p className="auth-fallback-note">
            {status === 'unconfigured' ? (
              <>
                <b>Sign-in is not available right now.</b> Google sign-in has
                not been set up on this server yet.
              </>
            ) : (
              <>
                <b>Google could not be reached.</b> You may be offline, or an
                ad or tracker blocker is stopping Google&rsquo;s sign-in. Allow
                it for this site and try again.
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

      {needsFallback && passwordSignIn && (
        <div className="auth-fallback">
          <p className="auth-fallback-note">
            {status === 'unconfigured' ? (
              <>
                <b>Google sign-in is not set up on this server yet.</b> Add a
                client ID to <code>backend/.env</code> as{' '}
                <code>GOOGLE_CLIENT_ID</code> and restart the API. Until then,{' '}
                {signingUp ? 'create an account with a password.' : 'sign in with a password.'}
              </>
            ) : (
              <>
                <b>Google could not be reached.</b> You are offline, or a
                blocker is stopping their script.{' '}
                {signingUp ? 'Create an account with a password instead.' : 'Sign in with a password instead.'}
              </>
            )}
          </p>

          <form onSubmit={handlePassword}>
            {signingUp && (
              <div className="field">
                <label className="field-label" htmlFor="name">
                  Name
                </label>
                <input
                  id="name"
                  type="text"
                  className="input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoComplete="name"
                  disabled={busy || isChecking}
                />
              </div>
            )}
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
                autoComplete={signingUp ? 'new-password' : 'current-password'}
                disabled={busy || isChecking}
              />
              {signingUp && <p className="field-hint">At least 8 characters.</p>}
            </div>
            <button
              className="btn btn-primary auth-submit"
              type="submit"
              disabled={busy || isChecking}
            >
              {busy
                ? signingUp ? 'Creating your account…' : 'Signing in…'
                : signingUp ? 'Create account' : 'Sign in'}
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
