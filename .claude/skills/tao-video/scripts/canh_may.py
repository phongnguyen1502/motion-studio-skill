"""[tao-video · đợt 3] Camera moves, colour looks and transitions applied to the FOOTAGE (cut.mp4 → work/may.mp4).

dung-video-quay.py calls apply() before rendering; nothing to run by hand. Plan key "canh" in fx-plan.json, times on
the cut.mp4 timeline like the fx items (seconds, "+1.2" after start, or a spoken word/phrase from timing.json;
no start = 0, no end = end of the video):

  "canh": [
    { "type": "nhay-cat", "params": { "zoom": 1.1 } },                       # hide jump cuts: every other take zoomed
    { "type": "di-mat", "start": "muôn người", "end": "+1.4", "params": { "zoom": 1.35 } },
    { "type": "mau-phim", "params": { "kieu": "lanh-cam", "do": 0.8 } } ]

Camera (combine; zoom is about the face, never shows an edge):
  day-may      slow push-in                         zoom 1.12
  di-mat       punch-in on the face (snap)           zoom 1.3, nay (bounce) false
  di-trai-phai punch-ins that alternate left/right   zoom 1.25, nhip 0.7 s (or moc: [times]), lech 0.07 (share of width)
  ken-burns    slow zoom + pan                        tu 1.0, den 1.15, x -0.03→0.03
  rung-may     handheld shake                         bien_do 9 px, toc_do 1
  zoom-giat    whip zoom with blur around `start`     zoom 1.6, time 0.3
  nhay-cat     every other kept take zoomed           zoom 1.1 (uses cut.json; jump cuts become punch-ins)
Colour (in order; fades 0.25 s at edges inside the video):
  mau-phim     look: kieu am | lanh-cam | den-trang | u-buon | phim-cu | tuoi | log, do 0–1 (strength)
  vuot-mau     wipe from `truoc` (log | goc) to `sau` (a look) over `time` s, then holds the look until end
  hat-phim     grain + vignette                       hat 0.06, vien 0.35
  vhs          tape look: colour bleed, scanlines, a tracking band
Transitions:
  chop-trang   white flash centred on start           time 0.3
  mo-den       fade from black (kieu "vao", from start) or to black (kieu "ra", ending at end)   time 0.6
"""
import hashlib, json, re, subprocess, unicodedata
from pathlib import Path

import cv2
import numpy as np

W, H, FPS = 1080, 1920, 30
CAMERA = {"day-may", "di-mat", "di-trai-phai", "ken-burns", "rung-may", "zoom-giat", "nhay-cat"}
COLOUR = {"mau-phim", "vuot-mau", "hat-phim", "vhs", "chop-trang", "mo-den"}


# ---------- time ----------
def fold(s):
    s = unicodedata.normalize("NFD", str(s).lower().replace("đ", "d"))
    return re.sub(r"[^\w%]+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")).strip()


def resolve(v, words, base, lo=0.0):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if re.match(r"^[+-]\d", s):
        return base + float(s)
    if re.match(r"^\d+(\.\d+)?$", s):
        return float(s)
    q = fold(s).split()
    for i in range(len(words)):
        if words[i][1] >= lo - 0.05 and [w for w, _ in words[i:i + len(q)]] == q:
            return words[i][1]
    raise SystemExit(f'canh: không thấy từ "{v}" trong lời nói (timing.json)')


def clamp(x, a=0.0, b=1.0):
    return min(b, max(a, x))


def io(p):   # in-out cubic
    p = clamp(p)
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


# ---------- looks ----------
def _curve(pts):
    x, y = zip(*pts)
    return np.interp(np.arange(256), x, y).clip(0, 255).astype(np.uint8)


S_CURVE = [(0, 0), (64, 50), (128, 128), (192, 206), (255, 255)]
LOOKS = {   # per-channel curves (r, g, b) + saturation
    "am": dict(r=[(0, 4), (128, 140), (255, 255)], g=[(0, 0), (128, 130), (255, 248)], b=[(0, 6), (128, 112), (255, 228)], sat=1.06),
    "lanh-cam": dict(r=[(0, 0), (64, 50), (128, 132), (192, 212), (255, 255)], g=[(0, 8), (64, 64), (128, 128), (192, 194), (255, 246)],
                     b=[(0, 24), (64, 80), (128, 124), (192, 170), (255, 222)], sat=1.12),
    "den-trang": dict(r=S_CURVE, g=S_CURVE, b=S_CURVE, sat=0.0),
    "u-buon": dict(r=[(0, 0), (60, 38), (190, 188), (255, 232)], g=[(0, 4), (60, 44), (190, 190), (255, 234)], b=[(0, 12), (60, 54), (190, 192), (255, 236)], sat=0.68),
    "phim-cu": dict(r=[(0, 34), (128, 142), (255, 242)], g=[(0, 30), (128, 132), (255, 234)], b=[(0, 34), (128, 116), (255, 208)], sat=0.8),
    "tuoi": dict(r=[(0, 0), (64, 58), (192, 200), (255, 255)], g=[(0, 0), (64, 58), (192, 200), (255, 255)], b=[(0, 0), (64, 58), (192, 200), (255, 255)], sat=1.32),
    "log": dict(r=[(0, 44), (255, 210)], g=[(0, 44), (255, 210)], b=[(0, 46), (255, 212)], sat=0.55),
}
_LUT = {k: np.dstack([_curve(v["b"]), _curve(v["g"]), _curve(v["r"])]).reshape(1, 256, 3) for k, v in LOOKS.items()}


def look(img, kieu):
    if kieu not in LOOKS:
        raise SystemExit(f"canh: kiểu màu '{kieu}' không có (dùng {', '.join(LOOKS)})")
    sat = LOOKS[kieu]["sat"]
    if sat != 1.0:
        f = img.astype(np.float32)
        l = (f[..., 0] * 0.114 + f[..., 1] * 0.587 + f[..., 2] * 0.299)[..., None]
        img = np.clip(l + (f - l) * sat, 0, 255).astype(np.uint8)
    return cv2.LUT(img, _LUT[kieu])


def mix(a, b, k):
    if k <= 0.001:
        return a
    if k >= 0.999:
        return b
    return cv2.addWeighted(a, 1 - k, b, k, 0)


_GRAIN, _VIG = None, {}


def grain(img, n, amt, vig):
    global _GRAIN
    if _GRAIN is None:
        r = np.random.default_rng(5)
        _GRAIN = [cv2.GaussianBlur(r.normal(0, 1, (H // 2, W // 2)).astype(np.float32), (0, 0), 0.6) for _ in range(6)]
    g = cv2.resize(_GRAIN[n % 6], (W, H), interpolation=cv2.INTER_LINEAR)
    f = img.astype(np.float32) + (g * 255 * amt)[..., None]
    if vig > 0:
        if vig not in _VIG:
            y, x = np.mgrid[0:H, 0:W].astype(np.float32)
            d = np.sqrt(((x - W / 2) / (W * 0.62)) ** 2 + ((y - H / 2) / (H * 0.62)) ** 2)
            _VIG[vig] = (1 - vig * np.clip(d - 0.45, 0, 1) ** 1.6 * 2.2).clip(0, 1)[..., None]
        f *= _VIG[vig]
    return np.clip(f, 0, 255).astype(np.uint8)


def vhs(img, n):
    r = np.random.default_rng(1000 + n)
    small = cv2.resize(img, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    out = cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)
    b, g, rr = cv2.split(out)
    out = cv2.merge([np.roll(b, -5, axis=1), g, np.roll(rr, 6, axis=1)])            # colour bleed
    out = look(out, "am")
    out[::3] = (out[::3].astype(np.float32) * 0.86).astype(np.uint8)                  # scanlines
    y0 = int((n * 9) % (H + 240)) - 120                                              # tracking band drifting down
    for y in range(max(0, y0), min(H, y0 + 90), 2):
        out[y:y + 2] = np.roll(out[y:y + 2], int(r.integers(-18, 18)), axis=1)
    noise = r.integers(0, 15, (H, W, 1), dtype=np.uint16)          # grey noise, same on all channels
    return np.minimum(out.astype(np.uint16) + noise, 255).astype(np.uint8)


# ---------- plan ----------
def face_center(cut):
    a = (cut.get("avoid") or [None])[0]
    if not a:
        return W / 2, H * 0.36
    w, h = a["w"] / 1.5, a["h"] / 1.75
    return a["x"] + w * 0.25 + w / 2, a["y"] + h * 0.45 + h / 2


def load(du):
    plan = json.loads((du / "fx-plan.json").read_text(encoding="utf-8"))
    items = plan.get("canh") or []
    if not items:
        return None
    cut = json.loads((du / "cut.json").read_text(encoding="utf-8"))
    timing = json.loads((du / "timing.json").read_text(encoding="utf-8")) if (du / "timing.json").exists() else []
    words = [(fold(w), t) for l in timing for w, t in l.get("words", []) if fold(w)]
    dur = float(cut["duration"])
    out = []
    for it in items:
        if it["type"] not in CAMERA | COLOUR:
            raise SystemExit(f"canh: không có hiệu ứng '{it['type']}' (máy quay: {', '.join(sorted(CAMERA))}; "
                             f"màu/chuyển cảnh: {', '.join(sorted(COLOUR))})")
        a = resolve(it.get("start"), words, 0.0) or 0.0
        b = resolve(it.get("end"), words, a, a)
        p = dict(it.get("params") or {})
        if p.get("moc"):    # di-trai-phai beats: seconds, "+x" or spoken words, searched from start
            p["moc"] = [resolve(m, words, a, a) for m in p["moc"]]
        out.append({"type": it["type"], "a": a, "b": dur if b is None else min(b, dur), "p": p})
    # take boundaries on the output timeline (for nhay-cat)
    acc, bounds = 0.0, []
    for x, y in cut["ranges"]:
        acc += y - x
        bounds.append(acc)
    return {"items": out, "dur": dur, "anchor": face_center(cut), "bounds": bounds}


def camera(P, t):
    """(scale, tx, ty, rot°, blur) of the frame at t."""
    s, tx, ty, rot, blur = 1.0, 0.0, 0.0, 0.0, 0.0
    for it in P["items"]:
        a, b, p, k = it["a"], it["b"], it["p"], it["type"]
        if k == "zoom-giat":
            d = float(p.get("time", 0.3)); z = float(p.get("zoom", 1.6))
            if a - d / 2 <= t < a + d / 2:
                q = 1 - abs(t - a) / (d / 2)
                s *= 1 + (z - 1) * q ** 2; blur = max(blur, q)
            continue
        if not (a <= t < b):
            continue
        if k == "day-may":
            s *= 1 + (float(p.get("zoom", 1.12)) - 1) * io((t - a) / max(0.01, b - a))
        elif k == "di-mat":
            z, e = float(p.get("zoom", 1.3)), clamp((t - a) / 0.08)
            bounce = 0.04 * np.exp(-(t - a) * 9) * np.sin((t - a) * 30) if p.get("nay") else 0
            s *= 1 + (z - 1) * e + bounce
        elif k == "di-trai-phai":
            moc = p.get("moc") or None
            i = (sum(1 for m in moc if m <= t) - 1) if moc else int((t - a) // float(p.get("nhip", 0.7)))
            if i >= 0:
                s *= float(p.get("zoom", 1.25)); tx += (-1 if i % 2 == 0 else 1) * W * float(p.get("lech", 0.07))
        elif k == "ken-burns":
            q = io((t - a) / max(0.01, b - a)); x0, x1 = p.get("x", [-0.03, 0.03])
            s *= float(p.get("tu", 1.0)) + (float(p.get("den", 1.15)) - float(p.get("tu", 1.0))) * q
            tx += W * (x0 + (x1 - x0) * q)
        elif k == "rung-may":
            amp, v = float(p.get("bien_do", 9)), float(p.get("toc_do", 1))
            tx += amp * (np.sin(t * 7.1 * v) * 0.6 + np.sin(t * 13.7 * v + 1.3) * 0.4)
            ty += amp * (np.sin(t * 6.3 * v + 2.1) * 0.6 + np.sin(t * 11.9 * v + 0.4) * 0.4)
            rot += 0.25 * np.sin(t * 5.3 * v); s *= 1 + 2.6 * amp / W
        elif k == "nhay-cat":
            idx = sum(1 for x in P["bounds"] if x <= t + 1e-6)
            if idx % 2 == 1:
                s *= float(p.get("zoom", 1.1))
    return s, tx, ty, rot, blur


def matrix(P, t):
    s, tx, ty, rot, blur = camera(P, t)
    ax, ay = P["anchor"]
    # translation that keeps the frame covered (zoom ≥ 1 about an interior point never shows an edge)
    tx = clamp(tx, -(W - ax) * (s - 1), ax * (s - 1)); ty = clamp(ty, -(H - ay) * (s - 1), ay * (s - 1))
    M = cv2.getRotationMatrix2D((ax, ay), rot, s)
    M[:, 2] += (tx, ty)
    return M, s, blur


def colour(P, img, t, n):
    for it in P["items"]:
        a, b, p, k = it["a"], it["b"], it["p"], it["type"]
        if k not in COLOUR:
            continue
        edge = lambda d=0.25: (1.0 if a <= 0.001 else clamp((t - a) / d)) * (1.0 if b >= P["dur"] - 0.001 else clamp((b - t) / d))
        if k == "chop-trang":
            d = float(p.get("time", 0.3))
            if abs(t - a) < d / 2:
                img = mix(img, np.full_like(img, 255), (1 - abs(t - a) / (d / 2)) ** 1.5)
            continue
        if k == "mo-den":
            d = float(p.get("time", 0.6))
            q = clamp((t - a) / d) if p.get("kieu", "vao") == "vao" else clamp((b - t) / d)
            if a <= t <= b and q < 1:
                img = mix(img, np.zeros_like(img), 1 - q)
            continue
        if not (a <= t < b):
            continue
        if k == "mau-phim":
            img = mix(img, look(img, p.get("kieu", "am")), float(p.get("do", 0.85)) * edge())
        elif k == "vuot-mau":
            d = float(p.get("time", 1.0)); q = io((t - a) / d)
            before = img if p.get("truoc", "log") == "goc" else look(img, "log")
            after = look(img, p.get("sau", "lanh-cam"))
            x = int(W * q)
            out = before.copy(); out[:, :x] = after[:, :x]
            if 0 < x < W:
                out[:, max(0, x - 2):x + 2] = 255
            img = out
        elif k == "hat-phim":
            img = grain(img, n, float(p.get("hat", 0.06)) * edge(), float(p.get("vien", 0.35)))
        elif k == "vhs":
            img = mix(img, vhs(img, n), edge(0.15))
    return img


# ---------- run ----------
def apply(du):
    """Returns (base video, person matte or None, track json name or None) to use for the render."""
    du = Path(du)
    mask0, track0 = du / "work/nguoi.mkv", du / "mat.json"
    P = load(du)
    if not P:
        return du / "cut.mp4", (mask0 if mask0.exists() else None), ("mat.json" if track0.exists() else None)
    has_cam = any(i["type"] in CAMERA for i in P["items"])
    use_mask = has_cam and mask0.exists()
    out, mout, tout = du / "work/may.mp4", du / "work/nguoi-may.mkv", du / "mat-may.json"
    key = hashlib.sha1(json.dumps([P["items"], (du / "cut.mp4").stat().st_mtime, mask0.stat().st_mtime if use_mask else 0,
                                   track0.stat().st_mtime if track0.exists() else 0], sort_keys=True).encode()).hexdigest()
    kf = du / "work/may.key"
    if not (out.exists() and kf.exists() and kf.read_text() == key and (not use_mask or mout.exists())):
        print(f"Xử lý hình gốc: {', '.join(i['type'] for i in P['items'])}…", flush=True)
        cv2.setNumThreads(4)
        dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(du / "cut.mp4"), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                               stdout=subprocess.PIPE)
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                                "-i", "-", "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", str(out)],
                               stdin=subprocess.PIPE)
        mdec = menc = None
        if use_mask:
            mdec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(mask0), "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
            menc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", str(FPS),
                                     "-i", "-", "-c:v", "ffv1", "-pix_fmt", "gray", str(mout)], stdin=subprocess.PIPE)
        Ms, n = [], 0
        while True:
            buf = dec.stdout.read(W * H * 3)
            if len(buf) < W * H * 3:
                break
            t = n / FPS
            img = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            M, s, blur = matrix(P, t) if has_cam else (None, 1.0, 0.0)
            Ms.append(M)
            if M is not None and (abs(s - 1) > 1e-4 or abs(M[0, 2]) + abs(M[1, 2]) > 1e-3):
                warp = lambda im, m, fl=cv2.INTER_LINEAR: cv2.warpAffine(im, m, (W, H), flags=fl, borderMode=cv2.BORDER_REFLECT101)
                if blur > 0.05:     # zoom blur: average of slightly different zooms
                    ax, ay = P["anchor"]
                    acc = np.zeros((H, W, 3), np.float32)
                    for f in (-1, 0, 1):
                        k = 1 + 0.035 * blur * f
                        M2 = M.copy(); M2[:, :2] *= k; M2[:, 2] = (M[:, 2] - (ax, ay)) * k + (ax, ay)
                        acc += warp(img, M2)
                    img = (acc / 3).astype(np.uint8)
                else:
                    img = warp(img, M)
            img = colour(P, img, t, n)
            enc.stdin.write(np.ascontiguousarray(img).tobytes())
            if mdec:
                mb = mdec.stdout.read(W * H)
                if len(mb) == W * H:
                    m = np.frombuffer(mb, np.uint8).reshape(H, W)
                    if M is not None:
                        m = cv2.warpAffine(m, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT101)
                    menc.stdin.write(m.tobytes())
            n += 1
            if n % 300 == 0:
                print(f"  {n} khung", flush=True)
        dec.wait(); enc.stdin.close(); enc.wait()
        if mdec:
            mdec.wait(); menc.stdin.close(); menc.wait()
        if enc.returncode:
            raise SystemExit("canh: lỗi khi ghi work/may.mp4")
        if has_cam and track0.exists():     # move the face track with the camera so face effects stay on the face
            tj = json.loads(track0.read_text(encoding="utf-8"))
            rows = []
            for i, r in enumerate(tj["f"]):
                M = Ms[min(i, len(Ms) - 1)] if Ms else None
                if r is None or M is None:
                    rows.append(r); continue
                x, y, w, h, top = r
                p0, p1, pt = M @ np.array([x, y, 1.0]), M @ np.array([x + w, y + h, 1.0]), M @ np.array([x + w / 2, top, 1.0])
                rows.append([round(p0[0]), round(p0[1]), round(p1[0] - p0[0]), round(p1[1] - p0[1]), round(pt[1])])
            tout.write_text(json.dumps({**tj, "f": rows}), encoding="utf-8")
        kf.write_text(key)
        print(f"✔ work/may.mp4 ({n} khung)")
    mask = mout if use_mask else (mask0 if mask0.exists() else None)
    track = ("mat-may.json" if has_cam and track0.exists() else "mat.json") if track0.exists() else None
    return out, mask, track
