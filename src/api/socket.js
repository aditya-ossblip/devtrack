import { io } from 'socket.io-client'

import { setSocketId } from './client.js'

let socket = null
const pendingHandlers = new Set()
// What each handler returned the last time it ran: its way of undoing itself
// (removing its listeners, leaving its room). Run before the handler runs
// again after a reconnect, and when its owner unsubscribes - otherwise every
// reconnect or project switch stacked another copy of every listener.
const cleanups = new Map()

function run(handler) {
  cleanups.get(handler)?.()
  const undo = handler(socket)
  if (typeof undo === 'function') cleanups.set(handler, undo)
  else cleanups.delete(handler)
}

/**
 * One socket per signed-in session. Live updates are an enhancement: if the
 * connection never comes up the app still works off REST, it just stops
 * updating other people's screens by itself.
 */
export function connectSocket(token) {
  if (socket) return socket

  socket = io({ auth: { token }, autoConnect: true, transports: ['websocket', 'polling'] })

  socket.on('connect', () => {
    setSocketId(socket.id)
    pendingHandlers.forEach(run)
  })
  socket.on('disconnect', () => setSocketId(null))

  return socket
}

export function getSocket() {
  return socket
}

/**
 * Run `handler(socket)` now if connected, and again after any reconnect.
 * Returns an unsubscribe function. Components use this rather than reading
 * getSocket() once, so a late connection still wires them up.
 */
export function onSocketReady(handler) {
  pendingHandlers.add(handler)
  if (socket?.connected) run(handler)
  return () => {
    pendingHandlers.delete(handler)
    cleanups.get(handler)?.()
    cleanups.delete(handler)
  }
}

export function disconnectSocket() {
  if (socket) {
    socket.disconnect()
    socket = null
    setSocketId(null)
    pendingHandlers.clear()
    cleanups.clear()
  }
}
