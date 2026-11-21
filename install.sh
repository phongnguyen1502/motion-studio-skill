#!/usr/bin/env bash
# install.sh — installs the skills of this repo (motion-studio, tao-video) for the current user (macOS / Linux / Git Bash).
#   ./install.sh            skills + renderer
#   ./install.sh --asr      + faster-whisper/opencv for voiceovers and talking-head videos
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
TARGET="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$TARGET"
for NAME in motion-studio tao-video; do
  [ -d "$ROOT/.claude/skills/$NAME" ] || continue
  DST="$TARGET/$NAME"
  if [ -d "$DST" ]; then
    BAK="$(dirname "$TARGET")/skill-backups/$NAME-$STAMP"
    mkdir -p "$(dirname "$BAK")"; mv "$DST" "$BAK"; echo "Previous $NAME backed up to $BAK"
  fi
  cp -R "$ROOT/.claude/skills/$NAME" "$DST"
  rm -rf "$DST/scripts/node_modules" "$DST/scripts/.asr-venv" "$DST/scripts/__pycache__"
  echo "Skill copied to $DST"
done
bash "$TARGET/motion-studio/scripts/setup.sh"
[ "${1:-}" = "--asr" ] && bash "$TARGET/motion-studio/scripts/setup-asr.sh"
echo "Done. Restart Claude Code, then type /motion-studio, or /tao-video setup once for tao-video."
