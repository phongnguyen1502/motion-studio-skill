#!/usr/bin/env python3
"""Dựng video hoàn chỉnh từ kich-ban.json: cảnh (ảnh hoặc clip) + giọng + nhạc nền + tiếng động
+ tiêu đề + phụ đề kiểu TikTok. Chỉ dùng ffmpeg, không gọi AI → không tốn token.

Dùng: dung-video.py kich-ban.json [--out video.mp4] [--nhap]
  --nhap   bản xem nhanh (720p, nén nhanh) để duyệt trước khi xuất bản thật.
Cần giong/<id>.mp3 cho mọi cảnh có `loi` (chạy giong.py trước).
Độ dài mỗi cảnh = độ dài giọng + `dem` giây; cảnh không lời dùng `giay` (mặc định 3).
Ảnh tĩnh được zoom chậm (xen kẽ vào/ra); clip được cắt vừa hoặc lặp cho đủ.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chuyen_dong_va_am_luong import ken_burns, lufs  # noqa: E402
# Windows: màn hình/ống dẫn mặc định cp1252 → in tiếng Việt là UnicodeEncodeError (máy Windows thật 15/10/2026).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")  # tiến trình Python con cũng in UTF-8


SFX_DIR = os.path.expanduser("~/.claude/skills/media-use/audio/assets/sfx")
# Thư mục font cho phụ đề ASS — mỗi hệ điều hành một nơi.
FONT_DIR = next((d for d in ("/System/Library/Fonts/Supplemental",
                             os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
                             "/usr/share/fonts/truetype") if os.path.isdir(d)), "/System/Library/Fonts/Supplemental")


def loc_path(path):
    """Đường dẫn đặt trong -filter_complex. Windows: đổi \\ thành / và thoát HAI lớp dấu : của ổ đĩa
    (C\\\\:/...) — thiếu là ffmpeg báo "No option name near '/Windows/Fonts'" (máy Windows thật, 15/10/2026)."""
    return path.replace("\\", "/").replace(":", "\\\\:") if os.name == "nt" else path
VIDEO_EXT = (".mp4", ".mov", ".webm", ".mkv", ".m4v")
# Kiểu chuyển cảnh → (hiệu ứng xfade, giây). "cat" = cắt thẳng (1 khung hoà để giữ một đường nối).
CHUYEN = {"cat": ("fade", 0.04), "hoa": ("fade", 0.4), "den": ("fadeblack", 0.6), "trang": ("fadewhite", 0.5),
          "truot": ("smoothleft", 0.35), "truot-len": ("smoothup", 0.35), "zoom": ("zoomin", 0.4),
          "tron": ("circleopen", 0.5)}

ap = argparse.ArgumentParser()
ap.add_argument("plan")
ap.add_argument("--out", default=None)
ap.add_argument("--nhap", action="store_true")
a = ap.parse_args()

plan = json.load(open(a.plan, encoding="utf-8-sig"))
base = os.path.dirname(os.path.abspath(a.plan))
W, H = plan.get("khung", [1080, 1920])
if a.nhap:
    W, H = W * 2 // 3 // 2 * 2, H * 2 // 3 // 2 * 2
FPS, DEM, VAO, AR = 30, float(plan.get("dem", 0.35)), float(plan.get("vao", 0.3)), 48000
out = a.out or os.path.join(base, "video-nhap.mp4" if a.nhap else "video.mp4")
tmp = tempfile.mkdtemp(prefix="tao-video-")
X264 = ["-c:v", "libx264", "-preset", "ultrafast" if a.nhap else "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
# File trung gian (từng cảnh, bản nối) còn bị nén lại ở bước cuối → nén nhanh, chất lượng cao.
# Nén "medium" cả 3 lượt từng làm bản 1080p ~4 phút mất >15 phút (video "Con số trên tường" v1, 12/10/2026).
X264_TAM = ["-c:v", "libx264", "-preset", "ultrafast" if a.nhap else "veryfast", "-crf", "14", "-pix_fmt", "yuv420p"]


def p(path):
    return path if os.path.isabs(path) else os.path.join(base, path)


def run(cmd, nhan=None, dai=None):
    """Chạy ffmpeg; có `dai` (giây đầu ra) thì in tiến độ mỗi 10% để người dùng biết còn bao lâu."""
    if not dai:
        subprocess.run(["ffmpeg", "-v", "error", "-y", *cmd], check=True)
        return
    pr = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-progress", "pipe:1", "-nostats", *cmd],
                          stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    moc = -10
    for line in pr.stdout:
        if not line.startswith("out_time_us="):
            continue
        try:
            pct = min(int(int(line.split("=", 1)[1]) / 1e6 / dai * 100), 100)
        except ValueError:                          # ffmpeg báo N/A lúc mới mở
            continue
        if pct >= moc + 10:
            moc = pct - pct % 10
            print(f"  {nhan}: {moc}%", flush=True)
    if pr.wait():
        raise subprocess.CalledProcessError(pr.returncode, cmd)


def dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    return float(r.stdout.strip())


def sfx_path(name):
    """Tên trong kho media-use (vd 'whoosh-short') hoặc đường dẫn file riêng."""
    if not name:
        return None
    for cand in (p(name), os.path.join(SFX_DIR, name), os.path.join(SFX_DIR, name + ".mp3")):
        if os.path.isfile(cand):
            return cand
    # Kho tiếng động nằm ở skill media-use (Claude Code) — máy học viên thường không có. Thiếu thì
    # bỏ qua tiếng đó và dựng tiếp, đừng làm hỏng cả video vì một tiếng "whoosh".
    print(f"⚠️ Không thấy tiếng động '{name}' — bỏ qua (thả file mp3 cùng tên vào thư mục dự án để dùng)")
    return None


# Font serif CÓ ĐỦ DẤU TIẾNG VIỆT. Georgia thiếu ử ệ ả ể… (ra ô vuông "Th□ trang duy□", phát hiện 22/11/2026) → bỏ.
SERIF = ["C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/cambria.ttc",
         "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
         "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]


def the_chu(src, dst, dong, phu=None):
    """Thẻ tiêu đề/kết: lấy ảnh cảnh làm nền, phủ tối, chữ serif trắng ấm ở giữa (bỏ nền đen trơn).
    Chữ tự thu nhỏ (rồi tự xuống dòng) cho vừa 86% bề ngang — dòng dài từng tràn ra ngoài khung."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFont
    im = Image.open(src).convert("RGB").resize((W, H), Image.LANCZOS)
    im = ImageEnhance.Brightness(im).enhance(0.42)
    d = ImageDraw.Draw(im)
    fp = next((x for x in SERIF if os.path.exists(x)), None)
    if not fp:
        print("⚠️ Không thấy font serif có dấu tiếng Việt cho thẻ tiêu đề — chữ có thể lỗi dấu")
    font = lambda px: ImageFont.truetype(fp, int(px)) if fp else ImageFont.load_default()
    lines = [x for x in (dong if isinstance(dong, list) else [dong]) if x]
    maxw, size = W * 0.86, H * 0.085
    big = font(size)
    while size > H * 0.05 and max((d.textlength(x, font=big) for x in lines), default=0) > maxw:
        size *= 0.93
        big = font(size)
    if max((d.textlength(x, font=big) for x in lines), default=0) > maxw:   # vẫn dài: xuống dòng theo chữ
        wrapped = []
        for ln in lines:
            cur = ""
            for word in ln.split():
                test = (cur + " " + word).strip()
                if cur and d.textlength(test, font=big) > maxw:
                    wrapped.append(cur)
                    cur = word
                else:
                    cur = test
            wrapped.append(cur)
        lines = wrapped
    small = font(min(H * 0.034, size * 0.45))
    lead = size * 1.24
    y = int(H * 0.5 - (len(lines) * lead) / 2 - (H * 0.03 if phu else 0))
    for ln in lines:
        w = d.textlength(ln, font=big)
        d.text(((W - w) / 2 + 3, y + 3), ln, font=big, fill=(0, 0, 0))
        d.text(((W - w) / 2, y), ln, font=big, fill=(255, 241, 214))
        y += int(lead)
    if phu:
        d.line([(W * 0.42, y + H * 0.01), (W * 0.58, y + H * 0.01)], fill=(255, 241, 214), width=2)
        w = d.textlength(phu, font=small)
        d.text(((W - w) / 2, y + H * 0.035), phu, font=small, fill=(235, 222, 200))
    im.save(dst)


for key, pos in (("the_dau", 0), ("the_ket", None)):
    cfg = plan.get(key)
    if not cfg:
        continue
    png = os.path.join(tmp_cards := tempfile.mkdtemp(prefix="the-"), f"{key}.png")
    nen = p(cfg.get("hinh") or plan["canh"][0 if pos == 0 else -1]["hinh"])
    the_chu(nen, png, cfg.get("dong") or cfg.get("tieu_de") or plan.get("tieu_de", ""), cfg.get("phu"))
    sc = {"id": "_" + key, "hinh": png, "giay": float(cfg.get("giay", 5 if pos == 0 else 7)),
          "chuyen_dong": "vao", "chuyen": cfg.get("chuyen", "hoa")}
    if pos == 0:
        plan["canh"].insert(0, sc)
    else:
        plan["canh"].append(sc)
    if key == "the_dau":
        plan.pop("tieu_de", None)                  # đã có thẻ, khỏi chồng chữ tiêu đề lên cảnh 1


# 1) Dựng từng cảnh thành đoạn mp4 cùng khung / fps / âm thanh.
cover = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1"
segs, starts, t, viec = [], [], 0.0, []


def lam_canh(i, src, motion, kieu, d, vin, vf, ain, amap, af, seg):
    # Ken Burns (Pillow) mất ~0,1s/khung 1080p → chạy tuần tự 17 cảnh từng mất >10 phút. Pillow nhả GIL lúc
    # resize, ffmpeg là tiến trình riêng → chạy song song bằng luồng là đủ, không cần multiprocessing.
    if motion:
        ken_burns(src, motion, kieu, i, W, H, int(d * FPS) + 1, FPS)
    run([*vin, *ain, "-t", f"{d:.3f}", "-vf", vf, "-map", "0:v", "-map", amap,
         "-af", f"aformat=channel_layouts=stereo,{af},aresample={AR}", "-ar", str(AR),
         *X264_TAM, "-c:a", "aac", "-b:a", "192k", seg])


for i, c in enumerate(plan["canh"]):
    src = p(c["hinh"])
    voice = os.path.join(base, "giong", f"{c['id']}.mp3") if c.get("loi") else None
    if voice and not os.path.exists(voice):
        raise SystemExit(f"Thiếu giọng cảnh {c['id']} — chạy giong.py trước")
    is_vid = src.lower().endswith(VIDEO_EXT)
    vdur = dur(voice) if voice else 0.0
    # Chuyển cảnh VÀO cảnh này: chồng lên đuôi cảnh trước `od` giây (đuôi đó là phần nghỉ sau lời).
    kind, od = CHUYEN.get(c.get("chuyen", plan.get("chuyen_mac_dinh", "hoa")), CHUYEN["hoa"])
    od = 0.0 if i == 0 else min(od, segs[-1][1] / 2)
    # Giọng vào trễ một nhịp: không đập ngay lúc hình đang chuyển (bài học "lệch giọng" 10/2026).
    lead = max(VAO, od * 0.75) if voice else 0.0
    d = max(lead + vdur + DEM, float(c.get("giay", 0))) if voice else float(c.get("giay", dur(src) if is_vid else 3))
    od = min(od, d / 2)
    c["_vdur"], c["_lead"] = vdur, lead
    seg = os.path.join(tmp, f"{i:03d}.mp4")
    if is_vid:
        motion, vin = None, ["-stream_loop", "-1", "-i", src]
        vf = f"{cover},fps={FPS}"
    else:                                           # ảnh: dựng chuyển động trước, rồi ghép tiếng
        motion = os.path.join(tmp, f"{i:03d}-hinh.mp4")
        vin, vf = ["-i", motion], "setsar=1"
    if voice:
        ms = int(lead * 1000)
        ain, amap, af = ["-i", voice], "1:a", f"adelay={ms}|{ms},apad"
    elif is_vid and c.get("giu_tieng"):            # giữ tiếng gốc của clip (vd clip Muse có thoại)
        ain, amap, af = [], "0:a", "apad"
    else:
        ain, amap, af = ["-f", "lavfi", "-i", f"anullsrc=r={AR}:cl=stereo"], "1:a", "apad"
    viec.append((i, src, motion, c.get("chuyen_dong"), d, vin, vf, ain, amap, af, seg))
    t -= od
    segs.append((seg, d, kind, od))
    starts.append(t)
    t += d
total = t
with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4) // 2)) as pool:
    cho = [pool.submit(lam_canh, *v) for v in viec]
    for k, f in enumerate(as_completed(cho), 1):
        f.result()                                  # cảnh hỏng thì dừng luôn, báo lỗi thật
        print(f"Bước 1/3 · dựng cảnh: {k}/{len(viec)} ({k * 100 // len(viec)}%)", flush=True)

# Nối các cảnh bằng xfade (hình) + acrossfade (tiếng), mỗi chỗ nối một kiểu riêng.
joined = os.path.join(tmp, "joined.mp4")
ins = sum((["-i", s[0]] for s in segs), [])
fil, v, au, acc = [], "[0:v]", "[0:a]", segs[0][1]
for j, (_, d, kind, od) in enumerate(segs[1:], 1):
    acc -= od
    fil.append(f"{v}[{j}:v]xfade=transition={kind}:duration={od:.3f}:offset={acc:.3f}[v{j}]")
    fil.append(f"{au}[{j}:a]acrossfade=d={od:.3f}[a{j}]")
    v, au, acc = f"[v{j}]", f"[a{j}]", acc + d
if fil:
    run([*ins, "-filter_complex", ";".join(fil), "-map", v, "-map", au, *X264_TAM, "-c:a", "aac", "-b:a", "192k",
         "-ar", str(AR), joined], "Bước 2/3 · nối cảnh", total)
else:
    joined = segs[0][0]


# 2) Phụ đề + tiêu đề dạng ASS (cụm 2–4 chữ, nảy nhẹ, như TikTok).
def ts(x):
    return f"{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}"


def chunks(text, n):
    words, out_, cur = text.split(), [], []
    for w in words:
        cur.append(w)
        if len(cur) >= n or w[-1] in ",.!?…:;":
            out_.append(" ".join(cur))
            cur = []
    return out_ + ([" ".join(cur)] if cur else [])


pd = plan.get("phu_de", {})
NGANG = W > H
# Bug cũ: k = W/1080 → khổ ngang 1920 cho k=1,78 → chữ 150px trên khung cao 1080 (~14%). Nay theo cạnh ngắn.
k = min(W, H) / 1080
CO = pd.get("co", 50 if NGANG else 84)
CAO = pd.get("cao", 0.07 if NGANG else 0.27)
VIEN = 3 if NGANG else 7
ass = [
    "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
    "[V4+ Styles]",
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
    "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    f"Style: Cap,{pd.get('font', 'Arial')},{int(CO * k)},{pd.get('mau', '&H00FFFFFF')},&H00FFFFFF,"
    f"&H00000000,&H80000000,{0 if NGANG else -1},0,0,0,100,100,0,0,1,{VIEN * k:.1f},{1.5 * k:.1f},2,{int(70 * k)},{int(70 * k)},{int(H * CAO)},1",
    f"Style: Title,{pd.get('font', 'Arial')},{int(92 * k)},&H0000E5FF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,"
    f"100,100,0,0,3,{int(18 * k)},0,8,{int(80 * k)},{int(80 * k)},{int(H * 0.11)},1",
    "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
]
if plan.get("tieu_de"):
    ass.append(f"Dialogue: 1,{ts(0)},{ts(float(plan.get('tieu_de_giay', 3)))},Title,,0,0,0,,"
               f"{{\\fad(200,300)}}{plan['tieu_de']}")
if pd.get("bat", True):
    for c, st in zip(plan["canh"], starts):
        if not c.get("loi"):
            continue
        parts = chunks(c["loi"], int(pd.get("so_chu", 4)))
        weights = [len(x) + 2 for x in parts]
        span, cur = max(c["_vdur"] - 0.1, 0.5), st + c["_lead"] + 0.05
        for txt, w in zip(parts, weights):
            nxt = cur + span * w / sum(weights)
            txt = txt.upper() if pd.get("chu_hoa") else txt
            ass.append(f"Dialogue: 0,{ts(cur)},{ts(nxt)},Cap,,0,0,0,,"
                       f"{{\\fscx85\\fscy85\\t(0,90,\\fscx100\\fscy100)}}{txt}")
            cur = nxt
if pd.get("srt", True):
    def sts(x):
        return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(x % 1 * 1000):03d}"
    srt, n = [], 0
    for c, st in zip(plan["canh"], starts):
        if c.get("loi"):
            n += 1
            a0 = st + c["_lead"]
            srt.append(f"{n}\n{sts(a0)} --> {sts(a0 + c['_vdur'])}\n{c['loi']}\n")
    open(os.path.splitext(out)[0] + ".srt", "w", encoding="utf-8").write("\n".join(srt))
# Mốc từng cảnh trong video ra — cho trang-duyet.py (chỉ ghi thêm file, không ảnh hưởng việc dựng)
open(os.path.splitext(out)[0] + ".moc.json", "w", encoding="utf-8").write(json.dumps(
    [{"id": c["id"], "tu": round(max(st, 0), 3), "den": round(st + sg[1], 3), "loi": c.get("loi", ""),
      "loi_tu": round(st + c["_lead"], 3) if c.get("loi") else None, "hinh": c.get("hinh")}
     for c, st, sg in zip(plan["canh"], starts, segs)], ensure_ascii=False, indent=1))
ass_path = os.path.join(tmp, "sub.ass")
open(ass_path, "w", encoding="utf-8").write("\n".join(ass) + "\n")

# 3) Trộn âm: giọng (chuẩn hoá RIÊNG nhánh giọng) + nhạc nền (đo LUFS rồi đưa về mức đích, tự hạ khi
#    có giọng) + tiếng động. Không loudnorm cả bản trộn: nhạc sẽ bị kéo to lên theo.
VOICE = f"[0:a]loudnorm=I=-15:TP=-1.5:LRA=11,aresample={AR}"
ins, fil, mix = ["-i", joined], [f"{VOICE},asplit=2[voice][sc]"], ["[voice]"]
NHAC = plan.get("nhac")
if isinstance(NHAC, list) and len(NHAC) >= 2:
    # 2 bài nhạc nối nhau (crossfade 4s), mỗi bài đưa về cùng mức LUFS trước khi nối.
    d1 = total * 0.5 + 2
    mix_path = os.path.join(tmp, "nhac-ghep.m4a")
    ga = float(plan.get("nhac_lufs", -30)) - lufs(p(NHAC[0]))
    gb = float(plan.get("nhac_lufs", -30)) - lufs(p(NHAC[1]))
    run(["-stream_loop", "-1", "-i", p(NHAC[0]), "-stream_loop", "-1", "-i", p(NHAC[1]), "-filter_complex",
         f"[0:a]aresample={AR},volume={ga:.1f}dB,atrim=0:{d1:.2f},asetpts=PTS-STARTPTS[a];"
         f"[1:a]aresample={AR},volume={gb:.1f}dB,atrim=0:{total - d1 + 4:.2f},asetpts=PTS-STARTPTS[b];"
         f"[a][b]acrossfade=d=4[m]", "-map", "[m]", "-c:a", "aac", "-b:a", "192k", mix_path])
    NHAC = mix_path
    plan["nhac"] = mix_path
elif isinstance(NHAC, list):
    plan["nhac"] = NHAC[0]
if plan.get("nhac"):
    ins += ["-stream_loop", "-1", "-i", p(plan["nhac"])]
    fade = max(total - 1.5, 0)
    # Hai bài nhạc có thể lệch nhau 12 LU → đo từng bài, không đặt cứng số dB.
    gain = float(plan.get("nhac_lufs", -30)) - lufs(p(plan["nhac"]))
    fil.append(f"[1:a]aresample={AR},volume={gain:.1f}dB,atrim=0:{total:.3f},"
               f"afade=t=out:st={fade:.3f}:d=1.5[bg];[bg][sc]sidechaincompress=threshold=0.05:ratio=4:"
               f"attack=30:release=400[duck]")
    mix.append("[duck]")
else:
    fil[0] = f"{VOICE}[voice]"
default_sfx = plan.get("sfx_chuyen_canh")
for i, (c, st) in enumerate(zip(plan["canh"], starts)):
    s = sfx_path(c.get("sfx") or (default_sfx if i > 0 else plan.get("sfx_mo_dau")))
    if not s:
        continue
    idx = ins.count("-i")                        # chỉ số input ffmpeg của file sắp thêm
    ins += ["-i", s]
    ms = int(max(st - 0.15, 0) * 1000)
    fil.append(f"[{idx}:a]aresample={AR},volume={plan.get('sfx_db', -14)}dB,adelay={ms}|{ms}[s{i}]")
    mix.append(f"[s{i}]")
fil.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,"
           f"alimiter=limit=0.95,aresample={AR}[aout]")
fil.append(f"[0:v]ass={loc_path(ass_path)}:fontsdir={loc_path(FONT_DIR)}[vout]")
run([*ins, "-filter_complex", ";".join(fil), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
     *X264, "-c:a", "aac", "-b:a", "192k", "-ar", str(AR), "-movflags", "+faststart", out],
    "Bước 3/3 · trộn tiếng + phụ đề", total)
print(f"XONG {out}  ({total:.1f}s, {len(segs)} cảnh, {W}x{H})")
