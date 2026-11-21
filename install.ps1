# install.ps1 — installs the skills of this repo for the current Windows user:
#   motion-studio (motion graphics, effect library, voiceover -> video) and tao-video (short videos from images/AI clips,
#   and "video quay sẵn": talking-head footage -> cut + effects + subtitles; it uses motion-studio's effect library).
#
#   powershell -ExecutionPolicy Bypass -File install.ps1            # skills + renderer
#   powershell -ExecutionPolicy Bypass -File install.ps1 -WithASR   # + faster-whisper/opencv (voiceovers, talking heads)
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Target D:\somewhere\skills
#
# Copies .claude\skills\<skill> to %USERPROFILE%\.claude\skills\<skill> (an existing copy is moved to
# %USERPROFILE%\.claude\skill-backups\<skill>-<date>, outside the skills folder), then runs motion-studio's setup.
param([switch]$WithASR, [string]$Target = (Join-Path $env:USERPROFILE '.claude\skills'), [switch]$SkipSetup)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $Target | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
foreach ($name in 'motion-studio', 'tao-video') {
  $src = Join-Path $PSScriptRoot ".claude\skills\$name"
  if (-not (Test-Path $src)) { continue }
  $dst = Join-Path $Target $name
  if (Test-Path $dst) {
    $bakRoot = Join-Path (Split-Path $Target -Parent) 'skill-backups'
    New-Item -ItemType Directory -Force $bakRoot | Out-Null
    $bak = Join-Path $bakRoot "$name-$stamp"
    Move-Item $dst $bak
    Write-Host "Previous $name backed up to $bak"
  }
  Copy-Item $src $dst -Recurse
  foreach ($junk in 'scripts\node_modules', 'scripts\.asr-venv', 'scripts\__pycache__') { $j = Join-Path $dst $junk; if (Test-Path $j) { Remove-Item $j -Recurse -Force } }
  Write-Host "Skill copied to $dst"
}
if (-not $SkipSetup) {
  $p = @{}; if ($WithASR) { $p.WithASR = $true }
  & (Join-Path $Target 'motion-studio\scripts\setup.ps1') @p
}
Write-Host 'Done. Restart Claude Code (desktop app or terminal), then type /motion-studio, or /tao-video setup once for tao-video.'
