#!/usr/bin/env python3
"""[tao-video · bước tuỳ chọn] Sửa hình clip gốc TRƯỚC khi dựng: chống rung, cân màu, HDR→SDR, che mờ, khử nhiễu, chỉnh nghiêng.

Mỗi lệnh đọc một clip, ghi ra FILE MỚI cạnh clip gốc (không bao giờ ghi đè clip gốc), kiểm lại thời lượng
tiếng/hình, và làm ảnh so sánh trước|sau `<ra>.so-sanh.jpg` để xem bằng mắt.

  python sua-hinh.py kiem <video>                                  xem clip có cần sửa gì không (HDR? tối? nghiêng?)
  python sua-hinh.py chong-rung <video> [--muc 15] [--chan-ba] [--zoom 0]
  python sua-hinh.py can-mau <video> [--tu-dong] [--sang 0.03] [--tuong-phan 1.08] [--bao-hoa 1.15]
                                     [--gamma 1.1] [--am 0.05] [--lut mau.cube] [--lut-manh 0.8]
  python sua-hinh.py hdr-sdr <video> [--tonemap hable] [--peak 1000]
  python sua-hinh.py che-mo <video> --vung x,y,w,h [--vung …] [--tu 3 --den 8] [--kieu mo|vo] [--manh 20]
  python sua-hinh.py khu-nhieu <video> [--hinh nhe|vua|manh|tat] [--tieng nhe|vua|manh|tat]
  python sua-hinh.py can-thang <video> --do -2.5

Chung: -o <file ra> (mặc định <tên>.<lệnh>.mp4 cạnh clip gốc) · --ghi-de (cho phép ghi đè file RA đã có)
       · --khong-so-sanh · --crf 18.
Nối nhiều bước: lấy file ra của bước trước làm đầu vào bước sau (thứ tự nên: hdr-sdr → can-thang → chong-rung
→ khu-nhieu → can-mau → che-mo). Xong thì đưa file cuối vào dung-video-quay.py chuan-bi như clip thường.

Cách làm tham khảo ffmpeg-skill (github.com/kajisho5/ffmpeg-skill, MIT): vidstab 2 lượt, chuỗi zscale/tonemap,
công thức phóng to khi xoay để không lộ góc đen. Viết lại gọn cho tao-video, chỉ cần ffmpeg/ffprobe.
"""
import argparse, json, math, os, shutil, subprocess, sys, tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

HDR_TRC = {"smpte2084": "PQ (HDR10/Dolby Vision)", "arib-std-b67": "HLG (iPhone/Android HDR)"}
TONEMAPS = ("hable", "mobius", "reinhard", "clip", "linear", "gamma")
LOI = "LỖI: "


# ---------- tiện ích ----------
def die(msg):
    sys.exit(LOI + msg)


def need_ffmpeg():
    for exe in ("ffmpeg", "ffprobe"):
        if not shutil.which(exe):
            die(f"không thấy {exe} trên PATH. Windows: winget install Gyan.FFmpeg rồi mở terminal mới.")


def probe(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration:stream=index,codec_type,codec_name,width,height,pix_fmt,r_frame_rate,"
                          "avg_frame_rate,duration,color_transfer,color_primaries,color_space,color_range:"
                          "stream_side_data=rotation",
                          "-of", "json", str(p)], capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        die(f"ffprobe không đọc được {p}: {out.stderr.strip()[-300:]}")
    j = json.loads(out.stdout)
    v = next((s for s in j.get("streams", []) if s["codec_type"] == "video"), None)
    a = next((s for s in j.get("streams", []) if s["codec_type"] == "audio"), None)
    if not v:
        die(f"{p} không có hình.")
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    w, h = v["width"], v["height"]
    if rot % 180:
        w, h = h, w  # ffmpeg tự xoay khi giải mã → kích thước hiển thị
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    dur = float(j.get("format", {}).get("duration") or v.get("duration") or 0)
    return {"v": v, "a": a, "w": w, "h": h, "fps": fps, "dur": dur, "rot": rot,
            "vdur": float(v.get("duration") or dur), "adur": float(a.get("duration") or dur) if a else None}


def is_hdr(m):
    return m["v"].get("color_transfer") in HDR_TRC


def out_path(args, cmd):
    src = Path(args.video).resolve()
    out = Path(args.o).resolve() if args.o else src.with_name(f"{src.stem}.{cmd}.mp4")
    if out == src:
        die("file ra trùng clip gốc. Script không ghi đè clip gốc — đặt -o tên khác.")
    if out.exists() and not args.ghi_de:
        die(f"{out.name} đã có. Thêm --ghi-de để làm lại, hoặc -o tên khác.")
    out.parent.mkdir(parents=True, exist_ok=True)
    return src, out


def enc_args(crf, audio="copy", hdr_src=False):
    v = ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p"]
    if not hdr_src:  # nguồn SDR: gắn nhãn BT.709 để TikTok/Reels không đoán sai màu
        v += ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]
    a = ["-c:a", "copy"] if audio == "copy" else ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    return v + a + ["-movflags", "+faststart"]


def run_ffmpeg(cmd, cwd=None, label=""):
    full = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-stats", "-y"] + [str(c) for c in cmd]
    print(f"  ▶ {label or 'ffmpeg'} …", flush=True)
    r = subprocess.run(full, cwd=cwd, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        die(f"ffmpeg dừng ({label}):\n{r.stderr.strip()[-1200:]}")


def even(n):
    return int(n) // 2 * 2


def maps(m):
    return ["-map", "0:v:0"] + (["-map", "0:a:0"] if m["a"] else [])


# ---------- kiểm sau khi ghi ----------
def verify(src_m, out, expect_hdr_off=False):
    o = probe(out)
    problems = []
    if abs(o["vdur"] - src_m["vdur"]) > max(0.15, 2 / src_m["fps"]):
        problems.append(f"thời lượng hình {o['vdur']:.2f}s ≠ gốc {src_m['vdur']:.2f}s")
    if src_m["a"]:
        if not o["a"]:
            problems.append("mất tiếng")
        elif abs((o["adur"] - o["vdur"]) - (src_m["adur"] - src_m["vdur"])) > 0.15:
            problems.append(f"lệch tiếng/hình: tiếng {o['adur']:.2f}s, hình {o['vdur']:.2f}s")
    if o["w"] % 2 or o["h"] % 2:
        problems.append(f"kích thước lẻ {o['w']}×{o['h']}")
    if expect_hdr_off and is_hdr(o):
        problems.append("file ra vẫn mang nhãn HDR")
    print(f"  ✔ {out.name}: {o['w']}×{o['h']}, {o['fps']:.2f} fps, {o['vdur']:.2f}s"
          + (f", tiếng {o['adur']:.2f}s" if o["a"] else ", không tiếng"))
    if problems:
        die("kiểm file ra không đạt: " + "; ".join(problems))
    return o


def compare(src, out, times, dur):
    """Ảnh so sánh: mỗi hàng một mốc thời gian, trái = gốc, phải = sau khi sửa."""
    jpg = out.with_suffix(".so-sanh.jpg")
    times = [min(max(0.0, t), max(0.0, dur - 0.1)) for t in times]
    ins, fc, rows = [], [], []
    for i, t in enumerate(times):
        ins += ["-ss", f"{t:.3f}", "-i", str(src), "-ss", f"{t:.3f}", "-i", str(out)]
        fc.append(f"[{2*i}:v]scale=-2:420,setsar=1,format=yuv420p[a{i}];[{2*i+1}:v]scale=-2:420,setsar=1,format=yuv420p[b{i}];"
                  f"[a{i}][b{i}]hstack=2[r{i}]")
        rows.append(f"[r{i}]")
    fc.append("".join(rows) + (f"vstack={len(rows)}[o]" if len(rows) > 1 else "null[o]"))
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *ins, "-filter_complex", ";".join(fc),
                        "-map", "[o]", "-frames:v", "1", "-q:v", "3", str(jpg)],
                       stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if r.returncode == 0:
        print(f"  🖼 so sánh trước|sau: {jpg}")
    else:
        print(f"  (không làm được ảnh so sánh: {r.stderr.strip()[-200:]})")


def finish(args, src, out, m, times=None, **kw):
    verify(m, out, **kw)
    if not args.khong_so_sanh:
        compare(src, out, times or [m["dur"] * f for f in (0.2, 0.5, 0.8)], m["dur"])


# ---------- kiem ----------
def luma_stats(src, m, n=12):
    """Độ sáng trung bình (0–255, thang TV 16–235) và độ trải sáng trên n khung rải đều."""
    step = max(m["dur"] / (n + 1), 0.04)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(src), "-map", "0:v:0",
                        "-vf", f"fps=1/{step:.3f},scale=320:-2,format=yuv420p,signalstats,metadata=print:file=-",
                        "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    avg, low, high = [], [], []
    for line in r.stdout.splitlines():
        if "lavfi.signalstats.YAVG=" in line:
            avg.append(float(line.split("=")[1]))
        elif "lavfi.signalstats.YLOW=" in line:
            low.append(float(line.split("=")[1]))
        elif "lavfi.signalstats.YHIGH=" in line:
            high.append(float(line.split("=")[1]))
    if not avg:
        return None
    f = lambda xs: sum(xs) / len(xs) if xs else None
    return {"yavg": f(avg), "ylow": f(low), "yhigh": f(high)}


def cmd_kiem(args):
    src = Path(args.video).resolve()
    m = probe(src)
    v = m["v"]
    print(f"{src.name}: {m['w']}×{m['h']}, {m['fps']:.2f} fps, {m['dur']:.1f}s, hình {v['codec_name']} {v.get('pix_fmt')}"
          + (f", tiếng {m['a']['codec_name']}" if m["a"] else ", KHÔNG có tiếng")
          + (f", xoay {m['rot']}°" if m["rot"] else ""))
    goi_y = []
    if is_hdr(m):
        print(f"  • HDR: {HDR_TRC[v['color_transfer']]} → lên TikTok/Reels dễ bị nhạt hoặc chói.")
        goi_y.append("hdr-sdr")
    else:
        print(f"  • Màu: SDR ({v.get('color_transfer') or 'không gắn nhãn'})")
    st = None if is_hdr(m) else luma_stats(src, m)  # HDR: đo độ sáng sau khi đã về SDR
    if is_hdr(m):
        print("  • Độ sáng: đo lại sau khi chạy hdr-sdr (số đo trên HDR không so được với SDR).")
    if st:
        y = st["yavg"]
        mo_ta = "tối" if y < 70 else "hơi tối" if y < 90 else "sáng gắt" if y > 175 else "ổn"
        print(f"  • Độ sáng trung bình {y:.0f}/235 ({mo_ta}), dải {st['ylow']:.0f}–{st['yhigh']:.0f}")
        if y < 90 or y > 175 or (st["yhigh"] - st["ylow"]) < 120:
            goi_y.append("can-mau --tu-dong")
        if y < 70:
            goi_y.append("khu-nhieu (quay tối thường nhiễu hạt)")
    print("  • Rung / nghiêng / cần che: máy không tự đo — xem ảnh khung hình rồi quyết.")
    print("Gợi ý: " + (", ".join(goi_y) if goi_y else "không cần sửa màu/HDR."))


# ---------- chong-rung ----------
def cmd_chong_rung(args):
    src, out = out_path(args, "on-dinh")
    m = probe(src)
    pre = "" if not (m["w"] % 2 or m["h"] % 2) else "scale=trunc(iw/2)*2:trunc(ih/2)*2,"
    pre = ("format=yuv420p," if (m["v"].get("pix_fmt") or "").startswith(("rgb", "bgr", "gbr")) else "") + pre
    with tempfile.TemporaryDirectory(prefix="sua-hinh-") as tmp:
        # đường dẫn tương đối trong thư mục tạm: tránh dấu ':' của ổ đĩa Windows trong bộ lọc
        det = f"{pre}vidstabdetect=shakiness={args.do_rung}:accuracy=15:result=tf.trf"
        if args.chan_ba:
            det += ":tripod=1"
        run_ffmpeg(["-i", src, "-map", "0:v:0", "-vf", det, "-f", "null", "-"], cwd=tmp, label="lượt 1/2: đo chuyển động")
        tr = f"{pre}vidstabtransform=input=tf.trf:smoothing={args.muc}:crop=keep:zoom={args.zoom:g}:optzoom={0 if args.zoom else 1}:interpol=bicubic"
        if args.chan_ba:
            tr += ":tripod=1"
        tr += ",unsharp=5:5:0.6:3:3:0.3"
        run_ffmpeg(["-i", src, *maps(m), "-vf", tr, *enc_args(args.crf, hdr_src=is_hdr(m)), out], cwd=tmp,
                   label="lượt 2/2: làm mượt")
    finish(args, src, out, m)


# ---------- can-mau ----------
def auto_grade(st):
    """Từ độ sáng đo được ra gamma/tương phản vừa phải (không 'phẫu thuật' màu)."""
    y = (st["yavg"] - 16) / 219
    y = min(max(y, 0.05), 0.95)
    target = 0.45
    # eq: ra = vào^(1/gamma) → gamma = log(y)/log(đích); >1 nâng vùng tối
    g = min(max(math.log(y) / math.log(target), 0.75), 1.6) if abs(y - target) > 0.04 else 1.0
    spread = (st["yhigh"] - st["ylow"]) / 219
    c = 1.0 if spread > 0.75 else min(1.0 + (0.75 - spread) * 0.5, 1.2)
    return round(g, 3), round(c, 3)


def cmd_can_mau(args):
    src, out = out_path(args, "mau")
    m = probe(src)
    if is_hdr(m):
        die("clip là HDR — chạy hdr-sdr trước, rồi cân màu trên file SDR đó.")
    gamma, contrast = args.gamma, args.tuong_phan
    if args.tu_dong:
        st = luma_stats(src, m)
        if st:
            ga, ca = auto_grade(st)
            gamma = gamma if gamma is not None else ga
            contrast = contrast if contrast is not None else ca
            print(f"  tự động: độ sáng TB {st['yavg']:.0f} → gamma {gamma}, tương phản {contrast}")
    gamma = 1.0 if gamma is None else gamma
    contrast = 1.0 if contrast is None else contrast
    sat = args.bao_hoa if args.bao_hoa is not None else (1.08 if args.tu_dong else 1.0)
    chain = []
    if (gamma, contrast, args.sang, sat) != (1.0, 1.0, 0.0, 1.0):
        chain.append(f"eq=brightness={args.sang:g}:contrast={contrast:g}:saturation={sat:g}:gamma={gamma:g}")
    if args.am:
        a = max(-0.3, min(0.3, args.am))
        chain.append(f"colorbalance=rm={a:g}:bm={-a:g}:rh={a/2:g}:bh={-a/2:g}")
    with tempfile.TemporaryDirectory(prefix="sua-hinh-") as tmp:
        if args.lut:
            lut = Path(args.lut).resolve()
            if not lut.exists() or lut.suffix.lower() not in (".cube", ".3dl", ".dat", ".m3d", ".csp"):
                die(f"không dùng được LUT {lut} (cần file .cube/.3dl có thật).")
            shutil.copy(lut, Path(tmp) / f"lut{lut.suffix.lower()}")
            k = max(0.0, min(1.0, args.lut_manh))
            if k >= 0.999:
                chain.append(f"lut3d=file=lut{lut.suffix.lower()}:interp=tetrahedral")
            else:  # trộn LUT với hình gốc theo độ mạnh
                chain = [",".join(chain)] if chain else []
                chain.append(f"split[g][l];[l]lut3d=file=lut{lut.suffix.lower()}:interp=tetrahedral[lt];"
                             f"[g][lt]blend=all_mode=normal:all_opacity={k:g}")
        if not chain:
            die("chưa có chỉnh gì: thêm --tu-dong hoặc --sang/--tuong-phan/--bao-hoa/--gamma/--am/--lut.")
        vf = ",".join(chain)
        if "[" in vf:
            cmd = ["-i", src, "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]"] + (["-map", "0:a:0"] if m["a"] else [])
        else:
            cmd = ["-i", src, *maps(m), "-vf", vf]
        print(f"  bộ lọc: {vf}")
        run_ffmpeg(cmd + [*enc_args(args.crf), out], cwd=tmp, label="cân màu")
    finish(args, src, out, m)


# ---------- hdr-sdr ----------
def cmd_hdr_sdr(args):
    src, out = out_path(args, "sdr")
    m = probe(src)
    v = m["v"]
    if not is_hdr(m) and not args.ep:
        die(f"clip không gắn nhãn HDR (transfer={v.get('color_transfer') or 'trống'}) — không cần chạy. "
            "Chắc chắn là HDR mà thiếu nhãn thì thêm --ep.")
    trc = v.get("color_transfer") if is_hdr(m) else "smpte2084"
    prim = v.get("color_primaries") or "bt2020"
    space = v.get("color_space") or "bt2020nc"
    if space not in ("bt2020nc", "bt2020c", "bt709"):
        space = "bt2020nc"
    if prim not in ("bt2020", "bt709"):
        prim = "bt2020"
    peak = 1000.0 if trc == "arib-std-b67" else args.peak
    chain = [f"setparams=color_primaries={prim}:color_trc={trc}:colorspace={space}",
             f"zscale=tin={trc}:pin={prim}:min={space}:rin={'pc' if v.get('color_range') == 'pc' else 'tv'}:t=linear:npl=100",
             "format=gbrpf32le", "zscale=p=bt709",
             f"tonemap=tonemap={args.tonemap}:desat=0:peak={peak / 100:g}",
             "zscale=t=bt709:m=bt709:r=tv", "format=yuv420p"]
    run_ffmpeg(["-i", src, *maps(m), "-vf", ",".join(chain), *enc_args(args.crf), out],
               label=f"HDR {HDR_TRC.get(trc, trc)} → SDR BT.709 ({args.tonemap})")
    finish(args, src, out, m, expect_hdr_off=True)


# ---------- che-mo ----------
def parse_box(s, W, H):
    try:
        x, y, w, h = (float(t) for t in s.replace(" ", "").split(","))
    except ValueError:
        die(f"--vung '{s}' phải là x,y,w,h (điểm ảnh, hoặc tỉ lệ 0–1 của khung).")
    if max(x, y, w, h) <= 1.0:
        x, y, w, h = x * W, y * H, w * W, h * H
    x, y = max(0, even(x)), max(0, even(y))
    w, h = even(min(w, W - x)), even(min(h, H - y))
    if w < 4 or h < 4:
        die(f"--vung '{s}' quá nhỏ hoặc nằm ngoài khung {W}×{H}.")
    return x, y, w, h


def cmd_che_mo(args):
    src, out = out_path(args, "che")
    m = probe(src)
    W, H = even(m["w"]), even(m["h"])
    boxes = [parse_box(b, W, H) for b in args.vung]
    tu = args.tu or 0.0
    den = args.den if args.den is not None else m["dur"] + 1
    if den <= tu:
        die("--den phải lớn hơn --tu.")
    en = f":enable='between(t,{tu:g},{den:g})'" if (args.tu or args.den is not None) else ""
    fc = [f"[0:v]scale={W}:{H},setsar=1,format=yuv420p,split={len(boxes) + 1}[base]" + "".join(f"[s{i}]" for i in range(len(boxes)))]
    last = "base"
    for i, (x, y, w, h) in enumerate(boxes):
        if args.kieu == "vo":
            b = max(2, args.manh // 2)
            eff = f"scale={max(1, w // b)}:{max(1, h // b)}:flags=neighbor,scale={w}:{h}:flags=neighbor"
        else:
            r = max(1, min(args.manh, min(w, h) // 2 - 1))
            cr = max(1, min(r // 2, min(w, h) // 4 - 1))
            eff = f"boxblur={r}:3:{cr}:3"
        fc.append(f"[s{i}]crop={w}:{h}:{x}:{y},{eff}[p{i}]")
        fc.append(f"[{last}][p{i}]overlay={x}:{y}{en}[o{i}]")
        last = f"o{i}"
        print(f"  vùng {i+1}: x={x} y={y} {w}×{h}" + (f", từ {tu:g}s đến {min(den, m['dur']):g}s" if en else ", cả clip"))
    run_ffmpeg(["-i", src, "-filter_complex", ";".join(fc), "-map", f"[{last}]"] + (["-map", "0:a:0"] if m["a"] else [])
               + [*enc_args(args.crf, hdr_src=is_hdr(m)), out], label="che vùng")
    mid = (tu + min(den, m["dur"])) / 2
    finish(args, src, out, m, times=[tu + 0.05, mid, min(den, m["dur"]) - 0.1] if en else None)
    print("  Lưu ý: vùng che đứng yên. Người/biển số di chuyển nhiều → chia thành nhiều đoạn --tu/--den với vùng khác nhau.")


# ---------- khu-nhieu ----------
DN_HINH = {"nhe": "hqdn3d=2:1.5:3:2.25", "vua": "hqdn3d=4:3:6:4.5", "manh": "hqdn3d=6:4.5:9:7,unsharp=5:5:0.4:3:3:0"}
DN_TIENG = {"nhe": "afftdn=nr=8:nf=-50:tn=1", "vua": "highpass=f=70,afftdn=nr=12:nf=-45:tn=1",
            "manh": "highpass=f=80,afftdn=nr=20:nf=-40:tn=1"}


def cmd_khu_nhieu(args):
    src, out = out_path(args, "sach")
    m = probe(src)
    if args.hinh == "tat" and (args.tieng == "tat" or not m["a"]):
        die("--hinh tat và --tieng tat: không có gì để làm.")
    cmd = ["-i", src, *maps(m)]
    if args.hinh != "tat":
        cmd += ["-vf", DN_HINH[args.hinh]]
    audio = "copy"
    if m["a"] and args.tieng != "tat":
        cmd += ["-af", DN_TIENG[args.tieng]]
        audio = "aac"
    if args.hinh == "tat":
        enc = ["-c:v", "copy"] + (["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]) + ["-movflags", "+faststart"]
    else:
        enc = enc_args(args.crf, audio=audio, hdr_src=is_hdr(m))
    run_ffmpeg(cmd + enc + [out], label=f"khử nhiễu (hình {args.hinh}, tiếng {args.tieng if m['a'] else '—'})")
    finish(args, src, out, m)


# ---------- can-thang ----------
def cmd_can_thang(args):
    src, out = out_path(args, "thang")
    m = probe(src)
    if abs(args.do) > 15:
        die("--do quá 15°: đó là xoay khung, không phải chỉnh nghiêng.")
    W, H = even(m["w"]), even(m["h"])
    rad = math.radians(args.do)
    s = abs(math.cos(rad)) + max(W / H, H / W) * abs(math.sin(rad))
    sw, sh = (c + math.ceil(max(0.0, c * s - c) / 4) * 4 for c in (W, H))
    vf = f"scale={sw}:{sh},setsar=1,rotate={rad:.8f}:bilinear=1,crop={W}:{H},setsar=1"
    print(f"  xoay {args.do:+g}° ({'chiều kim đồng hồ' if args.do > 0 else 'ngược chiều kim đồng hồ'}), "
          f"phóng {s:.3f}× để không lộ góc đen")
    run_ffmpeg(["-i", src, *maps(m), "-vf", vf, *enc_args(args.crf, hdr_src=is_hdr(m)), out], label="chỉnh nghiêng")
    finish(args, src, out, m)


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("video")
        if name != "kiem":
            p.add_argument("-o", help="file ra (mặc định <tên>.<lệnh>.mp4 cạnh clip gốc)")
            p.add_argument("--ghi-de", action="store_true", help="cho phép ghi đè file RA đã có (không bao giờ đè clip gốc)")
            p.add_argument("--khong-so-sanh", action="store_true", help="không làm ảnh so sánh trước|sau")
            p.add_argument("--crf", type=int, default=18, help="chất lượng x264, nhỏ = đẹp hơn (mặc định 18)")
        return p

    add("kiem", "xem clip có cần sửa không")
    p = add("chong-rung", "chống rung 2 lượt (vid.stab)")
    p.add_argument("--muc", type=int, default=15, help="độ mượt: số khung làm trơn (10 nhẹ · 15 vừa · 30 rất mượt)")
    p.add_argument("--do-rung", type=int, default=6, choices=range(1, 11), metavar="1-10",
                   help="clip rung cỡ nào (1 ít · 10 rất rung), mặc định 6")
    p.add_argument("--chan-ba", action="store_true", help="khoá cứng như đặt chân máy (clip vốn định đứng yên)")
    p.add_argument("--zoom", type=float, default=0, help="phóng to %% cố định để giấu viền; 0 = tự chọn tối thiểu")
    p = add("can-mau", "sáng/tương phản/bão hoà/ấm lạnh, LUT .cube")
    p.add_argument("--tu-dong", action="store_true", help="đo độ sáng rồi tự chỉnh gamma/tương phản vừa phải")
    p.add_argument("--sang", type=float, default=0.0, help="độ sáng cộng thêm, -0.2…0.2 (0.03 = sáng nhẹ)")
    p.add_argument("--tuong-phan", type=float, help="tương phản, 1 = giữ (1.08 = đậm nhẹ)")
    p.add_argument("--bao-hoa", type=float, help="độ rực màu, 1 = giữ (1.15 = tươi hơn)")
    p.add_argument("--gamma", type=float, help=">1 nâng vùng tối, <1 hạ")
    p.add_argument("--am", type=float, default=0.0, help="ấm (+) / lạnh (-), -0.3…0.3")
    p.add_argument("--lut", help="file LUT .cube")
    p.add_argument("--lut-manh", type=float, default=1.0, help="độ mạnh LUT 0–1 (mặc định 1)")
    p = add("hdr-sdr", "HDR (iPhone HLG, HDR10 PQ) → SDR BT.709")
    p.add_argument("--tonemap", choices=TONEMAPS, default="hable")
    p.add_argument("--peak", type=float, default=1000.0, help="độ sáng đỉnh nguồn PQ (nit), mặc định 1000")
    p.add_argument("--ep", action="store_true", help="coi là HDR PQ dù file thiếu nhãn")
    p = add("che-mo", "làm mờ / vỡ hạt vùng chữ nhật")
    p.add_argument("--vung", action="append", required=True, help="x,y,w,h (điểm ảnh hoặc tỉ lệ 0–1); lặp lại cho nhiều vùng")
    p.add_argument("--tu", type=float, help="giây bắt đầu che (mặc định cả clip)")
    p.add_argument("--den", type=float, help="giây hết che")
    p.add_argument("--kieu", choices=("mo", "vo"), default="mo", help="mo = làm mờ · vo = vỡ hạt (pixel)")
    p.add_argument("--manh", type=int, default=20, help="độ mạnh (mặc định 20)")
    p = add("khu-nhieu", "khử nhiễu hình (hqdn3d) và tiếng (afftdn)")
    p.add_argument("--hinh", choices=("nhe", "vua", "manh", "tat"), default="vua")
    p.add_argument("--tieng", choices=("nhe", "vua", "manh", "tat"), default="tat",
                   help="mặc định tắt: chỉ bật khi nghe rõ tiếng ù/xì")
    p = add("can-thang", "xoay chỉnh đường chân trời, tự cắt viền đen")
    p.add_argument("--do", type=float, required=True,
                   help="độ xoay: + theo chiều kim đồng hồ. Đường ngang chúi xuống bên PHẢI → số âm; chúi xuống bên TRÁI → số dương")

    args = ap.parse_args()
    need_ffmpeg()
    if not Path(args.video).exists():
        die(f"không thấy {args.video}")
    {"kiem": cmd_kiem, "chong-rung": cmd_chong_rung, "can-mau": cmd_can_mau, "hdr-sdr": cmd_hdr_sdr,
     "che-mo": cmd_che_mo, "khu-nhieu": cmd_khu_nhieu, "can-thang": cmd_can_thang}[args.cmd](args)


if __name__ == "__main__":
    main()
