#!/usr/bin/env python3
"""[tao-video · kiểu "clip có giọng sẵn"] Ghép clip Flow/Veo (đã có giọng) thành video: cắt theo mốc giọng, chuyển cảnh theo từng cặp, phụ đề tiếng Việt,
logo góc, thẻ kết (clip dựng sẵn), tiếng "ting", nền âm thanh liên tục.

Dùng: dung-clip-co-giong.py kich-ban.json [--out video.mp4] [--phu-de hyperframes|anh]
  --phu-de hyperframes (mặc định): phụ đề + logo là LỚP ĐỘNG dựng bằng HyperFrames (chữ bật từng từ, chữ {Y:...} to nảy), xuất WebM nền trong suốt
  --phu-de anh: phụ đề tĩnh vẽ bằng Pillow (dự phòng khi không có node/HyperFrames)
kich-ban.json:
  size · logo (png) · delogo [x,y,w,h] xoá dấu ✦ của Flow · ambient_db (nền âm thanh tiệm, mặc định -36)
  the_ket {clip: mp4 dựng sẵn, vd HyperFrames}
  shots[]: clip, cut_start, cut_len, next {tr, d} (chuyển sang cảnh sau: kiểu xfade + độ dài giây),
           sub[{t:[bắt đầu, kết thúc] (giây trong CLIP gốc), text}] (text có {y:chữ} = tô vàng)
  sfx[]: {shot, at (giây trong đoạn đã cắt), db}
Quy ước chuyển cảnh: hai cảnh NỐI KHUNG (cảnh sau bắt đầu từ khung cuối cảnh trước) → hoà rất ngắn (0.15–0.2s) gần như vô hình;
cảnh độc lập → hoà 0.4–0.5s; toàn cảnh → cận cảnh → "zoomin".
"""
import argparse, json, os, re, subprocess
from PIL import Image, ImageDraw, ImageFont
import sys
# Windows: màn hình/ống dẫn mặc định cp1252 → in tiếng Việt là UnicodeEncodeError (máy Windows thật 15/10/2026).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")  # tiến trình Python con cũng in UTF-8


ap = argparse.ArgumentParser()
ap.add_argument("plan")
ap.add_argument("--out", default="video.mp4")
ap.add_argument("--phu-de", dest="phu_de", choices=["hyperframes", "anh"], default="hyperframes")
a = ap.parse_args()
plan = json.load(open(a.plan, encoding="utf-8-sig"))
base = os.path.dirname(os.path.abspath(a.plan))
W, H = plan.get("size", [720, 1280])
work = os.path.join(base, "dung")
os.makedirs(work, exist_ok=True)
# Mỗi clip Flow/Veo có độ to và nền ồn riêng (đo 15/10/2026: tổng −20.9…−24.2 LUFS, đỉnh −2.7…−11.6 dB, nền −88…−42 dB) → chỗ nối nghe "nhảy".
# Khử ồn nhẹ + đưa từng clip về cùng độ to TRƯỚC khi nối, rồi mới loudnorm cả bản.
AUDIO_MATCH = "highpass=f=70,afftdn=nf=-35,loudnorm=I=-20:TP=-3:LRA=8,aresample=44100"
HF_VER = "0.8.77"  # ghim phiên bản HyperFrames, cùng ak:hyperframes/references/render-workflow.md
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
# Font đủ dấu tiếng Việt (Arial Rounded Bold thiếu ơ, ấ, ạ...). Tahoma Bold có ở cả macOS lẫn Windows, khác đường dẫn.
FONT = next((f for f in ("/System/Library/Fonts/Supplemental/Tahoma Bold.ttf", r"C:\Windows\Fonts\tahomabd.ttf",
                         "/System/Library/Fonts/Supplemental/Arial Bold.ttf", r"C:\Windows\Fonts\arialbd.ttf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if os.path.exists(f)),
            "/System/Library/Fonts/Supplemental/Tahoma Bold.ttf")
if a.phu_de == "hyperframes" and not __import__("shutil").which("npx"):
    # Máy học viên hay chưa có Node: thà ra phụ đề tĩnh còn hơn chết giữa chừng sau khi đã cắt xong mọi đoạn.
    print("⚠️ Không thấy npx (Node.js) → dùng phụ đề tĩnh (--phu-de anh). Cài Node 22+ để có phụ đề động HyperFrames.")
    a.phu_de = "anh"


def run(cmd):
    subprocess.run(cmd, check=True)


def probe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    return float(r.stdout.strip())


def wrap(text, fonts, draw, max_w):
    """Markup: {y:chữ} vàng · {Y:CHỮ} vàng và TO (nhấn chốt hài). words = (chữ, màu, to?)."""
    words = []
    for part in re.split(r"(\{[yY]:.*?\})", text):
        if part.startswith("{y:") or part.startswith("{Y:"):
            big = part[1] == "Y"
            words += [(w, (255, 214, 10), big) for w in part[3:-1].split()]
        else:
            toks = [(w, None, False) for w in part.split()]
            if toks and words and not part[:1].isspace():  # dấu câu dính liền chữ trước ("nhân}," → "nhân,")
                words[-1] = (words[-1][0] + toks[0][0], words[-1][1], words[-1][2])
                toks = toks[1:]
            words += toks
    lines, cur = [], []

    def width(ws):
        return sum(draw.textlength(w + " ", font=fonts[1] if big else fonts[0]) for w, _, big in ws)

    for w in words:
        if cur and width(cur + [w]) > max_w:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def sub_png(text, dst, scale=1.0):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    size = int(50 * scale)
    fonts = (ImageFont.truetype(FONT, size), ImageFont.truetype(FONT, int(size * 1.4)))
    lines = wrap(text, fonts, d, W - 90)
    heights = [fonts[1].size * 1.18 if any(b for _, _, b in ln) else fonts[0].size * 1.18 for ln in lines]
    y = int(H * 0.76 - sum(heights) / 2)
    for ln, hgt in zip(lines, heights):
        tw = sum(d.textlength(w + " ", font=fonts[1] if big else fonts[0]) for w, _, big in ln)
        x = (W - tw) / 2
        base_y = y + hgt * 0.82
        for w, col, big in ln:
            f = fonts[1] if big else fonts[0]
            d.text((x, base_y), w, font=f, fill=col or (255, 255, 255), stroke_width=8 if big else 7,
                   stroke_fill=(0, 0, 0), anchor="ls")
            x += d.textlength(w + " ", font=f)
        y += hgt
    img.save(dst)


def logo_png(dst, size):
    src = Image.open(os.path.join(base, plan["logo"])).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(src, (0, 0), mask)
    out.save(dst)


# 1) Cắt từng đoạn (xoá ✦ Flow, chuẩn kích thước/fps/âm thanh)
cuts, lens, trans = [], [], []
dl = plan.get("delogo")
for s in plan["shots"]:
    out = os.path.join(work, f"cut-{s['id']}.mp4")
    vf = (f"delogo=x={dl[0]}:y={dl[1]}:w={dl[2]}:h={dl[3]}," if dl else "") + f"scale={W}:{H},fps=24,setsar=1"
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["cut_start"]), "-t", str(s["cut_len"]), "-i", s["clip"],
         "-vf", vf, "-af", AUDIO_MATCH, "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", "-ac", "2", out])
    cuts.append(out)
    lens.append(float(s["cut_len"]))
    nx = s.get("next", {})
    trans.append((nx.get("tr", "fade"), float(nx.get("d", 0.4))))

# thẻ kết: clip dựng sẵn (HyperFrames) + âm thanh im lặng
end_src = os.path.join(base, plan["the_ket"]["clip"])
end_len = probe_dur(end_src)
end_mp4 = os.path.join(work, "the-ket.mp4")
run(["ffmpeg", "-v", "error", "-y", "-i", end_src, "-f", "lavfi", "-t", str(end_len), "-i", "anullsrc=r=44100:cl=stereo",
     "-vf", f"scale={W}:{H},fps=24,setsar=1", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
     "-c:a", "aac", "-shortest", end_mp4])
cuts.append(end_mp4)
lens.append(end_len)

n = len(cuts)
Ds = [t[1] for t in trans]  # Ds[i] = chuyển giữa cảnh i và i+1 (cảnh cuối → thẻ kết nằm ở trans cuối)
starts = [sum(lens[:i]) - sum(Ds[:i]) for i in range(n)]
total = sum(lens) - sum(Ds)
end_start = starts[-1]

# 2) Phụ đề + logo + sfx + nền âm thanh
inputs = []
for c in cuts:
    inputs += ["-i", c]
lg = os.path.join(work, "logo.png")
overlays, cues = [], []
if a.phu_de == "anh":
    logo_png(lg, 92)
    inputs += ["-i", lg]
    logo_idx = n
    idx = n + 1
else:  # lớp HyperFrames được render rồi nạp ở dưới; giữ chỗ chỉ số n cho nó
    idx = n + 1
for si, s in enumerate(plan["shots"]):
    for j, sb in enumerate(s.get("sub", [])):
        t0 = starts[si] + max(0.0, sb["t"][0] - s["cut_start"] - 0.05)
        t1 = starts[si] + min(float(s["cut_len"]), sb["t"][1] - s["cut_start"] + 0.3)
        cues.append({"t0": round(t0, 3), "t1": round(t1, 3), "text": sb["text"]})
        if a.phu_de != "anh":
            continue
        p = os.path.join(work, f"sub-{s['id']}-{j}.png")
        sub_png(sb["text"], p)
        inputs += ["-i", p]
        if sb.get("pop"):  # chữ bật to 0.14s đầu rồi về cỡ thường: nhấn cú chốt
            pp = os.path.join(work, f"sub-{s['id']}-{j}-pop.png")
            sub_png(sb["text"], pp, scale=1.14)
            inputs += ["-i", pp]
            overlays.append((idx, t0 + 0.14, t1))   # bản cỡ thường (input vừa thêm trước đó)
            overlays.append((idx + 1, t0, t0 + 0.14))  # bản bật to
            idx += 2
        else:
            overlays.append((idx, t0, t1))
            idx += 1
layer = os.path.join(work, "phu-de-layer.webm")
if a.phu_de == "hyperframes":
    import shutil
    proj = os.path.join(work, "hf-phu-de")
    shutil.rmtree(proj, ignore_errors=True)
    shutil.copytree(os.path.join(ASSETS, "phu-de-hyperframes"), proj)
    os.makedirs(os.path.join(proj, "assets"), exist_ok=True)
    shutil.copy(os.path.join(base, plan["logo"]), os.path.join(proj, "assets", "logo.png"))
    html = open(os.path.join(proj, "index.html"), encoding="utf-8").read()
    for k, v in {"__W__": str(W), "__H__": str(H), "__DURATION__": f"{total:.2f}", "__LOGO_END__": f"{end_start + 0.1:.2f}",
                 "__CUES__": json.dumps(cues, ensure_ascii=False)}.items():
        html = html.replace(k, v)
    open(os.path.join(proj, "index.html"), "w", encoding="utf-8").write(html)
    run(["npx", "-y", f"hyperframes@{HF_VER}", "render", proj, "--format", "webm", "--fps", "24", "--output", layer, "--quiet"])
    inputs += ["-c:v", "libvpx-vp9", "-i", layer]  # decoder libvpx giữ kênh alpha (decoder mặc định làm mất)
sfx = []
for e in plan.get("sfx", []):
    p = os.path.join(work, f"sfx-{len(sfx)}.wav")
    if e.get("kind") == "pop":  # tiếng "bụp" quét tần số lên: nhấn đúng chữ chốt hài
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "aevalsrc='sin(2*PI*(380+4200*t)*t)*exp(-t*16)':d=0.25:s=44100",
             "-af", "aformat=sample_rates=44100:channel_layouts=stereo", p])
    else:  # "ting" mặc định
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=1568:d=0.5",
             "-af", "afade=t=out:st=0.05:d=0.45,aformat=sample_rates=44100:channel_layouts=stereo", p])
    inputs += ["-i", p]
    sfx.append((idx, starts[e["shot"] - 1] + e["at"], e.get("db", -14)))
    idx += 1
amb = os.path.join(work, "ambient.wav")  # tiếng ồn nâu lọc thấp: che chỗ im lặng tuyệt đối giữa các clip
run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"anoisesrc=color=brown:amplitude=0.5:d={total + 1:.2f}:r=44100",
     "-af", "lowpass=f=700,highpass=f=60,aformat=channel_layouts=stereo", amb])
inputs += ["-i", amb]
amb_idx = idx

fc = []
vprev, aprev, acc = "0:v", "0:a", lens[0]
for i in range(1, n):
    tr, d = trans[i - 1]
    off = acc - sum(Ds[:i])
    fc.append(f"[{vprev}][{i}:v]xfade=transition={tr}:duration={d}:offset={off:.3f}[vx{i}]")
    fc.append(f"[{aprev}][{i}:a]acrossfade=d={d}[ax{i}]")
    vprev, aprev, acc = f"vx{i}", f"ax{i}", acc + lens[i]
if a.phu_de == "anh":
    fc.append(f"[{vprev}][{logo_idx}:v]overlay=22:22:enable='lt(t,{end_start + 0.1:.3f})'[o0]")
else:
    fc.append(f"[{vprev}][{n}:v]overlay=0:0:format=auto[o0]")
cur = "o0"
for m, (ix, t0, t1) in enumerate(overlays, 1):
    fc.append(f"[{cur}][{ix}:v]overlay=0:0:enable='between(t,{t0:.3f},{t1:.3f})'[o{m}]")
    cur = f"o{m}"
amix_in = [f"[{aprev}]"]
for m, (ix, t, db) in enumerate(sfx):
    fc.append(f"[{ix}:a]adelay={int(t * 1000)}|{int(t * 1000)},volume={db}dB[s{m}]")
    amix_in.append(f"[s{m}]")
fc.append(f"[{amb_idx}:a]volume={plan.get('ambient_db', -36)}dB,afade=t=in:st=0:d=0.8,afade=t=out:st={total - 0.8:.2f}:d=0.8[ambf]")
amix_in.append("[ambf]")
fc.append(f"{''.join(amix_in)}amix=inputs={len(amix_in)}:normalize=0:duration=first[amx]")
fc.append("[amx]loudnorm=I=-16:TP=-1.5:LRA=11[aout]")

final = os.path.join(base, a.out)
run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", f"[{cur}]", "-map", "[aout]",
     "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", final])
print(f"xong: {final} ({total:.1f}s, {len(cues)} phụ đề, {len(sfx)} sfx)")
