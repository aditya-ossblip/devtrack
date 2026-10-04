import React from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import AuthShell from '../components/AuthShell.jsx'
import SignInPanel from '../components/SignInPanel.jsx'
import { useAuth } from '../state/AuthContext.jsx'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isAuthenticated } = useAuth()

  if (isAuthenticated) return <Navigate to={location.state?.from ?? '/'} replace />

  return (
    <AuthShell>
      <SignInPanel
        mode="signin"
        // Back to wherever RequireAuth bounced them from, or the board.
        onDone={() => navigate(location.state?.from ?? '/', { replace: true })}
      />
    </AuthShell>
  )
}
