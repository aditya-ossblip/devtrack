import React, { useCallback, useEffect, useRef, useState } from 'react'

import { api, downloadFile, errorMessage } from '../api/client.js'
import { useAuth } from '../state/AuthContext.jsx'

/**
 * Files attached to one issue.
 *
 * Uploads go one at a time rather than in a single request, so a rejected file
 * in the middle of a batch does not take the accepted ones down with it — the
 * server checks the extension and the size per file, and a batch endpoint
 * would have to either fail wholesale or report partial success in a shape
 * every caller then has to unpack.
 */
export default function Attachments({ issueId, canManage, onChanged }) {
  const { user } = useAuth()
  const [files, setFiles] = useState([])
  const [error, setError] = useState('')
  const [pending, setPending] = useState(0)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)
  // dragenter/dragleave fire for every child element the pointer crosses, so
  // a boolean flickers. Counting entries against exits does not.
  const depth = useRef(0)

  useEffect(() => {
    let cancelled = false
    api
      .get(`/issues/${issueId}/attachments`)
      .then(({ data }) => {
        if (!cancelled) setFiles(data.attachments)
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err, 'Could not load the attachments.'))
      })
    return () => {
      cancelled = true
    }
  }, [issueId])

  const upload = useCallback(
    async (chosen) => {
      const list = Array.from(chosen || [])
      if (!list.length) return

      setError('')
      setPending((n) => n + list.length)

      for (const file of list) {
        const body = new FormData()
        body.append('file', file)
        try {
          // No Content-Type header on purpose: axios has to set it so it can
          // include the multipart boundary, and naming it here strips that.
          const { data } = await api.post(`/issues/${issueId}/attachments`, body)
          setFiles((current) => [...current, data.attachment])
          onChanged?.()
        } catch (err) {
          setError(errorMessage(err, `Could not upload ${file.name}.`))
        } finally {
          setPending((n) => n - 1)
        }
      }
    },
    [issueId, onChanged]
  )

  async function remove(attachment) {
    if (!window.confirm(`Delete ${attachment.filename}? This cannot be undone.`)) return
    try {
      await api.delete(`/attachments/${attachment.id}`)
      setFiles((current) => current.filter((f) => f.id !== attachment.id))
      onChanged?.()
    } catch (err) {
      setError(errorMessage(err, 'Could not delete that file.'))
    }
  }

  async function save(attachment) {
    try {
      await downloadFile(`/attachments/${attachment.id}`, attachment.filename)
    } catch (err) {
      setError(errorMessage(err, 'Could not download that file.'))
    }
  }

  function onDrop(e) {
    e.preventDefault()
    depth.current = 0
    setDragging(false)
    upload(e.dataTransfer.files)
  }

  return (
    <div className="attachments">
      {error && (
        <div className="banner banner--error" role="alert">
          {error}
        </div>
      )}

      {files.map((file) => {
        const mine = file.uploaderId === user?.id
        return (
          <div className="attachment" key={file.id}>
            <span className="attachment-kind" aria-hidden="true">
              {extensionOf(file.filename)}
            </span>
            <button type="button" className="attachment-main" onClick={() => save(file)}>
              <span className="attachment-name">{file.filename}</span>
              <span className="attachment-meta">
                {file.humanSize}
                {file.uploaderName ? ` · ${file.uploaderName}` : ''} · {file.time}
              </span>
            </button>
            {(mine || canManage) && (
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
        )
      })}

      <div
        className={`dropzone${dragging ? ' is-over' : ''}`}
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
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          onChange={(e) => {
            upload(e.target.files)
            // Clearing it means picking the same file twice in a row still
            // fires a change event.
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
            <span className="muted"> or drop them here</span>
          </>
        )}
      </div>
    </div>
  )
}

function extensionOf(filename) {
  const parts = String(filename || '').split('.')
  return parts.length > 1 ? parts.pop().slice(0, 4).toUpperCase() : 'FILE'
}
