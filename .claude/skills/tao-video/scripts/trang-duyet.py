#!/usr/bin/env python3
"""[tao-video · duyệt] Trang HTML để người dùng xem video và góp ý từng cảnh / từng câu, rồi dán góp ý lại cho Claude.

  python trang-duyet.py <du-an> [--video video.mp4] [--mo]
      → du-an/duyet/index.html (+ duyet/anh/*.jpg). Mở bằng Chrome/Edge, không cần mạng, không tải gì lên đâu.

Trang đọc thẳng file của dự án — không có định dạng dự án riêng:
  • video quay sẵn:  timing.json (câu), fx-plan.json (hiệu ứng), cut.json + cat.txt (chỗ đã cắt), goc.json (góc máy)
  • video kịch bản:  kich-ban.json (cảnh, lời, mô tả hình) + video.moc.json (mốc cảnh, dung-video.py ghi ra);
                     thiếu mốc thì ước từ video.srt
Người dùng bấm một cảnh/câu/hiệu ứng → nhảy tới đó trong video → ghi "cần sửa gì" (có nút ghi nhanh) → trang gom thành
một đoạn lệnh, bấm "Sao chép" rồi dán cho Claude, hoặc "Tải gop-y.json" lưu vào thư mục dự án để Claude đọc.
Góp ý được nhớ trong trình duyệt (mở lại trang vẫn còn). Có khung vùng an toàn TikTok/Reels để thấy chữ bị nút che.
"""
import argparse, json, os, re, subprocess, sys, webbrowser
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")


def die(msg):
    sys.exit("LỖI: " + msg)


def rj(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def probe(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                          "-of", "json", str(p)], capture_output=True, text=True, encoding="utf-8")
    j = json.loads(out.stdout or "{}")
    v = next((s for s in j.get("streams", []) if s["codec_type"] == "video"), {})
    return float(j.get("format", {}).get("duration", 0)), v.get("width", 1080), v.get("height", 1920)


def to_out(t, rs):
    acc = 0.0
    for a, b in rs:
        if t < a:
            return acc
        if t <= b:
            return acc + t - a
        acc += b - a
    return acc


def srt_times(p):
    out = []
    for m in re.finditer(r"(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)\s*\n(.+?)(?:\n\n|\Z)",
                         Path(p).read_text(encoding="utf-8-sig"), re.S):
        g = [int(x) for x in m.groups()[:8]]
        out.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000,
                    m.group(9).strip()))
    return out


def fx_text(f):
    p = f.get("params") or {}
    bits = []
    for k in ("text", "label", "value", "unit", "quote", "items", "title"):
        if k in p:
            v = p[k]
            bits.append(" · ".join(map(str, v)) if isinstance(v, list) else str(v))
    return (" — ".join(bits)).replace("\n", " ").replace("*", "")[:140]


# ---------- gom dữ liệu ----------
def project_quay(du, dur):
    items, notes = [], []
    rs = None
    if (du / "cut.json").exists():
        cj = rj(du / "cut.json")
        rs = cj.get("ranges")
        cut_d = cj.get("duration")
        if (du / "tail.mp4").exists() and cut_d and dur - cut_d > 0.2:
            items.append({"kind": "cau", "label": "Đoạn cuối giữ nguyên", "tu": round(cut_d, 2), "den": round(dur, 2),
                          "text": "(thẻ kết / phần sau --den, không cắt, không phụ đề)"})
    for l in rj(du / "timing.json"):
        items.append({"kind": "cau", "label": f"Câu {l['i'] + 1}", "tu": l["start"], "den": l["end"], "text": l["text"]})
    if (du / "fx-plan.json").exists():
        for i, f in enumerate(rj(du / "fx-plan.json").get("fx", [])):
            items.append({"kind": "fx", "label": f"Hiệu ứng {i + 1}: {f.get('type')}", "tu": max(0, f.get("start", 0)),
                          "den": f.get("end", 0), "text": fx_text(f), "fx": f.get("type")})
    if (du / "goc.json").exists() and rs:
        g = rj(du / "goc.json")
        for i, s in enumerate(g.get("chuyen", [])):
            a, b = to_out(s["tu"], rs), to_out(s["den"], rs)
            if b - a > 0.05:
                cam = Path(g["may"][s["may"]]["file"]).stem
                items.append({"kind": "goc", "label": f"Góc {s['may']} · {cam}", "tu": round(a, 2), "den": round(b, 2),
                              "text": s.get("loi", ""), "may": s["may"]})
    if (du / "cat.txt").exists():
        notes.append(("Chỗ máy đã cắt (giây trên video gốc)", (du / "cat.txt").read_text(encoding="utf-8")))
    return items, notes


def project_kich_ban(du, video, dur):
    kb = rj(du / "kich-ban.json")
    canh = kb.get("canh", [])
    moc_f = video.with_suffix(".moc.json")
    items, notes = [], []
    if moc_f.exists():
        moc = rj(moc_f)
        by = {m["id"]: m for m in moc}
        for m in moc:
            c = next((x for x in canh if x.get("id") == m["id"]), {})
            lab = {"_the_dau": "Thẻ đầu", "_the_ket": "Thẻ kết"}.get(m["id"], f"Cảnh {m['id']}")
            items.append({"kind": "canh", "label": lab, "tu": m["tu"], "den": min(m["den"], dur), "text": m.get("loi") or "",
                          "mo_ta": c.get("mo_ta_hinh", ""), "hinh": c.get("hinh") or "", "id": m["id"]})
        del by
    else:
        srt = srt_times(video.with_suffix(".srt")) if video.with_suffix(".srt").exists() else []
        notes.append(("Lưu ý", "Chưa có video.moc.json (video dựng bằng bản cũ) → mốc cảnh ước từ phụ đề, có thể lệch "
                               "vài giây. Dựng lại bằng dung-video.py để có mốc đúng."))
        k = 0
        prev_end = 0.0
        for i, c in enumerate(canh):
            if c.get("loi") and k < len(srt):
                a, b, _ = srt[k]
                k += 1
                tu, den = max(prev_end, a - 0.4), b + 0.35
            else:
                tu, den = prev_end, prev_end + float(c.get("giay", 3))
            items.append({"kind": "canh", "label": f"Cảnh {c.get('id', i + 1)}", "tu": round(tu, 2),
                          "den": round(min(den, dur), 2), "text": c.get("loi", ""), "mo_ta": c.get("mo_ta_hinh", ""),
                          "hinh": c.get("hinh") or "", "id": c.get("id")})
            prev_end = den
    return items, notes


def thumbs(video, items, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("*.jpg"):
        old.unlink()
    for i, it in enumerate(items):
        if it["kind"] == "fx":
            t = it["tu"] + min(1.2, (it["den"] - it["tu"]) * 0.6)    # hiệu ứng đã hiện hẳn
        else:
            t = (it["tu"] + it["den"]) / 2
        f = outdir / f"{i:03d}.jpg"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{max(0, t):.2f}", "-i", str(video),
                        "-frames:v", "1", "-vf", "scale=-2:220", "-q:v", "5", str(f)])
        if f.exists():
            it["anh"] = f"anh/{f.name}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("du_an")
    ap.add_argument("--video", help="video cần duyệt (mặc định du-an/video.mp4, không có thì video-nhap.mp4)")
    ap.add_argument("--mo", action="store_true", help="mở trang trong trình duyệt mặc định")
    a = ap.parse_args()
    du = Path(a.du_an).resolve()
    if not du.is_dir():
        die(f"không thấy thư mục {du}")
    video = Path(a.video).resolve() if a.video else next(
        (du / n for n in ("video.mp4", "video-nhap.mp4") if (du / n).exists()), None)
    if not video or not video.exists():
        die("không thấy video để duyệt (video.mp4 / video-nhap.mp4) — dựng xong rồi mới tạo trang.")
    dur, w, h = probe(video)
    if (du / "timing.json").exists():
        kind = "quay"
        items, notes = project_quay(du, dur)
    elif (du / "kich-ban.json").exists():
        kind = "kich-ban"
        items, notes = project_kich_ban(du, video, dur)
    else:
        die("thư mục không phải dự án tao-video (thiếu timing.json hoặc kich-ban.json).")
    items.sort(key=lambda x: (x["tu"], {"canh": 0, "cau": 0, "goc": 1, "fx": 2}.get(x["kind"], 3)))
    for i, it in enumerate(items):
        it["i"] = i
    out = du / "duyet"
    thumbs(video, items, out / "anh")
    rel = os.path.relpath(video, out).replace("\\", "/")
    data = {"du_an": str(du), "ten": du.name, "kieu": kind, "video": rel, "video_ten": video.name,
            "dur": round(dur, 2), "w": w, "h": h, "items": items, "notes": [{"t": t, "x": x} for t, x in notes],
            "tao_luc": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "mtime": int(video.stat().st_mtime)}
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    (out / "index.html").write_text(html, encoding="utf-8")
    n = {k: sum(1 for x in items if x["kind"] == k) for k in ("canh", "cau", "fx", "goc")}
    print(f"✔ {out / 'index.html'}")
    print("  " + ", ".join(f"{v} {({'canh': 'cảnh', 'cau': 'câu', 'fx': 'hiệu ứng', 'goc': 'đoạn góc máy'})[k]}"
                           for k, v in n.items() if v))
    print("  Gửi người dùng link này, nhắc: bấm vào mục cần sửa → ghi góp ý → 'Sao chép lệnh' rồi dán lại cho Claude.")
    if a.mo:
        webbrowser.open((out / "index.html").as_uri())


TEMPLATE = r"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Duyệt video</title>
<style>
:root{--bg:#f6f5f2;--panel:#fff;--ink:#1d1d1f;--muted:#6b6b70;--line:#e4e2dc;--accent:#c2410c;--accent-soft:#fff1e8;
 --cau:#2563eb;--canh:#2563eb;--fx:#9333ea;--goc:#0d9488;--note:#dc2626;--radius:12px;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#141415;--panel:#1e1e20;--ink:#ececee;--muted:#9a9aa1;--line:#2e2e32;
 --accent:#fb923c;--accent-soft:#2a1d14;--cau:#60a5fa;--canh:#60a5fa;--fx:#c084fc;--goc:#2dd4bf;--note:#f87171;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;padding:14px 20px;border-bottom:1px solid var(--line);background:var(--panel)}
header h1{font-size:17px;margin:0}
header .meta{color:var(--muted);font-size:13px}
main{display:grid;grid-template-columns:minmax(260px,340px) minmax(300px,1fr) minmax(280px,380px);gap:16px;padding:16px 20px;align-items:start}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius)}
.tabs{display:flex;gap:4px;padding:8px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.tabs button{border:0;background:transparent;color:var(--muted);padding:6px 10px;border-radius:8px;cursor:pointer;font:inherit}
.tabs button.on{background:var(--accent-soft);color:var(--accent);font-weight:600}
#list{max-height:calc(100vh - 170px);overflow:auto;padding:6px}
.it{display:grid;grid-template-columns:56px 1fr;gap:10px;padding:8px;border-radius:10px;cursor:pointer;border:1px solid transparent}
.it:hover{background:var(--bg)}
.it.sel{border-color:var(--accent);background:var(--accent-soft)}
.it img{width:56px;height:84px;object-fit:cover;border-radius:6px;background:var(--line)}
.it .lb{font-weight:600;font-size:13px;display:flex;gap:6px;align-items:center}
.it .tm{color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}
.it .tx{font-size:13px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;flex:none}
.has-note .lb::after{content:"✎ có góp ý";color:var(--note);font-weight:600;font-size:11px;margin-left:auto}
.stage{display:flex;flex-direction:column;align-items:center;gap:12px;padding:16px}
.phone{position:relative;width:min(100%,360px);border-radius:28px;padding:10px;background:#0b0b0c;box-shadow:0 8px 30px rgba(0,0,0,.18)}
.phone.land{width:min(100%,640px);border-radius:18px}
.screen{position:relative;border-radius:20px;overflow:hidden;background:#000}
.phone.land .screen{border-radius:10px}
video{display:block;width:100%;height:auto}
.safe{position:absolute;inset:0;pointer-events:none;display:none}
.safe.on{display:block}
.safe div{position:absolute;background:repeating-linear-gradient(45deg,rgba(239,68,68,.28) 0 8px,rgba(239,68,68,.12) 8px 16px);
 border:1px dashed rgba(255,255,255,.7)}
.safe span{position:absolute;font-size:10px;color:#fff;background:rgba(0,0,0,.55);padding:1px 5px;border-radius:4px;left:4px;top:4px}
.ctrl{display:flex;gap:10px;align-items:center;flex-wrap:wrap;justify-content:center;font-size:13px;color:var(--muted)}
.ctrl label{display:flex;gap:6px;align-items:center;cursor:pointer}
.ctrl button{font:inherit;border:1px solid var(--line);background:var(--panel);color:var(--ink);padding:6px 10px;border-radius:8px;cursor:pointer}
.tl{width:100%;padding:0 4px}
.track{position:relative;height:18px;margin:4px 0;background:var(--bg);border-radius:5px;cursor:pointer}
.track .seg{position:absolute;top:2px;bottom:2px;border-radius:4px;opacity:.75}
.track .seg.sel{outline:2px solid var(--accent);opacity:1}
.track .seg.n{box-shadow:inset 0 -3px 0 var(--note)}
.tlab{font-size:11px;color:var(--muted);display:flex;justify-content:space-between}
.ph{position:absolute;top:0;bottom:0;width:2px;background:var(--accent);pointer-events:none}
.tlwrap{position:relative}
.side{padding:14px;display:flex;flex-direction:column;gap:12px}
.side h2{font-size:15px;margin:0}
.det{color:var(--muted);font-size:13px;white-space:pre-wrap}
.det b{color:var(--ink);font-weight:600}
textarea{width:100%;min-height:84px;resize:vertical;font:inherit;padding:8px 10px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chips button{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);padding:4px 9px;border-radius:999px;cursor:pointer}
.chips button:hover{border-color:var(--accent);color:var(--accent)}
.out{border-top:1px solid var(--line);padding-top:12px;display:flex;flex-direction:column;gap:8px}
.out pre{margin:0;white-space:pre-wrap;font:12.5px/1.5 ui-monospace,Consolas,monospace;background:var(--bg);border:1px solid var(--line);
 border-radius:8px;padding:10px;max-height:260px;overflow:auto}
.row{display:flex;gap:8px;flex-wrap:wrap}
.btn{font:inherit;border:0;background:var(--accent);color:#fff;padding:8px 14px;border-radius:8px;cursor:pointer;font-weight:600}
.btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--line);font-weight:500}
.empty{color:var(--muted);font-size:13px}
details{font-size:13px}
details pre{white-space:pre-wrap;font-size:12px;color:var(--muted)}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--ink);color:var(--bg);padding:8px 14px;border-radius:8px;opacity:0;transition:.2s;pointer-events:none}
.toast.on{opacity:1}
@media (max-width:1100px){main{grid-template-columns:1fr 1fr}.side{grid-column:1/-1}}
@media (max-width:720px){main{grid-template-columns:1fr;padding:12px 16px}#list{max-height:none}}
</style>
</head>
<body>
<header><h1 id="ten"></h1><span class="meta" id="meta"></span></header>
<main>
 <section class="card">
  <div class="tabs" id="tabs"></div>
  <div id="list"></div>
 </section>
 <section class="card stage">
  <div class="phone" id="phone"><div class="screen">
   <video id="v" controls playsinline preload="metadata"></video>
   <div class="safe" id="safe"></div>
  </div></div>
  <div class="ctrl">
   <label><input type="checkbox" id="safeOn"> Vùng bị nút TikTok/Reels che</label>
   <button id="noteHere">✎ Góp ý tại giây đang xem</button>
  </div>
  <div class="tl"><div class="tlwrap" id="tl"></div><div class="tlab"><span>0:00</span><span id="tend"></span></div></div>
 </section>
 <section class="card side">
  <div id="detail"><p class="empty">Bấm một mục bên trái (hoặc trên thanh thời gian) để xem và ghi góp ý.</p></div>
  <div class="out">
   <h2>Lệnh gửi Claude</h2>
   <pre id="cmd"></pre>
   <div class="row">
    <button class="btn" id="copy">Sao chép lệnh</button>
    <button class="btn ghost" id="save">Tải gop-y.json</button>
    <button class="btn ghost" id="clear">Xoá hết góp ý</button>
   </div>
  </div>
  <div id="extra"></div>
 </section>
</main>
<div class="toast" id="toast"></div>
<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const $ = id => document.getElementById(id);
const KIND = {canh:'Cảnh', cau:'Câu', fx:'Hiệu ứng', goc:'Góc máy', ghi:'Ghi chú'};
const COLOR = {canh:'var(--canh)', cau:'var(--cau)', fx:'var(--fx)', goc:'var(--goc)'};
const CHIPS = {
 cau:['Sai chính tả phụ đề','Cắt bỏ câu này','Giữ lại chỗ bị cắt','Phụ đề đè mặt','Tô màu từ khác'],
 canh:['Làm lại hình','Đổi lời','Đọc lại giọng','Cảnh dài quá','Cảnh ngắn quá','Đổi chuyển cảnh'],
 fx:['Bỏ hiệu ứng này','Đổi hiệu ứng khác','Sửa chữ trong hiệu ứng','Hiệu ứng đè mặt','Hiện lâu hơn'],
 goc:['Đổi sang góc kia','Khung cắt cụt đầu','Chuyển góc sớm hơn','Chuyển góc muộn hơn'],
 ghi:['Nhạc to quá','Nhạc nhỏ quá','Chỗ này hơi chậm','Thêm hiệu ứng ở đây','Chèn cảnh minh hoạ']
};
const KEY = 'tao-video-duyet:' + D.du_an;
let store = {};
try { store = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e) {}
let notes = store.notes || {};       // key -> text
let extra = store.extra || [];       // [{t, text}]
if (store.mtime && store.mtime !== D.mtime) toast('Video đã được dựng lại — góp ý cũ vẫn giữ, xem lại mốc giờ.');
function persist(){ try { localStorage.setItem(KEY, JSON.stringify({notes, extra, mtime:D.mtime})); } catch(e) {} render(); }
const fmt = t => { t = Math.max(0,t); const m = Math.floor(t/60), s = (t - m*60); return m + ':' + s.toFixed(1).padStart(4,'0'); };
const keyOf = it => it.kind + ':' + it.i;
let tab = 'all', sel = null;

$('ten').textContent = 'Duyệt video · ' + D.ten;
$('meta').textContent = `${D.video_ten} · ${fmt(D.dur)} · ${D.w}×${D.h} · tạo lúc ${D.tao_luc}`;
document.title = 'Duyệt · ' + D.ten;
$('tend').textContent = fmt(D.dur);
const v = $('v'); v.src = D.video;
if (D.w > D.h) $('phone').classList.add('land');

// vùng an toàn: trên ~9%, dưới ~20%, phải ~13% (nút thả tim/bình luận) — khổ dọc
const safe = $('safe');
if (D.h > D.w) safe.innerHTML = '<div style="left:0;right:0;top:0;height:9%"><span>thanh trên</span></div>' +
 '<div style="left:0;right:0;bottom:0;height:20%"><span>tên kênh · mô tả</span></div>' +
 '<div style="right:0;top:42%;bottom:20%;width:13%"><span>nút</span></div>';
else safe.innerHTML = '<div style="left:0;right:0;bottom:0;height:12%"><span>thanh điều khiển</span></div>';
$('safeOn').onchange = e => safe.classList.toggle('on', e.target.checked);

const kinds = [...new Set(D.items.map(x => x.kind))];
function tabs(){
 const t = $('tabs'); t.innerHTML = '';
 [['all','Tất cả'], ...kinds.map(k => [k, KIND[k]]), ['note','Có góp ý']].forEach(([k, lab]) => {
  const b = document.createElement('button'); b.textContent = lab; if (k === tab) b.className = 'on';
  b.onclick = () => { tab = k; render(); }; t.appendChild(b);
 });
}
function list(){
 const L = $('list'); L.innerHTML = '';
 let rows = D.items.filter(it => tab === 'all' || it.kind === tab || (tab === 'note' && notes[keyOf(it)]));
 const ex = (tab === 'all' || tab === 'note') ? extra.map((x, j) => ({kind:'ghi', i:j, label:'Ghi chú tại ' + fmt(x.t), tu:x.t, den:x.t, text:x.text})) : [];
 rows = rows.concat(ex).sort((a,b) => a.tu - b.tu);
 if (!rows.length) { L.innerHTML = '<p class="empty" style="padding:10px">Chưa có mục nào.</p>'; return; }
 for (const it of rows) {
  const d = document.createElement('div');
  const k = it.kind === 'ghi' ? 'ghi:' + it.i : keyOf(it);
  d.className = 'it' + (sel && sel.k === k ? ' sel' : '') + ((notes[k] || it.kind === 'ghi') ? ' has-note' : '');
  d.innerHTML = `${it.anh ? `<img src="${it.anh}" alt="" loading="lazy">` : '<img alt="">'}
   <div><div class="lb"><span class="dot" style="background:${COLOR[it.kind] || 'var(--note)'}"></span>${esc(it.label)}</div>
   <div class="tm">${fmt(it.tu)}${it.den > it.tu ? ' – ' + fmt(it.den) : ''}</div>
   <div class="tx">${esc(it.text || it.mo_ta || '')}</div></div>`;
  d.onclick = () => pick(it.kind === 'ghi' ? {ghi:true, j:it.i, k} : {it, k}, true);
  L.appendChild(d);
 }
}
function timeline(){
 const T = $('tl'); T.innerHTML = '';
 const groups = kinds.map(k => [k, D.items.filter(x => x.kind === k)]);
 for (const [k, arr] of groups) {
  const tr = document.createElement('div'); tr.className = 'track'; tr.title = KIND[k];
  for (const it of arr) {
   const s = document.createElement('div');
   s.className = 'seg' + (sel && sel.k === keyOf(it) ? ' sel' : '') + (notes[keyOf(it)] ? ' n' : '');
   s.style.left = (it.tu / D.dur * 100) + '%';
   s.style.width = Math.max(0.6, (it.den - it.tu) / D.dur * 100) + '%';
   s.style.background = COLOR[k];
   s.title = `${it.label} · ${fmt(it.tu)}`;
   s.onclick = e => { e.stopPropagation(); pick({it, k:keyOf(it)}, true); };
   tr.appendChild(s);
  }
  tr.onclick = e => { const r = tr.getBoundingClientRect(); v.currentTime = (e.clientX - r.left) / r.width * D.dur; };
  T.appendChild(tr);
 }
 for (const x of extra) {
  const m = document.createElement('div'); m.className = 'ph'; m.style.background = 'var(--note)'; m.style.opacity = .6;
  m.style.left = (x.t / D.dur * 100) + '%'; T.appendChild(m);
 }
 const ph = document.createElement('div'); ph.className = 'ph'; ph.id = 'ph'; T.appendChild(ph);
 movePh();
}
function movePh(){ const p = $('ph'); if (p) p.style.left = (v.currentTime / D.dur * 100) + '%'; }
v.addEventListener('timeupdate', movePh);

function pick(s, seek){
 sel = s;
 const box = $('detail');
 if (s.ghi) {
  const x = extra[s.j];
  if (seek) v.currentTime = x.t;
  box.innerHTML = `<h2>Ghi chú tại ${fmt(x.t)}</h2>
   <textarea id="ta" placeholder="Cần sửa gì ở chỗ này?"></textarea>
   <div class="chips">${CHIPS.ghi.map(c => `<button>${c}</button>`).join('')}</div>
   <div class="row"><button class="btn ghost" id="del">Xoá ghi chú này</button></div>`;
  const ta = $('ta'); ta.value = x.text;
  ta.oninput = () => { x.text = ta.value; persist(); };
  chips(ta, () => { x.text = ta.value; persist(); });
  $('del').onclick = () => { extra.splice(s.j, 1); sel = null; box.innerHTML = ''; persist(); };
 } else {
  const it = s.it;
  if (seek) { v.currentTime = it.tu + 0.02; }
  const d = [];
  if (it.text) d.push(`<b>${it.kind === 'fx' ? 'Nội dung' : 'Lời'}:</b> ${esc(it.text)}`);
  if (it.mo_ta) d.push(`<b>Mô tả hình:</b> ${esc(it.mo_ta)}`);
  if (it.hinh) d.push(`<b>File hình:</b> ${esc(it.hinh)}`);
  box.innerHTML = `<h2>${esc(it.label)} <span class="tm" style="font-weight:400;color:var(--muted)">${fmt(it.tu)} – ${fmt(it.den)}</span></h2>
   <div class="det">${d.join('\n')}</div>
   <div class="row"><button class="btn ghost" id="play">▶ Xem đoạn này</button></div>
   <textarea id="ta" placeholder="Cần sửa gì? Ví dụ: chữ 'môn' phải là 'muôn'"></textarea>
   <div class="chips">${(CHIPS[it.kind] || []).map(c => `<button>${c}</button>`).join('')}</div>`;
  const ta = $('ta'); ta.value = notes[s.k] || '';
  ta.oninput = () => { if (ta.value.trim()) notes[s.k] = ta.value; else delete notes[s.k]; persist(); };
  chips(ta, ta.oninput);
  $('play').onclick = () => { v.currentTime = it.tu; v.play(); const stop = () => { if (v.currentTime >= it.den) { v.pause(); v.removeEventListener('timeupdate', stop); } }; v.addEventListener('timeupdate', stop); };
 }
 render(true);
}
function chips(ta, cb){
 ta.parentElement.querySelectorAll('.chips button').forEach(b => b.onclick = () => {
  ta.value = ta.value.trim() ? ta.value.trim() + '; ' + b.textContent : b.textContent; cb(); ta.focus();
 });
}
$('noteHere').onclick = () => {
 v.pause(); extra.push({t: Math.round(v.currentTime * 10) / 10, text: ''});
 const j = extra.length - 1; persist(); pick({ghi:true, j, k:'ghi:' + j}, false);
 setTimeout(() => $('ta') && $('ta').focus(), 0);
};
function command(){
 const lines = [];
 for (const it of D.items) {
  const n = notes[keyOf(it)]; if (!n) continue;
  const q = it.text ? ` "${it.text.slice(0, 70)}${it.text.length > 70 ? '…' : ''}"` : '';
  lines.push({t: it.tu, s: `${it.label} (${fmt(it.tu)}–${fmt(it.den)})${q}: ${n.trim()}`});
 }
 for (const x of extra) if (x.text.trim()) lines.push({t: x.t, s: `Tại ${fmt(x.t)}: ${x.text.trim()}`});
 lines.sort((a,b) => a.t - b.t);
 if (!lines.length) return '';
 return `Dự án tao-video: ${D.du_an}\nVideo: ${D.video_ten} (${fmt(D.dur)}). Sửa theo góp ý, giờ tính trên video này:\n` +
   lines.map((l, i) => `${i + 1}. ${l.s}`).join('\n') + '\nSửa xong dựng lại và tạo lại trang duyệt.';
}
function render(keepDetail){
 tabs(); list(); timeline();
 const c = command();
 $('cmd').textContent = c || 'Chưa có góp ý nào.';
}
$('copy').onclick = async () => {
 const c = command(); if (!c) return toast('Chưa có góp ý nào.');
 try { await navigator.clipboard.writeText(c); toast('Đã sao chép — dán vào ô chat với Claude.'); }
 catch(e) { const r = document.createRange(); r.selectNodeContents($('cmd')); const s = getSelection(); s.removeAllRanges(); s.addRange(r); document.execCommand('copy'); toast('Đã sao chép.'); }
};
$('save').onclick = () => {
 const c = command(); if (!c) return toast('Chưa có góp ý nào.');
 const items = D.items.filter(it => notes[keyOf(it)]).map(it => ({muc: it.label, loai: it.kind, tu: it.tu, den: it.den, noi_dung: it.text || '', gop_y: notes[keyOf(it)]}))
  .concat(extra.filter(x => x.text.trim()).map(x => ({muc: 'Ghi chú', loai: 'ghi', tu: x.t, den: x.t, gop_y: x.text})));
 const blob = new Blob([JSON.stringify({du_an: D.du_an, video: D.video_ten, lenh: c, gop_y: items}, null, 1)], {type:'application/json'});
 const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'gop-y.json'; a.click();
 toast('Lưu gop-y.json vào thư mục dự án rồi bảo Claude "đọc góp ý".');
};
$('clear').onclick = () => { if (confirm('Xoá hết góp ý của video này?')) { notes = {}; extra = []; sel = null; $('detail').innerHTML = ''; persist(); } };
function esc(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
let tt; function toast(m){ const t = $('toast'); t.textContent = m; t.classList.add('on'); clearTimeout(tt); tt = setTimeout(() => t.classList.remove('on'), 2600); }
if (D.notes.length) $('extra').innerHTML = D.notes.map(n => `<details><summary>${esc(n.t)}</summary><pre>${esc(n.x)}</pre></details>`).join('');
v.addEventListener('error', () => toast('Không phát được video — mở trang bằng Chrome hoặc Edge.'));
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
