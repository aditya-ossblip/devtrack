import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client.js'
import { onSocketReady } from '../api/socket.js'

export function useNotifications() {
  const [notifications, setNotifications] = useState([])
  const [unread, setUnread] = useState(0)
  const [status, setStatus] = useState('loading')

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/notifications')
      setNotifications(data.notifications)
      setUnread(data.unread)
      setStatus('ready')
    } catch {
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(
    () =>
      onSocketReady((socket) => {
        const onNew = (payload) => {
          if (payload?.notification) {
            setNotifications((current) => [payload.notification, ...current].slice(0, 30))
            setUnread((n) => n + 1)
          } else {
            load() // a bare ping — refetch rather than guess
          }
        }
        socket.on('notification:new', onNew)
        return () => socket.off('notification:new', onNew)
      }),
    [load]
  )

  const markRead = useCallback(async (id) => {
    setNotifications((current) =>
      current.map((item) => (item.id === id ? { ...item, read: true } : item))
    )
    setUnread((n) => Math.max(0, n - 1))
    try {
      await api.patch(`/notifications/${id}/read`)
    } catch {
      /* the count corrects itself on the next load */
    }
  }, [])

  const markAllRead = useCallback(async () => {
    setNotifications((current) => current.map((item) => ({ ...item, read: true })))
    setUnread(0)
    try {
      await api.post('/notifications/read-all')
    } catch {
      /* ditto */
    }
  }, [])

  return { notifications, unread, status, markRead, markAllRead, reload: load }
}
