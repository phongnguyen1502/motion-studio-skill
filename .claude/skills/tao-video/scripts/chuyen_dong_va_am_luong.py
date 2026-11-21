"""Chuyển động ảnh mượt (Ken Burns) + đo độ to âm thanh — dùng chung cho dung-video.py.

Vì sao Ken Burns hay giật (bài học dự án "Những con số trên tường", 10/2026):
zoompan của ffmpeg làm tròn toạ độ khung cắt về số nguyên → hình nhích từng bậc.
Ở đây tự tính từng khung bằng Pillow với toạ độ LẺ (resize theo box số thực, bicubic),
không làm tròn → không có bậc. Đo trên cùng ảnh 4s (12/10/2026):
  zoompan kiểu cũ: giật 0.22 · zoompan phóng 3× + khung 2×: 0.14, mất 19s · Pillow: 0.07, mất 2.4s.
Chuyển động có đà (smoothstep): chậm lúc đầu, chậm lúc cuối, không đi thẳng đều.
Chữ (tiêu đề, phụ đề) KHÔNG đi qua bước này — chữ nét nên nhích 1px là thấy rung.
"""
import subprocess

from PIL import Image

# Kiểu chuyển động → (zoom đầu, zoom cuối, tâm x đầu, tâm x cuối, tâm y đầu, tâm y cuối); tâm tính theo tỉ lệ ảnh.
KIEU = {
    "vao":   (1.00, 1.12, .50, .50, .50, .50),
    "ra":    (1.12, 1.00, .50, .50, .50, .50),
    "trai":  (1.12, 1.12, .60, .40, .50, .50),   # máy lia sang trái
    "phai":  (1.12, 1.12, .40, .60, .50, .50),
    "len":   (1.12, 1.12, .50, .50, .58, .42),
    "xuong": (1.12, 1.12, .50, .50, .42, .58),
    "dung":  (1.04, 1.04, .50, .50, .50, .50),   # gần như đứng yên (ảnh có chữ/chi tiết cần đọc)
}
VONG = ["vao", "phai", "ra", "trai"]               # mặc định xoay vòng để cảnh liền nhau khác nhịp


def ken_burns(src, out, kieu, i, W, H, n, fps):
    """Ghi n khung chuyển động mượt cỡ W×H từ một ảnh tĩnh → out (mp4, chỉ hình)."""
    z0, z1, x0, x1, y0, y1 = KIEU.get(kieu or VONG[i % len(VONG)], KIEU["vao"])
    im = Image.open(src).convert("RGB")
    s = max(W / im.width, H / im.height)            # cửa sổ zoom 1 phủ kín khung ra
    bw, bh = W / s, H / s
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
         "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", out],
        stdin=subprocess.PIPE)
    for k in range(n):
        p = k / max(n - 1, 1)
        e = p * p * (3 - 2 * p)                     # smoothstep: có đà đầu và cuối
        z = z0 + (z1 - z0) * e
        w, h = bw / z, bh / z
        cx = min(max((x0 + (x1 - x0) * e) * im.width, w / 2), im.width - w / 2)   # kẹp trong ảnh, không lộ mép
        cy = min(max((y0 + (y1 - y0) * e) * im.height, h / 2), im.height - h / 2)
        ff.stdin.write(im.resize((W, H), Image.BICUBIC, box=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)).tobytes())
    ff.stdin.close()
    if ff.wait():
        raise SystemExit(f"Lỗi dựng chuyển động cho {src}")


def lufs(path):
    """Độ to tích hợp (LUFS) của cả file. Đọc dòng Integrated, không đọc số giây đầu."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=framelog=quiet",
                        "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = r.stderr.split("Integrated loudness")[-1]
    return float(tail.split("I:")[1].split("LUFS")[0].strip())
