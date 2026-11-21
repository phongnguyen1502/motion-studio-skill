#!/usr/bin/env python3
"""Kiểm máy có đủ đồ để chạy /tao-video không, và (tuỳ chọn) dựng thử 2 cảnh mẫu.

  python kiem-moi-truong.py            # chỉ kiểm, in bảng ✅/❌ kèm cách cài
  python kiem-moi-truong.py --thu-dung # kiểm + sinh 2 ảnh mẫu + giọng edge + dựng video-thu.mp4

Không cần GaBee, không cần tài khoản nào. Phần GaBee/Muse do Claude kiểm bằng công cụ (xem setup.md).
"""
import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
# Windows: màn hình/ống dẫn mặc định cp1252 → in tiếng Việt là UnicodeEncodeError (máy Windows thật 15/10/2026).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")  # tiến trình Python con cũng in UTF-8


HERE = os.path.dirname(os.path.abspath(__file__))
KHO = os.path.expanduser("~/Downloads/tao-video-kho")
HE = platform.system()  # Darwin / Linux / Windows


def cach_cai(mac, linux, win):
    return {"Darwin": mac, "Linux": linux, "Windows": win}.get(HE, linux)


def chay(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return r.returncode, (r.stdout + r.stderr)
    except Exception as e:  # không có lệnh, hết giờ...
        return 1, str(e)


def kiem_python():
    ok = sys.version_info >= (3, 9)
    return ok, f"Python {platform.python_version()}", "cần Python 3.9 trở lên (python.org)"


def kiem_pillow():
    ok = importlib.util.find_spec("PIL") is not None
    return ok, "Pillow (vẽ chuyển động ảnh)", "pip install pillow"


def kiem_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return False, "ffmpeg + ffprobe", cach_cai("brew install ffmpeg", "sudo apt install ffmpeg",
                                                    "winget install ffmpeg")
    return True, "ffmpeg + ffprobe", ""


def kiem_phu_de():
    # phụ đề dùng bộ lọc ass → cần ffmpeg có libass
    if not shutil.which("ffmpeg"):
        return False, "ffmpeg có libass (phụ đề)", "cài ffmpeg trước"
    _, out = chay(["ffmpeg", "-hide_banner", "-filters"])
    ok = " ass " in out or "subtitles" in out
    return ok, "ffmpeg có libass (phụ đề)", cach_cai("brew reinstall ffmpeg (bản đầy đủ)",
                                                      "sudo apt install ffmpeg libass9", "dùng bản ffmpeg full build")


def kiem_edge():
    exe = shutil.which("edge-tts") or os.path.expanduser("~/.local/bin/edge-tts")
    ok = os.path.exists(exe) or importlib.util.find_spec("edge_tts") is not None
    return ok, "edge-tts (giọng nháp free, không key)", "pip install -U edge-tts   (bản cũ bị Microsoft trả 403 — luôn -U)"


def kiem_whisper():  # tuỳ chọn — tên giữ nguyên, nay kiểm NGUỒN chuyển giọng thành chữ (không cài whisper: nặng)
    sys.path.insert(0, HERE)
    import khoa
    khoa.load_env()
    co = [n for n, k in (("Soniox", "SONIOX_API_KEY"), ("OpenAI", "OPENAI_API_KEY"), ("Gemini", "GEMINI_API_KEY"))
          if os.environ.get(k)]
    if importlib.util.find_spec("whisper"):
        co.append("whisper (máy)")
    return bool(co), f"giọng → chữ có mốc thời gian ({', '.join(co) or 'chưa có'}) — phụ đề, chia cảnh, kiểm giọng", \
        "lấy khoá Gemini free (aistudio.google.com) rồi: python khoa.py luu GEMINI_API_KEY"


def kiem_gemini():  # tuỳ chọn
    sys.path.insert(0, HERE)
    import khoa
    khoa.load_env()
    co = bool(os.environ.get("GEMINI_API_KEY"))
    return co, "GEMINI_API_KEY (giọng + ảnh Gemini — tuỳ chọn)", "lấy key free ở aistudio.google.com, copy rồi chạy: python khoa.py luu GEMINI_API_KEY"


def kiem_node():  # tuỳ chọn — phụ đề động + thẻ kết HyperFrames (kiểu "clip có giọng sẵn")
    if not shutil.which("npx"):
        return False, "Node.js 22+ (phụ đề động, thẻ kết HyperFrames — tuỳ chọn)", cach_cai(
            "brew install node", "cài Node 22 từ nodejs.org", "winget install OpenJS.NodeJS.LTS")
    _, out = chay(["node", "-v"])
    try:
        ok = int(out.strip().lstrip("v").split(".")[0]) >= 22
    except ValueError:
        ok = False
    return ok, f"Node.js 22+ (đang có {out.strip()}) — phụ đề động, thẻ kết HyperFrames", "nâng Node lên 22+ (nodejs.org)"


def kiem_numpy():  # tuỳ chọn — đo cao độ giọng clip (do-cao-do-giong.py)
    ok = importlib.util.find_spec("numpy") is not None
    return ok, "numpy (đo cao độ giọng clip — tuỳ chọn)", "pip install numpy"


def kiem_kho():
    try:
        os.makedirs(KHO, exist_ok=True)
        return True, f"thư mục kho {KHO}", ""
    except OSError as e:
        return False, f"thư mục kho {KHO}", str(e)


BAT_BUOC = [kiem_python, kiem_pillow, kiem_ffmpeg, kiem_phu_de, kiem_edge, kiem_kho]
TUY_CHON = [kiem_whisper, kiem_gemini, kiem_node, kiem_numpy]


def in_bang():
    thieu = 0
    print("== BẮT BUỘC ==")
    for f in BAT_BUOC:
        ok, ten, cai = f()
        print(f"  {'✅' if ok else '❌'} {ten}" + ("" if ok else f"\n       → {cai}"))
        thieu += 0 if ok else 1
    print("== TUỲ CHỌN ==")
    for f in TUY_CHON:
        ok, ten, cai = f()
        print(f"  {'✅' if ok else '➖'} {ten}" + ("" if ok else f"\n       → {cai}"))
    return thieu


def thu_dung():
    """Sinh 2 ảnh mẫu bằng Pillow + giọng edge → dựng video-thu.mp4. Chứng minh khâu dựng chạy được."""
    from PIL import Image, ImageDraw
    thu = tempfile.mkdtemp(prefix="tao-video-thu-")
    os.makedirs(os.path.join(thu, "canh"))
    for i, mau in enumerate([(200, 120, 90), (90, 140, 200)], 1):
        im = Image.new("RGB", (1920, 1080), mau)
        ImageDraw.Draw(im).ellipse((760, 340, 1160, 740), fill=(255, 235, 200))
        im.save(os.path.join(thu, "canh", f"{i:02d}.png"))
    kb = {"che_do": "tung-buoc", "kieu": "anh", "khung": [1920, 1080], "tieu_de": "Thử dựng", "tieu_de_giay": 2,
          "giong": {"nguon": "edge", "ten": "vi-VN-HoaiMyNeural"}, "chuyen_mac_dinh": "hoa",
          "canh": [{"id": "01", "hinh": "canh/01.png", "loi": "Đây là cảnh thứ nhất của video thử."},
                   {"id": "02", "hinh": "canh/02.png", "loi": "Và đây là cảnh thứ hai."}]}
    with open(os.path.join(thu, "kich-ban.json"), "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)
    for buoc in (["giong.py"], ["dung-video.py"]):
        print(f"→ {buoc[0]} ...")
        r = subprocess.run([sys.executable, os.path.join(HERE, buoc[0]), "kich-ban.json"], cwd=thu,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(f"❌ {buoc[0]} lỗi:\n{(r.stdout + r.stderr)[-800:]}")
            return False
    video = os.path.join(thu, "video.mp4")
    ok = os.path.exists(video) and os.path.getsize(video) > 10_000
    print(f"{'✅' if ok else '❌'} video thử: {video}" if ok else "❌ không thấy video.mp4")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--thu-dung", action="store_true", help="dựng thử 2 cảnh mẫu")
    a = ap.parse_args()
    thieu = in_bang()
    if thieu:
        print(f"\nCòn thiếu {thieu} thứ bắt buộc — cài xong chạy lại.")
        sys.exit(1)
    print("\nMáy đủ đồ bắt buộc.")
    if a.thu_dung:
        sys.exit(0 if thu_dung() else 1)
