#!/usr/bin/env python3
"""Khoá API cho /tao-video: nạp, lưu, kiểm — không bao giờ in giá trị khoá ra màn hình.

  python khoa.py kiem                       # khoá nào đã có + gọi thử 1 lần xem còn dùng được không
  python khoa.py luu GEMINI_API_KEY         # lưu khoá đang nằm trong CLIPBOARD (người dùng vừa copy)
  python khoa.py luu GEMINI_API_KEY --stdin # hoặc đọc từ stdin

Khoá lưu ở ~/.tao-video/.env (quyền 0600) — chỗ chung cho MỌI agent (Claude, Codex, Gemini,
Cursor…), không gắn với một agent nào. Lúc đọc vẫn nhận thêm ~/.claude/.env và
~/.config/tts-keys.env cho máy đã để khoá ở đó từ trước.

Vì sao lưu qua clipboard: người dùng dán khoá vào ô chat là khoá nằm lại trong lịch sử
hội thoại. Copy → agent chạy lệnh này → khoá đi thẳng vào file, agent không nhìn thấy.
"""
import json
import os
import platform
import subprocess
import sys
import urllib.request
# Windows: màn hình/ống dẫn mặc định cp1252 → in tiếng Việt là UnicodeEncodeError (máy Windows thật 15/10/2026).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")  # tiến trình Python con cũng in UTF-8


FILE_CHINH = os.path.expanduser("~/.tao-video/.env")
NGUON_DOC = [FILE_CHINH, os.path.expanduser("~/.claude/.env"), os.path.expanduser("~/.config/tts-keys.env")]

# Khoá skill biết dùng, kèm việc nó mở ra và chỗ lấy.
KHOA = {
    # Thứ tự = thứ tự gợi ý cho người mới. Link đi THẲNG tới trang tạo khoá (đăng ký xong là quay về đúng trang đó).
    "ELEVENLABS_API_KEY": ("giọng ElevenLabs tự nhiên nhất + giọng → chữ (free 10.000 ký tự/tháng, không thương mại)",
                           "đăng ký https://elevenlabs.io/app/sign-up → tạo khoá ở https://elevenlabs.io/app/settings/api-keys"),
    "OPENAI_API_KEY": ("giọng OpenAI + giọng → chữ + ảnh gpt-image (trả phí, nạp tối thiểu 5 USD, rất rẻ cho video ngắn)",
                       "tạo khoá ở https://platform.openai.com/api-keys → nạp tiền ở https://platform.openai.com/settings/organization/billing"),
    "GEMINI_API_KEY": ("giọng + ảnh + giọng → chữ của Google (free nhưng ÍT lượt: giọng ~3 lượt/phút)",
                       "https://aistudio.google.com/apikey (đăng nhập Gmail là tạo được)"),
    "SONIOX_API_KEY": ("giọng → chữ tiếng Việt chính xác nhất + giọng Soniox (trả phí rẻ)",
                       "https://console.soniox.com"),
}


def load_env():
    """Nạp khoá từ các file vào os.environ (biến đã đặt sẵn trong môi trường được ưu tiên)."""
    for p in NGUON_DOC:
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            line = line.strip().removeprefix("export ")
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if v:
                    os.environ.setdefault(k.strip(), v)


def _doc_clipboard():
    he = platform.system()
    cmd = {"Darwin": ["pbpaste"], "Windows": ["powershell", "-NoProfile", "-Command", "Get-Clipboard"]}.get(
        he, ["sh", "-c", "wl-paste 2>/dev/null || xclip -o -selection clipboard 2>/dev/null || xsel -b"])
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def luu(ten, gia_tri):
    gia_tri = gia_tri.strip()
    if not gia_tri or " " in gia_tri or "\n" in gia_tri or len(gia_tri) < 16:
        print(f"❌ Clipboard không giống một khoá API (rỗng, có dấu cách hoặc quá ngắn). Copy lại khoá rồi chạy lại.")
        return 1
    os.makedirs(os.path.dirname(FILE_CHINH), exist_ok=True)
    dong = []
    if os.path.exists(FILE_CHINH):
        dong = [l for l in open(FILE_CHINH, encoding="utf-8").read().splitlines()
                if not l.strip().removeprefix("export ").startswith(ten + "=")]
    dong.append(f"{ten}={gia_tri}")
    with open(FILE_CHINH, "w", encoding="utf-8") as f:
        f.write("\n".join(dong) + "\n")
    if platform.system() != "Windows":
        os.chmod(FILE_CHINH, 0o600)
    print(f"✅ Đã lưu {ten} vào {FILE_CHINH} ({len(gia_tri)} ký tự, đuôi …{gia_tri[-4:]})")
    return 0


def _goi(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200].decode("utf-8", "ignore")
    except Exception as e:  # mạng hỏng, DNS…
        return 0, str(e)[:200]


def thu_khoa(ten, v):
    """Một lời gọi rẻ nhất có thể (liệt kê model / tài khoản) — không tốn lượt tạo nội dung."""
    if ten == "GEMINI_API_KEY":
        return _goi(f"https://generativelanguage.googleapis.com/v1beta/models?key={v}&pageSize=1", {})
    if ten == "OPENAI_API_KEY":
        return _goi("https://api.openai.com/v1/models", {"Authorization": f"Bearer {v}"})
    if ten == "ELEVENLABS_API_KEY":
        return _goi("https://api.elevenlabs.io/v1/user", {"xi-api-key": v})
    return None, "không có lời gọi thử — dùng thật mới biết"


def kiem():
    load_env()
    kq = {}
    for ten, (viec, lay) in KHOA.items():
        v = os.environ.get(ten)
        if not v:
            print(f"  ➖ {ten:20} chưa có   ({viec}) — lấy ở {lay}")
            kq[ten] = "chua_co"
            continue
        ma, loi = thu_khoa(ten, v)
        if ma is None:
            print(f"  ✅ {ten:20} có       ({viec}) — {loi}")
            kq[ten] = "co"
        elif ma == 200:
            print(f"  ✅ {ten:20} dùng được ({viec})")
            kq[ten] = "ok"
        elif ma == 401 and "missing the permission" in loi:
            # Khoá ElevenLabs tạo kiểu "giới hạn quyền" không đọc được /v1/user nhưng vẫn đọc chữ thành giọng được.
            print(f"  ✅ {ten:20} có (khoá giới hạn quyền — bật quyền Text to Speech + Speech to Text khi tạo khoá) ({viec})")
            kq[ten] = "co"
        else:
            print(f"  ❌ {ten:20} bị từ chối (HTTP {ma}) — khoá sai/hết hạn/hết hạn mức: {loi[:120]}")
            kq[ten] = f"loi_{ma}"
    print(json.dumps(kq))
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "kiem":
        sys.exit(kiem())
    if len(sys.argv) >= 3 and sys.argv[1] == "luu":
        ten = sys.argv[2].upper()
        gia_tri = sys.stdin.read() if "--stdin" in sys.argv else _doc_clipboard()
        sys.exit(luu(ten, gia_tri))
    print(__doc__)
    sys.exit(2)
