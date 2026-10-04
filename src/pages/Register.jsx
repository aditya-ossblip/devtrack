import React from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import AuthShell from '../components/AuthShell.jsx'
import SignInPanel from '../components/SignInPanel.jsx'
import { useAuth } from '../state/AuthContext.jsx'

export default function Register() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()

  if (isAuthenticated) return <Navigate to="/" replace />

  return (
    <AuthShell>
      {/* A new account has no project yet, so it lands on the list rather than
          on a board that would have nothing to show. */}
      <SignInPanel mode="signup" onDone={() => navigate('/projects', { replace: true })} />
    </AuthShell>
  )
}
