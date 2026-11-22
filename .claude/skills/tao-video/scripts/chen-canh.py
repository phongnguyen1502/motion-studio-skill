#!/usr/bin/env python3
"""[tao-video · dựng thêm] Chèn cảnh minh hoạ (B-roll), tua nhanh/chậm từng đoạn, tìm đoạn hay trong video dài.

  python chen-canh.py b-roll <video> --chen canh.mp4@12-16 [--chen anh.png@20-23] [--tieng goc|tron] [-o ra.mp4]
      → trong khoảng 12–16 s hình được thay bằng canh.mp4 (phủ kín khung, cắt giữa), lời nói vẫn chạy liền bên dưới.
        Video ra DÀI ĐÚNG như video gốc. `canh.mp4@12-16+3` = lấy canh.mp4 từ giây 3; giờ viết được 1:05. Ảnh tĩnh: tự đẩy chậm (Ken Burns).
        --tieng tron: trộn nhỏ tiếng của cảnh chèn (-14 dB) dưới lời; mặc định chỉ giữ tiếng video gốc.
  python chen-canh.py tua <video> --doan 0-4:1,4-9:2.5,9-11:0.5 [-o ra.mp4]
      → mỗi đoạn một tốc độ (2.5 = nhanh 2,5 lần, 0.5 = chậm một nửa), tiếng giữ cao độ. Phần không nêu giữ 1×.
  python chen-canh.py doan-hay <video> [--so 5] [--dai 30-60] [--nghe]
      → gợi ý các đoạn đáng cắt thành short: dựa trên chỗ chuyển cảnh, khoảng ngắt lời, độ to/sôi nổi của tiếng.
        --nghe: chép lời từng đoạn (faster-whisper trên máy) để đọc nội dung. Chỉ là GỢI Ý — xem lại trước khi cắt.
        Ra: <video>.doan-hay.json + .doan-hay.jpg (3 khung mỗi đoạn).

Mọi lệnh ra FILE MỚI (mặc định <tên>.<lệnh>.mp4), không ghi đè video gốc, tự kiểm thời lượng tiếng/hình.
Cách làm tham khảo ffmpeg-skill (kajisho5, MIT), viết lại.
"""
import argparse, importlib.util, json, math, os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("sua_hinh", HERE / "sua-hinh.py")
sh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sh)

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
IMG = (".png", ".jpg", ".jpeg", ".webp")


def die(msg):
    sys.exit("LỖI: " + msg)


def out_for(args, src, tag):
    out = Path(args.o).resolve() if args.o else src.with_name(f"{src.stem}.{tag}.mp4")
    if out == src:
        die("file ra trùng video gốc — đặt -o khác.")
    if out.exists() and not args.ghi_de:
        die(f"{out.name} đã có. Thêm --ghi-de để làm lại.")
    return out


def tsec(s):
    s = s.strip()
    if ":" in s:  # mm:ss
        m, x = s.split(":", 1)
        return int(m) * 60 + float(x)
    return float(s)


def enc(m):
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-bsf:v", sh.BT709_BSF,
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart"]


# ---------- b-roll ----------
def parse_chen(s):
    m = re.match(r"^(.*)@([\d.:]+)-([\d.:]+)(?:\+([\d.]+))?$", s)
    if not m:
        die(f"--chen '{s}' phải dạng file@đầu-cuối[+giây-bắt-đầu-trong-file], vd canh.mp4@12-16, canh.mp4@1:05-1:09+3")
    f, a, b, frm = m.group(1), tsec(m.group(2)), tsec(m.group(3)), float(m.group(4) or 0)
    p = Path(f).resolve()
    if not p.exists():
        die(f"không thấy {p}")
    if b <= a:
        die(f"--chen '{s}': cuối phải lớn hơn đầu.")
    return p, a, b, frm


def cmd_b_roll(args):
    src = Path(args.video).resolve()
    m = sh.probe(src)
    out = out_for(args, src, "broll")
    W, H = sh.even(m["w"]), sh.even(m["h"])
    fps = round(m["fps"]) or 30
    chens = sorted((parse_chen(c) for c in args.chen), key=lambda c: c[1])
    for (p1, a1, b1, _), (p2, a2, b2, _) in zip(chens, chens[1:]):
        if a2 < b1:
            die(f"hai cảnh chèn chồng nhau ở {a2:g}–{b1:g}s.")
    inputs = ["-i", str(src)]
    fc = [f"[0:v]fps={fps},scale={W}:{H},setsar=1,format=yuv420p[base]"]
    last, mix = "base", []
    for i, (p, a, b, frm) in enumerate(chens, 1):
        b = min(b, m["dur"])
        d = b - a
        if p.suffix.lower() in IMG:
            inputs += ["-loop", "1", "-t", f"{d + 0.5:.3f}", "-i", str(p)]
            # đẩy chậm 6% suốt cảnh để ảnh không "chết"
            prep = (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
                    f"zoompan=z='1+0.06*on/{max(1, int(d * fps))}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                    f"d=1:s={W}x{H}:fps={fps}")
        else:
            bi = sh.probe(p)
            if frm + d > bi["dur"] + 0.05:
                die(f"{p.name} chỉ dài {bi['dur']:.1f}s, không đủ {d:.1f}s từ giây {frm:g}.")
            inputs += ["-ss", f"{frm:.3f}", "-t", f"{d:.3f}", "-i", str(p)]
            prep = f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
            if args.tieng == "tron" and bi["a"]:
                mix.append((i, a, d))
        fc.append(f"[{i}:v]{prep},setsar=1,format=yuv420p,trim=0:{d:.3f},setpts=PTS-STARTPTS+{a:.3f}/TB[c{i}]")
        fc.append(f"[{last}][c{i}]overlay=0:0:eof_action=pass:enable='between(t,{a:.3f},{b - 0.001:.3f})'[o{i}]")
        last = f"o{i}"
        print(f"  {a:6.2f}–{b:6.2f}s  ← {p.name}" + (f" (từ giây {frm:g})" if frm else ""))
    amap = []
    if m["a"]:
        if mix:
            parts = [f"[0:a]aresample=48000[a0]"]
            for i, a, d in mix:
                parts.append(f"[{i}:a]aresample=48000,volume=-14dB,afade=t=in:d=0.15,afade=t=out:st={max(0, d - 0.25):.3f}:d=0.25,"
                             f"adelay={int(a * 1000)}:all=1[x{i}]")
            parts.append("[a0]" + "".join(f"[x{i}]" for i, _, _ in mix) +
                         f"amix=inputs={len(mix) + 1}:duration=first:normalize=0[a]")
            fc += parts
            amap = ["-map", "[a]"]
        else:
            amap = ["-map", "0:a:0"]
    sh.run_ffmpeg([*inputs, "-filter_complex", ";".join(fc), "-map", f"[{last}]", *amap, "-t", f"{m['dur']:.3f}",
                   *enc(m), out], label="chèn cảnh")
    sh.verify(m, out)
    if not args.khong_so_sanh:
        sh.compare(src, out, [(c[1] + min(c[2], m["dur"])) / 2 for c in chens][:4], m["dur"])


# ---------- tua ----------
def atempo_chain(f):
    parts = []
    while f > 2.0:
        parts.append("atempo=2.0"); f /= 2.0
    while f < 0.5:
        parts.append("atempo=0.5"); f /= 0.5
    parts.append(f"atempo={f:.5f}")
    return ",".join(parts)


def cmd_tua(args):
    src = Path(args.video).resolve()
    m = sh.probe(src)
    out = out_for(args, src, "tua")
    segs = []
    for part in args.doan.split(","):
        mm = re.match(r"^\s*([\d.:]+)-([\d.:]+):([\d.]+)\s*$", part)
        if not mm:
            die(f"--doan '{part}' phải dạng đầu-cuối:tốc-độ, vd 4-9:2.5")
        a, b, f = tsec(mm.group(1)), min(tsec(mm.group(2)), m["vdur"]), float(mm.group(3))
        if not 0.1 <= f <= 16:
            die(f"tốc độ {f} ngoài 0.1–16.")
        segs.append((a, b, f))
    segs.sort()
    full, t = [], 0.0
    for a, b, f in segs:
        if a < t - 1e-6:
            die(f"các đoạn chồng nhau ở {a:g}s.")
        if a > t + 1e-3:
            full.append((t, a, 1.0))
        full.append((a, b, f))
        t = b
    if t < m["vdur"] - 0.1:
        full.append((t, m["vdur"], 1.0))
    elif t < m["vdur"] - 1e-3:   # đuôi lẻ < 0,1 s: nhập vào đoạn cuối
        a, _, f = full[-1]
        full[-1] = (a, m["vdur"], f)
    fps = round(m["fps"]) or 30
    n = len(full)
    fc = [f"[0:v]fps={fps},split={n}" + "".join(f"[vs{i}]" for i in range(n))]
    if m["a"]:
        fc.append(f"[0:a]aresample=48000,asplit={n}" + "".join(f"[as{i}]" for i in range(n)))
    lab = []
    total = 0.0
    for i, (a, b, f) in enumerate(full):
        fc.append(f"[vs{i}]trim=start={a:.4f}:end={b:.4f},setpts=(PTS-STARTPTS)/{f:.5f}[v{i}]")
        lab.append(f"[v{i}]")
        if m["a"]:
            fc.append(f"[as{i}]atrim=start={a:.4f}:end={b:.4f},asetpts=PTS-STARTPTS,{atempo_chain(f)}[a{i}]")
            lab.append(f"[a{i}]")
        total += (b - a) / f
        print(f"  {a:6.2f}–{b:6.2f}s  ×{f:g}  → {(b - a) / f:.2f}s")
    fc.append("".join(lab) + f"concat=n={n}:v=1:a={1 if m['a'] else 0}" + ("[v][a]" if m["a"] else "[v]"))
    fc[-1] = fc[-1].replace("[v]", "[vc]", 1)
    fc.append(f"[vc]fps={fps},format=yuv420p[v]")
    sh.run_ffmpeg(["-i", src, "-filter_complex", ";".join(fc), "-map", "[v]"] + (["-map", "[a]"] if m["a"] else [])
                  + [*enc(m), out], label=f"tua ({m['vdur']:.1f}s → {total:.1f}s)")
    o = sh.probe(out)
    if abs(o["vdur"] - total) > 0.15 or (o["a"] and abs(o["adur"] - o["vdur"]) > 0.15):
        die(f"thời lượng ra lệch: hình {o['vdur']:.2f}s, tiếng {o['adur']}s, mong {total:.2f}s")
    print(f"  ✔ {out.name}: {o['vdur']:.2f}s (gốc {m['vdur']:.2f}s)")


# ---------- doan-hay ----------
def cmd_doan_hay(args):
    import statistics
    src = Path(args.video).resolve()
    m = sh.probe(src)
    lo, hi = (float(x) for x in args.dai.split("-"))
    if m["dur"] < lo:
        die(f"video chỉ {m['dur']:.0f}s, ngắn hơn đoạn tối thiểu {lo:g}s.")
    print("Đo chuyển cảnh + tiếng…")
    # hai lượt riêng: in chung một luồng thì dòng của hình và tiếng chen lẫn nhau
    rv = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(src), "-map", "0:v:0",
                         "-vf", "scale=320:-2,scdet=threshold=100,metadata=print:file=-", "-f", "null", "-"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    ra = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(src), "-map", "0:a:0",
                         "-af", "aresample=8000,asetnsamples=800,astats=metadata=1:reset=1,"
                                "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-", "-f", "null", "-"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    scores, rms, cur_t = [], [], None
    for line in (rv + "\n" + ra).splitlines():
        mt = re.search(r"pts_time:([\d.]+)", line)
        if mt:
            cur_t = float(mt.group(1))
        if "lavfi.scd.score=" in line and cur_t is not None:
            scores.append((cur_t, float(line.split("=")[1])))
        elif "RMS_level=" in line and cur_t is not None:
            v = line.split("=")[1]
            rms.append((cur_t, -90.0 if v in ("-inf", "inf") else float(v)))
    if not rms:
        die("không đo được tiếng.")
    # chuyển cảnh: điểm thay đổi khung nổi hẳn so với cả video (video dựng hay dùng chuyển mờ → điểm thấp)
    sv = sorted(s for _, s in scores)
    thr = max(4.0, sv[int(len(sv) * 0.995)] if sv else 99)
    cuts = [t for t, s in scores if s >= thr]
    lv = [v for _, v in rms]
    med = statistics.median(lv)
    sd = statistics.pstdev(lv) or 1.0
    # khoảng ngắt lời: tiếng tụt dưới mức chung 8 dB ≥ 0,3 s (có nhạc nền vẫn bắt được — không dùng ngưỡng tuyệt đối)
    starts, ends, run0 = [], [], None
    for t, v in rms:
        if v < med - 8:
            run0 = t if run0 is None else run0
        else:
            if run0 is not None and t - run0 >= 0.3:
                starts.append(run0); ends.append(t)
            run0 = None
    anchors = sorted(set([0.0] + ends + cuts))
    print(f"  {len(cuts)} chỗ chuyển cảnh, {len(ends)} khoảng ngắt lời")

    def score(a, b):
        xs = [v for t, v in rms if a <= t < b]
        if not xs:
            return -99
        speech = sum(1 for v in xs if v > med - 10) / len(xs)        # ít khoảng chết
        loud = (statistics.mean(xs) - med) / sd                       # to hơn mặt bằng
        lively = statistics.pstdev(xs) / sd                           # lên xuống, có nhấn nhá
        ncut = sum(1 for c in cuts if a < c < b)
        return speech * 2 + loud + lively * 0.7 + min(ncut, 6) * 0.15

    cands = []
    for a in anchors:
        if a + lo > m["dur"]:
            break
        # kết thúc ở khoảng ngắt gần nhất trong [lo, hi], không có thì cắt cứng ở hi
        ok_end = [s for s in starts if a + lo <= s <= a + hi]
        b = max(ok_end) if ok_end else min(a + hi, m["dur"])
        cands.append((score(a, b), a, b))
    cands.sort(reverse=True)
    picked = []
    for sc, a, b in cands:
        if all(b <= pa or a >= pb for _, pa, pb in picked):
            picked.append((sc, a, b))
        if len(picked) >= args.so:
            break
    picked.sort(key=lambda x: x[1])
    res = [{"tu": round(a, 2), "den": round(b, 2), "dai": round(b - a, 1), "diem": round(sc, 2)} for sc, a, b in picked]
    if args.nghe:
        print("Chép lời từng đoạn (faster-whisper)…")
        venv = Path.home() / ".motion-studio/asr-venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        code = ("import sys,json,subprocess,numpy as np\nfrom faster_whisper import WhisperModel\n"
                "m=WhisperModel('small',device='cpu',compute_type='int8')\nout=[]\n"
                "for a,b in json.loads(sys.argv[2]):\n"
                " p=subprocess.run(['ffmpeg','-v','error','-ss',str(a),'-t',str(b-a),'-i',sys.argv[1],'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True).stdout\n"
                " s,_=m.transcribe(np.frombuffer(p,np.float32),language='vi')\n out.append(' '.join(x.text.strip() for x in s))\n"
                "print(json.dumps(out,ensure_ascii=False))")
        rr = subprocess.run([str(venv), "-X", "utf8", "-c", code, str(src), json.dumps([[x["tu"], x["den"]] for x in res])],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            for x, t in zip(res, json.loads(rr.stdout.strip().splitlines()[-1])):
                x["loi"] = t
        except (ValueError, IndexError):
            print("  (không chép được lời — cần môi trường ~/.motion-studio/asr-venv có faster-whisper)")
    jf = src.with_name(src.stem + ".doan-hay.json")
    jf.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for i, x in enumerate(res, 1):
        print(f"  #{i}  {x['tu']:7.1f}–{x['den']:7.1f}s ({x['dai']:.0f}s)  điểm {x['diem']:.2f}"
              + (f"\n      {x['loi'][:160]}" if x.get("loi") else ""))
    # ảnh: mỗi đoạn một hàng 3 khung
    ins, fc = [], []
    for i, x in enumerate(res):
        for j, f in enumerate((0.15, 0.5, 0.85)):
            ins += ["-ss", f"{x['tu'] + x['dai'] * f:.2f}", "-i", str(src)]
            fc.append(f"[{i * 3 + j}:v]scale=-2:300,setsar=1[k{i}_{j}]")
        fc.append(f"[k{i}_0][k{i}_1][k{i}_2]hstack=3[r{i}]")
    fc.append("".join(f"[r{i}]" for i in range(len(res))) + (f"vstack={len(res)}[o]" if len(res) > 1 else "null[o]"))
    jpg = src.with_name(src.stem + ".doan-hay.jpg")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *ins, "-filter_complex", ";".join(fc),
                    "-map", "[o]", "-frames:v", "1", "-q:v", "4", str(jpg)])
    print(f"→ {jf}\n🖼 {jpg}\nCắt đoạn đã chọn: ffmpeg -ss <đầu> -to <cuối> -i video … hoặc dung-video-quay.py chuan-bi --tu --den")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("b-roll", help="chèn cảnh minh hoạ, giữ lời liền mạch")
    p.add_argument("video")
    p.add_argument("--chen", action="append", required=True, help="file@đầu-cuối[+từ-giây], lặp lại được")
    p.add_argument("--tieng", choices=("goc", "tron"), default="goc")
    p = sub.add_parser("tua", help="tua nhanh/chậm từng đoạn")
    p.add_argument("video")
    p.add_argument("--doan", required=True, help="đầu-cuối:tốc-độ,… vd 0-4:1,4-9:2.5,9-11:0.5")
    p = sub.add_parser("doan-hay", help="gợi ý đoạn đáng cắt thành short")
    p.add_argument("video")
    p.add_argument("--so", type=int, default=5, help="số đoạn gợi ý (mặc định 5)")
    p.add_argument("--dai", default="30-60", help="độ dài đoạn, giây (mặc định 30-60)")
    p.add_argument("--nghe", action="store_true", help="chép lời từng đoạn để đọc nội dung")
    for name in ("b-roll", "tua"):
        sp = sub.choices[name]
        sp.add_argument("-o")
        sp.add_argument("--ghi-de", action="store_true")
        sp.add_argument("--khong-so-sanh", action="store_true")
    a = ap.parse_args()
    sh.need_ffmpeg()
    if not Path(a.video).exists():
        die(f"không thấy {a.video}")
    {"b-roll": cmd_b_roll, "tua": cmd_tua, "doan-hay": cmd_doan_hay}[a.cmd](a)


if __name__ == "__main__":
    main()
