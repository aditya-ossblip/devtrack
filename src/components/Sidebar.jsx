import React from 'react'
import { NavLink } from 'react-router-dom'

import { LogoMark } from './Logo.jsx'
import { useNotifications } from '../state/useNotifications.js'
import { useAuth } from '../state/AuthContext.jsx'
import { useProjects } from '../state/ProjectContext.jsx'

const PROJECT_NAV = [
  { to: '/board', label: 'Board', icon: '▦' },
  { to: '/backlog', label: 'Backlog', icon: '≡' },
  { to: '/files', label: 'Files', icon: '⇪' },
  { to: '/team', label: 'Team', icon: '◍' },
  { to: '/analytics', label: 'Reports', icon: '◔' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
]

const GLOBAL_NAV = [
  { to: '/projects', label: 'Projects', icon: '◈' },
  { to: '/my-tasks', label: 'My tasks', icon: '☑' },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  const { projects, projectId, selectProject } = useProjects()
  const { unread } = useNotifications()

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <LogoMark size={26} />
        <span>DevTrack</span>
      </div>

      {projects.length > 0 && (
        <div className="sidebar-project">
          <div className="sidebar-project-label">Project</div>
          <select
            className="sidebar-project-select"
            value={projectId ?? ''}
            onChange={(e) => selectProject(Number(e.target.value))}
            aria-label="Switch project"
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.key} · {project.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <nav className="sidebar-nav" aria-label="Workspace">
        {GLOBAL_NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `sidebar-nav-item${isActive ? ' is-active' : ''}`}
          >
            <span className="sidebar-nav-icon" aria-hidden="true">
              {item.icon}
            </span>
            {item.label}
            {item.to === '/my-tasks' && unread > 0 && (
              <span className="sidebar-nav-count">{unread}</span>
            )}
          </NavLink>
        ))}
      </nav>

      {projects.length > 0 && (
        <>
          <div className="sidebar-section-label">Current project</div>
          <nav className="sidebar-nav" aria-label="Project">
            {PROJECT_NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `sidebar-nav-item${isActive ? ' is-active' : ''}`}
              >
                <span className="sidebar-nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </>
      )}

      <div className="sidebar-footer">
        <div className="avatar">{user?.initials ?? '··'}</div>
        <div className="sidebar-footer-text">
          <div className="sidebar-footer-name">{user?.name ?? 'Signed out'}</div>
          <div className="sidebar-footer-role">{user?.role ?? ''}</div>
        </div>
        <button type="button" className="sidebar-signout" onClick={logout}>
          Sign out
        </button>
      </div>
    </aside>
  )
}
