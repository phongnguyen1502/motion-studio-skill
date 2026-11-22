#!/usr/bin/env python3
"""[tao-video · nhiều góc máy / mic rời] Khớp giờ các máy theo tiếng, đề xuất chỗ chuyển góc, dựng một video 9:16.

  python ghep-goc.py khop <máy-chính> <máy-2> [máy-3 …] <du-an> [--mic mic.wav] [--khung 1080x1920]
      → du-an/goc.json: độ lệch giờ mỗi máy (+ trôi giờ khi quay dài), khung cắt theo mặt cho từng máy, nguồn tiếng.
        Máy đầu tiên là máy CHÍNH (mốc thời gian, tiếng mặc định). Chỉ có 1 máy + --mic = thay tiếng bằng mic rời.
  python ghep-goc.py de-xuat <du-an> [--min 2.5] [--max 7] [--model small] [--chinh-nhieu 0.5]
      → nghe lời (faster-whisper, trên máy), điền goc.json "chuyen": đổi góc ở chỗ ngắt câu, không đoạn nào quá ngắn/dài.
        [agent] đọc bảng in ra, sửa "chuyen" nếu cần (câu nhấn mạnh → máy cận, câu mở/kết → máy chính).
  python ghep-goc.py dung <du-an> [-o mc.mp4]
      → du-an/mc.mp4 (1080×1920, 30 fps, tiếng đã khớp) + du-an/goc-xem.jpg (một khung mỗi đoạn).
        Rồi: dung-video-quay.py chuan-bi du-an/mc.mp4 du-an  (cắt vấp, phụ đề, hiệu ứng như video một máy).

Khớp giờ: đường bao âm lượng 10 ms tương quan chéo bằng FFT, rồi tinh chỉnh 1 ms trên sóng âm. KHÔNG dùng giờ ghi
trong file (hai điện thoại lệch nhau cả chục giây). Cách làm tham khảo ffmpeg-skill (kajisho5, MIT), viết lại.
Cần numpy + opencv (môi trường ~/.motion-studio/asr-venv; script tự chuyển sang Python đó), faster-whisper cho de-xuat.
"""
import argparse, json, math, os, re, subprocess, sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

HOME = Path.home()
VENV_PY = HOME / ".motion-studio/asr-venv/Scripts/python.exe"
if not VENV_PY.exists():
    VENV_PY = HOME / ".motion-studio/asr-venv/bin/python"
FPS = 30
SR = 8000          # tần số mẫu khi khớp tiếng
ENV_HOP = 80       # 10 ms


def need_libs(whisper=False):
    try:
        import numpy, cv2  # noqa: F401
        if whisper:
            import faster_whisper  # noqa: F401
        return
    except ImportError:
        pass
    if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
        sys.exit(subprocess.call([str(VENV_PY), "-X", "utf8", __file__, *sys.argv[1:]]))
    sys.exit("Thiếu numpy/opencv/faster-whisper. Cài môi trường giọng của motion-studio (scripts/setup-asr.ps1), rồi "
             "~/.motion-studio/asr-venv/Scripts/python -m pip install opencv-python-headless")


def die(msg):
    sys.exit("LỖI: " + msg)


def probe(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration:stream=codec_type,width,height,avg_frame_rate,duration:stream_side_data=rotation",
                          "-of", "json", str(p)], capture_output=True, text=True, encoding="utf-8")
    if out.returncode:
        die(f"không đọc được {p}")
    j = json.loads(out.stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    a = any(s["codec_type"] == "audio" for s in j["streams"])
    info = {"dur": float(j["format"]["duration"]), "tieng": a}
    if v:
        w, h = v["width"], v["height"]
        rot = next((int(float(sd["rotation"])) for sd in v.get("side_data_list", []) or [] if "rotation" in sd), 0)
        if rot % 180:
            w, h = h, w
        n, d = (v.get("avg_frame_rate") or "30/1").split("/")
        # điện thoại hay ghi tiếng dài hơn hình vài trăm ms: thời lượng HÌNH mới là thứ đem đi cắt
        vd = float(v["duration"]) if v.get("duration") not in (None, "N/A") else info["dur"]
        info.update(w=w, h=h, fps=float(n) / float(d) if float(d) else 30.0, vdur=vd)
    return info


def pcm(p, sr=SR, start=None, dur=None):
    import numpy as np
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{start:.3f}"] if start else []) + (["-t", f"{dur:.3f}"] if dur else [])
    cmd += ["-i", str(p), "-map", "0:a:0", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        die(f"không lấy được tiếng của {p}: {r.stderr.decode(errors='replace')[-200:]}")
    return np.frombuffer(r.stdout, dtype=np.float32)


# ---------- khớp giờ ----------
def envelope(x):
    import numpy as np
    n = len(x) // ENV_HOP
    e = np.sqrt((x[:n * ENV_HOP].reshape(n, ENV_HOP) ** 2).mean(1) + 1e-10)
    e = np.log(e + 1e-4)
    e = np.diff(e, prepend=e[:1])          # nhịp lên xuống của tiếng, bớt ảnh hưởng mic to/nhỏ khác nhau
    return (e - e.mean()) / (e.std() + 1e-9)


def xcorr(a, b, max_lag=None):
    """Lag L (mẫu) sao cho a[n] ≈ b[n - L]; L > 0: b bắt đầu SAU a. Trả (L, độ khớp, tỉ lệ đỉnh1/đỉnh2)."""
    import numpy as np
    n = 1 << int(math.ceil(math.log2(len(a) + len(b))))
    c = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    lags = np.concatenate([np.arange(0, len(a)), np.arange(-(len(b) - 1), 0)])
    c = np.concatenate([c[:len(a)], c[n - (len(b) - 1):]])
    if max_lag is not None:
        keep = np.abs(lags) <= max_lag
        c, lags = c[keep], lags[keep]
    k = int(c.argmax())
    norm = math.sqrt(float((a ** 2).sum()) * float((b ** 2).sum())) or 1.0
    # đỉnh thứ hai cách đỉnh chính > 0,3 s
    far = np.abs(lags - lags[k]) > 30
    second = float(c[far].max()) if far.any() else 0.0
    return int(lags[k]), float(c[k]) / norm, (float(c[k]) / second if second > 0 else 99.0)


def refine(ref, oth, lag_s):
    """Tinh chỉnh tới 1/8000 s quanh lag_s trên sóng âm (đoạn chồng nhau dài nhất, tối đa 40 s)."""
    import numpy as np
    L = int(round(lag_s * SR))
    a0 = max(0, L)                       # vị trí trong ref nơi oth bắt đầu
    span = min(len(ref) - a0, len(oth) - max(0, -L), 40 * SR)
    if span < SR:
        return lag_s
    mid = a0 + max(0, (len(ref) - a0 - span) // 2)
    seg_r = ref[mid:mid + span]
    o0 = mid - L
    w = 400  # ±50 ms
    best, bl = -1e18, 0
    seg_o_full = oth[max(0, o0 - w):o0 + span + w]
    off = o0 - max(0, o0 - w)
    for d in range(-w, w + 1, 4):
        s = off + d
        if s < 0 or s + span > len(seg_o_full):
            continue
        v = float(np.dot(seg_r, seg_o_full[s:s + span]))
        if v > best:
            best, bl = v, d
    for d in range(bl - 4, bl + 5):
        s = off + d
        if s < 0 or s + span > len(seg_o_full):
            continue
        v = float(np.dot(seg_r, seg_o_full[s:s + span]))
        if v > best:
            best, bl = v, d
    return (L - bl) / SR


def measure(ref_pcm, oth_pcm):
    """(lệch giây, độ khớp, tỉ lệ đỉnh): lệch > 0 = nguồn này bắt đầu SAU máy chính."""
    L, conf, ratio = xcorr(envelope(ref_pcm), envelope(oth_pcm))
    lag = refine(ref_pcm, oth_pcm, L * ENV_HOP / SR)
    return lag, conf, ratio


def drift(ref_p, oth_p, lag, ref_dur, oth_dur):
    """Trôi giờ (đồng hồ hai máy chạy lệch nhau, thấy rõ khi quay dài): đo lại độ lệch ở đầu và cuối đoạn chồng nhau.
    Trả (k, lệch, ghi chú) với t_máy-chính = lệch + t_nguồn·k."""
    a, b = max(0.0, lag), min(ref_dur, lag + oth_dur)
    if b - a < 150:
        return 1.0, lag, None
    res = []
    for t0 in (a + 5, b - 35):
        s0 = max(0.0, t0 - lag - 1)
        r = pcm(ref_p, start=t0, dur=30)
        o = pcm(oth_p, start=s0, dur=32)
        L, conf, _ = xcorr(envelope(r), envelope(o), max_lag=150)
        local = refine(r, o, L * ENV_HOP / SR)
        res.append((t0, (t0 - s0) + local, conf))   # l = t_máy-chính − t_nguồn tại t0
    (t1, l1, c1), (t2, l2, c2) = res
    if min(c1, c2) < 0.2:
        return 1.0, lag, f"không đo chắc được trôi giờ (độ khớp {c1:.2f}/{c2:.2f}) — giữ nguyên"
    d = (l2 - l1) / (t2 - t1)
    if abs(d * (b - a)) < 1 / FPS:
        return 1.0, lag, f"trôi giờ {d * 3600:+.2f} s/giờ — không đáng kể"
    k = 1.0 / (1.0 - d)
    return k, (l1 - d * t1) * k, f"trôi giờ {d * 3600:+.2f} s/giờ → đã bù"


def face_box(p, info, samples=14):
    import cv2
    cap = cv2.VideoCapture(str(p))
    cas = [cv2.CascadeClassifier(cv2.data.haarcascades + n) for n in
           ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml")]
    boxes, sw = [], info["w"]
    k = 540 / sw
    for i in range(samples):
        cap.set(cv2.CAP_PROP_POS_MSEC, (info["dur"] * (i + 0.5) / samples) * 1000)
        ok, fr = cap.read()
        if not ok:
            continue
        if fr.shape[1] != sw:  # OpenCV không xoay theo metadata → xoay tay
            fr = cv2.rotate(fr, cv2.ROTATE_90_CLOCKWISE)
            if fr.shape[1] != sw:
                continue
        g = cv2.cvtColor(cv2.resize(fr, (540, int(fr.shape[0] * k))), cv2.COLOR_BGR2GRAY)
        found = []
        for c in cas:
            for img, flip in ((g, False), (cv2.flip(g, 1), True)):
                f = c.detectMultiScale(img, 1.1, 6, minSize=(int(540 * 0.1),) * 2)
                for x, y, w, h in f:
                    found.append((540 - x - w if flip else x, y, w, h))
            if found:
                break
        if found:
            x, y, w, h = max(found, key=lambda r: r[2] * r[3])
            boxes.append([x / k, y / k, w / k, h / k])
    cap.release()
    if not boxes:
        return None
    return [sorted(c)[len(c) // 2] for c in zip(*boxes)]


def frame_for(info, face, W, H):
    """Khung cắt lớn nhất đúng tỉ lệ W:H, đưa mặt vào giữa ngang, đỉnh khung mặt ~24% từ trên."""
    sw, sh = info["w"], info["h"]
    if sw / sh > W / H:
        ch, cw = sh, sh * W / H
    else:
        cw, ch = sw, sw * H / W
    if face:
        cx = face[0] + face[2] / 2
        x = min(max(cx - cw / 2, 0), sw - cw)
        y = min(max(face[1] - ch * 0.24, 0), sh - ch)   # khung mặt Haar không gồm tóc → chừa thêm khoảng trên đầu
    else:
        x, y = (sw - cw) / 2, (sh - ch) / 2
    e = lambda v: int(v) // 2 * 2
    return {"x": e(x), "y": e(y), "w": e(cw), "h": e(ch)}


def cmd_khop(a):
    need_libs()
    files = [Path(f).resolve() for f in a.files[:-1]]
    du = Path(a.files[-1]).resolve()
    if not files:
        die("cần ít nhất 1 video và thư mục dự án (đối số cuối).")
    for f in files:
        if not f.exists():
            die(f"không thấy {f}")
    if len(files) == 1 and not a.mic:
        die("chỉ có 1 máy: thêm --mic <file tiếng> để thay tiếng, hoặc thêm máy thứ 2.")
    du.mkdir(parents=True, exist_ok=True)
    W, H = (int(v) for v in a.khung.lower().split("x"))
    infos = [probe(f) for f in files]
    for f, i in zip(files, infos):
        if not i["tieng"]:
            die(f"{f.name} không có tiếng — không khớp giờ được.")
    print(f"Máy chính: {files[0].name} ({infos[0]['w']}×{infos[0]['h']}, {infos[0]['dur']:.1f}s)")
    ref = pcm(files[0])
    may = []
    for idx, (f, info) in enumerate(zip(files, infos)):
        if idx == 0:
            lag, conf, ratio, k, note = 0.0, 1.0, 99.0, 1.0, None
        else:
            lag, conf, ratio = measure(ref, pcm(f))
            k, lag, note = drift(files[0], f, lag, infos[0]["dur"], info["dur"])
        face = face_box(f, info)
        fr = frame_for(info, face, W, H)
        if info["w"] < W * 0.7:
            print(f"  ⚠ {f.name} chỉ {info['w']}×{info['h']}: phóng lên {W}×{H} sẽ mềm — lần sau quay 1080p/4K.")
        may.append({"file": str(f), "lech": round(lag, 4), "troi": round(k, 7), "do_khop": round(conf, 3),
                    "w": info["w"], "h": info["h"], "dur": round(info["vdur"] - 0.5 / FPS, 3), "khung": fr,
                    "mat": bool(face)})
        if idx:
            tin = "chắc" if (ratio > 2.5 or (conf > 0.35 and ratio > 1.4)) else "KÉM — kiểm lại bằng tai/mắt"
            print(f"Máy {idx}: {f.name} lệch {lag:+.3f}s ({'bắt đầu sau' if lag > 0 else 'bắt đầu trước'} máy chính), "
                  f"độ khớp {conf:.2f}, đỉnh rõ ×{ratio:.1f} → {tin}" + (f"; {note}" if note else ""))
        print(f"  khung cắt {fr['w']}×{fr['h']} tại ({fr['x']},{fr['y']})" + ("" if face else " — KHÔNG thấy mặt, cắt giữa"))
    tieng = {"nguon": 0}
    if a.mic:
        m = Path(a.mic).resolve()
        mi = probe(m)
        lag, conf, ratio = measure(ref, pcm(m))
        k, lag, note = drift(files[0], m, lag, infos[0]["dur"], mi["dur"])
        tieng = {"nguon": "mic", "file": str(m), "lech": round(lag, 4), "troi": round(k, 7), "do_khop": round(conf, 3)}
        print(f"Mic rời {m.name}: lệch {lag:+.3f}s, độ khớp {conf:.2f}, đỉnh rõ ×{ratio:.1f}"
              + (" → chắc" if (ratio > 2.5 or (conf > 0.35 and ratio > 1.4)) else " → KÉM, kiểm lại") + (f"; {note}" if note else ""))
    # khoảng mọi nguồn tiếng + máy chính đều có
    end = may[0]["dur"]
    if tieng["nguon"] == "mic":
        end = min(end, tieng["lech"] + probe(Path(tieng["file"]))["dur"] * tieng["troi"])
    start = max(0.0, tieng.get("lech", 0.0)) if tieng["nguon"] == "mic" else 0.0
    g = {"khung": [W, H], "may": may, "tieng": tieng, "tu": round(start, 3), "den": round(end, 3),
         "chuyen": [{"tu": round(start, 3), "den": round(end, 3), "may": 0}]}
    out = du / "goc.json"
    if out.exists() and not a.ghi_de:
        old = json.loads(out.read_text(encoding="utf-8"))
        if len(old.get("chuyen", [])) > 1:
            g["chuyen"] = old["chuyen"]
            print("Giữ danh sách chuyển góc đã có trong goc.json (--ghi-de để bỏ).")
    out.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {out}\nTiếp: python {Path(__file__).name} de-xuat \"{du}\"" if len(files) > 1 else
          f"\n→ {out}\nTiếp: python {Path(__file__).name} dung \"{du}\"")


# ---------- đề xuất ----------
def covers(m, a, b):
    s0 = (a - m["lech"]) / m["troi"]
    s1 = (b - m["lech"]) / m["troi"]
    return s0 >= -0.02 and s1 <= m["dur"] + 0.02


def transcribe(src, start, dur, model):
    from faster_whisper import WhisperModel
    audio = pcm(src, sr=16000, start=start or None, dur=dur)
    wm = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = wm.transcribe(audio, language="vi", word_timestamps=True, condition_on_previous_text=False)
    return [{"w": w.word.strip(), "s": round(w.start + start, 3), "e": round(w.end + start, 3)}
            for s in segs for w in (s.words or []) if w.word.strip()]


def cmd_de_xuat(a):
    need_libs(whisper=True)
    du = Path(a.du_an).resolve()
    g = json.loads((du / "goc.json").read_text(encoding="utf-8"))
    may = g["may"]
    if len(may) < 2:
        die("chỉ 1 máy — không có góc nào để chuyển. Chạy thẳng: dung.")
    t = g["tieng"]
    # lời lấy theo thời gian máy chính
    if t["nguon"] == "mic":
        src, off, k = Path(t["file"]), t["lech"], t["troi"]
    else:
        src, off, k = Path(may[0]["file"]), 0.0, 1.0
    cache = du / "work" / "loi-goc.json"
    cache.parent.mkdir(exist_ok=True)
    key = {"src": str(src), "model": a.model}
    if cache.exists() and json.loads(cache.read_text(encoding="utf-8")).get("key") == key:
        words = json.loads(cache.read_text(encoding="utf-8"))["words"]
    else:
        print(f"Nghe lời ({a.model}, trên máy)…")
        raw = transcribe(src, 0.0, None, a.model)
        words = [{"w": w["w"], "s": round(off + w["s"] * k, 3), "e": round(off + w["e"] * k, 3)} for w in raw]
        cache.write_text(json.dumps({"key": key, "words": words}, ensure_ascii=False), encoding="utf-8")
    T0, T1 = g["tu"], g["den"]
    words = [w for w in words if T0 <= w["s"] < T1]
    if not words:
        die("không nghe thấy lời nói.")
    # Chỗ có thể cắt: ranh giới giữa hai chữ (không bao giờ giữa một chữ). Máy nghe hay ghi các chữ sát nhau (không
    # thấy khoảng ngắt), nên độ "ngắt" đo trên chính tiếng: tìm chỗ tiếng nhỏ nhất quanh ranh giới, ngắt càng sâu và
    # càng dài càng tốt, cộng điểm khi hết câu/dấu phẩy. Tiếng Việt: hai âm tiết dính liền thường là một từ ghép.
    import numpy as np
    x = pcm(src)
    hop = ENV_HOP
    n = len(x) // hop
    db = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-6)
    tref = off + (np.arange(n) * hop / SR) * k
    speech = float(np.median([db[int(((w["s"] + w["e"]) / 2 - off) / k * SR / hop)] for w in words
                              if 0 <= int(((w["s"] + w["e"]) / 2 - off) / k * SR / hop) < n]))
    cand = []
    for w1, w2 in zip(words, words[1:]):
        b = (w1["e"] + w2["s"]) / 2
        lo = max(b - 0.15, (w1["s"] + w1["e"]) / 2)
        hi = min(b + 0.15, (w2["s"] + w2["e"]) / 2)
        m = (tref >= lo) & (tref <= hi)
        if not m.any():
            continue
        ii = np.where(m)[0]
        j = ii[int(db[ii].argmin())]
        depth = max(0.0, speech - float(db[j]))
        quiet = float((db[ii] < speech - 12).sum()) * hop / SR      # giây "lặng" quanh ranh giới
        # phụ âm tắc (t, ch, c, p) cũng tạo khoảng lặng ngắn ~20–40 ms: chỉ tính độ sâu khi lặng đủ ≥ 60 ms
        sc = (min(depth, 30) / 15 if quiet >= 0.06 else 0) + quiet * 6 + (0.8 if re.search(r"[.?!…]$", w1["w"]) else
                                                 0.4 if w1["w"].endswith(",") else 0)
        cand.append((round(float(tref[j]), 3), sc))
    others = list(range(1, len(may)))
    segs, t_, cam, oi, turn = [], T0, 0, 0, 0
    while T1 - t_ > a.min:
        win = [(c, s) for c, s in cand if t_ + a.min <= c <= t_ + a.max and T1 - c >= a.min * 0.6]
        if win:
            # ưu tiên ngắt câu; đoạn máy chính được dài hơn
            target = t_ + (a.max if cam == 0 else (a.min + a.max) / 2) * 0.7
            cut = max(win, key=lambda cs: cs[1] - abs(cs[0] - target) * 0.05)[0]
        elif T1 - t_ <= a.max * 1.5:
            break
        else:
            cut = round(t_ + a.max, 3)
        segs.append([t_, cut, cam])
        t_ = cut
        turn += 1
        # luân phiên: chính → phụ → chính → phụ khác …, tỉ lệ máy chính theo --chinh-nhieu
        if cam != 0 or (turn % 2 == 0 and a.chinh_nhieu > 0.66):
            nxt = 0
        else:
            nxt = others[oi % len(others)]
            oi += 1
        cam = nxt
    segs.append([t_, T1, cam])
    # máy phụ tắt sớm / bật muộn: giữ phần nó có (cắt ở chỗ ngắt tốt nhất), phần còn lại về máy chính
    fixed = []
    for s, e, c in segs:
        if c and not covers(may[c], s, e):
            m = may[c]
            ce = m["lech"] + m["dur"] * m["troi"]
            inner = [(t, sc) for t, sc in cand if s + a.min * 0.6 <= t <= ce - 0.05]
            if covers(m, s, s + 0.1) and inner:
                cut = max(inner, key=lambda ts: ts[1])[0]
                fixed += [[s, cut, c], [cut, e, 0]]
                continue
            c = 0
        fixed.append([s, e, c])
    out = []
    for s, e, c in fixed:
        if out and out[-1]["may"] == c:
            out[-1]["den"] = round(e, 3)
        else:
            out.append({"tu": round(s, 3), "den": round(e, 3), "may": c})
    for seg in out:
        seg["loi"] = " ".join(w["w"] for w in words if seg["tu"] <= w["s"] < seg["den"])[:120]
    g["chuyen"] = out
    (du / "goc.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} đoạn:")
    for s in out:
        print(f"  {s['tu']:7.2f}–{s['den']:7.2f}  máy {s['may']}  {s['loi']}")
    share = sum(s["den"] - s["tu"] for s in out if s["may"] == 0) / max(1e-6, T1 - T0)
    print(f"Máy chính chiếm {share:.0%}. Sửa 'chuyen' trong {du / 'goc.json'} nếu muốn, rồi: "
          f"python {Path(__file__).name} dung \"{du}\"")


# ---------- dựng ----------
def cmd_dung(a):
    du = Path(a.du_an).resolve()
    g = json.loads((du / "goc.json").read_text(encoding="utf-8"))
    W, H = g["khung"]
    may, ch, t = g["may"], g["chuyen"], g["tieng"]
    ch = sorted(ch, key=lambda s: s["tu"])
    for x, y in zip(ch, ch[1:]):
        if abs(x["den"] - y["tu"]) > 0.002:
            die(f"'chuyen' bị hở/chồng ở {x['den']}–{y['tu']}: đoạn sau phải bắt đầu đúng chỗ đoạn trước hết.")
    for s in ch:
        if not 0 <= s["may"] < len(may):
            die(f"đoạn {s['tu']}–{s['den']}: không có máy {s['may']}.")
        if not covers(may[s["may"]], s["tu"], s["den"]):
            die(f"đoạn {s['tu']}–{s['den']}: máy {s['may']} không quay tới khoảng này (lệch {may[s['may']]['lech']}s).")
    T0, T1 = ch[0]["tu"], ch[-1]["den"]
    used = sorted({s["may"] for s in ch})
    inputs, fc = [], []
    idx = {}
    for m in used:
        idx[m] = len(inputs) // 2
        inputs += ["-i", may[m]["file"]]
    cnt = {m: sum(1 for s in ch if s["may"] == m) for m in used}
    for m in used:
        k = may[m]["khung"]
        fc.append(f"[{idx[m]}:v]fps={FPS},crop={k['w']}:{k['h']}:{k['x']}:{k['y']},scale={W}:{H}:flags=lanczos,setsar=1,"
                  f"split={cnt[m]}" + "".join(f"[m{m}_{j}]" for j in range(cnt[m])))
    used_j = {m: 0 for m in used}
    labels = []
    for i, s in enumerate(ch):
        m = s["may"]
        mm = may[m]
        s0 = (s["tu"] - mm["lech"]) / mm["troi"]
        s1 = (s["den"] - mm["lech"]) / mm["troi"]
        j = used_j[m]
        used_j[m] += 1
        stretch = f"setpts=(PTS-STARTPTS)*{mm['troi']:.7f}" if abs(mm["troi"] - 1) > 1e-6 else "setpts=PTS-STARTPTS"
        fc.append(f"[m{m}_{j}]trim=start={max(0, s0):.4f}:end={s1:.4f},{stretch}[v{i}]")
        labels.append(f"[v{i}]")
    fc.append("".join(labels) + f"concat=n={len(ch)}:v=1:a=0,fps={FPS},format=yuv420p[v]")
    # tiếng
    if t["nguon"] == "mic":
        ai = len(inputs) // 2
        inputs += ["-i", t["file"]]
        k = t["troi"]
        chain = [f"[{ai}:a]aresample=48000"]
        if abs(k - 1) > 1e-6:
            chain.append(f"atempo={1 / k:.7f}")
        lag = t["lech"]
        if lag > T0:
            chain.append(f"adelay={int(round((lag - T0) * 1000))}:all=1")
            chain.append(f"atrim=0:{T1 - T0:.4f}")
        else:
            chain.append(f"atrim=start={(T0 - lag):.4f}:end={(T1 - lag):.4f}")
        fc.append(",".join(chain) + ",asetpts=PTS-STARTPTS[a]")
    else:
        fc.append(f"[{idx.get(0, 0)}:a]aresample=48000,atrim=start={T0:.4f}:end={T1:.4f},asetpts=PTS-STARTPTS[a]"
                  if 0 in idx else "")
        if 0 not in idx:
            ai = len(inputs) // 2
            inputs += ["-i", may[0]["file"]]
            fc[-1] = f"[{ai}:a]aresample=48000,atrim=start={T0:.4f}:end={T1:.4f},asetpts=PTS-STARTPTS[a]"
    out = Path(a.o).resolve() if a.o else du / "mc.mp4"
    print(f"Dựng {out.name}: {len(ch)} đoạn, {T1 - T0:.1f}s, {W}×{H}…")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(fc),
                        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "17", "-preset", "medium",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                        "-movflags", "+faststart", str(out)], stderr=subprocess.PIPE, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode:
        die(f"ffmpeg dừng:\n{r.stderr[-1500:]}")
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0", str(out)],
                       capture_output=True, text=True).stdout.split()
    d = {x.split(",")[0]: float(x.split(",")[1]) for x in p if "," in x and x.split(",")[1] not in ("", "N/A")}
    if abs(d.get("video", 0) - (T1 - T0)) > 0.15 or abs(d.get("audio", 0) - d.get("video", 0)) > 0.1:
        die(f"thời lượng không khớp: {d}, mong {T1 - T0:.2f}s")
    print(f"  ✔ hình {d['video']:.2f}s, tiếng {d['audio']:.2f}s")
    # ảnh xem: một khung giữa mỗi đoạn
    times = [((s["tu"] + s["den"]) / 2 - T0) for s in ch][:12]
    sel = "+".join(f"eq(n\\,{int(tt * FPS)})" for tt in times)
    cols = min(len(times), 6)
    rows = math.ceil(len(times) / cols)
    jpg = du / "goc-xem.jpg"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(out), "-vf",
                    f"select='{sel}',scale=-2:360,tile={cols}x{rows}", "-frames:v", "1", "-fps_mode", "passthrough",
                    str(jpg)])
    print(f"  🖼 một khung mỗi đoạn: {jpg}")
    print(f"Tiếp: python dung-video-quay.py chuan-bi \"{out}\" \"{du}\"   (cắt vấp, phụ đề, hiệu ứng)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("khop", help="khớp giờ các máy (+ mic rời) theo tiếng")
    p.add_argument("files", nargs="+", help="máy-chính máy-2 … du-an")
    p.add_argument("--mic", help="file tiếng mic rời (wav/mp3/m4a) thay cho tiếng máy")
    p.add_argument("--khung", default="1080x1920", help="khung ra, mặc định 1080x1920 (ngang: 1920x1080)")
    p.add_argument("--ghi-de", action="store_true", help="bỏ danh sách chuyển góc cũ trong goc.json")
    p = sub.add_parser("de-xuat", help="đề xuất chỗ chuyển góc theo câu nói")
    p.add_argument("du_an")
    p.add_argument("--min", type=float, default=2.5, help="đoạn ngắn nhất (giây), mặc định 2,5")
    p.add_argument("--max", type=float, default=7.0, help="đoạn dài nhất (giây), mặc định 7")
    p.add_argument("--model", default="medium",
                   help="faster-whisper: medium (mặc định — bộ cài tải sẵn, máy không mạng vẫn chạy) / small (nhanh hơn)")
    p.add_argument("--chinh-nhieu", type=float, default=0.5,
                   help="tỉ lệ máy chính mong muốn: 0.5 luân phiên đều, 0.7 máy chính nhiều hơn")
    p = sub.add_parser("dung", help="dựng video theo goc.json")
    p.add_argument("du_an")
    p.add_argument("-o", help="file ra (mặc định du-an/mc.mp4)")
    a = ap.parse_args()
    {"khop": cmd_khop, "de-xuat": cmd_de_xuat, "dung": cmd_dung}[a.cmd](a)


if __name__ == "__main__":
    main()
