# Kept for anyone used to running this file. Setup is now one script that
# works on Windows, macOS and Linux:
#
#   npm run setup
#
# Running this file does exactly that.
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1

Set-Location $PSScriptRoot
& node scripts/setup.mjs
exit $LASTEXITCODE
