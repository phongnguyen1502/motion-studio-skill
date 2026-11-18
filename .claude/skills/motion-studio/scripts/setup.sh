#!/usr/bin/env bash
# Installs Playwright + Chromium inside the skill folder (nothing global).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
command -v node >/dev/null || { echo "Node.js is missing (macOS: brew install node · Windows: winget install OpenJS.NodeJS.LTS · Linux: apt install nodejs npm)"; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg is missing (macOS: brew install ffmpeg · Windows: winget install Gyan.FFmpeg · Linux: apt install ffmpeg)"; exit 1; }
cd "$DIR"
npm install --no-audit --no-fund
npx playwright install chromium
echo "motion-studio is ready."
