# Motion Studio + tao-video — skill làm video cho Claude Code

Repo có hai skill, cài cùng lúc bằng `install.ps1`:

- **motion-studio**: video đồ hoạ chuyển động dựng bằng code, thư viện 20 hiệu ứng, video tự dựng từ giọng đọc.
- **tao-video**: video ngắn từ ảnh/clip AI có kịch bản, và kiểu **video quay sẵn** (người nói trước máy → cắt vấp, cắt lặng, thêm hiệu ứng + phụ đề). tao-video dùng thư viện hiệu ứng của motion-studio.

So với bản gốc, **motion-studio** có thêm:

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
   Lệnh này chép hai skill vào `%USERPROFILE%\.claude\skills\motion-studio` và `…	ao-video`, cài Playwright và Chromium (khoảng 150 MB), rồi tạo môi trường nhận dạng giọng + dò mặt (faster-whisper, opencv). Bỏ `-WithASR` nếu không làm video có voiceover hay video quay sẵn. Nếu máy đã có bản cũ, bản cũ được cất vào `%USERPROFILE%\.claude\skill-backups\`.
3. Khởi động lại Claude Code, rồi gõ `/motion-studio` hoặc yêu cầu "làm video motion…". Với tao-video, gõ `/tao-video setup` một lần để kiểm máy (giọng đọc, công cụ tạo ảnh).

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

## Thư viện hiệu ứng (`assets/fx/`)

20 hiệu ứng dùng lại được: đếm số, biểu đồ cột, so sánh, danh sách tick, thanh và vòng tiến độ, mốc thời gian, trích dẫn, đóng dấu, gõ chữ, chữ đập, thẻ tên, mũi tên và khoanh tròn vẽ tay, thông báo điện thoại, bình chọn, lưu ý, biểu đồ tròn, nhãn dán. Có 4 giao diện (`kinh`, `giay`, `dam`, `sach`), tự tránh mặt người, tự tránh vùng phụ đề, và gắn chuyển động vào đúng chữ được nói.

- Xem thử tất cả: `node scripts/render.mjs assets --entry fx/index.html --serve --format 9x16`
- Danh mục (hiệu ứng nào hợp câu nào, giới hạn chữ): `assets/fx/hieu-ung.json`
- Xuất lớp hiệu ứng nền trong suốt (WebM) để chồng lên video quay: xem `references/fx-library.md`
- Trình dựng có thêm `--alpha` (WebM trong suốt) và `--query` (tham số cho trang).

## Video quay sẵn (tao-video)

Đưa một video người nói (tự quay, MC, clip AI có thoại) rồi nhờ Claude "dựng video quay này":

1. `dung-video-quay.py chuan-bi <video> <du-an>`: nghe lời trên máy, cắt từ đệm/lời lặp/khoảng lặng, đưa về 9:16 canh theo mặt, gợi ý hiệu ứng. Có thẻ kết thì thêm `--den <giây> --giu-sau`; có kịch bản thì `--loi loi.txt` để phụ đề đúng chính tả.
2. Claude điền nội dung hiệu ứng theo đúng lời nói (`fx-plan.json`).
3. `dung-video-quay.py anh <du-an> 3,8,15`: ảnh kiểm tra; `dung-video-quay.py dung <du-an>`: ra `video.mp4` (hiệu ứng, phụ đề kiểu TikTok, -14 LUFS).

Chi tiết: mục "Kiểu video quay sẵn" trong `.claude/skills/tao-video/SKILL.md`.

Clip có vấn đề thì sửa trước khi dựng bằng `sua-hinh.py` (chống rung, cân màu/LUT, HDR→SDR, che mờ, khử nhiễu, chỉnh nghiêng). Mỗi lệnh ra file mới kèm ảnh so sánh trước | sau, clip gốc giữ nguyên. Chi tiết: mục "Sửa hình trước khi dựng" trong SKILL.md.

Quay nhiều máy hoặc thu mic rời: `ghep-goc.py khop/de-xuat/dung` khớp giờ theo tiếng (bù trôi giờ), đề xuất chỗ chuyển góc theo câu nói, ra `mc.mp4` rồi đưa vào `chuan-bi`. `chen-canh.py` chèn cảnh minh hoạ (B-roll), tua nhanh/chậm từng đoạn, gợi ý đoạn hay trong video dài.

Dựng xong thì `xuat.py kiem-dang video.mp4 --nen tiktok` kiểm theo yêu cầu nền tảng (✅/⚠️/❌ kèm lệnh sửa), `xuat.py xuat video.mp4 --nen tiktok,reels,vuong` xuất mỗi nền một bản, `xuat.py hang-loat <thư-mục> --cong-thuc x.json` xử lý cả thư mục và bỏ qua clip đã làm.

## Nguồn

motion-studio dựa trên skill Motion Studio của flaviorg (bản đã rà soát ở commit 7e9e70f), có chỉnh sửa. `tao-video/scripts/sua-hinh.py`, `xuat.py`, `ghep-goc.py` và `chen-canh.py` tham khảo cách làm của ffmpeg-skill (kajisho5, giấy phép MIT), viết lại. Font Be Vietnam Pro dùng giấy phép SIL OFL 1.1. Repo này để dùng nội bộ, nên giữ ở chế độ riêng tư (private).
