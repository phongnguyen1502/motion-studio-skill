#!/usr/bin/env python3
"""Tạo một câu giọng mẫu để người dùng NGHE trước khi chọn giọng cho video.

  python giong-mau.py edge                      # free, không key
  python giong-mau.py edge vi-VN-NamMinhNeural
  python giong-mau.py gemini Kore               # cần GEMINI_API_KEY
  python giong-mau.py openai nova | eleven <voice_id> | soniox Linh

Ra file <KHO>/_thu/giong-<nguon>[-<ten>].mp3 rồi tự mở để nghe.
Dùng đúng đường của giong.py nên giọng nghe được ở đây là giọng sẽ ra trong video.
Giọng Vbee (web, không có API) thì chạy flow GaBee `vbee-tts` — xem references/nguon-giong.md.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kho import KHO  # noqa: E402  (kho theo thư mục Downloads thật, kể cả khi đã chuyển sang ổ khác)
# Windows: màn hình/ống dẫn mặc định cp1252 → in tiếng Việt là UnicodeEncodeError (máy Windows thật 15/10/2026).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")  # tiến trình Python con cũng in UTF-8


HERE = os.path.dirname(os.path.abspath(__file__))
CAU = "Xin chào, đây là giọng đọc thử cho video của bạn. Nghe có tự nhiên không?"


def mo(path):
    he = platform.system()
    try:
        if he == "Darwin":
            subprocess.Popen(["open", path])
        elif he == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    nguon = sys.argv[1]
    ten = sys.argv[2] if len(sys.argv) > 2 else None
    tmp = tempfile.mkdtemp(prefix="giong-mau-")
    giong = {"nguon": nguon}
    if ten:
        giong["ten"] = ten
    kb = {"giong": giong, "canh": [{"id": "01", "loi": CAU}]}
    with open(os.path.join(tmp, "kich-ban.json"), "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False)
    r = subprocess.run([sys.executable, os.path.join(HERE, "giong.py"), "kich-ban.json"], cwd=tmp,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    src = os.path.join(tmp, "giong", "01.mp3")
    if r.returncode != 0 or not os.path.exists(src) or os.path.getsize(src) < 2000:
        log = r.stdout + r.stderr
        print(f"❌ Không tạo được giọng {nguon}:\n{log[-600:]}")
        if nguon == "edge" and "403" in log:
            # Microsoft đổi khoá bắt tay định kỳ; bản edge-tts cũ bị 403 (7.2.8 hỏng, 7.3.1 chạy — 15/10/2026).
            print("→ edge-tts quá cũ: chạy  pip install -U edge-tts  (hoặc uv tool upgrade edge-tts) rồi thử lại")
        return 1
    out_dir = os.path.join(KHO, "_thu")
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, f"giong-{nguon}" + (f"-{ten}" if ten else "") + ".mp3")
    shutil.copyfile(src, dst)
    print(f"✅ Giọng mẫu: {dst}")
    mo(dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
