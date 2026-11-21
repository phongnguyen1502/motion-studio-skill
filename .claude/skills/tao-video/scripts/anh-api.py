#!/usr/bin/env python3
"""Tạo ảnh bằng API (khi người dùng có khoá) — đường thay cho flow GaBee, cùng chỗ đặt file.

  python anh-api.py gemini "mô tả ảnh" canh/01.png [--khung 9:16] [--tham-chieu a.png b.png] [--model ...]
  python anh-api.py openai "mô tả ảnh" canh/01.png [--khung 16:9] [--tham-chieu a.png]
  python anh-api.py thu gemini|openai            # tạo 1 ảnh nhỏ để kiểm khoá (tốn 1 lượt)

Khoá đọc qua khoa.py (~/.tao-video/.env…). Gemini: GEMINI_API_KEY, model mặc định
gemini-3.1-flash-image (Nano Banana) — free tier của Google có thể không gồm tạo ảnh, lỗi 429
nghĩa là hết hạn mức chứ không phải khoá sai. OpenAI: OPENAI_API_KEY, model gpt-image-1 (trả phí).
Ảnh tham chiếu = giữ nhân vật/bối cảnh như flow GaBee (xem nhat-quan-va-noi-canh.md).
"""
import argparse
import base64
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import khoa  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kho import KHO  # noqa: E402  (kho theo thư mục Downloads thật, kể cả khi đã chuyển sang ổ khác)
# Windows: màn hình/ống dẫn mặc định cp1252 → in tiếng Việt là UnicodeEncodeError (máy Windows thật 15/10/2026).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")  # tiến trình Python con cũng in UTF-8


KHUNG_OPENAI = {"16:9": "1536x1024", "9:16": "1024x1536", "1:1": "1024x1024"}


def gemini(prompt, dst, khung, tham_chieu, model):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    parts = []
    for p in tham_chieu:
        mime = "image/png" if p.lower().endswith(".png") else "image/jpeg"
        parts.append(types.Part.from_bytes(data=open(p, "rb").read(), mime_type=mime))
    parts.append(f"{prompt}\nKhung hình {khung}.")
    cfg = types.GenerateContentConfig(response_modalities=["IMAGE"],
                                      image_config=types.ImageConfig(aspect_ratio=khung))
    r = client.models.generate_content(model=model or "gemini-3.1-flash-image", contents=parts, config=cfg)
    for part in r.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            open(dst, "wb").write(part.inline_data.data)
            return
    raise RuntimeError("Gemini không trả ảnh (có thể bị chặn nội dung) — đổi mô tả rồi thử lại")


def openai(prompt, dst, khung, tham_chieu, model):
    key = os.environ["OPENAI_API_KEY"]
    size = KHUNG_OPENAI.get(khung, "1024x1024")
    if tham_chieu:  # /images/edits nhận ảnh tham chiếu qua multipart
        import uuid
        b = uuid.uuid4().hex
        body = b""
        fields = {"model": model or "gpt-image-1", "prompt": prompt, "size": size}
        for k, v in fields.items():
            body += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        for p in tham_chieu:
            body += (f"--{b}\r\nContent-Disposition: form-data; name=\"image[]\"; filename=\"{os.path.basename(p)}\"\r\n"
                     f"Content-Type: image/png\r\n\r\n").encode() + open(p, "rb").read() + b"\r\n"
        body += f"--{b}--\r\n".encode()
        req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=body,
                                     headers={"Authorization": f"Bearer {key}",
                                              "Content-Type": f"multipart/form-data; boundary={b}"})
    else:
        req = urllib.request.Request("https://api.openai.com/v1/images/generations",
                                     data=json.dumps({"model": model or "gpt-image-1", "prompt": prompt,
                                                      "size": size}).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
    open(dst, "wb").write(base64.b64decode(d["data"][0]["b64_json"]))


NGUON = {"gemini": gemini, "openai": openai}


def main():
    khoa.load_env()
    if len(sys.argv) >= 3 and sys.argv[1] == "thu":
        nguon = sys.argv[2]
        dst = os.path.join(KHO, "_thu", f"anh-api-{nguon}.png")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        args = argparse.Namespace(nguon=nguon, prompt="một quả táo đỏ trên bàn gỗ, ánh sáng buổi sáng, không chữ",
                                  dst=dst, khung="1:1", tham_chieu=[], model=None)
    else:
        ap = argparse.ArgumentParser()
        ap.add_argument("nguon", choices=NGUON)
        ap.add_argument("prompt")
        ap.add_argument("dst")
        ap.add_argument("--khung", default="9:16")
        ap.add_argument("--tham-chieu", nargs="*", default=[])
        ap.add_argument("--model")
        args = ap.parse_args()
    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.dst)), exist_ok=True)
        NGUON[args.nguon](args.prompt, args.dst, args.khung, args.tham_chieu, args.model)
    except KeyError as e:
        print(f"❌ Chưa có khoá {e} — lưu bằng: python khoa.py luu {str(e).strip(chr(39))}")
        return 1
    except Exception as e:
        print(f"❌ {args.nguon} lỗi: {str(e)[:400]}")
        return 1
    print(f"✅ Ảnh: {args.dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
