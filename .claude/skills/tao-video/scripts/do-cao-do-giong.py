#!/usr/bin/env python3
"""Đo cao độ giọng (F0, Hz) trong các đợt nói của một clip để phân biệt giọng TRẺ CON (~280–450 Hz) với người lớn nữ (~170–260 Hz)
và nam (~90–160 Hz). Dùng: do-cao-do-giong.py clip.mp4 [bắt_đầu kết_thúc ...]  (không đưa mốc thì tự dò đợt to nhất)
Nguồn: video "thành công nhân" 15/10/2026 — Flow đổi giọng bé sang giọng người lớn ở cảnh cuối mà whisper vẫn nghe đúng chữ."""
import subprocess, sys, tempfile, os, wave
import numpy as np
# Windows: màn hình/ống dẫn mặc định cp1252 → in tiếng Việt là UnicodeEncodeError (máy Windows thật 15/10/2026).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")  # tiến trình Python con cũng in UTF-8


clip = sys.argv[1]
spans = [(float(sys.argv[i]), float(sys.argv[i + 1])) for i in range(2, len(sys.argv) - 1, 2)]
with tempfile.TemporaryDirectory() as t:
    wav = os.path.join(t, "a.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", clip, "-ac", "1", "-ar", "16000", wav], check=True)
    w = wave.open(wav)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64)
sr = 16000
win, hop = int(0.04 * sr), int(0.01 * sr)
rms = np.array([np.sqrt(np.mean(x[i:i + win] ** 2)) for i in range(0, len(x) - win, hop)])
if not spans:
    thr = max(rms.max() * 0.25, np.median(rms) * 4)
    on = rms > thr
    segs, s = [], None
    for i, v in enumerate(on):
        if v and s is None:
            s = i
        if not v and s is not None:
            if i - s > 20:
                segs.append((s * hop / sr, i * hop / sr))
            s = None
    spans = segs[:6]


def f0(frame):
    frame = frame - frame.mean()
    if np.sqrt(np.mean(frame ** 2)) < 200:
        return None
    ac = np.correlate(frame, frame, mode="full")[len(frame) - 1:]
    lo, hi = int(sr / 500), int(sr / 80)
    seg = ac[lo:hi]
    k = int(np.argmax(seg)) + lo
    return sr / k if ac[k] > 0.35 * ac[0] else None


for a, b in spans:
    vals = []
    for i in range(int(a * sr), int(b * sr) - 1024, 320):
        v = f0(x[i:i + 1024])
        if v:
            vals.append(v)
    if len(vals) >= 5:
        print(f"{a:5.2f}-{b:5.2f}s  F0 trung vị {np.median(vals):4.0f} Hz  (khoảng {np.percentile(vals, 20):.0f}–{np.percentile(vals, 80):.0f})")
    else:
        print(f"{a:5.2f}-{b:5.2f}s  không đủ đoạn có thanh để đo")
