import axios from 'axios'

export const TOKEN_KEY = 'devtrack.token'

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null // private mode, or storage disabled
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* nothing we can do; the session just won't survive a reload */
  }
}

export const api = axios.create({ baseURL: '/api' })

// Set by the socket layer once connected. The backend skips this socket when
// broadcasting, so whoever made a change doesn't receive their own echo.
let socketId = null
export function setSocketId(id) {
  socketId = id
}

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (socketId) config.headers['X-Socket-Id'] = socketId
  return config
})

let onUnauthorized = null
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      setToken(null)
      // Let the auth context clear its state and route, rather than a hard
      // location assign that throws away React state mid-render.
      onUnauthorized?.()
    }
    return Promise.reject(error)
  }
)

/** Pull a human-readable message out of an axios failure. */
export function errorMessage(error, fallback = 'Something went wrong. Try again.') {
  if (error?.response?.data?.error) return error.response.data.error
  if (error?.code === 'ERR_NETWORK') return 'Cannot reach the server. Is the backend running?'
  return fallback
}

/**
 * Save a file from an endpoint that requires the Authorization header.
 *
 * An `<a href>` cannot carry one, and putting the token in the query string
 * would write it into server logs and browser history — so the bytes come
 * through axios instead and go to a throwaway link.
 *
 * The object URL is revoked immediately afterwards. Without that, every file
 * downloaded stays pinned in memory for as long as the tab is open.
 */
export async function downloadFile(path, filename = 'download') {
  const { data } = await api.get(path, { responseType: 'blob' })
  const url = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
