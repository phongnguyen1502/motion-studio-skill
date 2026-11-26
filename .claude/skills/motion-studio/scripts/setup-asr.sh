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
"$VPY" -m pip install --quiet faster-whisper "opencv-python-headless<5"
# person matte + face track for tao-video's speaker effects: MODNet (Apache-2.0, 25.9 MB) + YuNet (MIT, 0.23 MB), ONNX
M="$HOME/.motion-studio/models"; mkdir -p "$M"
# a blocked download only disables the speaker effects: warn, do not fail the setup
get() { { [ -f "$M/$1" ] || curl -fsSL -o "$M/$1" "$2"; } && echo "$3  $M/$1" | sha256sum -c --quiet - \
        || { rm -f "$M/$1"; echo "warning: model $1 not installed, talking-head speaker effects stay off" >&2; }; }
get modnet.onnx https://huggingface.co/Xenova/modnet/resolve/main/onnx/model.onnx 07c308cf0fc7e6e8b2065a12ed7fc07e1de8febb7dc7839d7b7f15dd66584df9
get face_detection_yunet_2023mar.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx 8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4
echo "ASR ready: $VPY $DIR/voice-timing.py <voice> <script.txt> <timing.json>"
