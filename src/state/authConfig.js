import { api } from '../api/client.js'

/**
 * The sign-in settings the server publishes at /auth/config:
 * `{ googleClientId, passwordSignIn }`.
 *
 * Fetched once per page load and shared, so the Google button, the sign-in
 * form and Settings all agree without each asking the server. A failed request
 * is not cached, so "Try again" really does try again.
 */
let pending = null

export function getAuthConfig() {
  if (!pending) {
    pending = api
      .get('/auth/config')
      .then(({ data }) => ({
        googleClientId: data.googleClientId || '',
        passwordSignIn: Boolean(data.passwordSignIn),
      }))
      .catch((err) => {
        pending = null
        throw err
      })
  }
  return pending
}
