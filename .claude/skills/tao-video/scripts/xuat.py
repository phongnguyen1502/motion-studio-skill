#!/usr/bin/env python3
"""[tao-video · bước cuối] Kiểm video trước khi đăng, xuất bản riêng cho từng nền tảng, chạy hàng loạt.

  python xuat.py kiem-dang <video> [--nen tiktok] [--json]
      → bảng ĐẠT / CẢNH BÁO / LỖI: khung, fps, codec, màu, tiếng, độ to (LUFS), đỉnh âm, thời lượng, dung lượng,
        faststart. Mỗi dòng chưa đạt có lệnh sửa. Thoát mã 1 khi có LỖI.
  python xuat.py xuat <video> --nen tiktok,reels,vuong [--khop mo|cat|vien] [--cat-y 0.4] [--cat-cho-vua]
                              [--thu-muc-ra ra/] [--ten ten-goc] [--ghi-de]
      → <tên>.<nền>.mp4 cho từng nền: đúng khung, H.264 + AAC 48 kHz, -14 LUFS / đỉnh -1 dBTP (đo 2 lượt),
        nhãn BT.709, faststart; rồi tự chạy kiem-dang trên từng file ra.
  python xuat.py hang-loat <thu-muc> --cong-thuc cong-thuc.json [--chay-lai]
      → áp cùng một chuỗi bước cho mọi clip trong thư mục; clip đã làm (cùng nội dung + cùng công thức) thì bỏ qua.

Nền (--nen): tiktok · reels · shorts · facebook (Reels FB) · doc45 (bài đăng 4:5 FB/IG) · vuong (1:1) · youtube (16:9)
Giới hạn thời lượng/dung lượng là THAM KHẢO (nền tảng đổi luôn) → chỉ CẢNH BÁO, không chặn.
Clip HDR: chạy `sua-hinh.py hdr-sdr` trước. Cách kiểm tham khảo ffmpeg-skill (kajisho5, MIT), viết lại.
"""
import argparse, hashlib, importlib.util, json, re, shutil, subprocess, sys, tempfile
from fnmatch import fnmatch
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("sua_hinh", HERE / "sua-hinh.py")
sh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sh)  # dùng chung probe / run_ffmpeg / is_hdr với sua-hinh.py

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

# w, h, thời lượng tối đa (giây, tham khảo), dung lượng tối đa (MB, tham khảo), ghi chú vùng an toàn
NEN = {
    "tiktok":   {"w": 1080, "h": 1920, "max_s": 600, "max_mb": 500, "ten": "TikTok"},
    "reels":    {"w": 1080, "h": 1920, "max_s": 180, "max_mb": 650, "ten": "Instagram Reels"},
    "shorts":   {"w": 1080, "h": 1920, "max_s": 180, "max_mb": 2000, "ten": "YouTube Shorts"},
    "facebook": {"w": 1080, "h": 1920, "max_s": 90, "max_mb": 1000, "ten": "Facebook Reels"},
    "doc45":    {"w": 1080, "h": 1350, "max_s": 3600, "max_mb": 4000, "ten": "bài đăng 4:5 Facebook/Instagram"},
    "vuong":    {"w": 1080, "h": 1080, "max_s": 3600, "max_mb": 4000, "ten": "vuông 1:1 (LinkedIn, Facebook)"},
    "youtube":  {"w": 1920, "h": 1080, "max_s": 43200, "max_mb": 256000, "ten": "YouTube ngang"},
}
LUFS, TP = -14.0, -1.0
DAT, CB, LOI = "ĐẠT", "CẢNH BÁO", "LỖI"


def die(msg):
    sys.exit("LỖI: " + msg)


def q(p):
    return f'"{p}"' if " " in str(p) else str(p)


# ---------- đo ----------
def loudness(p):
    """(LUFS tích hợp, đỉnh thật dBTP) bằng ebur128."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(p), "-map", "0:a:0", "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = r.stderr[r.stderr.rfind("Summary:"):] if "Summary:" in r.stderr else ""
    i = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", tail)
    tp = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", tail)
    f = lambda m: float(m.group(1)) if m and m.group(1) != "-inf" else None
    return f(i), f(tp)


def faststart(p):
    """True khi khối 'moov' đứng trước 'mdat' (xem được ngay khi đang tải)."""
    try:
        with open(p, "rb") as fh:
            pos = 0
            while True:
                head = fh.read(8)
                if len(head) < 8:
                    return None
                size, typ = int.from_bytes(head[:4], "big"), head[4:8]
                if size == 1:
                    size = int.from_bytes(fh.read(8), "big")
                    hdr = 16
                else:
                    hdr = 8
                if typ == b"moov":
                    return True
                if typ == b"mdat":
                    return False
                if size == 0:
                    return None
                pos += size
                fh.seek(pos)
    except OSError:
        return None


# ---------- kiem-dang ----------
def check(p, nen):
    spec = NEN[nen]
    m = sh.probe(p)
    v, a = m["v"], m["a"]
    rows = []

    def row(muc, kq, gt, sua=""):
        rows.append({"muc": muc, "kq": kq, "gia_tri": gt, "sua": sua})

    fix_xuat = f"python xuat.py xuat {q(p)} --nen {nen}"
    W, H = spec["w"], spec["h"]
    if (m["w"], m["h"]) == (W, H):
        row("Khung hình", DAT, f"{m['w']}×{m['h']}")
    elif abs(m["w"] / m["h"] - W / H) < 0.01:
        row("Khung hình", CB if m["w"] < W else DAT, f"{m['w']}×{m['h']} (đúng tỉ lệ, chuẩn {W}×{H})",
            fix_xuat if m["w"] < W else "")
    else:
        row("Khung hình", LOI, f"{m['w']}×{m['h']} — {spec['ten']} cần {W}×{H}", fix_xuat)
    fps = m["fps"]
    row("Số khung/giây", DAT if 23.5 <= fps <= 60.5 else LOI, f"{fps:.2f}", "" if 23.5 <= fps <= 60.5 else fix_xuat)
    codec = v.get("codec_name")
    row("Mã hình", DAT if codec == "h264" else CB if codec == "hevc" else LOI, codec,
        "" if codec == "h264" else fix_xuat)
    pf = v.get("pix_fmt")
    row("Định dạng điểm ảnh", DAT if pf == "yuv420p" else LOI, pf, "" if pf == "yuv420p" else fix_xuat)
    trc = v.get("color_transfer")
    if sh.is_hdr(m):
        row("Màu", LOI, f"HDR ({trc}) — dễ nhạt/chói khi đăng", f"python sua-hinh.py hdr-sdr {q(p)}")
    elif trc in (None, "", "unknown") or v.get("color_primaries") in (None, "", "unknown"):
        row("Màu", CB, "không gắn nhãn màu (máy xem có thể đoán sai)", fix_xuat)
    else:
        row("Màu", DAT, f"{v.get('color_primaries')}/{trc}")
    if not a:
        row("Tiếng", CB, "không có tiếng")
    else:
        sr = int(a.get("sample_rate") or 0)
        ok = a.get("codec_name") == "aac" and sr in (44100, 48000)
        row("Tiếng", DAT if ok else CB, f"{a.get('codec_name')} {sr} Hz", "" if ok else fix_xuat)
        i, tp = loudness(p)
        if i is None:
            row("Độ to", CB, "không đo được (im lặng?)")
        else:
            d = abs(i - LUFS)
            kq = DAT if d <= 1 else CB if (d <= 3 or i > LUFS) and i <= -9 else LOI
            row("Độ to", kq, f"{i:.1f} LUFS (chuẩn {LUFS:g})" + (" — nhỏ hơn video khác khi lướt" if i < LUFS - 1 else
                                                                   " — nền tảng sẽ tự hạ" if i > LUFS + 1 else ""),
                "" if kq == DAT else fix_xuat)
        if tp is not None:
            kq = DAT if tp <= TP + 0.05 else CB if tp <= 0 else LOI
            row("Đỉnh âm", kq, f"{tp:.1f} dBTP (tối đa {TP:g})" + (" — có thể rè/vỡ tiếng" if tp > 0 else ""),
                "" if kq == DAT else fix_xuat)
    dur = m["dur"]
    over = dur > spec["max_s"]
    row("Thời lượng", CB if over else DAT,
        f"{dur:.1f}s" + (f" — quá mức tham khảo {spec['max_s']}s của {spec['ten']}" if over else ""),
        f"{fix_xuat} --cat-cho-vua (hoặc cắt nội dung cho ngắn lại)" if over else "")
    mb = Path(p).stat().st_size / 1e6
    row("Dung lượng", CB if mb > spec["max_mb"] else DAT, f"{mb:.1f} MB", fix_xuat if mb > spec["max_mb"] else "")
    fs = faststart(p)
    row("Mở nhanh (faststart)", DAT if fs else CB, "có" if fs else "không — phải tải hết mới phát",
        "" if fs else fix_xuat)
    return rows


def print_rows(p, nen, rows):
    icon = {DAT: "✅", CB: "⚠️ ", LOI: "❌"}
    print(f"\n{Path(p).name} → {NEN[nen]['ten']}")
    w = max(len(r["muc"]) for r in rows)
    for r in rows:
        print(f"  {icon[r['kq']]} {r['muc']:<{w}}  {r['gia_tri']}")
        if r["sua"]:
            print(f"      sửa: {r['sua']}")
    n = {k: sum(r["kq"] == k for r in rows) for k in (DAT, CB, LOI)}
    print(f"  → {n[DAT]} đạt · {n[CB]} cảnh báo · {n[LOI]} lỗi")


def cmd_kiem_dang(args):
    p = Path(args.video).resolve()
    out, bad = {}, False
    for nen in split_nen(args.nen):
        rows = check(p, nen)
        out[nen] = rows
        bad |= any(r["kq"] == LOI for r in rows)
        if not args.json:
            print_rows(p, nen, rows)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(1 if bad else 0)


# ---------- xuat ----------
def split_nen(s):
    nens = [n.strip().lower() for n in s.split(",") if n.strip()]
    for n in nens:
        if n not in NEN:
            die(f"không biết nền '{n}'. Có: {', '.join(NEN)}")
    return nens


def frame_filter(m, W, H, khop, cat_y):
    sw, sh_ = m["w"], m["h"]
    if abs(sw / sh_ - W / H) < 0.01:
        return f"scale={W}:{H}:flags=lanczos,setsar=1", "scale"
    if khop == "vien":
        return (f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"), "vien"
    if khop == "cat":
        y = max(0.0, min(1.0, cat_y))
        return (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={W}:{H}:(iw-{W})/2:(ih-{H})*{y:g},setsar=1"), "cat"
    # mo: nền là chính hình đó phóng to + làm mờ, hình gốc nguyên vẹn ở giữa (không mất phụ đề/chữ)
    return (f"split[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur=40:3,eq=brightness=-0.06[b];[fg]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos[f];"
            f"[b][f]overlay=(W-w)/2:(H-h)/2,setsar=1"), "mo"


def target_fps(f):
    std = min((23.976, 24, 25, 29.97, 30, 50, 59.94, 60), key=lambda s: abs(f - s))
    return std if abs(f - std) < 0.05 else (30 if f < 45 else 60)


def measure_ln(p, start=0.0, dur=None):
    pre = (["-ss", f"{start:g}"] if start else []) + (["-t", f"{dur:g}"] if dur else [])
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", *pre, "-i", str(p), "-map", "0:a:0",
                        "-af", f"loudnorm=I={LUFS:g}:TP={TP:g}:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    j = r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1]
    try:
        return json.loads(j)
    except ValueError:
        return None


def cmd_xuat(args):
    src = Path(args.video).resolve()
    m = sh.probe(src)
    if sh.is_hdr(m):
        die(f"clip là HDR. Chạy trước: python sua-hinh.py hdr-sdr {q(src)}")
    outdir = Path(args.thu_muc_ra).resolve() if args.thu_muc_ra else src.parent
    outdir.mkdir(parents=True, exist_ok=True)
    base = args.ten or src.stem
    fps = target_fps(m["fps"])
    ln = measure_ln(src) if m["a"] else None
    if m["a"] and not ln:
        print("  (không đo được độ to — dùng loudnorm 1 lượt)")
    made, bad = [], False
    for nen in split_nen(args.nen):
        spec = NEN[nen]
        out = outdir / f"{base}.{nen}.mp4"
        if out == src:
            die("file ra trùng file gốc — đặt --ten hoặc --thu-muc-ra khác.")
        if out.exists() and not args.ghi_de:
            print(f"  bỏ qua {out.name}: đã có (thêm --ghi-de để làm lại)")
            continue
        vf, how = frame_filter(m, spec["w"], spec["h"], args.khop, args.cat_y)
        dur = m["dur"]
        trim = []
        if dur > spec["max_s"]:
            if args.cat_cho_vua:
                dur = spec["max_s"] - 0.05
                trim = ["-t", f"{dur:.3f}"]
                vf += f",fade=t=out:st={dur - 0.6:.3f}:d=0.6"
                print(f"  {nen}: cắt còn {dur:.1f}s (mờ dần 0,6s cuối)")
            else:
                print(f"  ⚠️  {nen}: {m['dur']:.0f}s dài hơn mức tham khảo {spec['max_s']}s — vẫn xuất đủ. "
                      "Thêm --cat-cho-vua để cắt.")
        vf += f",fps={fps},format=yuv420p"
        fc = f"[0:v]{vf}[v]"
        cmd = ["-i", src, *trim, "-filter_complex", fc, "-map", "[v]"]
        if m["a"]:
            if ln:
                af = (f"loudnorm=I={LUFS:g}:TP={TP:g}:LRA=11:measured_I={ln['input_i']}:measured_TP={ln['input_tp']}:"
                      f"measured_LRA={ln['input_lra']}:measured_thresh={ln['input_thresh']}:offset={ln['target_offset']}:"
                      "linear=true")
            else:
                af = f"loudnorm=I={LUFS:g}:TP={TP:g}:LRA=11"
            if trim:
                af += f",afade=t=out:st={dur - 0.6:.3f}:d=0.6"
            af += ",aresample=48000,aformat=channel_layouts=stereo"
            cmd += ["-map", "0:a:0", "-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        g = int(round(fps * 2))
        cmd += ["-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", str(args.crf),
                "-maxrate", "16M" if spec["w"] * spec["h"] > 1.5e6 else "12M", "-bufsize", "24M", "-g", str(g),
                "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
                "-bsf:v", sh.BT709_BSF, "-movflags", "+faststart", out]
        sh.run_ffmpeg(cmd, label=f"{spec['ten']} {spec['w']}×{spec['h']} ({'giữ nguyên tỉ lệ' if how == 'scale' else {'mo': 'nền mờ', 'cat': 'cắt khung', 'vien': 'viền đen'}[how]})")
        rows = check(out, nen)
        # loudnorm tuyến tính có thể không chạm đúng -14 khi đỉnh bị chặn: đo lại, lệch nhiều thì chạy 1 lượt động
        lo = next((r for r in rows if r["muc"] == "Độ to"), None)
        if lo and lo["kq"] != DAT and ln:
            print("  độ to còn lệch (đỉnh âm chặn mức tăng) → làm lại với loudnorm động")
            i = cmd.index("-af")
            cmd[i + 1] = cmd[i + 1].replace(":linear=true", ":linear=false")
            sh.run_ffmpeg(cmd, label="lượt bù độ to")
            rows = check(out, nen)
        print_rows(out, nen, rows)
        bad |= any(r["kq"] == LOI for r in rows)
        made.append(out)
    if made and not args.khong_so_sanh:
        # ảnh xem nhanh các bản: khung giữa video, cùng chiều cao
        jpg = outdir / f"{base}.cac-ban.jpg"
        t = min(m["dur"] / 2, 30)
        ins = sum((["-ss", f"{t:.2f}", "-i", str(o)] for o in made), [])
        fc = "".join(f"[{i}:v]scale=-2:640,setsar=1,pad=iw+16:ih:8:0:white[x{i}];" for i in range(len(made)))
        fc += "".join(f"[x{i}]" for i in range(len(made))) + (f"hstack={len(made)}[o]" if len(made) > 1 else "null[o]")
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *ins, "-filter_complex", fc,
                            "-map", "[o]", "-frames:v", "1", "-q:v", "3", str(jpg)], capture_output=True)
        if r.returncode == 0:
            print(f"\n🖼 các bản cạnh nhau: {jpg}")
    sys.exit(1 if bad else 0)


# ---------- hang-loat ----------
def file_key(p, recipe):
    st = p.stat()
    h = hashlib.sha1()
    h.update(f"{p.name}|{st.st_size}|{st.st_mtime_ns}|".encode())
    h.update(json.dumps(recipe, sort_keys=True, ensure_ascii=False).encode())
    return h.hexdigest()[:16]


def cmd_hang_loat(args):
    folder = Path(args.thu_muc).resolve()
    if not folder.is_dir():
        die(f"{folder} không phải thư mục.")
    try:
        recipe = json.loads(Path(args.cong_thuc).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        die(f"không đọc được công thức {args.cong_thuc}: {e}")
    steps = recipe.get("buoc") or []
    if not steps or not all(isinstance(s, list) and s and s[0] in ("sua-hinh", "xuat") for s in steps):
        die('công thức cần "buoc": [["sua-hinh","<lệnh>",…], …, ["xuat","--nen","tiktok"]]')
    known = ("chong-rung", "can-mau", "hdr-sdr", "che-mo", "khu-nhieu", "can-thang", "lam-dep")
    for s in steps:
        if s[0] == "sua-hinh" and (len(s) < 2 or s[1] not in known):
            die(f"bước {s}: lệnh sua-hinh phải là một trong {', '.join(known)}")
    if any(s[0] == "xuat" for s in steps[:-1]):
        die('"xuat" chỉ được là bước cuối.')
    pattern = recipe.get("loc", "*.mp4;*.mov;*.MP4;*.MOV")
    outdir = folder / recipe.get("ra", "da-xu-ly")
    outdir.mkdir(exist_ok=True)
    cache_f = outdir / ".hang-loat.json"
    try:
        cache = json.loads(cache_f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    files = sorted(p for p in folder.iterdir() if p.is_file() and any(fnmatch(p.name, pt) for pt in pattern.split(";")))
    if not files:
        die(f"không có clip nào khớp '{pattern}' trong {folder}")
    py = sys.executable
    tong = {"xong": 0, "bo-qua": 0, "loi": 0}
    for k, f in enumerate(files, 1):
        key = file_key(f, steps)
        if not args.chay_lai and cache.get(f.name, {}).get("key") == key and \
                all((outdir / o).exists() for o in cache[f.name].get("ra", [])):
            print(f"[{k}/{len(files)}] {f.name}: đã làm với công thức này — bỏ qua")
            tong["bo-qua"] += 1
            continue
        print(f"[{k}/{len(files)}] {f.name}")
        cur, ok, outs = f, True, []
        with tempfile.TemporaryDirectory(prefix="hang-loat-") as tmp:
            for i, st in enumerate(steps):
                if st[0] == "sua-hinh":
                    if st[1] == "hdr-sdr" and not sh.is_hdr(sh.probe(cur)):
                        print("   · hdr-sdr: không phải HDR — bỏ bước")
                        continue
                    nxt = Path(tmp) / f"b{i}.mp4"
                    cmd = [py, str(HERE / "sua-hinh.py"), st[1], str(cur), *st[2:], "-o", str(nxt), "--ghi-de",
                           "--khong-so-sanh"]
                else:
                    nxt = None
                    cmd = [py, str(HERE / "xuat.py"), "xuat", str(cur), *st[1:], "--thu-muc-ra", str(outdir),
                           "--ten", f.stem, "--ghi-de", "--khong-so-sanh"]
                r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
                tail = (r.stdout + r.stderr).strip().splitlines()
                if r.returncode != 0 and not (st[0] == "xuat" and r.returncode == 1 and "LỖI:" not in r.stderr):
                    print(f"   ✗ {' '.join(st)}: {tail[-1] if tail else 'lỗi'}")
                    ok = False
                    break
                print(f"   ✓ {' '.join(st)}")
                if nxt:
                    cur = nxt
            if ok and steps[-1][0] != "xuat":  # không có bước xuất: giữ file cuối của sua-hinh
                dst = outdir / f"{f.stem}.sua.mp4"
                shutil.copy(cur, dst)
                outs.append(dst.name)
            elif ok:
                nens = split_nen(next(steps[-1][j + 1] for j, a in enumerate(steps[-1]) if a == "--nen"))
                outs += [f"{f.stem}.{n}.mp4" for n in nens]
        if ok:
            cache[f.name] = {"key": key, "ra": outs}
            cache_f.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
            tong["xong"] += 1
        else:
            tong["loi"] += 1
    print(f"\nXong: {tong['xong']} làm mới · {tong['bo-qua']} bỏ qua (đã có) · {tong['loi']} lỗi → {outdir}")
    sys.exit(1 if tong["loi"] else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("kiem-dang", help="kiểm video theo yêu cầu nền tảng")
    p.add_argument("video")
    p.add_argument("--nen", default="tiktok", help=f"một hoặc nhiều, cách nhau dấu phẩy: {','.join(NEN)}")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("xuat", help="xuất bản riêng cho từng nền tảng")
    p.add_argument("video")
    p.add_argument("--nen", required=True, help=f"cách nhau dấu phẩy: {','.join(NEN)}")
    p.add_argument("--khop", choices=("mo", "cat", "vien"), default="mo",
                   help="khác tỉ lệ thì: mo = nền mờ giữ trọn hình (mặc định) · cat = cắt khung · vien = viền đen")
    p.add_argument("--cat-y", type=float, default=0.4, help="--khop cat: vị trí cắt dọc 0 (giữ trên) … 1 (giữ dưới)")
    p.add_argument("--cat-cho-vua", action="store_true", help="dài hơn mức tham khảo của nền thì cắt + mờ dần cuối")
    p.add_argument("--thu-muc-ra", help="thư mục ra (mặc định cạnh video)")
    p.add_argument("--ten", help="tên gốc của file ra (mặc định tên video)")
    p.add_argument("--ghi-de", action="store_true")
    p.add_argument("--khong-so-sanh", action="store_true", help="không làm ảnh các bản cạnh nhau")
    p.add_argument("--crf", type=int, default=19)
    p = sub.add_parser("hang-loat", help="áp một công thức cho cả thư mục")
    p.add_argument("thu_muc")
    p.add_argument("--cong-thuc", required=True, help="file JSON: {loc, ra, buoc:[[…],…]}")
    p.add_argument("--chay-lai", action="store_true", help="làm lại cả clip đã làm")
    args = ap.parse_args()
    sh.need_ffmpeg()
    if args.cmd != "hang-loat" and not Path(args.video).exists():
        die(f"không thấy {args.video}")
    {"kiem-dang": cmd_kiem_dang, "xuat": cmd_xuat, "hang-loat": cmd_hang_loat}[args.cmd](args)


if __name__ == "__main__":
    main()
