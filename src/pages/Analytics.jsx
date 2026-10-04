import React, { useCallback, useEffect, useState } from 'react'

import { api, errorMessage } from '../api/client.js'
import ActivityFeed from '../components/ActivityFeed.jsx'
import Empty from '../components/Empty.jsx'
import ProjectEmpty from '../components/ProjectEmpty.jsx'
import Topbar from '../components/Topbar.jsx'
import { BarList, LineChart, SplitBarList } from '../components/charts.jsx'
import { priorityLabel, typeLabel } from '../components/issueMeta.jsx'
import { useProjects } from '../state/ProjectContext.jsx'

const CATEGORY_COLOR = {
  todo: 'var(--cat-todo)',
  in_progress: 'var(--cat-progress)',
  done: 'var(--cat-done)',
}

function shortDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export default function Analytics() {
  const { project, projectId, status: projectStatus } = useProjects()
  const [data, setData] = useState(null)
  const [burndown, setBurndown] = useState(null)
  const [velocity, setVelocity] = useState([])
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (!projectId) return
    try {
      const [analyticsRes, burndownRes, velocityRes] = await Promise.all([
        api.get(`/projects/${projectId}/analytics`),
        api.get(`/projects/${projectId}/burndown`),
        api.get(`/projects/${projectId}/velocity`),
      ])
      setData(analyticsRes.data)
      setBurndown(burndownRes.data)
      setVelocity(velocityRes.data.sprints)
      setError('')
    } catch (err) {
      setError(errorMessage(err, 'Could not load reports.'))
    }
  }, [projectId])

  useEffect(() => {
    load()
  }, [load])

  if (projectStatus === 'empty') return <ProjectEmpty />

  if (!data) {
    return (
      <>
        <Topbar title="Reports" subtitle={project?.name} />
        <div className="app-content">
          {error ? (
            <div className="banner banner--error" role="alert">
              <span>{error}</span>
              <button type="button" className="banner-action" onClick={load}>
                Retry
              </button>
            </div>
          ) : (
            <div className="app-loading" style={{ minHeight: 200 }}>
              <div className="spinner" />
            </div>
          )}
        </div>
      </>
    )
  }

  const { totals } = data
  const hasIssues = totals.issues > 0

  return (
    <>
      <Topbar title="Reports" subtitle={project?.name} />

      <div className="app-content">
        {!hasIssues ? (
          <div className="panel">
            <Empty mark="◔" title="No data yet">
              Reports fill in as issues move through the board. Create a few and come back.
            </Empty>
          </div>
        ) : (
          <>
            <div className="stat-row">
              <div className="stat">
                <div className="stat-label">Completion</div>
                <div className="stat-value">{totals.completionPct}%</div>
                <div className="stat-note stat-note--neutral">
                  {totals.done} of {totals.issues} issues
                </div>
                <div className="stat-bar">
                  <span style={{ width: `${totals.completionPct}%` }} />
                </div>
              </div>
              <div className="stat">
                <div className="stat-label">Open issues</div>
                <div className="stat-value">{totals.issues - totals.done}</div>
                <div className={`stat-note stat-note--${totals.overdue ? 'danger' : 'neutral'}`}>
                  {totals.overdue ? `${totals.overdue} overdue` : 'None overdue'}
                </div>
              </div>
              <div className="stat">
                <div className="stat-label">Story points</div>
                <div className="stat-value">{totals.storyPointsDone}</div>
                <div className="stat-note stat-note--neutral">of {totals.storyPoints} delivered</div>
              </div>
              <div className="stat">
                <div className="stat-label">Team</div>
                <div className="stat-value">{totals.members}</div>
                <div className="stat-note stat-note--neutral">
                  {data.byAssignee.filter((row) => row.name !== 'Unassigned').length} with work
                </div>
              </div>
            </div>

            <div className="chart-grid">
              <section className="panel">
                <div className="panel-head">
                  <h2 className="panel-title">Issues by status</h2>
                </div>
                <div className="panel-body">
                  <BarList
                    rows={data.byState.map((row) => ({
                      label: row.name,
                      value: row.count,
                      category: row.category,
                    }))}
                    colorFor={(row) => CATEGORY_COLOR[row.category] ?? 'var(--chart-1)'}
                  />
                </div>
              </section>

              <section className="panel">
                <div className="panel-head">
                  <h2 className="panel-title">Workload by person</h2>
                </div>
                <div className="panel-body">
                  <SplitBarList
                    rows={data.byAssignee.map((row) => ({
                      label: row.name,
                      total: row.total,
                      done: row.done,
                    }))}
                    emptyText="Nothing is assigned yet."
                  />
                </div>
              </section>

              <section className="panel">
                <div className="panel-head">
                  <h2 className="panel-title">By priority</h2>
                </div>
                <div className="panel-body">
                  <BarList
                    rows={data.byPriority.map((row) => ({
                      label: priorityLabel(row.name),
                      value: row.count,
                    }))}
                  />
                </div>
              </section>

              <section className="panel">
                <div className="panel-head">
                  <h2 className="panel-title">By type</h2>
                </div>
                <div className="panel-body">
                  <BarList
                    rows={data.byType.map((row) => ({
                      label: typeLabel(row.name),
                      value: row.count,
                    }))}
                  />
                </div>
              </section>

              <section className="panel">
                <div className="panel-head">
                  <h2 className="panel-title">Completed per day</h2>
                  <span className="muted panel-action" style={{ fontSize: 12 }}>
                    Last 14 days
                  </span>
                </div>
                <div className="panel-body">
                  <LineChart
                    labels={data.completedByDay.map((row) => shortDate(row.date))}
                    yLabel="Issues completed per day"
                    series={[
                      {
                        label: 'Completed',
                        color: 'var(--chart-1)',
                        points: data.completedByDay.map((row) => ({ y: row.count })),
                      },
                    ]}
                  />
                </div>
              </section>

              <section className="panel">
                <div className="panel-head">
                  <h2 className="panel-title">Sprint burndown</h2>
                  {burndown?.sprint && (
                    <span className="muted panel-action" style={{ fontSize: 12 }}>
                      {burndown.sprint.name}
                    </span>
                  )}
                </div>
                <div className="panel-body">
                  {burndown?.points?.length ? (
                    <LineChart
                      labels={burndown.points.map((row) => shortDate(row.date))}
                      yLabel="Story points remaining"
                      series={[
                        {
                          label: 'Ideal',
                          color: 'var(--chart-ink)',
                          dashed: true,
                          points: burndown.points.map((row) => ({ y: row.ideal })),
                        },
                        {
                          label: 'Remaining',
                          color: 'var(--chart-1)',
                          points: burndown.points.map((row) => ({ y: row.remaining })),
                        },
                      ]}
                    />
                  ) : (
                    <p className="muted">
                      Start a sprint with dates and story points, and the burndown appears here.
                    </p>
                  )}
                </div>
              </section>

              {velocity.length > 0 && (
                <section className="panel">
                  <div className="panel-head">
                    <h2 className="panel-title">Velocity</h2>
                    <span className="muted panel-action" style={{ fontSize: 12 }}>
                      Completed sprints
                    </span>
                  </div>
                  <div className="panel-body">
                    <SplitBarList
                      rows={velocity.map((sprint) => ({
                        label: sprint.name,
                        total: sprint.committed,
                        done: sprint.completed,
                      }))}
                    />
                  </div>
                </section>
              )}

              {/* The numbers above say what the state of the project is. This
                  says what people actually did to get it there — the question
                  every stand-up opens with. */}
              <section className="panel">
                <div className="panel-head">
                  <h2 className="panel-title">Recent activity</h2>
                  <span className="muted panel-action" style={{ fontSize: 12 }}>
                    Everything, newest first
                  </span>
                </div>
                <div className="panel-body">
                  <ActivityFeed
                    source={`/projects/${projectId}/activity`}
                    showSubject
                    emptyText="Nothing has happened in this project yet."
                  />
                </div>
              </section>
            </div>
          </>
        )}
      </div>
    </>
  )
}
