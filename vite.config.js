import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 5001, not 5000: on macOS 12+ the AirPlay Receiver already listens on 5000
// and answers every request with a 403, so the login page decided the API was
// down. 127.0.0.1 rather than localhost, because Node may resolve localhost to
// the IPv6 address first and reach a different program than the one Flask is
// bound to.
const BACKEND = process.env.VITE_API_TARGET || 'http://127.0.0.1:5001'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxying keeps the browser on one origin, so there is no CORS setup to
    // get wrong and cookies/headers behave the same as they will in production.
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/socket.io': { target: BACKEND, changeOrigin: true, ws: true },
    },
  },
})
