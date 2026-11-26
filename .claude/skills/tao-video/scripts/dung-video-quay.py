#!/usr/bin/env python3
"""[tao-video · kiểu "video quay sẵn"] Video người nói (tự quay, MC, clip AI có thoại) → video 9:16 đã cắt vấp + hiệu ứng.

Hai bước, giữa hai bước là việc của agent (điền nội dung hiệu ứng theo đúng lời nói):

  python dung-video-quay.py chuan-bi <video> <du-an> [--tu 0] [--den 38.2] [--giu-sau]
                                     [--bo 12.3-14.0,20-21] [--giu 5-6] [--khong-cat] [--theme sach] [--model medium]
                                     [--loi loi.txt] [--sua "môn người=muôn người;cực đầu=gật đầu"]
     → du-an/cut.mp4      phần nói, đã cắt từ đệm/lặp/khoảng lặng dài, 1080×1920, 30 fps
       du-an/tail.mp4     (--giu-sau) phần sau --den giữ nguyên (thẻ kết, nhạc…), cũng 1080×1920
       du-an/timing.json  lời nói theo thời gian MỚI (định dạng voice-timing.py: câu + từng chữ)
       du-an/cat.txt      danh sách chỗ đã cắt (đọc lại! cắt nhầm → chạy lại với --giu, sót → --bo)
       du-an/fx-plan.json bản nháp hiệu ứng (fx-suggest.mjs của motion-studio) + "avoid" = vùng mặt
  --loi: lời gốc (mỗi câu một dòng) → phụ đề đúng chính tả, chỉ lấy MỐC thời gian từ máy nghe. Nên dùng khi có kịch bản.
  --sua: sửa nhanh chữ máy nghe sai (cụm=cụm, cách nhau bằng ;) khi không có kịch bản.
  [agent] điền params trong fx-plan.json theo lời nói, xoá _dien, đổi hiệu ứng/cues nếu cần.
  python dung-video-quay.py dung <du-an> [--nhac nhac.mp3] [--nhac-db -20] [--out video.mp4] [--khong-phu-de]
     → du-an/render/fx-9x16.webm (lớp hiệu ứng + phụ đề, nền trong suốt) rồi du-an/video.mp4
       (= cut.mp4 + lớp hiệu ứng + tiếng hiệu ứng + nhạc nền tự nhỏ khi có lời, chuẩn -14 LUFS, + tail.mp4)
  python dung-video-quay.py anh <du-an> 3,8,15      ảnh tĩnh để kiểm (du-an/render/stills/9x16/luoi.png)
  python dung-video-quay.py tach <du-an> [--lam-lai] tách người khỏi nền + bám mặt (anh/dung tự gọi khi plan có hiệu ứng
     cần người: chữ sau lưng, neon sau lưng, chữ trượt sau lưng, hào quang, sticker/vẽ tay quanh đầu, khoá mặt, mở tròn)
     → du-an/work/nguoi.mkv (lớp người) + du-an/mat.json (khung mặt + đỉnh đầu từng khung hình). Model MODNet + YuNet
     (ONNX, chạy trên máy) ở ~/.motion-studio/models. Có hiệu ứng lớp "sau" thì video ghép 3 lớp: nền → hiệu ứng sau
     lưng → người → hiệu ứng trước + phụ đề.

Cần: ffmpeg, node, skill motion-studio (thư viện hiệu ứng assets/fx, render.mjs + Playwright) và một Python có
faster-whisper + opencv (môi trường ~/.motion-studio/asr-venv; script tự chuyển sang Python đó nếu Python đang chạy thiếu).
--tu/--den/--bo/--giu tính bằng giây trên video GỐC. Thời gian trong fx-plan.json là thời gian của cut.mp4.
"""
import argparse, json, os, re, shutil, subprocess, sys, unicodedata
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")

HOME = Path.home()
MS = HOME / ".claude/skills/motion-studio"
VENV_PY = HOME / ".motion-studio/asr-venv/Scripts/python.exe"
if not VENV_PY.exists():
    VENV_PY = HOME / ".motion-studio/asr-venv/bin/python"
W, H, FPS = 1080, 1920, 30
FILLERS = {"ờ", "ừ", "ừm", "ờm", "ơ", "ớ", "à", "um", "uh", "uhm", "hmm", "hừm", "ừa"}


def need_libs():
    try:
        import faster_whisper, cv2  # noqa: F401
        return
    except ImportError:
        pass
    if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
        sys.exit(subprocess.call([str(VENV_PY), __file__, *sys.argv[1:]]))
    sys.exit("Thiếu faster-whisper/opencv. Cài môi trường giọng của motion-studio: scripts/setup-asr.ps1, "
             "rồi: ~/.motion-studio/asr-venv/Scripts/python -m pip install opencv-python-headless")


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def probe(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                          "-of", "json", str(p)], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    return float(j["format"]["duration"]), v["width"], v["height"]


def norm(s):  # same as voice-timing.py
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFC", s.lower()))


def ranges(s):
    out = []
    for part in filter(None, (s or "").split(",")):
        a, b = part.split("-")
        out.append((float(a), float(b)))
    return out


def inside(t, rs):
    return any(a <= t <= b for a, b in rs)


# ---------- 1. lời nói ----------
def transcribe(video, tu, den, model, lang):
    from faster_whisper import WhisperModel
    import numpy as np
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(tu), "-to", str(den), "-i", str(video),
                          "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, dtype=np.float32)
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(audio, language=lang, word_timestamps=True, beam_size=5,
                           condition_on_previous_text=False, vad_filter=False)
    words = []
    for s in segs:
        print(f"  {s.start + tu:6.1f}  {s.text.strip()[:90]}", flush=True)
        for w in s.words or []:
            t = w.word.strip()
            if t:
                words.append({"w": t, "s": round(w.start + tu, 3), "e": round(w.end + tu, 3), "p": round(w.probability, 2)})
    return words


# ---------- 2. chỗ cắt ----------
def decide_cuts(words, bo, giu):
    removed = {}
    for i, w in enumerate(words):
        if inside(w["s"], giu):
            continue
        if inside(w["s"], bo):
            removed[i] = "bỏ theo --bo"
        elif norm(w["w"]) in {norm(f) for f in FILLERS}:
            removed[i] = "từ đệm"
    n = [norm(w["w"]) for w in words]
    for k in (3, 2, 1):  # lặp lời: "tôi tôi", "mình sẽ mình sẽ" → bỏ lần đầu
        for i in range(len(words) - 2 * k + 1):
            if any(j in removed for j in range(i, i + 2 * k)) or inside(words[i]["s"], giu):
                continue
            if n[i:i + k] == n[i + k:i + 2 * k] and all(n[i:i + k]) and words[i + k]["s"] - words[i + k - 1]["e"] < 0.8:
                for j in range(i, i + k):
                    removed[j] = "lặp lời"
    return removed


def keep_ranges(words, removed, tu, den, gap=0.45, pre=0.10, post=0.14):
    """Runs of kept words → source ranges; pauses > gap are shortened to about pre+post."""
    rs, run_ = [], []
    def close():
        if not run_:
            return
        a, b = words[run_[0]]["s"] - pre, words[run_[-1]]["e"] + post
        i0, i1 = run_[0], run_[-1]
        if i0 - 1 in removed: a = max(a, words[i0 - 1]["e"])
        if i1 + 1 in removed: b = min(b, words[i1 + 1]["s"])
        rs.append([max(tu, a), min(den, b)])
    for i, w in enumerate(words):
        if i in removed:
            close(); run_ = []; continue
        if run_ and (w["s"] - words[run_[-1]]["e"] > gap or run_[-1] + 1 != i):
            close(); run_ = []
        run_.append(i)
    close()
    # snap to the frame grid and merge overlaps
    out = []
    for a, b in rs:
        a, b = round(a * FPS) / FPS, round(b * FPS) / FPS
        if out and a <= out[-1][1] + 1e-6:
            out[-1][1] = max(out[-1][1], b)
        elif b - a >= 2 / FPS:
            out.append([a, b])
    return out


def to_out(t, rs):
    acc = 0.0
    for a, b in rs:
        if t < a:
            return acc
        if t <= b:
            return acc + t - a
        acc += b - a
    return acc


# ---------- 3. mặt ----------
def faces(video, rs, sw, sh):
    import cv2
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(str(video))
    boxes, k = [], 540 / sw
    for a, b in rs:
        t = a + 0.2
        while t < b:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, fr = cap.read()
            t += 0.6
            if not ok:
                continue
            g = cv2.cvtColor(cv2.resize(fr, (540, int(sh * k))), cv2.COLOR_BGR2GRAY)
            f = cas.detectMultiScale(g, 1.1, 6, minSize=(int(540 * 0.12), int(540 * 0.12)))
            if len(f):
                x, y, w, h = max(f, key=lambda r: r[2] * r[3])
                boxes.append([x / k, y / k, w / k, h / k])
    cap.release()
    if not boxes:
        return None, 0
    med = [sorted(c)[len(c) // 2] for c in zip(*boxes)]
    return med, len(boxes)


# ---------- 4. câu ----------
def build_lines(words, removed, rs, maxw=22):
    kept = [(w, to_out(w["s"], rs)) for i, w in enumerate(words) if i not in removed]
    lines, cur = [], []
    for k, (w, t) in enumerate(kept):
        cur.append((w, t))
        nxt = kept[k + 1] if k + 1 < len(kept) else None
        gap = nxt[0]["s"] - w["e"] if nxt else 9
        end = re.search(r"[.?!…]$", w["w"]) or gap > 0.7 or len(cur) >= maxw or (len(cur) >= 14 and w["w"].endswith(","))
        if end or not nxt:
            text = " ".join(x["w"] for x, _ in cur)
            lines.append({"i": len(lines), "start": round(cur[0][1], 2), "end": round(to_out(cur[-1][0]["e"], rs), 2),
                          "text": text, "miss": 0, "words": [[norm(x["w"]), round(tt, 2)] for x, tt in cur if norm(x["w"])]})
            cur = []
    return lines


def apply_sua(words, sua):
    """'môn người=muôn người;…' — replace spoken phrases (matched without case/punctuation), keeping the times."""
    for pair in filter(None, (sua or "").split(";")):
        old, new = (x.strip() for x in pair.split("="))
        o, nw = [norm(x) for x in old.split()], new.split()
        i = 0
        while i <= len(words) - len(o):
            if [norm(w["w"]) for w in words[i:i + len(o)]] == o:
                tail = re.search(r"[^\w]*$", words[i + len(o) - 1]["w"]).group(0)   # keep trailing punctuation
                seg = words[i:i + len(o)]
                s0, e0 = seg[0]["s"], seg[-1]["e"]
                rep = [{"w": t, "s": round(s0 + (e0 - s0) * k / len(nw), 3), "e": round(s0 + (e0 - s0) * (k + 1) / len(nw), 3), "p": 1.0}
                       for k, t in enumerate(nw)]
                rep[-1]["w"] += tail
                words[i:i + len(o)] = rep
                i += len(nw)
            else:
                i += 1
    return words


def align_script(kept, script):
    """Script lines (exact text) aligned onto the kept spoken words → voice-timing.py lines (times = output timeline)."""
    import difflib
    lines = [l.strip() for l in open(script, encoding="utf-8") if l.strip()]
    st, own = [], []
    for i, l in enumerate(lines):
        for t in l.split():
            if norm(t):
                st.append(norm(t)); own.append(i)
    wt = [norm(w["w"]) for w, _ in kept]
    tm = [None] * len(st)
    for x, y, n in difflib.SequenceMatcher(None, st, wt, autojunk=False).get_matching_blocks():
        for k in range(n):
            tm[x + k] = [kept[y + k][1], kept[y + k][2]]
    known = [k for k in range(len(st)) if tm[k]]
    for k in range(len(st)):
        if tm[k] is None:
            p = max([j for j in known if j < k], default=None); q = min([j for j in known if j > k], default=None)
            if p is None: tm[k] = [0, 0.2]
            elif q is None: tm[k] = [tm[p][1], tm[p][1] + 0.25]
            else:
                f = (k - p) / (q - p); s0 = tm[p][1] + (tm[q][0] - tm[p][1]) * f; tm[k] = [s0, s0 + 0.2]
    out = []
    for i, l in enumerate(lines):
        idx = [k for k in range(len(st)) if own[k] == i]
        if idx:
            out.append({"i": i, "start": round(tm[idx[0]][0], 2), "end": round(tm[idx[-1]][1], 2), "text": l,
                        "miss": sum(1 for k in idx if k not in set(known)), "words": [[st[k], round(tm[k][0], 2)] for k in idx]})
    return out


def chuan_bi(a):
    need_libs()
    video, du = Path(a.video).resolve(), Path(a.du_an).resolve()
    du.mkdir(parents=True, exist_ok=True)
    dur, sw, sh = probe(video)
    tu, den = a.tu, min(a.den or dur, dur)
    print(f"Video {sw}×{sh}, {dur:.1f}s — xử lý {tu:.1f}–{den:.1f}s" + (", giữ nguyên phần sau" if a.giu_sau else ""))

    cache = du / "work" / "words.json"
    cache.parent.mkdir(exist_ok=True)
    key = {"video": str(video), "tu": tu, "den": den, "model": a.model}
    if cache.exists() and json.loads(cache.read_text(encoding="utf-8")).get("key") == key:
        words = json.loads(cache.read_text(encoding="utf-8"))["words"]
        print(f"Dùng lại bản nghe lời đã có ({len(words)} chữ).")
    else:
        print(f"Nghe lời (faster-whisper {a.model}, chạy trên máy)…")
        words = transcribe(video, tu, den, a.model, a.lang)
        cache.write_text(json.dumps({"key": key, "words": words}, ensure_ascii=False), encoding="utf-8")
    if not words:
        sys.exit("Không nghe thấy lời nói nào.")

    words = apply_sua(words, a.sua)
    if a.den and den - words[-1]["e"] < 0.3:
        print(f"⚠ Chữ cuối ('{words[-1]['w']}') kết thúc sát --den ({words[-1]['e']:.2f}s): có thể lời còn nói tiếp sau {den:.2f}s. "
              "Với --giu-sau phần đó vẫn còn trong đoạn giữ nguyên; nếu không, tăng --den.")
    removed = {} if a.khong_cat else decide_cuts(words, ranges(a.bo), ranges(a.giu))
    rs = [[round(tu * FPS) / FPS, round(den * FPS) / FPS]] if a.khong_cat else keep_ranges(words, removed, tu, den)
    total = sum(b - a_ for a_, b in rs)

    # review file
    with open(du / "cat.txt", "w", encoding="utf-8") as f:
        f.write(f"Giữ {len(rs)} đoạn, {total:.1f}s / {den - tu:.1f}s gốc (bớt {den - tu - total:.1f}s)\n\n")
        for i, w in enumerate(words):
            if i in removed:
                ctx = " ".join(x["w"] for x in words[max(0, i - 4):i + 5])
                f.write(f"  {w['s']:7.2f}  bỏ '{w['w']}' ({removed[i]})   …{ctx}…\n")
        prev = tu
        for a_, b in rs:
            if a_ - prev > 0.3:
                f.write(f"  {prev:7.2f}–{a_:.2f}  rút khoảng lặng {a_ - prev:.1f}s\n")
            prev = b
        f.write("\nCắt nhầm → chạy lại với --giu a-b (giây gốc); sót chỗ vấp/nói lại → --bo a-b.\n")
    print((du / "cat.txt").read_text(encoding="utf-8"))

    # face → crop + avoid box
    print("Dò mặt…")
    face, n = faces(video, rs, sw, sh)
    sc = max(W / sw, H / sh)
    fw, fh = sw * sc, sh * sc
    cx = (face[0] + face[2] / 2) * sc if face else fw / 2
    ox = min(max(cx - W / 2, 0), fw - W)
    oy = (fh - H) / 2 if not face else min(max((face[1] * sc) - H * 0.18, 0), fh - H)
    ox, oy = int(round(ox / 2) * 2), int(round(oy / 2) * 2)
    avoid = []
    if face:
        x, y, w, h = face[0] * sc - ox, face[1] * sc - oy, face[2] * sc, face[3] * sc
        avoid = [{"x": round(x - w * 0.25), "y": round(y - h * 0.45), "w": round(w * 1.5), "h": round(h * 1.75)}]
        print(f"  mặt ở {n} khung, vùng tránh {avoid[0]}")
    else:
        print("  không thấy mặt → cắt giữa khung, hiệu ứng không có vùng tránh")

    # render cut.mp4 (one decode: select/aselect)
    vf = f"scale={round(fw / 2) * 2}:{round(fh / 2) * 2}:flags=lanczos,crop={W}:{H}:{ox}:{oy},fps={FPS},setsar=1"
    expr = "+".join(f"between(t,{a_:.4f},{b - 0.0005:.4f})" for a_, b in rs)
    print(f"Dựng cut.mp4 ({total:.1f}s)…")
    # video: one select pass; audio: atrim + concat per range (aselect keeps every frame on some builds) with
    # 8 ms fades at each edge so the joins do not click
    n = len(rs)
    af = f"[0:a]aresample=48000,asplit={n}" + "".join(f"[s{i}]" for i in range(n)) + ";"
    af += "".join(f"[s{i}]atrim={a_:.4f}:{b:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.008,"
                  f"afade=t=out:st={max(0, b - a_ - 0.008):.4f}:d=0.008[p{i}];" for i, (a_, b) in enumerate(rs))
    af += "".join(f"[p{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-filter_complex",
         f"[0:v]select='{expr}',setpts=N/FRAME_RATE/TB,{vf}[v];{af}",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", du / "cut.mp4"])
    vd = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0", du / "cut.mp4"],
                        capture_output=True, text=True).stdout.split()
    ds = [float(x.split(",")[1]) for x in vd if "," in x and x.split(",")[1] not in ("", "N/A")]
    if ds and max(ds) - min(ds) > 0.1:
        sys.exit(f"Lỗi: hình và tiếng của cut.mp4 lệch nhau ({vd}) — báo lại để sửa.")
    if a.giu_sau and den < dur - 0.1:
        print("Dựng tail.mp4 (phần giữ nguyên)…")
        tvf = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},fps={FPS},setsar=1"
        run(["ffmpeg", "-v", "error", "-y", "-ss", den, "-i", video, "-vf", tvf, "-af", "aresample=48000",
             "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
             du / "tail.mp4"])
    elif (du / "tail.mp4").exists():
        (du / "tail.mp4").unlink()

    if a.loi:
        kept = [(w, to_out(w["s"], rs), to_out(w["e"], rs)) for i, w in enumerate(words) if i not in removed]
        lines = align_script(kept, a.loi)
        bad = [l for l in lines if l["miss"] > len(l["words"]) / 3]
        print(f"Khớp lời gốc: {len(lines)} câu" + (f", {len(bad)} câu khớp kém (kiểm lại lời gốc có đúng với lời nói không)" if bad else ""))
    else:
        lines = build_lines(words, removed, rs)
    (du / "timing.json").write_text(json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    (du / "cut.json").write_text(json.dumps({"video": str(video), "tu": tu, "den": den, "ranges": rs, "duration": total,
                                             "avoid": avoid}, ensure_ascii=False, indent=1), encoding="utf-8")

    # draft effects
    plan = du / "fx-plan.json"
    if plan.exists() and not a.lam_lai_plan:
        print(f"\nĐã có {plan.name} — giữ nguyên (thời gian có thể đã đổi nếu chỗ cắt đổi; --lam-lai-plan để tạo lại nháp).")
    else:
        run(["node", MS / "scripts/fx-suggest.mjs", du / "timing.json", "--out", plan, "--theme", a.theme,
             *(["--nguoi"] if face else [])])
        p = json.loads(plan.read_text(encoding="utf-8"))
        p.update({"avoid": avoid, "duration": round(total, 2), "subtitles": True, "voice": None})
        plan.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nXong bước 1. Việc tiếp: điền params trong {plan} theo đúng lời nói, xoá _dien; rồi\n"
          f"  python {Path(__file__).name} anh \"{du}\" 3,8      (kiểm ảnh)\n  python {Path(__file__).name} dung \"{du}\"")


# ---------- 5. tách người + bám mặt (cho hiệu ứng sau lưng người / quanh đầu) ----------
MODELS = HOME / ".motion-studio/models"
MODNET, YUNET = MODELS / "modnet.onnx", MODELS / "face_detection_yunet_2023mar.onnx"
CATALOG = MS / "assets/fx/hieu-ung.json"


def person_types():
    """(types drawn behind the speaker, types that need the speaker) from the fx catalogue."""
    c = json.loads(CATALOG.read_text(encoding="utf-8"))
    sau = {k for k, v in c.items() if isinstance(v, dict) and v.get("lop") == "sau"}
    nguoi = {k for k, v in c.items() if isinstance(v, dict) and v.get("can_nguoi")}
    return sau, nguoi | sau


def tach(du, force=False):
    """cut.mp4 → work/nguoi.mkv (person matte, gray, lossless) + mat.json (face box + top of head per frame).
    MODNet portrait matting and YuNet face detection, both ONNX on the CPU (~0.1 s per frame)."""
    need_libs()
    import cv2, numpy as np, onnxruntime as ort
    cut, mask, track = du / "cut.mp4", du / "work/nguoi.mkv", du / "mat.json"
    if not force and mask.exists() and track.exists() and mask.stat().st_mtime > cut.stat().st_mtime:
        return
    for m in (MODNET, YUNET):
        if not m.exists():
            sys.exit(f"Thiếu model {m.name} trong {MODELS} — chạy lại setup-asr của motion-studio (tải MODNet + YuNet).")
    dur, _, _ = probe(cut)
    n_est = int(dur * FPS + 0.5)
    sw, sh = W // 2, H // 2                       # work at 540×960
    mw, mh = 384, 672                             # MODNet input (multiples of 32)
    # OpenCV's and onnxruntime's thread pools fight over the cores (measured 0.45 s/frame → 0.1 s/frame when separated)
    cv2.setNumThreads(1)
    so = ort.SessionOptions(); so.intra_op_num_threads = max(1, min(8, (os.cpu_count() or 4) - 2))
    sess = ort.InferenceSession(str(MODNET), so, providers=["CPUExecutionProvider"])
    iname = sess.get_inputs()[0].name
    det = cv2.FaceDetectorYN.create(str(YUNET), "", (sw, sh), 0.6, 0.3, 50)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(cut), "-vf", f"scale={sw}:{sh}", "-f", "rawvideo",
                            "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    mask.parent.mkdir(exist_ok=True)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{sw}x{sh}",
                            "-r", str(FPS), "-i", "-", "-vf", f"scale={W}:{H}:flags=bicubic", "-c:v", "ffv1",
                            "-pix_fmt", "gray", str(mask)], stdin=subprocess.PIPE)
    prev, rows, i = None, [], 0
    print(f"Tách người khỏi nền + dò mặt ({n_est} khung, chạy trên máy)…", flush=True)
    while True:
        buf = dec.stdout.read(sw * sh * 3)
        if len(buf) < sw * sh * 3:
            break
        fr = np.frombuffer(buf, np.uint8).reshape(sh, sw, 3)
        x = cv2.resize(fr, (mw, mh), interpolation=cv2.INTER_AREA)[:, :, ::-1].astype(np.float32)
        x = np.ascontiguousarray(((x / 255.0 - 0.5) / 0.5).transpose(2, 0, 1)[None])
        a = sess.run(None, {iname: x})[0][0, 0]
        a = cv2.resize(a, (sw, sh), interpolation=cv2.INTER_LINEAR)
        a = a if prev is None else 0.7 * a + 0.3 * prev          # a little temporal smoothing against flicker
        prev = a
        enc.stdin.write((np.clip(a, 0, 1) * 255).astype(np.uint8).tobytes())
        _, faces_ = det.detect(fr)
        if faces_ is not None and len(faces_):
            fx, fy, fw, fh = max(faces_, key=lambda r: r[2] * r[3] * r[14])[:4]
            x0, x1 = int(max(0, fx + fw * 0.2)), int(min(sw, fx + fw * 0.8))
            col = (a[:, x0:x1] > 0.5).mean(axis=1) if x1 > x0 else np.zeros(sh)
            hit = np.nonzero(col > 0.35)[0]
            top = float(hit[0]) if len(hit) and hit[0] < fy else fy - fh * 0.35
            rows.append([fx, fy, fw, fh, max(0.0, top)])
        else:
            rows.append(None)
        i += 1
        if i % 150 == 0:
            print(f"  {i}/{n_est}", flush=True)
    dec.wait(); enc.stdin.close(); enc.wait()
    if enc.returncode or i == 0:
        sys.exit("Lỗi khi ghi lớp tách người (work/nguoi.mkv).")
    # fill gaps from the nearest detected frame, then a centred moving average against jitter
    known = [k for k, r in enumerate(rows) if r]
    if not known:
        print("⚠ Không thấy mặt trong video: hiệu ứng quanh đầu sẽ đặt theo vùng mặc định.")
        track.write_text(json.dumps({"fps": FPS, "w": W, "h": H, "f": [None] * len(rows)}), encoding="utf-8")
        return
    arr = np.array([rows[min(known, key=lambda k: abs(k - j))] for j in range(len(rows))], dtype=np.float64)
    ker = np.ones(7) / 7
    sm = np.stack([np.convolve(np.pad(arr[:, c], 3, mode="edge"), ker, mode="valid") for c in range(5)], axis=1) * 2
    track.write_text(json.dumps({"fps": FPS, "w": W, "h": H, "f": [[round(v) for v in r] for r in sm.tolist()]}), encoding="utf-8")
    print(f"✔ work/nguoi.mkv + mat.json — mặt thấy ở {len(known)}/{len(rows)} khung")


def plan_layers(du):
    """(has effects behind the speaker, needs the matte/track) for the current fx-plan.json."""
    p = json.loads((du / "fx-plan.json").read_text(encoding="utf-8"))
    sau, nguoi = person_types()
    types = {x["type"] for x in p.get("fx", [])}
    back = any(x.get("layer") == "sau" or (x["type"] in sau and x.get("layer") != "truoc") for x in p.get("fx", []))
    return back, bool(types & nguoi) or back


def prepare_person(du):
    """Matte + track when the plan needs them; points the plan at mat.json. Returns True when there is a back layer."""
    back, need = plan_layers(du)
    if need:
        tach(du)
        pf = du / "fx-plan.json"
        p = json.loads(pf.read_text(encoding="utf-8"))
        if p.get("track") != "mat.json":
            p["track"] = "mat.json"
            pf.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return back


def comp_graph(base, front, back=None, mask=None, out="v"):
    """Video filter: base footage, then the 'behind' layer, then the person cut out by the matte, then the front layer."""
    if back is None:
        return f"[{base}:v][{front}:v]overlay=format=auto:eof_action=pass[{out}]"
    return (f"[{base}:v]split[cbg][cfg];[cbg][{back}:v]overlay=format=auto:eof_action=pass[cb1];"
            f"[{mask}:v]format=gray,scale={W}:{H}[cm];[cfg]format=yuva420p[cfa];[cfa][cm]alphamerge[cpp];"
            f"[cb1][cpp]overlay=format=auto[cb2];[cb2][{front}:v]overlay=format=auto:eof_action=pass[{out}]")


# ---------- 6. dựng ----------
def copy_fx(du):
    if not (MS / "assets/fx/overlay.html").exists():
        sys.exit(f"Không thấy thư viện hiệu ứng ở {MS}/assets/fx — cần skill motion-studio bản có assets/fx.")
    shutil.copytree(MS / "assets/fx", du / "fx", dirs_exist_ok=True)
    for f in ("kit.js", "typeset.js"):
        shutil.copy2(MS / "assets/template" / f, du / f)
    shutil.copytree(MS / "assets/template/fonts-vi", du / "fonts-vi", dirs_exist_ok=True)


def render_layer(du, extra, layer=None):
    q = "plan=../fx-plan.json" + (f"&layer={layer}" if layer else "")
    run(["node", MS / "scripts/render.mjs", du, "--entry", "fx/overlay.html", "--query", q, "--format", "9x16", *extra])


def check_plan(du):
    p = json.loads((du / "fx-plan.json").read_text(encoding="utf-8"))
    left = [f"#{i + 1} {x['type']}" for i, x in enumerate(p.get("fx", [])) if "_dien" in x]
    if left:
        print("⚠ Chưa điền xong (còn _dien): " + ", ".join(left))


def anh(a):
    """Transparent stills of the layer (Playwright's Chromium cannot decode H.264), laid on cut.mp4 frames by ffmpeg."""
    du = Path(a.du_an).resolve()
    copy_fx(du); check_plan(du)
    back = prepare_person(du)
    sd = du / "render/stills/9x16"
    times = [float(x) for x in a.times.split(",")]
    name = lambda t: sd / ("t_" + f"{t:.2f}".zfill(6) + ".png")   # render.mjs naming
    bd = du / "render/stills/sau"                      # render.mjs empties stills/9x16 on every run
    if back:
        render_layer(du, ["--stills", a.times, "--alpha"], "sau")
        bd.mkdir(parents=True, exist_ok=True)
        for t in times:
            shutil.move(name(t), bd / f"sau_{t:.2f}.png")
    render_layer(du, ["--stills", a.times, "--alpha"], "truoc" if back else None)
    outs = []
    for t in times:
        o = sd / f"anh_{t:.2f}.png"
        # -loop 1: a one-frame PNG ends at once, and with eof_action=pass the overlay would drop it when the
        # person branch of the 3-layer graph arrives later
        ins = ["-ss", t, "-i", du / "cut.mp4", "-loop", "1", "-i", name(t)]
        if back:
            ins += ["-loop", "1", "-i", bd / f"sau_{t:.2f}.png", "-ss", t, "-i", du / "work/nguoi.mkv"]
        fc = comp_graph(0, 1, 2 if back else None, 3 if back else None, "c") + ";[c]scale=540:-2[o]"
        run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", "[o]", "-frames:v", "1", o])
        outs.append(o)
    cols = min(4, len(outs))
    lst = sd / "anh.txt"
    lst.write_text("\n".join(f"file '{o.as_posix()}'" for o in outs), encoding="utf-8")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-vf",
         f"tile={cols}x{-(-len(outs) // cols)}:padding=6:color=black", "-frames:v", "1", sd / "luoi.png"])
    print(f"✔ {sd / 'luoi.png'}")


def dung(a):
    du = Path(a.du_an).resolve()
    copy_fx(du); check_plan(du)
    p = json.loads((du / "fx-plan.json").read_text(encoding="utf-8"))
    if a.khong_phu_de:
        p["subtitles"] = False
        (du / "fx-plan.json").write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    back = prepare_person(du)
    if back:
        print("Dựng lớp hiệu ứng SAU LƯNG người (nền trong suốt)…")
        render_layer(du, ["--alpha", "--name", "fx-sau"], "sau")
    print("Dựng lớp hiệu ứng + phụ đề (nền trong suốt)…")
    render_layer(du, ["--alpha", "--name", "fx"], "truoc" if back else None)
    layer = du / "render/fx-9x16.webm"
    out = du / a.out
    music = Path(a.nhac).resolve() if a.nhac else None
    cut = json.loads((du / "cut.json").read_text(encoding="utf-8"))
    tail = du / "tail.mp4"
    # The voice comes straight from the ORIGINAL video in one chain: no AAC file boundary and no fade at the join with the
    # kept tail (speech often runs across it, e.g. "…không nhận ra" over the end-card transition). Fades only at real cuts.
    rs = [list(r) for r in cut["ranges"]]
    if tail.exists():
        src_dur, _, _ = probe(cut["video"])
        if rs and abs(rs[-1][1] - cut["den"]) < 0.02:
            rs[-1][1] = src_dur
        else:
            rs.append([cut["den"], src_dur])
    n = len(rs)
    ins = ["-i", du / "cut.mp4", "-c:v", "libvpx-vp9", "-i", layer, "-i", cut["video"]]
    k = 3
    if tail.exists():
        ins += ["-i", tail]; ti = k; k += 1
    bi = mi = None
    if back:
        ins += ["-c:v", "libvpx-vp9", "-i", du / "render/fx-sau-9x16.webm", "-i", du / "work/nguoi.mkv"]; bi, mi = k, k + 1; k += 2
    fc = comp_graph(0, 1, bi, mi, "bv" if tail.exists() else "v") + (f";[bv][{ti}:v]concat=n=2:v=1:a=0[v];" if tail.exists() else ";")
    fc += f"[2:a]aresample=48000,asplit={n}" + "".join(f"[s{i}]" for i in range(n)) + ";"
    for i, (x, y) in enumerate(rs):
        fades = ([f"afade=t=in:d=0.008"] if i > 0 else []) + ([f"afade=t=out:st={max(0, y - x - 0.008):.4f}:d=0.008"] if i < n - 1 else [])
        fc += f"[s{i}]atrim={x:.4f}:{y:.4f},asetpts=PTS-STARTPTS" + "".join("," + f for f in fades) + f"[p{i}];"
    fc += "".join(f"[p{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[vo];[1:a]volume=0.9,apad[sx];"
    if music:
        ins += ["-stream_loop", "-1", "-i", music]
        fc += (f"[{k}:a]volume={a.nhac_db}dB,aresample=48000[m];[vo]asplit=2[vv][key];"
               "[m][key]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[md];"
               "[vv][sx][md]amix=inputs=3:normalize=0:duration=first[mx];")
    else:
        fc += "[vo][sx]amix=inputs=2:normalize=0:duration=first[mx];"
    fc += "[mx]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]"
    print("Ghép lớp hiệu ứng, tiếng" + (", nhạc nền" if music else "") + (", phần giữ nguyên ở cuối" if tail.exists() else "") + "…")
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-shortest", out])
    d, _, _ = probe(out)
    print(f"✔ {out}  ({d:.1f}s)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p1 = sp.add_parser("chuan-bi")
    p1.add_argument("video"); p1.add_argument("du_an")
    p1.add_argument("--tu", type=float, default=0.0); p1.add_argument("--den", type=float)
    p1.add_argument("--giu-sau", action="store_true"); p1.add_argument("--khong-cat", action="store_true")
    p1.add_argument("--bo", default=""); p1.add_argument("--giu", default="")
    p1.add_argument("--theme", default="sach"); p1.add_argument("--model", default="medium"); p1.add_argument("--lang", default="vi")
    p1.add_argument("--lam-lai-plan", action="store_true")
    p1.add_argument("--loi", help="lời gốc, mỗi câu một dòng"); p1.add_argument("--sua", default="")
    p2 = sp.add_parser("dung")
    p2.add_argument("du_an"); p2.add_argument("--nhac"); p2.add_argument("--nhac-db", type=float, default=-20)
    p2.add_argument("--out", default="video.mp4"); p2.add_argument("--khong-phu-de", action="store_true")
    p3 = sp.add_parser("anh")
    p3.add_argument("du_an"); p3.add_argument("times")
    p4 = sp.add_parser("tach")
    p4.add_argument("du_an"); p4.add_argument("--lam-lai", action="store_true")
    a = ap.parse_args()
    {"chuan-bi": chuan_bi, "dung": dung, "anh": anh,
     "tach": lambda a: tach(Path(a.du_an).resolve(), a.lam_lai)}[a.cmd](a)


if __name__ == "__main__":
    main()
