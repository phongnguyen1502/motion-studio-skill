#!/usr/bin/env python3
"""Cho máy NGHE LẠI từng file giọng rồi so với lời gốc — bắt lỗi đọc thiếu chữ, đọc sai,
thẻ cảm xúc ([warm]…) bị đọc thành tiếng. Tai người rất dễ bỏ qua các lỗi này.

Dùng: kiem-giong.py kich-ban.json [--nguong 0.85] [--nguon soniox|openai|gemini|whisper]
Nghe bằng chu-tu-giong.py (Soniox/OpenAI/Gemini theo khoá có sẵn; whisper chỉ khi máy đã cài — không cần cài,
nặng). In điểm khớp từng cảnh; cảnh dưới ngưỡng → tạo lại giọng cảnh đó.
Bài học "Những con số trên tường" 10/2026: tts-1-hd của OpenAI đọc thiếu chữ, chỉ STT bắt được.
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
# Windows: màn hình/ống dẫn mặc định cp1252 → in tiếng Việt là UnicodeEncodeError (máy Windows thật 15/10/2026).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")  # tiến trình Python con cũng in UTF-8


ap = argparse.ArgumentParser()
ap.add_argument("plan")
ap.add_argument("--nguong", type=float, default=0.85)
ap.add_argument("--nguon")
a = ap.parse_args()

plan = json.load(open(a.plan, encoding="utf-8-sig"))
base = os.path.dirname(os.path.abspath(a.plan))


def words(s):
    s = re.sub(r"\[[a-z ]+\]", " ", s.lower())          # bỏ thẻ cảm xúc khỏi lời gốc
    return re.findall(r"\w+", s)


tmp, bad = tempfile.mkdtemp(), []
for c in plan["canh"]:
    if not c.get("loi"):
        continue
    f = os.path.join(base, "giong", f"{c['id']}.mp3")
    cmd = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "chu-tu-giong.py"), f,
           "--ra", os.path.join(tmp, c["id"])] + (["--nguon", a.nguon] if a.nguon else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"Không nghe lại được cảnh {c['id']}: {(r.stdout + r.stderr).strip()[-300:]}")
    heard = json.load(open(os.path.join(tmp, f"{c['id']}.chu.json"), encoding="utf-8"))["text"]
    score = difflib.SequenceMatcher(None, words(c["loi"]), words(heard)).ratio()
    flag = "" if score >= a.nguong else "  ← NGHE LẠI / TẠO LẠI"
    print(f"{c['id']}  {score:.2f}{flag}\n    gốc : {c['loi']}\n    nghe: {heard.strip()}")
    if flag:
        bad.append(c["id"])
print("Cảnh cần xem lại:", ", ".join(bad) if bad else "không có")
