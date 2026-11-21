# Nhất quán nhân vật · bối cảnh · nối cảnh mượt

Ba tầng, làm đủ cả ba thì video không giật cục:

## 1. Bộ nhân vật (lưu kho, dùng lại)

Kho: `<KHO>/<ten-bo>/`
```
bo.json
nhan-vat/<ten>.png     ← 1 nhân vật 1 ảnh, nền trơn hoặc đúng bối cảnh, thấy rõ mặt + trang phục
boi-canh/<ten>.png     ← ảnh bối cảnh không người
```
```json
{
  "ten": "be-na-va-anh-hai",
  "phong_cach": "ảnh chụp điện ảnh, ánh sáng ấm buổi chiều, màu phim nhẹ",
  "nhan_vat": {
    "Na": {"mo_ta": "bé gái 6 tuổi, tóc ngang vai buộc nơ đỏ, váy vàng cổ trắng", "anh": "nhan-vat/na.png"}
  },
  "boi_canh": {
    "phong-khach": {"mo_ta": "phòng khách gỗ kiểu Việt, sofa xanh rêu, cửa sổ lớn bên trái", "anh": "boi-canh/phong-khach.png"}
  },
  "giong": {"nguon": "gemini", "ten": "Kore"}
}
```
- `mo_ta` viết **cụ thể, cố định**: tuổi, tóc, màu áo, một chi tiết nhận dạng (nơ đỏ, kính…).
  Đừng sửa giữa chừng một video.
- Tạo ảnh nhân vật: 1 lần/nhân vật, chọn ảnh ưng nhất → lưu. Bối cảnh tương tự.
- Bộ có sẵn trong kho → hỏi người dùng có dùng lại không trước khi tạo mới.

## 2. Kịch bản có "cầu nối" giữa các cảnh

Khi viết kịch bản, mỗi cảnh sau phải **móc vào cảnh trước** bằng ít nhất một thứ:

| Cầu nối | Ví dụ |
|---|---|
| Liên tục thời gian/hành động | cảnh 1 bé cầm hộp quà → cảnh 2 bé mở hộp |
| Vật/màu chung | quả bóng đỏ lăn từ cảnh này sang cảnh kia |
| Hướng chuyển động | nhân vật đi sang phải → cảnh sau bước vào từ trái |
| Ánh mắt/âm thanh | bé nhìn ra cửa → cảnh sau là người ở cửa |
| Câu lời nối | "…và rồi" / "nhưng" ở đầu câu cảnh sau |

Ghi cầu nối vào `mo_ta_hinh`. Đổi bối cảnh → dùng chuyển `den` hoặc `trang` (báo người xem
"sang chỗ khác"); cùng bối cảnh → `hoa` hoặc `cat`.

## 3. Hình nối hình (lúc tạo)

`scripts/ghep-prompt.py` tự lo:
- Chép nguyên văn mô tả + đính ảnh tham chiếu nhân vật/bối cảnh vào **mọi** cảnh.
- `noi_tiep: true` → đính thêm ảnh cảnh trước (clip: khung cuối) làm mốc tư thế/ánh sáng.
- Nối **tối đa 2 cảnh liền**, cảnh thứ 3 tự **neo lại** chỉ bằng ảnh tham chiếu gốc.
  Lý do: nối khung liên tiếp 3 bước thì mặt nhân vật trôi (thí nghiệm Muse 10/2026).

Clip: sau khi tải `canh/02.mp4`, lấy khung cuối cho cảnh sau dùng:
`ffmpeg -v error -y -sseof -0.1 -i canh/02.mp4 -frames:v 1 canh/02-cuoi.png`

Nguồn không nhận nhiều ảnh (Muse hay `attach_failed` khi 2 ảnh): ưu tiên ảnh cảnh trước
nếu nối tiếp, ảnh nhân vật nếu neo lại. Muse nhiều cảnh: giao cả kịch bản trong một
thread (`muse-ask`) — Muse tự giữ nhân vật tốt hơn làm lẻ từng cảnh.

## 4. Dựng (đã tự động)

`dung-video.py` dùng `canh[].chuyen` (hoặc `chuyen_mac_dinh`):
`cat` · `hoa` (mặc định) · `den` · `trang` · `truot` · `truot-len` · `zoom` · `tron`.
Ảnh tĩnh zoom xen kẽ vào/ra để có chuyển động liên tục.

## Kiểm sau khi có đủ hình

Ghép tất cả hình thành **một** ảnh lưới rồi xem một lần: mặt/áo/bối cảnh có khớp không,
cảnh nào lệch thì tạo lại riêng cảnh đó (giữ nguyên các cảnh khác).
`ffmpeg -v error -y -pattern_type glob -i 'canh/*.png' -vf "scale=180:-1,tile=6x2" -frames:v 1 luoi.png`
