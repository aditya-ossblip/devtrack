# DevTrack one-shot setup for Windows PowerShell.
#   cd "C:\Users\Aditya\Downloads\College Work\Devtrack"
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
#
# Safe to re-run: it skips work that is already done.

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

function Step($n) { Write-Host "`n=== $n ===" -ForegroundColor Cyan }
function Ok($n)   { Write-Host "  OK  $n" -ForegroundColor Green }
function Die($n)  { Write-Host "  !!  $n" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- prereqs
Step 'Checking Node and Python'

try { $nodeVersion = (& node -v).Trim() } catch { Die 'Node is not on your PATH. Install Node 22 LTS from nodejs.org.' }
$major, $minor = ($nodeVersion.TrimStart('v').Split('.'))[0..1] | ForEach-Object { [int]$_ }
if ($major -lt 20 -or ($major -eq 20 -and $minor -lt 19) -or ($major -eq 21)) {
  Die "Node $nodeVersion is too old. Vite 8 needs 20.19+ or 22.12+. Install Node 22 LTS."
}
Ok "Node $nodeVersion"

$py = $null
foreach ($candidate in @('python', 'py')) {
  try { $out = & $candidate --version 2>&1; if ($LASTEXITCODE -eq 0 -and "$out" -match '(\d+)\.(\d+)') { $py = $candidate; break } } catch { }
}
if (-not $py) { Die 'Python is not on your PATH. Install Python 3.11 from python.org and tick "Add python.exe to PATH".' }
$pyVersion = (& $py --version 2>&1) -replace 'Python ', ''
$pyMajor, $pyMinor = ($pyVersion.Split('.'))[0..1] | ForEach-Object { [int]$_ }
if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 10)) { Die "Python $pyVersion is too old; need 3.10+." }
Ok "Python $pyVersion"

# ---------------------------------------------------------------- frontend
Step 'Installing frontend packages'
& npm install
if ($LASTEXITCODE -ne 0) { Die 'npm install failed. Scroll up for the reason.' }
Ok 'node_modules ready'

# ---------------------------------------------------------------- backend
Step 'Creating the backend virtualenv'
Set-Location (Join-Path $root 'backend')

if (-not (Test-Path '.venv')) { & $py -m venv .venv; Ok 'virtualenv created' }
else { Ok 'virtualenv already there' }

$venvPy = Join-Path $PWD '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) { Die 'The virtualenv looks broken. Delete backend\.venv and re-run.' }

Step 'Installing backend packages'
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Die 'pip install failed. Scroll up for the reason.' }
Ok 'Flask and friends installed'

# ---------------------------------------------------------------- .env
Step 'Writing backend\.env'
if (-not (Test-Path '.env')) {
  Copy-Item '.env.example' '.env'
  $key = & $venvPy -c "import secrets; print(secrets.token_hex(32))"
  (Get-Content '.env') -replace '^SECRET_KEY=.*', "SECRET_KEY=$key" | Set-Content '.env'
  Ok 'created with a fresh SECRET_KEY'
} else {
  Ok '.env already exists - left alone'
}

# ---------------------------------------------------------------- tests
Step 'Running the backend test suite'
& $venvPy -m pytest
$testsPassed = ($LASTEXITCODE -eq 0)

# ---------------------------------------------------------------- seed
if ($testsPassed) {
  Step 'Seeding the demo project'
  & $venvPy seed.py
  if ($LASTEXITCODE -ne 0) { Die 'Seeding failed. Scroll up for the reason.' }
}

# ---------------------------------------------------------------- done
Set-Location $root
Write-Host ''
if ($testsPassed) {
  Write-Host '=== Ready. Start it with two terminals ===' -ForegroundColor Green
  Write-Host '  1)  cd backend;  .\.venv\Scripts\python.exe run.py'
  Write-Host '  2)  npm run dev'
  Write-Host ''
  Write-Host '  Then open http://localhost:5173'
  Write-Host '  Sign in:  aditya@devtrack.local  /  devtrack123'
} else {
  Write-Host '=== Setup is done, but tests failed ===' -ForegroundColor Yellow
  Write-Host '  Everything is installed. Scroll up for the failing test.'
  Write-Host '  Nothing was seeded, so the database is still untouched.'
}
