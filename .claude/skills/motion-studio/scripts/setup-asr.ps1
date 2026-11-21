# setup-asr.ps1 — creates %USERPROFILE%\.motion-studio\asr-venv with faster-whisper for scripts\voice-timing.py.
# The Whisper model (~1.5 GB for "medium") downloads on first use and is cached in %USERPROFILE%\.cache.
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { throw 'Python 3.10+ is missing: winget install Python.Python.3.12' }
# short path outside the skill: survives reinstalls and avoids Windows' 260-char path limit
$venv = Join-Path $env:USERPROFILE '.motion-studio\asr-venv'
New-Item -ItemType Directory -Force (Split-Path $venv) | Out-Null
if (-not (Test-Path $venv)) { python -m venv $venv }
& (Join-Path $venv 'Scripts\python.exe') -m pip install --quiet --upgrade pip
& (Join-Path $venv 'Scripts\python.exe') -m pip install --quiet faster-whisper "opencv-python-headless<5"
if ($LASTEXITCODE -ne 0) { throw 'pip install faster-whisper opencv failed' }
Write-Host "ASR ready: $venv\Scripts\python.exe $dir\voice-timing.py <voice> <script.txt> <timing.json>"
