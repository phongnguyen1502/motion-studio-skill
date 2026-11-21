#!/usr/bin/env python3
"""Tạo giọng đọc cho từng cảnh có `loi` trong kich-ban.json → giong/<id>.mp3.

Dùng: giong.py kich-ban.json [--lam-lai]
Nguồn lấy từ kich_ban["giong"]["nguon"]:
  edge    Microsoft Edge TTS — free, không key (vi-VN-HoaiMyNeural nữ, vi-VN-NamMinhNeural nam)
  gemini  Gemini TTS API — free tier, cần GEMINI_API_KEY (giọng Kore, Puck, Charon, Aoede…)
  eleven  ElevenLabs API — free 10k ký tự/tháng, không thương mại, cần ELEVENLABS_API_KEY
  file    không tạo: đã có sẵn giong/<id>.mp3 (Vbee qua GaBee, tự thu, nguồn khác)
File đã có thì bỏ qua (trừ --lam-lai), nên thả file tay vào giong/ để thay riêng một cảnh.
"""
import argparse
import json
import re
import os
import shutil
import subprocess
import time
import sys
import urllib.request
import wave
# Windows: màn hình/ống dẫn mặc định cp1252 → in tiếng Việt là UnicodeEncodeError (máy Windows thật 15/10/2026).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")  # tiến trình Python con cũng in UTF-8


ap = argparse.ArgumentParser()
ap.add_argument("plan")
ap.add_argument("--lam-lai", action="store_true", help="tạo lại cả file đã có")
a = ap.parse_args()

plan = json.load(open(a.plan, encoding="utf-8-sig"))
base = os.path.dirname(os.path.abspath(a.plan))
cfg = plan.get("giong", {})
nguon = cfg.get("nguon", "edge")
out_dir = os.path.join(base, "giong")
os.makedirs(out_dir, exist_ok=True)


def load_env():
    """Nạp khoá từ ~/.tao-video/.env (+ ~/.claude/.env, ~/.config/tts-keys.env) — xem khoa.py."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import khoa
    khoa.load_env()


def to_mp3(src, dst):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ar", "44100", "-b:a", "192k", dst], check=True)


def tts_edge(text, dst):
    exe = shutil.which("edge-tts") or os.path.expanduser("~/.local/bin/edge-tts")
    # pip --user để lệnh edge-tts ngoài PATH (macOS ~/Library/Python/x/bin, Windows %APPDATA%\Python\…\Scripts)
    # → gọi qua module của chính Python đang chạy, khỏi phải sửa PATH của học viên.
    base = [exe] if os.path.exists(exe) else [sys.executable, "-m", "edge_tts"]
    cmd = [*base, "--voice", cfg.get("ten", "vi-VN-HoaiMyNeural"), "--text", text, "--write-media", dst]
    if cfg.get("toc_do"):
        cmd += ["--rate", cfg["toc_do"]]          # vd "+10%" / "-5%"
    subprocess.run(cmd, check=True)


def tts_gemini(text, dst):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    style = cfg.get("phong_cach", "")             # vd "Đọc ấm áp, chậm rãi"
    r = client.models.generate_content(
        model=cfg.get("model", "gemini-3.8-flash-tts"),
        contents=f"{style}: {text}" if style else text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=cfg.get("ten", "Kore"))))))
    pcm = r.candidates[0].content.parts[0].inline_data.data
    tmp = dst + ".wav"
    with wave.open(tmp, "wb") as w:               # Gemini trả PCM 24kHz mono 16-bit
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(24000), w.writeframes(pcm)
    to_mp3(tmp, dst)
    os.remove(tmp)


def tts_eleven(text, dst):
    vid = cfg.get("ten") or "SAz9YHcvj6GT2YYXdXww"
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
        # eleven_multilingual_v2 KHÔNG có tiếng Việt → đọc sai ("giống dược thử trộ video"). Đo 15/10/2026, nghe lại
        # bằng Soniox: turbo_v2_5 đúng từng chữ, flash_v2_5 sai 1 chữ, v3 mất chữ cuối câu.
        data=json.dumps({"text": text, "model_id": cfg.get("model", "eleven_turbo_v2_5"),
                         "language_code": cfg.get("ngon_ngu", "vi")}).encode(),
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
        f.write(r.read())


def tts_soniox(text, dst):
    # Endpoint là tts-rt.soniox.com (KHÔNG phải api.soniox.com → 404); UA mặc định của urllib bị chặn 403.
    req = urllib.request.Request(
        "https://tts-rt.soniox.com/tts",
        data=json.dumps({"model": cfg.get("model", "tts-rt-v2"), "language": "vi", "voice": cfg.get("ten", "Linh"),
                         "text": text, "audio_format": "mp3"}).encode(),
        headers={"Authorization": f"Bearer {os.environ['SONIOX_API_KEY']}", "Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=180) as r:
        audio = r.read()
    if len(audio) < 2000:
        raise RuntimeError(f"audio quá nhỏ ({len(audio)}B)")
    open(dst, "wb").write(audio)


def tts_openai(text, dst):
    # Chỉ gpt-4o-mini-tts có `instructions` điều khiển cảm xúc; tts-1-hd đọc thiếu chữ → đừng dùng.
    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/speech",
        data=json.dumps({"model": cfg.get("model", "gpt-4o-mini-tts"), "voice": cfg.get("ten", "nova"), "input": text,
                         "instructions": cfg.get("phong_cach", "Kể chuyện tự nhiên, có ngữ điệu, không đọc đều đều."),
                         "response_format": "mp3"}).encode(),
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dst, "wb") as f:
        f.write(r.read())


load_env()
make = {"edge": tts_edge, "gemini": tts_gemini, "eleven": tts_eleven,
        "soniox": tts_soniox, "openai": tts_openai}.get(nguon)
missing = []
for c in plan["canh"]:
    if not c.get("loi"):
        continue
    dst = os.path.join(out_dir, f"{c['id']}.mp3")
    if os.path.exists(dst) and os.path.getsize(dst) > 0 and not a.lam_lai:
        print(f"có sẵn  {c['id']}")
        continue
    if make is None:                              # nguon=file mà thiếu file
        missing.append(c["id"])
        continue
    for lan in range(5):                          # Edge/API thỉnh thoảng rớt kết nối: thử lại
        part = dst[:-4] + ".dang-tao.mp3"         # ghi ra file tạm, xong mới đổi tên → không để file hỏng
        try:
            make(c.get("loi_doc") or c["loi"], part)  # loi_doc = lời kèm thẻ cảm xúc [warm]…, chỉ để đọc; loi sạch cho phụ đề
            os.replace(part, dst)
            print(f"tạo     {c['id']}  ({nguon})")
            break
        except Exception as e:
            err = e
            if os.path.exists(part):
                os.remove(part)
            # Hết hạn mức theo phút (Gemini free: 3 lượt/phút → cảnh thứ 4–5 dính 429, máy Windows 15/10/2026):
            # CHỜ đúng số giây máy chủ đòi rồi thử lại, thay vì báo hỏng và bắt agent tự ngồi chờ.
            msg = str(e)
            if "exceeded your current quota" in msg or "PerDay" in msg:
                # Hết hạn mức THEO NGÀY (Gemini free) — chờ vài giây không cứu được, đừng phí 5 lượt thử.
                print(f"HẾT     {c['id']}: {nguon} hết hạn mức trong ngày → đổi nguồn giọng (eleven / openai / edge)")
                missing.append(c["id"])           # break bỏ qua nhánh else → phải tự ghi thiếu ở đây
                break
            if any(k in msg for k in ("429", "RESOURCE_EXHAUSTED", "rate limit", "Too Many Requests")):
                m = re.search(r"retry(?:Delay)?['\"]?[:=]\s*['\"]?(\d+)", msg, re.I) or re.search(r"in (\d+(?:\.\d+)?)s", msg)
                cho = min(65, int(float(m.group(1))) + 2) if m else 25
                print(f"chờ     {c['id']}: {nguon} hết lượt theo phút, đợi {cho}s rồi thử lại")
                time.sleep(cho)
    else:                                         # báo rõ cảnh nào hỏng, chạy tiếp cảnh khác
        print(f"LỖI     {c['id']}: {err}")
        missing.append(c["id"])

if missing:
    print("THIẾU giọng các cảnh:", ", ".join(missing))
    raise SystemExit(1)
