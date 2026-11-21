# /tao-video — hướng dẫn nhanh

Đọc cho người dùng bằng lời gọn, đừng dán nguyên file. Gõ lệnh không cần chính xác
(`/tao-video huong dan`, `huong-dan`, `help` đều ra trang này).

## Làm được gì

Biến **kịch bản hoặc ý tưởng** thành **video ngắn** (dọc 9:16 cho TikTok/Reels, ngang 16:9 cho YouTube)
từ ảnh hoặc clip AI, có giọng đọc, nhạc nền, tiếng động, tiêu đề, phụ đề. Nhân vật giữ nguyên
mặt/áo từ cảnh này sang cảnh khác. Khâu dựng chạy bằng ffmpeg trên máy bạn, gần như không tốn token.

## Lần đầu: cài đặt

```
/tao-video setup
```
Claude kiểm máy, kiểm GaBee + đăng nhập Muse, tạo thử 1 ảnh, thử giọng, dựng thử video. Làm một lần,
mất khoảng 10 phút. Cần: Claude Code, phần mềm GaBee (điều khiển trình duyệt tạo ảnh), tài khoản Muse
(hoặc ChatGPT/Gemini), ffmpeg + Python.

## Làm một video

```
/tao-video   rồi dán kịch bản, hoặc nói ý tưởng ("video kể chuyện bé Na và con diều, 1 phút")
```
Claude hỏi bạn vài câu rồi làm theo thứ tự:

| # | Bước | Bạn cần làm |
|---|---|---|
| 1 | Viết/chốt kịch bản | đọc, nói "ok" hoặc sửa |
| 2 | Tạo nhân vật + bối cảnh | xem ảnh, chọn ảnh ưng |
| 3 | Chọn giọng đọc | **nghe mẫu và chọn** (luôn hỏi) |
| 4 | Thử 1–2 cảnh | xem có giống nhân vật, có mượt không |
| 5 | Tạo hết ảnh | chờ; xem ảnh lưới một lần |
| 6 | Giọng + bản nháp | xem nháp |
| 7 | Bản thật `video.mp4` | nhận video |

Chọn chế độ **từng bước** (dừng hỏi ở mỗi bước) hoặc **tự động** (hỏi một lần ở đầu rồi chạy hết).
Muốn tự động: nói "chạy tự động".

## Mẹo để mượt và nhanh

- **Chốt kịch bản xong mới làm ảnh.** Sửa kịch bản sau khi có ảnh là làm lại ảnh.
- **Đừng đóng cửa sổ trình duyệt GaBee** khi đang tạo ảnh — lượt đang chạy sẽ hỏng.
- Muốn quay màn hình lúc làm: bật quay trước, rồi mới bảo Claude chạy.
- Ảnh tạo hơi chậm là bình thường (~1–1,5 phút/ảnh, chạy 2 ảnh một lúc). 17 cảnh ≈ 15 phút.
- Bộ nhân vật được lưu ở `<KHO>/` — video sau dùng lại, khỏi tạo mới.
- Một cảnh lệch: nói số cảnh, Claude tạo lại riêng cảnh đó.
- Sửa một câu giọng: nói số cảnh, chỉ tạo lại câu đó.

## Cách gọi nhanh

| Gõ | Ra |
|---|---|
| `/tao-video setup` | cài đặt + test lần đầu |
| `/tao-video huong-dan` | trang này |
| `/tao-video` + kịch bản/ý tưởng | làm video |

## Gặp lỗi

| Thấy | Làm |
|---|---|
| Không tạo được ảnh, hỏi đăng nhập | đăng nhập Muse trong cửa sổ GaBee, rồi nói "tiếp" |
| "Chưa được phép đọc thư mục" | GaBee → Cài đặt → Thư mục được phép → thêm `<KHO>` |
| Ảnh quá lâu (> 3 phút) | báo Claude, nó sẽ dừng và chạy lại |
| Giọng đọc thiếu/sai chữ | nói số cảnh, tạo lại câu đó |
| Mọi thứ lạ | chạy lại `/tao-video setup` |
