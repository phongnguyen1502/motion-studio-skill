"""[tao-video · bộ lọc da] Làm mịn + sáng da kiểu TikTok/CapCut, chạy trên máy (opencv + numpy).
Thường gọi qua: python sua-hinh.py lam-dep <video> [--muc nhe|vua|manh]   (kiểm thời lượng + ảnh so sánh)

  python lam-dep.py <vào.mp4> <ra.mp4> [--min 0.6] [--sang 0.35] [--giu-van 0.35]

Cách làm (để KHÔNG ra da nhựa — lần thử GFPGAN trước bị chê "da như nhựa"):
  1. Vùng da = màu da (YCrCb) ∩ vùng quanh mặt + cổ (dò mặt mỗi 6 khung, làm trơn vị trí) → mặt nạ mềm, viền mờ.
     Tóc, mắt, nền tường, áo không bị đụng tới.
  2. Mịn: lọc giữ cạnh (bilateral) ở nửa độ phân giải, rồi TRẢ LẠI một phần vân da (--giu-van) để còn lỗ chân lông.
  3. Sáng: nâng vùng tối/trung của da theo đường cong mềm + hơi hồng ấm, chỉ trong mặt nạ.
  4. Miệng (răng, lòng miệng, môi) KHÔNG làm mịn/ám hồng — bản đầu làm răng nhoè (người dùng bắt lỗi 22/11/2026).
Mức người dùng chọn 22/11/2026: VỪA (mặc định ở đây). Mức mạnh bị chê "quá sáng mịn, không tự nhiên".
"""
import argparse, json, os, subprocess, sys
from pathlib import Path

try:
    import numpy as np
    import cv2
except ImportError:
    _venv = Path.home() / ".motion-studio/asr-venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if _venv.exists() and Path(sys.executable).resolve() != _venv.resolve():
        sys.exit(subprocess.call([str(_venv), "-X", "utf8", __file__, *sys.argv[1:]]))
    sys.exit("LỖI: thiếu numpy/opencv — cài môi trường nghe lời của motion-studio (setup-asr) hoặc bản KEM-GIONG-NOI.")
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ap = argparse.ArgumentParser()
ap.add_argument("vao"); ap.add_argument("ra")
ap.add_argument("--min", type=float, default=0.6, help="độ mịn 0–1")
ap.add_argument("--sang", type=float, default=0.35, help="độ sáng da 0–1")
ap.add_argument("--giu-van", type=float, default=0.35, help="giữ lại vân da 0–1 (cao = tự nhiên hơn)")
ap.add_argument("--mask-ra", help="ghi thêm video mặt nạ để kiểm")
ap.add_argument("--mieng-ra", help="tiền tố ảnh kiểm vùng răng/miệng được giữ nguyên (mỗi 15 khung)")
a = ap.parse_args()

info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                  "stream=width,height,avg_frame_rate:stream_side_data=rotation", "-of", "json", a.vao],
                                 capture_output=True, text=True).stdout)["streams"][0]
W, H = info["width"], info["height"]
rot = next((int(float(s["rotation"])) for s in info.get("side_data_list", []) if "rotation" in s), 0)
if rot % 180:
    W, H = H, W
n, d = info["avg_frame_rate"].split("/")
src_fps = float(n) / float(d) if float(d) else 30.0
# Điện thoại ghi số khung KHÔNG ĐỀU (29,3 fps "trung bình"). Ống raw không mang mốc giờ → nếu ghi lại theo nhịp đều thì
# hình trôi so với tiếng (thấy rõ: mắt nhắm/mở lệch khung, 22/11/2026). Ép về nhịp chuẩn THEO GIỜ THẬT ngay lúc giải mã.
fps = min((24, 25, 30, 50, 60), key=lambda s: abs(s - src_fps))

dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", a.vao, "-vf", f"fps={fps}", "-f", "rawvideo", "-pix_fmt", "bgr24",
                        "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                        "-r", f"{fps:.5f}", "-i", "-", "-i", a.vao, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264",
                        "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy",
                        # không -shortest: điện thoại hay ghi tiếng dài hơn hình, giữ nguyên như gốc
                        "-movflags", "+faststart", a.ra], stdin=subprocess.PIPE)
menc = None
if a.mask_ra:
    menc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
                             "-r", f"{fps:.5f}", "-i", "-", "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p",
                             a.mask_ra], stdin=subprocess.PIPE)

casc = [cv2.CascadeClassifier(cv2.data.haarcascades + f) for f in
        ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml")]
box = None          # vị trí mặt đã làm trơn (x, y, w, h)
mouth = None        # vùng miệng giữ nguyên: [tâm x, tâm y, bán trục x, bán trục y] theo tỉ lệ khung mặt
k = 480 / W
# đường cong sáng: nâng vùng tối/trung, giữ vùng sáng (không cháy)
x = np.arange(256, dtype=np.float32) / 255
lift = np.clip(x + a.sang * 0.22 * np.clip(np.sin(np.pi * x), 0, 1) ** 0.9, 0, 1)
LUT = (lift * 255).astype(np.uint8)
frame_size = W * H * 3
i = 0
while True:
    raw = dec.stdout.read(frame_size)
    if len(raw) < frame_size:
        break
    f = np.frombuffer(raw, np.uint8).reshape(H, W, 3)
    # 1. mặt (mỗi 6 khung), làm trơn để mặt nạ không giật
    if i % 6 == 0:
        g = cv2.cvtColor(cv2.resize(f, (480, int(H * k))), cv2.COLOR_BGR2GRAY)
        found = []
        for c in casc:
            for img, flip in ((g, False), (cv2.flip(g, 1), True)):
                for (fx, fy, fw, fh) in c.detectMultiScale(img, 1.1, 5, minSize=(40, 40)):
                    found.append(((480 - fx - fw) if flip else fx, fy, fw, fh))
            if found:
                break
        if found:
            nb = np.array(max(found, key=lambda r: r[2] * r[3]), np.float32) / k
            box = nb if box is None else box * 0.6 + nb * 0.4
    if box is None:                      # không thấy mặt: để nguyên khung
        enc.stdin.write(raw)
        if menc:
            menc.stdin.write(bytes(W * H))
        i += 1
        continue
    # 2. vùng xử lý = khung quanh mặt + cổ (chỉ tính trong khung này → nhanh hơn nhiều)
    bx, by, bw, bh = box
    x0, x1 = int(max(0, bx - bw * 0.9)), int(min(W, bx + bw * 1.9))
    y0, y1 = int(max(0, by - bh * 0.6)), int(min(H, by + bh * 2.6))
    f0 = f[y0:y1, x0:x1]
    h0, w0 = f0.shape[:2]
    ycc = cv2.cvtColor(f0, cv2.COLOR_BGR2YCrCb)
    skin = cv2.inRange(ycc, (40, 133, 77), (255, 178, 130))
    skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    # vùng mềm: hình mặt + cổ, mờ dần ra rìa (không có cạnh thẳng → không thấy đường nối trên cổ)
    # vẽ + làm mờ ở 1/8 kích thước rồi phóng lại (làm mờ rộng ở kích thước thật rất chậm)
    q = 8
    region = np.zeros((max(2, h0 // q), max(2, w0 // q)), np.uint8)
    cx, cy = (bx + bw / 2 - x0) / q, (by + bh * 0.55 - y0) / q
    cv2.ellipse(region, (int(cx), int(cy)), (int(bw * 0.8 / q), int(bh * 1.0 / q)), 0, 0, 360, 255, -1)
    cv2.ellipse(region, (int(cx), int(cy + bh * 1.05 / q)), (int(bw * 0.55 / q), int(bh * 0.75 / q)), 0, 0, 360, 255, -1)
    region = cv2.GaussianBlur(region, (0, 0), bw * 0.14 / q)
    region = cv2.resize(region, (w0, h0), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255
    sk = cv2.resize(skin, (max(2, w0 // 2), max(2, h0 // 2)), interpolation=cv2.INTER_AREA)
    sk = cv2.GaussianBlur(sk, (0, 0), max(1.5, bw / 120))
    m = cv2.resize(sk, (w0, h0), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255 * region
    # Răng + lòng miệng: KHÔNG làm mịn/sáng (bản đầu làm răng nhoè). Vùng miệng = phần dưới khung mặt; răng = ít màu
    # hơn hẳn da mà vẫn sáng, lòng miệng = tối. Ngưỡng tính theo chính da của người trong khung (đèn nào cũng được).
    mx0, mx1 = int(max(0, bx - bw * 0.1 - x0)), int(min(w0, bx + bw * 1.1 - x0))
    my0, my1 = int(max(0, by + bh * 0.58 - y0)), int(min(h0, by + bh * 1.08 - y0))
    mb = m                      # mặt nạ làm SÁNG (miệng vẫn sáng nhẹ để không thành vòng tối quanh môi)
    if mx1 - mx0 > 8 and my1 - my0 > 8:
        hsv = cv2.cvtColor(f0, cv2.COLOR_BGR2HSV)
        core = m > 0.6
        if core.sum() > 500:
            s_med = float(np.median(hsv[..., 1][core])); v_med = float(np.median(hsv[..., 2][core]))
            z = hsv[my0:my1, mx0:mx1]
            teeth = (z[..., 1] < 0.62 * s_med) & (z[..., 2] > 0.72 * v_med)
            cavity = z[..., 2] < 0.45 * v_med
            # chỉ tính phần NẰM TRONG mặt: lỗ được da bao quanh (tường sau lưng cũng sáng, ít màu như răng)
            sb = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))   # nhân nhỏ: không lấp khe miệng hé
            ff_ = 255 - sb
            hmask = np.zeros((h0 + 2, w0 + 2), np.uint8)
            for seed in ((0, 0), (w0 - 1, 0), (0, h0 - 1), (w0 - 1, h0 - 1)):
                if ff_[seed[1], seed[0]] == 255:
                    cv2.floodFill(ff_, hmask, seed, 0)
            inside = ff_[my0:my1, mx0:mx1] > 0
            # miệng hé: răng tối/lòng miệng hồng không qua ngưỡng màu → mọi lỗ trong da ở vùng miệng đều là miệng
            keep = (inside | ((teeth | cavity) & inside)).astype(np.uint8) * 255
            keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
            # khoảng miệng mở = mảng răng/lòng miệng lớn nhất, đủ rộng (lỗ mũi nhỏ hơn nhiều → bỏ qua).
            # Khoanh trọn cả môi bằng một hình bầu dục mềm quanh nó: môi + răng giữ nguyên độ sắc, không lốm đốm.
            kf = np.zeros((h0, w0), np.float32)
            nlab, lab_, st, _ = cv2.connectedComponentsWithStats(keep)
            found_m = None
            if nlab > 1:
                j = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
                kx, ky, kw, kh = st[j, :4]
                if kw > 0.12 * bw:          # lỗ mũi chỉ ~0,06 bề ngang mặt
                    # lưu theo toạ độ TƯƠNG ĐỐI với khung mặt → bám theo đầu khi miệng khép/mặt di chuyển
                    found_m = np.array([(x0 + mx0 + kx + kw / 2 - bx) / bw, (y0 + my0 + ky + kh / 2 - by) / bh,
                                        kw / 2 / bw + 0.04, max(kh / 2 / bh, 0.03) + 0.05], np.float32)
            if found_m is not None:
                # miệng mở to thì vùng khoanh lớn theo; khép lại thì co dần chứ không biến mất (tránh răng lúc rõ lúc nhoè)
                mouth = found_m if mouth is None else np.maximum(mouth * 0.85 + found_m * 0.15, found_m)
            elif mouth is not None:
                mouth = mouth * 0.97 + np.array([mouth[0], mouth[1], mouth[2], 0.06], np.float32) * 0.03
            if mouth is not None:
                ecx, ecy = bx + mouth[0] * bw - x0, by + mouth[1] * bh - y0
                cv2.ellipse(kf, (int(ecx), int(ecy)), (int(mouth[2] * bw), int(mouth[3] * bh)), 0, 0, 360, 1.0, -1)
                kf = cv2.GaussianBlur(kf, (0, 0), max(2.0, bw / 70))
            mb = m * (1 - 0.35 * kf)     # răng không phải màu da → gần như không bị làm sáng/ám hồng
            m = m * (1 - kf)
            if a.mieng_ra and i % 15 == 0:
                vis = f0.copy(); vis[kf > 0.5] = (0, 0, 255)
                cv2.imwrite(f"{a.mieng_ra}-{i:04d}.jpg", np.hstack([f0[my0:my1, mx0:mx1], vis[my0:my1, mx0:mx1]]))
    m3 = m[..., None]
    # 3. mịn: bilateral ở nửa độ phân giải + trả lại một phần vân da
    half = cv2.resize(f0, (max(2, w0 // 2), max(2, h0 // 2)), interpolation=cv2.INTER_AREA)
    sm = cv2.bilateralFilter(half, 9, 38, 7)
    sm = cv2.bilateralFilter(sm, 7, 30, 5)
    sm = cv2.resize(sm, (w0, h0), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    ff = f0.astype(np.float32)
    detail = ff - cv2.GaussianBlur(ff, (0, 0), 1.2)              # vân rất nhỏ (lỗ chân lông)
    smooth = sm + detail * a.giu_van
    out0 = ff * (1 - m3 * a.min) + smooth * (m3 * a.min)
    # 4. sáng + hồng ấm nhẹ trong vùng da
    if a.sang > 0:
        o8 = np.clip(out0, 0, 255).astype(np.uint8)
        lab = cv2.cvtColor(o8, cv2.COLOR_BGR2LAB)
        lab[..., 0] = LUT[lab[..., 0]]
        bright = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR).astype(np.float32)
        bright[..., 2] += 4 * a.sang      # đỏ
        bright[..., 0] -= 3 * a.sang      # bớt xanh → ấm
        mb3 = mb[..., None]
        out0 = out0 * (1 - mb3) + bright * mb3
    out = f.copy()
    out[y0:y1, x0:x1] = np.clip(out0, 0, 255).astype(np.uint8)
    enc.stdin.write(out.tobytes())
    if menc:
        mm = np.zeros((H, W), np.uint8)
        mm[y0:y1, x0:x1] = (m * 255).astype(np.uint8)
        menc.stdin.write(mm.tobytes())
    i += 1
    if i % 60 == 0:
        print(f"  {i} khung", flush=True)
enc.stdin.close(); enc.wait()
if menc:
    menc.stdin.close(); menc.wait()
print(f"xong {i} khung → {a.ra}")
