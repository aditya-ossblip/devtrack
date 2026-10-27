import React, { useCallback, useEffect, useRef, useState } from 'react'

import { api, downloadFile, errorMessage } from '../api/client.js'
import Empty from '../components/Empty.jsx'
import ProjectEmpty from '../components/ProjectEmpty.jsx'
import Topbar from '../components/Topbar.jsx'
import { useAuth } from '../state/AuthContext.jsx'
import { useProjects } from '../state/ProjectContext.jsx'

/** 104857600 -> "100 MB", 5242 -> "0.01 MB" style, kept short for one line. */
function megabytes(bytes) {
  const mb = bytes / (1024 * 1024)
  if (mb >= 10 || Number.isInteger(mb)) return `${Math.round(mb)} MB`
  return `${mb.toFixed(1)} MB`
}

/**
 * Every file in the project, in one place.
 *
 * The thing this replaces is a group chat with a document in it somewhere
 * around last Tuesday. Files attached to a task show up here too, labelled
 * with the task — so you never have to remember which issue somebody put the
 * report on, which is the actual reason people give up and use Drive.
 */
export default function Files() {
  const { project, projectId, status: projectStatus } = useProjects()
  const { user } = useAuth()

  const [files, setFiles] = useState([])
  // `role` is not on the project list payload — it comes from the project
  // detail endpoint, which is the only thing that knows your role *here*.
  const [role, setRole] = useState('developer')
  const [meta, setMeta] = useState(null)
  // { used, limit, maxFileSize } in bytes: the project's share of the file space.
  const [usage, setUsage] = useState(null)
  const [scope, setScope] = useState('all')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [pending, setPending] = useState(0)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)
  // dragenter/dragleave fire for every child the pointer crosses, so a
  // boolean flickers. Counting entries against exits does not.
  const depth = useRef(0)

  const load = useCallback(async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const [fileRes, projectRes] = await Promise.all([
        api.get(`/projects/${projectId}/files`, {
          params: { perPage: 100, ...(scope === 'project' ? { scope: 'project' } : {}) },
        }),
        api.get(`/projects/${projectId}`),
      ])
      setFiles(fileRes.data.files)
      setMeta(fileRes.data.meta)
      setUsage(fileRes.data.usage ?? null)
      setRole(projectRes.data.role)
      setError('')
    } catch (err) {
      setError(errorMessage(err, 'Could not load the files.'))
    } finally {
      setLoading(false)
    }
  }, [projectId, scope])

  useEffect(() => {
    load()
  }, [load])

  const upload = useCallback(
    async (chosen) => {
      const list = Array.from(chosen || [])
      if (!list.length || !projectId) return

      setError('')
      setPending((n) => n + list.length)

      // One request per file, so a rejected one does not take the accepted
      // ones down with it — the server checks type and size per file.
      for (const file of list) {
        const body = new FormData()
        body.append('file', file)
        try {
          // No Content-Type header: axios has to set it to include the
          // multipart boundary, and naming it here strips that.
          const { data } = await api.post(`/projects/${projectId}/files`, body)
          setFiles((current) => [data.file, ...current])
          setUsage((u) => (u ? { ...u, used: u.used + data.file.size } : u))
        } catch (err) {
          setError(errorMessage(err, `Could not upload ${file.name}.`))
        } finally {
          setPending((n) => n - 1)
        }
      }
    },
    [projectId]
  )

  async function remove(file) {
    if (!window.confirm(`Delete ${file.filename}? This cannot be undone.`)) return
    try {
      await api.delete(`/attachments/${file.id}`)
      setFiles((current) => current.filter((f) => f.id !== file.id))
      setUsage((u) => (u ? { ...u, used: Math.max(u.used - file.size, 0) } : u))
    } catch (err) {
      setError(errorMessage(err, 'Could not delete that file.'))
    }
  }

  async function save(file) {
    try {
      await downloadFile(`/attachments/${file.id}`, file.filename)
    } catch (err) {
      setError(errorMessage(err, 'Could not download that file.'))
    }
  }

  if (projectStatus === 'empty') return <ProjectEmpty />

  return (
    <>
      <Topbar title="Files" subtitle={project?.name}>
        <button type="button" className="btn btn-primary" onClick={() => inputRef.current?.click()}>
          + Upload
        </button>
      </Topbar>

      <div className="app-content">
        {error && (
          <div className="banner banner--error" role="alert">
            <span>{error}</span>
            <button type="button" className="banner-action" onClick={load}>
              Retry
            </button>
          </div>
        )}

        <div
          className={`dropzone dropzone--page${dragging ? ' is-over' : ''}`}
          onDragEnter={(e) => {
            e.preventDefault()
            depth.current += 1
            setDragging(true)
          }}
          onDragOver={(e) => e.preventDefault()}
          onDragLeave={() => {
            depth.current -= 1
            if (depth.current <= 0) setDragging(false)
          }}
          onDrop={(e) => {
            e.preventDefault()
            depth.current = 0
            setDragging(false)
            upload(e.dataTransfer.files)
          }}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            hidden
            onChange={(e) => {
              upload(e.target.files)
              // Cleared so picking the same file twice still fires a change.
              e.target.value = ''
            }}
          />
          {pending > 0 ? (
            <span className="muted">
              Uploading {pending} file{pending === 1 ? '' : 's'}…
            </span>
          ) : (
            <>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => inputRef.current?.click()}>
                Choose files
              </button>
              <span className="muted">
                {' '}or drop them here — everyone on the project can download them
                {usage && (
                  <>
                    <br />
                    Up to {megabytes(usage.maxFileSize)} per file · {megabytes(usage.used)} of{' '}
                    {megabytes(usage.limit)} used
                  </>
                )}
              </span>
            </>
          )}
        </div>

        <div className="tabs" style={{ marginTop: 'var(--space-6)' }}>
          <button
            type="button"
            className={`tab${scope === 'all' ? ' is-active' : ''}`}
            onClick={() => setScope('all')}
          >
            Everything
          </button>
          <button
            type="button"
            className={`tab${scope === 'project' ? ' is-active' : ''}`}
            onClick={() => setScope('project')}
          >
            Not on a task
          </button>
          {meta?.total > 0 && (
            <span className="muted panel-action" style={{ fontSize: 12 }}>
              {meta.total} file{meta.total === 1 ? '' : 's'}
            </span>
          )}
        </div>

        {loading ? (
          <p className="muted">Loading…</p>
        ) : files.length === 0 ? (
          <Empty mark="⇪" title={scope === 'project' ? 'No project-level files' : 'No files yet'}>
            {scope === 'project'
              ? 'Files attached to a task live under Everything.'
              : 'Drop the report, the deck, the source archive. Anyone on the project can download them, any time.'}
          </Empty>
        ) : (
          <section className="panel">
            {files.map((file) => (
              <div className="list-row" key={file.id}>
                <span className="attachment-kind" aria-hidden="true">
                  {extensionOf(file.filename)}
                </span>
                <button
                  type="button"
                  className="list-main"
                  style={{ textAlign: 'left' }}
                  onClick={() => save(file)}
                >
                  <div className="list-title">{file.filename}</div>
                  <div className="list-sub">
                    {file.humanSize}
                    {file.uploaderName ? ` · ${file.uploaderName}` : ''} · {file.time}
                  </div>
                </button>

                {/* What the file is *for*. A Drive folder cannot tell you this. */}
                {file.issueKey ? (
                  <span className="file-context" title={file.issueTitle}>
                    <span className="issue-key">{file.issueKey}</span>
                  </span>
                ) : (
                  <span className="file-context muted">Project file</span>
                )}

                {/* The server enforces this too; hiding it just avoids offering
                    a button that answers 403. */}
                {(file.uploaderId === user?.id || role === 'manager' || role === 'admin') && (
                  <button
                    type="button"
                    className="btn-icon"
                    onClick={() => remove(file)}
                    aria-label={`Delete ${file.filename}`}
                    title="Delete"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </section>
        )}
      </div>
    </>
  )
}

function extensionOf(filename) {
  const parts = String(filename || '').split('.')
  return parts.length > 1 ? parts.pop().slice(0, 4).toUpperCase() : 'FILE'
}
