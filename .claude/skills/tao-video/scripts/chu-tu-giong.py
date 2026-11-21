#!/usr/bin/env python3
"""Giọng → chữ có MỐC THỜI GIAN (từng từ + từng câu) để căn phụ đề và chia cảnh theo lời nói thật.

  python chu-tu-giong.py <file mp3/wav/mp4…> [--nguon soniox|openai|gemini|whisper] [--ngon-ngu vi]
                          [--so-chu 6] [--ra <tên gốc>]

Ra hai file cạnh file vào (hoặc theo --ra):
  <tên>.chu.json  {"nguon", "text", "tu": [{"w", "bd", "kt"}], "cau": [{"text", "bd", "kt"}]}  (giây)
  <tên>.srt       phụ đề, mỗi dòng tối đa --so-chu chữ, ngắt ở dấu câu hoặc chỗ ngừng > 0,5s

Dùng khi lời nói KHÔNG do skill tự sinh: giọng tự thu, clip Flow/Veo/Muse có thoại sẵn, video có sẵn cần phụ đề,
hoặc muốn chia cảnh theo câu nói. (Giọng TTS do giong.py tạo thì dung-video.py đã tự căn, không cần bước này.)

Nguồn (bỏ --nguon thì tự chọn cái đầu tiên có khoá theo đúng thứ tự này):
  soniox  SONIOX_API_KEY — tiếng Việt tốt nhất, mốc từng từ chính xác, rẻ
  openai  OPENAI_API_KEY — whisper-1, mốc từng từ
  eleven  ELEVENLABS_API_KEY — Scribe v2, mốc từng từ, nhanh nhất (1,1s cho 6s giọng); cùng khoá với giọng ElevenLabs
  gemini  GEMINI_API_KEY — free tier; mốc theo CÂU (ước lượng, kém chính xác hơn hai nguồn trên)
  whisper chỉ dùng khi máy ĐÃ có sẵn (không gợi ý cài: nặng hàng GB, chậm gấp ~3, sai chữ nhiều hơn)
Khoá đọc qua khoa.py (~/.tao-video/.env…).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import khoa  # noqa: E402
# Windows: màn hình/ống dẫn mặc định cp1252 → in tiếng Việt là UnicodeEncodeError (máy Windows thật 15/10/2026).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")  # tiến trình Python con cũng in UTF-8


THU_TU = ["soniox", "openai", "eleven", "gemini", "whisper"]
KHOA_CUA = {"soniox": "SONIOX_API_KEY", "openai": "OPENAI_API_KEY", "eleven": "ELEVENLABS_API_KEY",
            "gemini": "GEMINI_API_KEY"}


def am_thanh_gon(src, tmp):
    """Tách tiếng ra mp3 mono 16kHz: file nhỏ để tải lên nhanh, video cũng dùng được."""
    dst = os.path.join(tmp, "a.mp3")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", dst],
                   check=True)
    return dst


def _http(method, url, headers=None, data=None, timeout=300):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    return json.loads(body) if body else {}


def _multipart(fields, file_field, path, mime="audio/mpeg"):
    b = uuid.uuid4().hex
    out = b""
    for k, v in fields:
        out += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    out += (f"--{b}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{os.path.basename(path)}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n").encode() + open(path, "rb").read() + b"\r\n"
    out += f"--{b}--\r\n".encode()
    return out, f"multipart/form-data; boundary={b}"


def stt_soniox(audio, lang):
    h = {"Authorization": f"Bearer {os.environ['SONIOX_API_KEY']}"}
    api = "https://api.soniox.com/v1"
    body, ctype = _multipart([], "file", audio)
    f = _http("POST", f"{api}/files", {**h, "Content-Type": ctype}, body)
    t = _http("POST", f"{api}/transcriptions", {**h, "Content-Type": "application/json"},
              json.dumps({"model": "stt-async-v5", "file_id": f["id"], "language_hints": [lang]}).encode())
    try:
        for _ in range(600):
            st = _http("GET", f"{api}/transcriptions/{t['id']}", h)
            if st.get("status") == "completed":
                break
            if st.get("status") == "error":
                raise RuntimeError(st.get("error_message") or "Soniox báo lỗi")
            time.sleep(1)
        tr = _http("GET", f"{api}/transcriptions/{t['id']}/transcript", h)
    finally:  # không để file ghi âm của người dùng nằm lại trên máy chủ Soniox
        for u in (f"{api}/transcriptions/{t['id']}", f"{api}/files/{f['id']}"):
            try:
                _http("DELETE", u, h)
            except Exception:
                pass
    # Token Soniox là mẩu chữ; mẩu bắt đầu bằng dấu cách = từ mới.
    tu = []
    for tok in tr.get("tokens", []):
        txt = tok.get("text", "")
        if not txt.strip():
            continue
        if txt.startswith(" ") or not tu:
            tu.append({"w": txt.strip(), "bd": tok["start_ms"] / 1000, "kt": tok["end_ms"] / 1000})
        else:
            tu[-1]["w"] += txt
            tu[-1]["kt"] = tok["end_ms"] / 1000
    return tu, None


def stt_openai(audio, lang):
    body, ctype = _multipart([("model", "whisper-1"), ("language", lang), ("response_format", "verbose_json"),
                              ("timestamp_granularities[]", "word"), ("timestamp_granularities[]", "segment")],
                             "file", audio)
    d = _http("POST", "https://api.openai.com/v1/audio/transcriptions",
              {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": ctype}, body)
    tu = [{"w": w["word"].strip(), "bd": w["start"], "kt": w["end"]} for w in d.get("words", [])]
    cau = [{"text": s["text"].strip(), "bd": s["start"], "kt": s["end"]} for s in d.get("segments", [])]
    return tu, cau


def stt_eleven(audio, lang):
    body, ctype = _multipart([("model_id", "scribe_v2"), ("language_code", lang), ("timestamps_granularity", "word")],
                             "file", audio)
    d = _http("POST", "https://api.elevenlabs.io/v1/speech-to-text",
              {"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": ctype}, body)
    tu = [{"w": w["text"].strip(), "bd": w["start"], "kt": w["end"]} for w in d.get("words", [])
          if w.get("type") == "word" and w.get("start") is not None and w["text"].strip()]
    return tu, None


def stt_gemini(audio, lang, model=None):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    hd = (f"Chép lại chính xác lời nói trong đoạn âm thanh (ngôn ngữ: {lang}), giữ dấu câu. Trả về JSON: "
          '{"cau": [{"text": "...", "bd": <giây bắt đầu>, "kt": <giây kết thúc>}]}, mỗi câu một phần tử, '
          "mốc thời gian là số giây tính từ đầu file, chính xác tới 0,1 giây. Không thêm gì khác.")
    r = client.models.generate_content(
        model=model or "gemini-2.5-flash",
        contents=[types.Part.from_bytes(data=open(audio, "rb").read(), mime_type="audio/mpeg"), hd],
        config=types.GenerateContentConfig(response_mime_type="application/json"))
    cau = json.loads(r.text)["cau"]
    # Gemini chỉ cho mốc câu → chia đều mốc cho từng từ theo độ dài chữ (đủ để căn phụ đề theo cụm).
    tu = []
    for c in cau:
        ws = c["text"].split()
        tong = sum(len(w) for w in ws) or 1
        t = float(c["bd"])
        for w in ws:
            d = (float(c["kt"]) - float(c["bd"])) * len(w) / tong
            tu.append({"w": w, "bd": round(t, 2), "kt": round(t + d, 2)})
            t += d
    return tu, [{"text": c["text"], "bd": float(c["bd"]), "kt": float(c["kt"])} for c in cau]


def stt_whisper(audio, lang, tmp):
    try:
        import whisper  # noqa: F401
    except ImportError:
        raise RuntimeError("máy chưa có whisper — dùng --nguon soniox/openai/gemini (đừng cài whisper: nặng)")
    subprocess.run([sys.executable, "-m", "whisper", audio, "--language", lang, "--model", "small",
                    "--word_timestamps", "True", "--output_format", "json", "--output_dir", tmp],
                   check=True, capture_output=True)
    d = json.load(open(os.path.join(tmp, "a.json"), encoding="utf-8"))
    tu = [{"w": w["word"].strip(), "bd": w["start"], "kt": w["end"]}
          for s in d["segments"] for w in s.get("words", [])]
    cau = [{"text": s["text"].strip(), "bd": s["start"], "kt": s["end"]} for s in d["segments"]]
    return tu, cau


def gom_cau(tu):
    """Câu = cụm từ kết thúc ở dấu câu cuối câu hoặc chỗ ngừng > 0,7s."""
    cau, cur = [], []
    for i, w in enumerate(tu):
        cur.append(w)
        ngung = i + 1 < len(tu) and tu[i + 1]["bd"] - w["kt"] > 0.7
        if re.search(r"[.!?…]$", w["w"]) or ngung or i == len(tu) - 1:
            cau.append({"text": " ".join(x["w"] for x in cur), "bd": cur[0]["bd"], "kt": cur[-1]["kt"]})
            cur = []
    return cau


def srt(tu, so_chu):
    def ts(x):
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    dong, cur, out = [], [], []
    for i, w in enumerate(tu):
        cur.append(w)
        ngat = (len(cur) >= so_chu or re.search(r"[,.!?;:…]$", w["w"])
                or (i + 1 < len(tu) and tu[i + 1]["bd"] - w["kt"] > 0.5) or i == len(tu) - 1)
        if ngat:
            dong.append(cur)
            cur = []
    for n, d in enumerate(dong, 1):
        out.append(f"{n}\n{ts(d[0]['bd'])} --> {ts(d[-1]['kt'])}\n{' '.join(x['w'] for x in d)}\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vao")
    ap.add_argument("--nguon", choices=THU_TU)
    ap.add_argument("--ngon-ngu", default="vi")
    ap.add_argument("--so-chu", type=int, default=6)
    ap.add_argument("--ra")
    ap.add_argument("--model")
    a = ap.parse_args()
    khoa.load_env()
    co_whisper = __import__("importlib.util").util.find_spec("whisper") is not None
    nguon = a.nguon or next((n for n in THU_TU if (co_whisper if n == "whisper" else os.environ.get(KHOA_CUA[n]))), None)
    if not nguon:
        # Không gợi ý cài whisper: nặng (PyTorch + model, hàng GB) và chậm — khoá Gemini free nhanh và nhẹ hơn hẳn.
        print("❌ Chưa có nguồn chuyển giọng thành chữ. Lấy khoá Gemini miễn phí ở aistudio.google.com, copy rồi chạy:"
              " python khoa.py luu GEMINI_API_KEY (hoặc dùng SONIOX_API_KEY / OPENAI_API_KEY)")
        return 1
    if nguon in KHOA_CUA and not os.environ.get(KHOA_CUA[nguon]):
        print(f"❌ Chưa có {KHOA_CUA[nguon]} — copy khoá rồi chạy: python khoa.py luu {KHOA_CUA[nguon]}")
        return 1
    goc = a.ra or os.path.splitext(a.vao)[0]
    with tempfile.TemporaryDirectory() as tmp:
        audio = am_thanh_gon(a.vao, tmp)
        t0 = time.time()
        try:
            if nguon == "soniox":
                tu, cau = stt_soniox(audio, a.ngon_ngu)
            elif nguon == "openai":
                tu, cau = stt_openai(audio, a.ngon_ngu)
            elif nguon == "eleven":
                tu, cau = stt_eleven(audio, a.ngon_ngu)
            elif nguon == "gemini":
                tu, cau = stt_gemini(audio, a.ngon_ngu, a.model)
            else:
                tu, cau = stt_whisper(audio, a.ngon_ngu, tmp)
        except urllib.error.HTTPError as e:
            print(f"❌ {nguon} lỗi HTTP {e.code}: {e.read()[:300].decode('utf-8', 'ignore')}")
            return 1
        except Exception as e:
            print(f"❌ {nguon} lỗi: {str(e)[:300]}")
            return 1
    if not tu:
        print(f"❌ {nguon} không nghe ra lời nào (file im lặng hoặc sai ngôn ngữ?)")
        return 1
    cau = cau or gom_cau(tu)
    kq = {"nguon": nguon, "text": " ".join(w["w"] for w in tu), "tu": tu, "cau": cau}
    json.dump(kq, open(goc + ".chu.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(goc + ".srt", "w", encoding="utf-8").write(srt(tu, a.so_chu))
    print(f"✅ {nguon}: {len(tu)} từ, {len(cau)} câu, {time.time() - t0:.1f}s → {goc}.chu.json + {goc}.srt")
    print("   " + kq["text"][:160])
    return 0


if __name__ == "__main__":
    sys.exit(main())
