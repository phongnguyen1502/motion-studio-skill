# Motion Studio — skill làm video đồ hoạ chuyển động cho Claude Code

Bản skill **motion-studio** đã được chỉnh cho công việc của anh. So với bản gốc, bản này có thêm:

- **Ngắt dòng theo nghĩa tiếng Việt và canh đều chữ (Justify)** có kiểm soát khoảng trắng (`typeset.js`, `references/typography.md`).
- **Font Be Vietnam Pro** có đủ dấu tiếng Việt, chạy offline.
- **Nhạc nền đổi theo từng phần nội dung**: piano, chuông, dàn dây, dây gảy, `cue()`, tự hạ nhạc khi có giọng nói.
- **Video dùng voiceover**: lấy thời điểm từng chữ ngay trên máy bằng faster-whisper (`voice-timing.py`), không cần khóa API.
- Quy tắc "bỏ nhạc nền, giữ hiệu ứng âm thanh", và đề xuất 2–3 hướng phong cách trước khi dựng.

## Cách 1 — Cài cho cả máy (khuyên dùng trên máy công ty)

Skill sẽ dùng được ở mọi thư mục, trong app Claude desktop lẫn Claude Code terminal.

1. Cài các phần mềm cần thiết (một lần):
   ```powershell
   winget install OpenJS.NodeJS.LTS
   ```
   ```powershell
   winget install Gyan.FFmpeg
   ```
   ```powershell
   winget install Python.Python.3.12
   ```
   Python chỉ cần nếu làm video có voiceover. Cài xong thì mở lại cửa sổ PowerShell để các lệnh mới có hiệu lực.
2. Tải repo về máy (bằng `git clone` hoặc tải file ZIP rồi giải nén), mở PowerShell trong thư mục repo và chạy:
   ```powershell
   powershell -ExecutionPolicy Bypass -File install.ps1 -WithASR
   ```
   Lệnh này chép skill vào `%USERPROFILE%\.claude\skills\motion-studio`, cài Playwright và Chromium (khoảng 150 MB), rồi tạo môi trường nhận dạng giọng. Bỏ `-WithASR` nếu không cần voiceover. Nếu máy đã có bản cũ, bản cũ được cất vào `%USERPROFILE%\.claude\skill-backups\`.
3. Khởi động lại Claude Code, rồi gõ `/motion-studio` hoặc yêu cầu "làm video motion…".

Lần đầu dùng voiceover, mô hình Whisper "medium" sẽ tự tải về (khoảng 1,5 GB). Máy công ty cần mở được kết nối tới huggingface.co.

## Cách 2 — Dùng ngay trong repo (không cần cài)

Khi mở thư mục repo này trong Claude Code (desktop, terminal hoặc bản web), skill tự có sẵn, vì nó nằm trong `.claude/skills/`. Lần đầu dùng cần chạy `setup.ps1` (Windows) hoặc `setup.sh` trong `.claude/skills/motion-studio/scripts/`. Nên tạo các dự án video trong một thư mục con của repo, ví dụ `video/<ten-du-an>/`. File `.gitignore` đã chặn các file mp4, wav và thư mục render nên repo không bị phình.

## Cập nhật

Khi skill có thay đổi: kéo bản mới về (`git pull`) rồi chạy lại `install.ps1`.

## Quy trình một video (tóm tắt)

1. **Brief:** nội dung, thời lượng, khổ hình, có voice hay không, có nhạc hay chỉ hiệu ứng âm thanh.
2. **2–3 hướng phong cách:** mỗi hướng có khung hình mẫu, anh chọn một.
3. **Nếu có voice:** `voice-timing.py` lấy thời điểm từng chữ, và mọi hình bám theo lời đọc.
4. **Bảng cảnh:** anh duyệt trước khi dựng.
5. **Dựng bằng code:** sau đó chụp ảnh thử, chấm điểm và sửa (kể cả kiểm tra chữ: không rớt dòng, canh đều không hở).
6. **Render MP4:** kiểm tra thời lượng, mức âm thanh, và giọng to hơn nhạc 7–10 dB.

## Nguồn

Dựa trên skill Motion Studio của flaviorg (bản đã rà soát ở commit 7e9e70f), có chỉnh sửa. Font Be Vietnam Pro dùng giấy phép SIL OFL 1.1. Repo này để dùng nội bộ, nên giữ ở chế độ riêng tư (private).
