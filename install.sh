#!/usr/bin/env bash
# install.sh — installs the motion-studio skill for the current user (macOS / Linux / Git Bash).
#   ./install.sh            skill + renderer
#   ./install.sh --asr      + faster-whisper for voiceovers
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
TARGET="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
DST="$TARGET/motion-studio"
mkdir -p "$TARGET"
if [ -d "$DST" ]; then
  BAK="$(dirname "$TARGET")/skill-backups/motion-studio-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$(dirname "$BAK")"; mv "$DST" "$BAK"; echo "Previous copy backed up to $BAK"
fi
cp -R "$ROOT/.claude/skills/motion-studio" "$DST"
rm -rf "$DST/scripts/node_modules" "$DST/scripts/.asr-venv"
echo "Skill copied to $DST"
bash "$DST/scripts/setup.sh"
[ "${1:-}" = "--asr" ] && bash "$DST/scripts/setup-asr.sh"
echo "Done. Restart Claude Code and type /motion-studio."
