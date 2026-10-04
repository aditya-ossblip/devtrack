import React from 'react'
import { useNavigate } from 'react-router-dom'

import Empty from './Empty.jsx'
import Topbar from './Topbar.jsx'

/** Shown wherever a page needs a project and there isn't one yet. */
export default function ProjectEmpty() {
  const navigate = useNavigate()

  return (
    <>
      <Topbar title="Welcome to DevTrack" />
      <div className="app-content">
        <Empty
          mark="◈"
          title="No projects yet"
          action={
            <button type="button" className="btn btn-primary" onClick={() => navigate('/projects')}>
              Create your first project
            </button>
          }
        >
          A project holds a board, a backlog and a team. Create one to get started — you can
          invite the rest of your team while you set it up.
        </Empty>
      </div>
    </>
  )
}
