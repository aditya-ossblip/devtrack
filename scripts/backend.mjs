// Runs a command with the backend's own Python, on Windows, macOS or Linux.
//
//   node scripts/backend.mjs run.py
//   node scripts/backend.mjs -m flask --app run:app db upgrade
//
// The virtualenv keeps its interpreter in a different place on each system
// (.venv\Scripts\python.exe on Windows, .venv/bin/python everywhere else), so
// the npm scripts go through this file instead of naming one of them. It runs
// from inside backend/, which is where Flask-Migrate and pytest expect to be.

import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const backend = join(dirname(fileURLToPath(import.meta.url)), '..', 'backend')
const python =
  process.platform === 'win32'
    ? join(backend, '.venv', 'Scripts', 'python.exe')
    : join(backend, '.venv', 'bin', 'python')

if (!existsSync(python)) {
  const make = process.platform === 'win32' ? 'python -m venv .venv' : 'python3 -m venv .venv'
  const pip = process.platform === 'win32' ? '.venv\\Scripts\\pip' : '.venv/bin/pip'
  console.error(
    `\nNo backend virtualenv at ${python}\n\n` +
      'Create it once, from the project root:\n\n' +
      `  cd backend\n  ${make}\n  ${pip} install -r requirements.txt\n`
  )
  process.exit(1)
}

// `--test-on-postgres` (npm run test:postgres) points the test suite at
// TEST_DATABASE_URL from backend/.env instead of in-memory SQLite. It is passed
// as an environment variable rather than typed before the command, because
// `NAME=value npm ...` does not work in Command Prompt or PowerShell.
const args = process.argv.slice(2)
const env = { ...process.env }
if (args[0] === '--test-on-postgres') {
  args.shift()
  env.DEVTRACK_TEST_ON_POSTGRES = '1'
}

const child = spawn(python, args, { cwd: backend, stdio: 'inherit', env })

// Ctrl+C reaches the child through the terminal on its own; this just stops
// Node from exiting first and leaving the server orphaned.
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => {})

child.on('exit', (code, signal) => process.exit(signal ? 1 : (code ?? 0)))
