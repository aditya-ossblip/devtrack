import React from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import AppLayout from './components/AppLayout.jsx'
import RequireAuth from './components/RequireAuth.jsx'
import Analytics from './pages/Analytics.jsx'
import Backlog from './pages/Backlog.jsx'
import Board from './pages/Board.jsx'
import Files from './pages/Files.jsx'
import Login from './pages/Login.jsx'
import MyTasks from './pages/MyTasks.jsx'
import Projects from './pages/Projects.jsx'
import Register from './pages/Register.jsx'
import Settings from './pages/Settings.jsx'
import Team from './pages/Team.jsx'
import { AuthProvider } from './state/AuthContext.jsx'
import { ProjectProvider } from './state/ProjectContext.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Everything below the layout is signed-in only. Adding a route
              here inherits the guard rather than re-checking a boolean. */}
          <Route
            element={
              <RequireAuth>
                <ProjectProvider>
                  <AppLayout />
                </ProjectProvider>
              </RequireAuth>
            }
          >
            <Route path="/" element={<Navigate to="/board" replace />} />
            <Route path="/board" element={<Board />} />
            <Route path="/backlog" element={<Backlog />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/my-tasks" element={<MyTasks />} />
            <Route path="/files" element={<Files />} />
            <Route path="/team" element={<Team />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/settings" element={<Settings />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
