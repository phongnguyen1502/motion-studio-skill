# setup.ps1 — Windows version of setup.sh: installs Playwright + Chromium for the renderer.
#   powershell -ExecutionPolicy Bypass -File setup.ps1 [-WithASR]
# -WithASR also creates %USERPROFILE%\.motion-studio\asr-venv with faster-whisper (word timestamps for voiceovers).
param([switch]$WithASR)
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js is missing: winget install OpenJS.NodeJS.LTS' }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw 'ffmpeg is missing: winget install Gyan.FFmpeg' }
Push-Location $dir
try {
  npm install --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { throw 'npm install failed' }
  npx playwright install chromium
  if ($LASTEXITCODE -ne 0) { throw 'playwright install failed' }
  if ($WithASR) { & (Join-Path $dir 'setup-asr.ps1') }
} finally { Pop-Location }
Write-Host 'motion-studio is ready.'
