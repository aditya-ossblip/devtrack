# Apply the phase-3 rebuild: new packages, fresh schema, tests, reseed.
#   powershell -ExecutionPolicy Bypass -File .\refresh.ps1
#
# WARNING: this DROPS the existing database. The old schema (tasks) and the new
# one (issues, workflow states, sprints, comments) are too far apart to migrate
# by hand, and the only data in there is demo data.
#
# ASCII ONLY in this file. Windows PowerShell 5.1 reads a BOM-less .ps1 as
# cp1252, and a UTF-8 dash or curly quote decodes into characters the tokenizer
# treats as string delimiters - which breaks the parse in a way the error
# message does not point at.

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Step($n) { Write-Host "`n=== $n ===" -ForegroundColor Cyan }
function Ok($n)   { Write-Host "  OK  $n" -ForegroundColor Green }
function Die($n)  { Write-Host "  !!  $n" -ForegroundColor Red; exit 1 }

Write-Host 'Stop both dev servers before running this (Ctrl+C in each pane).' -ForegroundColor Yellow

Step 'Frontend packages'
& npm install
if ($LASTEXITCODE -ne 0) { Die 'npm install failed.' }
Ok 'node_modules ready'

$venvPy = Join-Path $PSScriptRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) { Die 'backend\.venv is missing. Run setup.ps1 first.' }

Set-Location (Join-Path $PSScriptRoot 'backend')

Step 'Backend tests'
& $venvPy -m pytest
if ($LASTEXITCODE -ne 0) {
  Write-Host "`n=== Tests failed. Database left untouched ===" -ForegroundColor Yellow
  Write-Host '  Scroll up for the failing test.'
  exit 1
}
Ok 'all tests pass'

Step 'Rebuilding the database'
& $venvPy seed.py --reset
if ($LASTEXITCODE -ne 0) { Die 'Seeding failed.' }

Set-Location $PSScriptRoot
Write-Host "`n=== Ready ===" -ForegroundColor Green
Write-Host '  1)  .\backend\.venv\Scripts\python.exe backend\run.py'
Write-Host '  2)  npm run dev'
Write-Host ''
Write-Host '  http://localhost:5173'
Write-Host '  Sign in: aditya@devtrack.local / devtrack123'
Write-Host '  Other accounts: sign up at /register, then add them from the Team page.'
