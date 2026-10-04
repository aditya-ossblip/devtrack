import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { api, errorMessage, getToken, setToken, setUnauthorizedHandler } from '../api/client.js'
import { connectSocket, disconnectSocket } from '../api/socket.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // 'checking' until we know whether the stored token is still good — without
  // it the app flashes the login page on every reload.
  const [status, setStatus] = useState('checking')

  const clear = useCallback(() => {
    setToken(null)
    setUser(null)
    setStatus('signed-out')
    disconnectSocket()
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(clear)
    return () => setUnauthorizedHandler(null)
  }, [clear])

  useEffect(() => {
    const token = getToken()
    if (!token) {
      setStatus('signed-out')
      return undefined
    }

    let cancelled = false
    api
      .get('/auth/me')
      .then(({ data }) => {
        if (cancelled) return
        setUser(data.user)
        setStatus('signed-in')
        connectSocket(token)
      })
      .catch(() => {
        if (!cancelled) clear()
      })

    return () => {
      cancelled = true
    }
  }, [clear])

  const accept = useCallback((data) => {
    setToken(data.token)
    setUser(data.user)
    setStatus('signed-in')
    connectSocket(data.token)
  }, [])

  const login = useCallback(
    async (email, password) => {
      try {
        const { data } = await api.post('/auth/login', { email, password })
        accept(data)
        return { ok: true }
      } catch (error) {
        return { ok: false, error: errorMessage(error, 'Could not sign in. Try again.') }
      }
    },
    [accept]
  )

  const register = useCallback(
    async (payload) => {
      try {
        const { data } = await api.post('/auth/register', payload)
        accept(data)
        return { ok: true }
      } catch (error) {
        return { ok: false, error: errorMessage(error, 'Could not create your account.') }
      }
    },
    [accept]
  )

  /**
   * Trade a Google ID token for one of ours.
   *
   * The token is not stored and never becomes the session — the backend
   * verifies Google's signature on it, then issues a DevTrack token exactly
   * like a password sign-in would. Everything downstream is unaware Google
   * was involved.
   */
  const loginWithGoogle = useCallback(
    async (credential) => {
      try {
        const { data } = await api.post('/auth/google', { credential })
        accept(data)
        return { ok: true }
      } catch (error) {
        return { ok: false, error: errorMessage(error, 'Could not sign in with Google.') }
      }
    },
    [accept]
  )

  const value = useMemo(
    () => ({
      user,
      status,
      isAuthenticated: status === 'signed-in',
      isChecking: status === 'checking',
      login,
      loginWithGoogle,
      register,
      logout: clear,
      updateUser: setUser,
    }),
    [user, status, login, loginWithGoogle, register, clear]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
