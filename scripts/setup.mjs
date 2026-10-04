// One-time setup for DevTrack on Windows, macOS or Linux.
//
//   npm run setup        (or: node scripts/setup.mjs)
//
// Installs the frontend packages, creates backend/.venv and installs the
// Python packages into it, writes backend/.env with a fresh SECRET_KEY,
// builds the database schema and creates the demo account. Safe to re-run:
// each step skips what is already done. Uses only Node's own modules, so it
// works before `npm install` has ever been run.

import { spawnSync } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { copyFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const windows = process.platform === 'win32'
const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const backend = join(root, 'backend')
const venvPython = windows
  ? join(backend, '.venv', 'Scripts', 'python.exe')
  : join(backend, '.venv', 'bin', 'python')

const paint = (code) => (text) => (process.stdout.isTTY ? `\x1b[${code}m${text}\x1b[0m` : text)
const cyan = paint('36')
const green = paint('32')
const red = paint('31')

const step = (name) => console.log(`\n${cyan(`=== ${name} ===`)}`)
const ok = (text) => console.log(`  ${green('OK')}  ${text}`)
function die(text) {
  console.error(`  ${red('!!')}  ${text}`)
  process.exit(1)
}

/** Run a program with live output. `shell` is needed for npm on Windows (npm.cmd). */
function run(command, args, { cwd = root, shell = false } = {}) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit', shell })
  return result.status === 0
}

/** Run quietly and return what it printed, or null if it could not start. */
function capture(command, args) {
  const result = spawnSync(command, args, { encoding: 'utf8' })
  if (result.error || result.status !== 0) return null
  return `${result.stdout}${result.stderr}`.trim()
}

// ------------------------------------------------------------------ prereqs
step('Checking Node and Python')

const [major, minor] = process.versions.node.split('.').map(Number)
if (major < 20 || (major === 20 && minor < 19) || major === 21 || (major === 22 && minor < 12)) {
  die(`Node ${process.version} is too old. Vite 8 needs 20.19+ or 22.12+. Install Node 22 LTS from nodejs.org.`)
}
ok(`Node ${process.version}`)

// The usual names for Python 3 on each system, most specific first.
const candidates = windows
  ? [['py', ['-3']], ['python', []], ['python3', []]]
  : [['python3', []], ['python', []]]

let python = null
for (const [command, prefix] of candidates) {
  const out = capture(command, [...prefix, '--version'])
  const match = out && /Python (\d+)\.(\d+)/.exec(out)
  if (!match) continue
  const [pyMajor, pyMinor] = [Number(match[1]), Number(match[2])]
  if (pyMajor === 3 && pyMinor >= 10) {
    python = { command, prefix, version: `${pyMajor}.${pyMinor}` }
    break
  }
}
if (!python) {
  die(
    windows
      ? 'Python 3.10+ was not found. Install it from python.org and tick "Add python.exe to PATH".'
      : 'Python 3.10+ was not found. Install it from python.org (or `brew install python`).'
  )
}
ok(`Python ${python.version} (${python.command})`)

// ------------------------------------------------------------------ frontend
step('Installing frontend packages')
if (!run('npm', ['install'], { shell: windows })) die('npm install failed. Scroll up for the reason.')
ok('node_modules ready')

// ------------------------------------------------------------------ backend
step('Creating the backend virtualenv')
if (existsSync(venvPython)) {
  ok('virtualenv already there')
} else {
  if (existsSync(join(backend, '.venv'))) {
    // A .venv copied from another computer (Windows ↔ Mac) has the wrong layout
    // and cannot be repaired in place.
    die('backend/.venv exists but has no Python for this system — it was probably copied from another computer. Delete backend/.venv and run this again.')
  }
  if (!run(python.command, [...python.prefix, '-m', 'venv', '.venv'], { cwd: backend })) {
    die('Could not create the virtualenv.')
  }
  ok('virtualenv created')
}

step('Installing backend packages')
run(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip', '--quiet'], { cwd: backend })
if (!run(venvPython, ['-m', 'pip', 'install', '-r', 'requirements.txt'], { cwd: backend })) {
  die('pip install failed. Scroll up for the reason.')
}
ok('Flask and friends installed')

// ------------------------------------------------------------------ .env
step('Writing backend/.env')
const envFile = join(backend, '.env')
if (existsSync(envFile)) {
  ok('.env already exists — left alone')
} else {
  copyFileSync(join(backend, '.env.example'), envFile)
  const key = randomBytes(32).toString('hex')
  writeFileSync(envFile, readFileSync(envFile, 'utf8').replace(/^SECRET_KEY=.*$/m, `SECRET_KEY=${key}`))
  ok('created with a fresh SECRET_KEY')
}

// ------------------------------------------------------------------ database
step('Building the database')
if (!run(venvPython, ['-m', 'flask', '--app', 'run:app', 'db', 'upgrade'], { cwd: backend })) {
  die('The migration failed. Scroll up for the reason.')
}
ok('schema up to date')

if (!run(venvPython, ['seed.py'], { cwd: backend })) die('Creating the demo account failed.')
ok('demo account ready')

// ------------------------------------------------------------------ done
console.log(`\n${green('=== Ready. Start it with two terminals ===')}`)
console.log('  1)  npm run api')
console.log('  2)  npm run dev')
console.log('')
console.log('  Then open http://localhost:5173')
console.log('  Sign in:  aditya@devtrack.local  /  devtrack123')
