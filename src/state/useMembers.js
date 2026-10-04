import { useCallback, useEffect, useState } from 'react'

import { api, errorMessage } from '../api/client.js'

/** The current project's members, plus add/remove/role changes. */
export function useMembers(projectId) {
  const [members, setMembers] = useState([])
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (!projectId) return
    try {
      const { data } = await api.get(`/projects/${projectId}/members`)
      setMembers(data.members)
      setStatus('ready')
    } catch (err) {
      setError(errorMessage(err, 'Could not load the team.'))
      setStatus('error')
    }
  }, [projectId])

  useEffect(() => {
    load()
  }, [load])

  const addMember = useCallback(
    async (payload) => {
      setError('')
      try {
        await api.post(`/projects/${projectId}/members`, payload)
        await load()
        return { ok: true }
      } catch (err) {
        const message = errorMessage(err, 'Could not add them.')
        setError(message)
        return { ok: false, error: message }
      }
    },
    [projectId, load]
  )

  const removeMember = useCallback(
    async (userId) => {
      setError('')
      try {
        await api.delete(`/projects/${projectId}/members/${userId}`)
        setMembers((current) => current.filter((m) => m.id !== userId))
        return { ok: true }
      } catch (err) {
        const message = errorMessage(err, 'Could not remove them.')
        setError(message)
        return { ok: false, error: message }
      }
    },
    [projectId]
  )

  const changeRole = useCallback(
    async (userId, role) => {
      setError('')
      try {
        const { data } = await api.patch(`/projects/${projectId}/members/${userId}`, { role })
        setMembers((current) => current.map((m) => (m.id === userId ? data.member : m)))
        return { ok: true }
      } catch (err) {
        const message = errorMessage(err, 'Could not change their role.')
        setError(message)
        return { ok: false, error: message }
      }
    },
    [projectId]
  )

  return { members, status, error, addMember, removeMember, changeRole, reload: load }
}
