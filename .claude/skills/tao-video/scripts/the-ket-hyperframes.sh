#!/usr/bin/env bash
# Dựng thẻ kết động bằng HyperFrames (logo bật nảy + vòng sáng, chữ trượt lên, nút URL nhấp nháy). Ra mp4 5s, 720x1280.
# Dùng: the-ket-hyperframes.sh <logo.png> "<dòng 1>" "<dòng 2 (*chữ* = in đậm)>" "<url>" <ra.mp4>
# Cần: node 22+, ffmpeg; font Tahoma Bold (macOS) đủ dấu tiếng Việt. Nguồn: video "thành công nhân" 15/10/2026 —
# thẻ kết ffmpeg+Pillow bị chê "xấu lắm", dựng lại bằng HyperFrames thì đạt.
set -euo pipefail
[ $# -eq 5 ] || { echo "dùng: $0 <logo.png> \"<dòng1>\" \"<dòng2>\" \"<url>\" <ra.mp4>" >&2; exit 1; }
LOGO="$1"; D1="$2"; D2="$3"; URL="$4"; OUT="$(cd "$(dirname "$5")" && pwd)/$(basename "$5")"
HERE="$(cd "$(dirname "$0")/.." && pwd)/assets/the-ket-hyperframes"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
cp -R "$HERE/." "$WORK/"; cp "$LOGO" "$WORK/assets/logo.png"
PYBIN=python; command -v python >/dev/null 2>&1 || PYBIN=python3
"$PYBIN" - "$WORK/index.html" "$D1" "$D2" "$URL" <<'PY'
import html, re, sys
p, d1, d2, url = sys.argv[1:5]
s = open(p, encoding="utf-8").read()
e2 = re.sub(r"\*(.+?)\*", lambda m: f"<b>{html.escape(m.group(1))}</b>", html.escape(d2, quote=False).replace("&lt;", "<"))
s = s.replace("__DONG1__", html.escape(d1)).replace("__DONG2__", e2).replace("__URL__", html.escape(url))
open(p, "w", encoding="utf-8").write(s)
PY
cd "$WORK"
npx -y hyperframes@0.8.77 check . >/dev/null
npx -y hyperframes@0.8.77 render . --strict --output "$OUT" >/dev/null
ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT" | xargs -I{} echo "xong: $OUT ({}s)"
