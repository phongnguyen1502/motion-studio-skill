#!/usr/bin/env bash
# setup-asr.sh — creates ~/.motion-studio/asr-venv with faster-whisper for scripts/voice-timing.py.
# The Whisper model (~1.5 GB for "medium") downloads on first use and is cached in ~/.cache.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3 || command -v python)" || { echo "Python 3.10+ is missing"; exit 1; }
VENV="$HOME/.motion-studio/asr-venv"; mkdir -p "$HOME/.motion-studio"
[ -d "$VENV" ] || "$PY" -m venv "$VENV"
VPY="$VENV/bin/python"; [ -x "$VPY" ] || VPY="$VENV/Scripts/python.exe"
"$VPY" -m pip install --quiet --upgrade pip
"$VPY" -m pip install --quiet faster-whisper
echo "ASR ready: $VPY $DIR/voice-timing.py <voice> <script.txt> <timing.json>"
