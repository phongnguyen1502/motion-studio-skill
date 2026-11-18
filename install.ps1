# install.ps1 — installs the motion-studio skill for the current Windows user.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1            # skill + renderer
#   powershell -ExecutionPolicy Bypass -File install.ps1 -WithASR   # + faster-whisper for voiceovers
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Target D:\somewhere\skills
#
# Copies .claude\skills\motion-studio to %USERPROFILE%\.claude\skills\motion-studio (an existing copy is
# moved to %USERPROFILE%\.claude\skill-backups\motion-studio-<date>, outside the skills folder), then runs setup.
param([switch]$WithASR, [string]$Target = (Join-Path $env:USERPROFILE '.claude\skills'), [switch]$SkipSetup)
$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot '.claude\skills\motion-studio'
$dst = Join-Path $Target 'motion-studio'
New-Item -ItemType Directory -Force $Target | Out-Null
if (Test-Path $dst) {
  $bakRoot = Join-Path (Split-Path $Target -Parent) 'skill-backups'
  New-Item -ItemType Directory -Force $bakRoot | Out-Null
  $bak = Join-Path $bakRoot ('motion-studio-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
  Move-Item $dst $bak
  Write-Host "Previous copy backed up to $bak"
}
Copy-Item $src $dst -Recurse
foreach ($junk in 'scripts\node_modules', 'scripts\.asr-venv') { $j = Join-Path $dst $junk; if (Test-Path $j) { Remove-Item $j -Recurse -Force } }
Write-Host "Skill copied to $dst"
if (-not $SkipSetup) {
  $p = @{}; if ($WithASR) { $p.WithASR = $true }
  & (Join-Path $dst 'scripts\setup.ps1') @p
}
Write-Host 'Done. Restart Claude Code (desktop app or terminal) and type /motion-studio.'
