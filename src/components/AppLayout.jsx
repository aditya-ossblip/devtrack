import React from 'react'
import { Outlet } from 'react-router-dom'

import Sidebar from './Sidebar.jsx'

export default function AppLayout() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <Outlet />
      </div>
    </div>
  )
}
