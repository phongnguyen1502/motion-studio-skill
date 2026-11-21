#!/usr/bin/env python3
"""Ghép prompt tạo hình cho từng cảnh từ BỘ nhân vật/bối cảnh → prompts.json.

Dùng: ghep-prompt.py kich-ban.json
Mô tả nhân vật + bối cảnh + phong cách được CHÉP NGUYÊN VĂN từ bo.json vào mọi cảnh
(không để AI viết lại mỗi lần → mặt/áo/phòng không trôi), kèm ảnh tham chiếu.
Cảnh `noi_tiep: true` thêm ảnh cảnh trước làm mốc tư thế/ánh sáng; nối tối đa 2 cảnh
liền rồi tự NEO lại bằng ảnh tham chiếu gốc (nối dài làm nhân vật trôi — bài học Muse 10/2026).

kich_ban["bo"] = tên bộ trong kho (<KHO>/<tên>) hoặc đường dẫn thư mục bộ.
Mỗi cảnh: nhan_vat [tên…], boi_canh "tên", mo_ta_hinh "hành động/khung hình", noi_tiep bool.
"""
import json
import os
import sys
# Windows: màn hình/ống dẫn mặc định cp1252 → in tiếng Việt là UnicodeEncodeError (máy Windows thật 15/10/2026).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONUTF8", "1")  # tiến trình Python con cũng in UTF-8


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kho import KHO  # noqa: E402  (kho theo thư mục Downloads thật, kể cả khi đã chuyển sang ổ khác)
MAX_NOI = 2

plan_path = sys.argv[1]
plan = json.load(open(plan_path, encoding="utf-8-sig"))
base = os.path.dirname(os.path.abspath(plan_path))
bo_dir = plan["bo"] if os.path.isdir(plan.get("bo", "")) else os.path.join(KHO, plan["bo"])
bo = json.load(open(os.path.join(bo_dir, "bo.json"), encoding="utf-8-sig"))
khung = "dọc 9:16" if plan.get("khung", [1080, 1920])[1] > plan.get("khung", [1080, 1920])[0] else "ngang 16:9"


def ref(path):
    return path if os.path.isabs(path) else os.path.join(bo_dir, path)


# Khung hình tự xoay vòng khi cảnh không nêu `loai_khung` → không bao giờ 2 cảnh liền cùng loại khung
# (dự án "Con số trên tường" 12/10/2026: 17 cảnh cùng cỡ trung vì cảnh nối bị bảo "giữ góc máy").
VONG_KHUNG = ["TOÀN CẢNH rộng, nhiều chiều sâu", "trung cảnh ngang hông", "CẬN CẢNH chi tiết (tay/vật), trường ảnh nông",
              "QUA VAI: nhân vật quay lưng ở tiền cảnh", "trung cảnh", "CẬN MẶT, ánh sáng hắt một bên"]
STYLE = plan.get("phong_cach") or bo.get("phong_cach", "")
out, chuoi, prev_hinh = [], 0, None
for idx, c in enumerate(plan["canh"]):
    nv = [(n, bo["nhan_vat"][n]) for n in c.get("nhan_vat", [])]
    bc = bo.get("boi_canh", {}).get(c.get("boi_canh")) if c.get("boi_canh") else None
    images = [ref(v["anh"]) for _, v in nv if v.get("anh")]
    if bc and bc.get("anh"):
        images.append(ref(bc["anh"]))
    noi = bool(c.get("noi_tiep")) and prev_hinh is not None and chuoi < MAX_NOI
    chuoi = chuoi + 1 if noi else 0
    # Câu lệnh mở đầu: Muse gặp prompt mơ hồ hoặc ảnh đính kèm lệch mô tả thì hay HỎI LẠI thay vì vẽ,
    # mà flow muse-image cứ chờ ảnh tới 5 phút → treo. Ra lệnh vẽ ngay + luật xử lý khi lệch.
    parts = [f"Vẽ ngay 1 ảnh, không hỏi lại. Chi tiết nào thiếu thì tự quyết cho hợp cảnh; "
             f"ảnh đính kèm khác mô tả thì làm theo mô tả chữ. {STYLE}, khung {khung}."]
    if bc:
        parts.append(f"Bối cảnh: {bc['mo_ta']}.")
    for n, v in nv:
        parts.append(f"Nhân vật {n}: {v['mo_ta']}.")
    parts.append(f"Cảnh: {c.get('mo_ta_hinh', c.get('loi', ''))}.")
    parts.append(f"Khung hình: {c.get('loai_khung') or VONG_KHUNG[idx % len(VONG_KHUNG)]}.")
    if c.get("anh_sang"):
        parts.append(f"Ánh sáng: {c['anh_sang']}.")
    if noi:
        images.append(prev_hinh)
        parts.append("Cùng không gian, ánh sáng và nhân vật như ảnh cuối cùng đính kèm, nhưng ĐỔI sang khung hình "
                     "khác như mô tả — không lặp lại cùng góc máy.")
    if nv:
        parts.append("Giữ đúng khuôn mặt, kiểu tóc, trang phục như ảnh tham chiếu nhân vật.")
    parts.append("Không chữ, không logo, không watermark.")
    out.append({"id": c["id"], "prompt": " ".join(p for p in parts if p.strip(".")),
                "images": images, "noi_tiep": noi, "neo_lai": bool(c.get("noi_tiep")) and not noi})
    hinh = c.get("hinh")
    if hinh and hinh.lower().endswith((".mp4", ".mov", ".webm")):
        hinh = os.path.splitext(hinh)[0] + "-cuoi.png"   # clip: dùng khung cuối (lấy sau khi tải clip về)
    prev_hinh = os.path.join(base, hinh) if hinh else None

dst = os.path.join(base, "prompts.json")
json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for o in out:
    tag = "NỐI" if o["noi_tiep"] else ("NEO LẠI" if o["neo_lai"] else "")
    print(f"{o['id']}  {len(o['images'])} ảnh  {tag}")
print(f"→ {dst}")
