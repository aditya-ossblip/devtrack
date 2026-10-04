import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { api } from '../api/client.js'
import { useAuth } from './AuthContext.jsx'

const ProjectContext = createContext(null)
const LAST_PROJECT_KEY = 'devtrack.lastProject'

/**
 * Which project the app is looking at, shared by every page.
 *
 * The choice is remembered per browser so a reload lands you back where you
 * were, and falls back to the first project you can see.
 */
export function ProjectProvider({ children }) {
  const { isAuthenticated } = useAuth()
  const [projects, setProjects] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [status, setStatus] = useState('loading')

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/projects')
      setProjects(data.projects)
      setStatus(data.projects.length ? 'ready' : 'empty')

      setActiveId((current) => {
        if (current && data.projects.some((p) => p.id === current)) return current
        let remembered = null
        try {
          remembered = Number(localStorage.getItem(LAST_PROJECT_KEY)) || null
        } catch {
          /* storage unavailable */
        }
        if (remembered && data.projects.some((p) => p.id === remembered)) return remembered
        return data.projects[0]?.id ?? null
      })
    } catch {
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    if (isAuthenticated) load()
  }, [isAuthenticated, load])

  const selectProject = useCallback((id) => {
    setActiveId(id)
    try {
      localStorage.setItem(LAST_PROJECT_KEY, String(id))
    } catch {
      /* storage unavailable */
    }
  }, [])

  const project = useMemo(
    () => projects.find((p) => p.id === activeId) ?? null,
    [projects, activeId]
  )

  const value = useMemo(
    () => ({ projects, project, projectId: activeId, status, selectProject, reload: load }),
    [projects, project, activeId, status, selectProject, load]
  )

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
}

export function useProjects() {
  const context = useContext(ProjectContext)
  if (!context) throw new Error('useProjects must be used inside <ProjectProvider>')
  return context
}
