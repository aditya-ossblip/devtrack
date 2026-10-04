import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../state/AuthContext.jsx'

export default function RequireAuth({ children }) {
  const { isAuthenticated, isChecking } = useAuth()
  const location = useLocation()

  if (isChecking) {
    return (
      <div className="app-loading" role="status">
        <div className="spinner" />
        <span>Loading your workspace…</span>
      </div>
    )
  }

  if (!isAuthenticated) {
    // `state.from` lets Login send them back where they were headed.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return children
}
