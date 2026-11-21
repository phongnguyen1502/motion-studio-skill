# Clip có giọng sẵn (Google Flow / Veo): giữ nhân vật, nối khung, phụ đề + thẻ kết bằng HyperFrames

Dùng khi: tiểu phẩm thoại ngắn, nhân vật cố định, muốn **nhép miệng sẵn** (Flow/Veo tự nói tiếng Việt giọng trẻ con),
không thu giọng riêng. Khác `"kieu":"anh"` (ảnh + TTS lồng lên) ở chỗ giọng nằm TRONG clip, nên khâu dựng cắt theo **mốc giọng thật**.
Ví dụ đã chạy trọn: video "Không thành công thì thành công nhân" (15/10/2026, 4 cảnh + cảnh mở + thẻ kết, 39 giây, 9:16).

## Quy trình (⛳ = điểm duyệt)

1. **Kịch bản theo nhịp "lời → phản ứng SAU lời".** Mỗi cảnh một người nói. Phản ứng của người nghe phải đến **sau** câu, không trước
   (người dùng chê "chưa nghe mà đã tỏ thái độ"). Cú chốt hài nên chơi vào sự sĩ diện/ngây thơ của nhân vật, không hạ thấp một nhóm
   người (nghề nghiệp, vùng miền): câu đùa "thành công nhân" bị cân nhắc rủi ro vì coi công nhân là phương án tệ nhất.
2. **Ảnh tham chiếu nhân vật**: tạo bằng ChatGPT (`chatgpt-image-v2`, profile đã đăng nhập ChatGPT — máy gốc dùng Cloak1) hoặc **cắt từ video cũ** (nhân vật dùng lại).
   Ảnh phải ở thư mục GaBee cho phép (`~/Downloads/...`).
3. **Ảnh khung đầu từng cảnh** (ChatGPT, kèm ảnh tham chiếu + ảnh cảnh 1 để giữ cùng bối cảnh; nói rõ ai bên TRÁI/PHẢI, "chỉ hai nhân vật này").
   Có cảnh mở toàn cảnh (nhân vật nhỏ trong khung, thấy cả bối cảnh) trước cảnh đối thoại. **Ghép lưới 4–5 ảnh xem một lần** ⛳.
4. **Tạo clip**: `google-flow-anh-thanh-video` (profile đã đăng nhập Google Flow — máy gốc dùng `idex`; ~100–120s/clip, 10s, mp4 720p). Dùng chung `project_url`. Chạy MỘT lượt/lần trên một profile.
   Muse KHÔNG dùng được để giữ nhân vật (ảnh đính kèm không tới Muse → nó tự lấy ảnh cũ → đổi người, bé mập thay bé ốm).
5. **NỐI KHUNG (bắt buộc cho cảnh liền mạch)**: khung ở điểm cắt cuối cảnh N làm ảnh đầu cảnh N+1:
   `ffmpeg -ss <điểm cắt> -i canh-N.mp4 -frames:v 1 -vf "delogo=x=570:y=1130:w=60:h=60" noi-N-cuoi.png` (xoá luôn dấu ✦ của Flow).
   Tối đa 2 cảnh liền rồi neo lại bằng ảnh khung đầu gốc (nối nhiều bước thì mặt trôi).
6. **Kiểm từng clip trước khi ghép** (đừng đợi tới khi ghép xong mới thấy):
   - dải khung 1 fps: `ffmpeg -i c.mp4 -vf "fps=1,scale=170:-1,tile=10x1" -frames:v 1 dai.png` → ai bên trái/phải, mặt có đổi không, phản ứng có đúng lúc không;
   - `python scripts/do-cao-do-giong.py c.mp4`: giọng bé ~300–350 Hz; ≤270 Hz là bị đổi sang giọng người lớn (clip lỗi đo 262 Hz, máy nhận chữ vẫn nghe đúng nên không bắt được);
   - mốc chữ: `python scripts/chu-tu-giong.py c.mp4` → `c.chu.json` (mốc từng từ + câu) + `c.srt`, dùng để điền `sub[].t`
     và `cut_start/cut_len`. Soniox chính xác nhất cho tiếng Việt; máy nghe hay lệch chữ cuối ("nhân" thành "nhanh") —
     chỉ dùng cho MỐC, không kết luận sai phát âm (phát hiện khi dùng whisper ở video "thành công nhân").
7. **Ghép**: `python scripts/dung-clip-co-giong.py kich-ban.json --out video.mp4` (cắt theo mốc giọng, chuyển cảnh theo cặp, nền âm thanh, loudnorm -16 LUFS,
   phụ đề + logo động HyperFrames). Khoá JSON: xem docstring đầu script. Chuyển cảnh: cặp **nối khung → fade 0.15–0.2s** (gần như vô hình);
   cảnh độc lập → fade 0.4–0.5s. Đừng dùng xfade `zoomin` (ra khung trơn).
8. **Thẻ kết**: `bash scripts/the-ket-hyperframes.sh logo.png "Video tạo bởi X" "Tự động hóa bằng *GaBee*" "mecode.pro" the-ket.mp4`, rồi đặt vào `the_ket.clip`.
   Cần Node 22+. Script là bash: Windows chạy trong Git Bash/WSL, hoặc tự chạy các bước bên trong (chép `assets/the-ket-hyperframes`, thay `__DONG1__/__DONG2__/__URL__`, `npx hyperframes@0.8.77 render`).

## Mẫu prompt Flow (đã chạy tốt)

> Tiếp nối liền mạch từ ảnh này. MÁY QUAY CỐ ĐỊNH, không đổi góc, không zoom. GIỮ NGUYÊN VỊ TRÍ: <A> ngồi yên bên TRÁI, <B> đứng yên bên PHẢI.
> Hai bé KHÔNG đi lại, KHÔNG đổi chỗ, KHÔNG xoay người, KHÔNG đứng dậy. Giữ nguyên khuôn mặt, tóc, mũ của hai bé, không đổi kích thước hay độ tuổi.
> Chỉ cử động đầu, nét mặt và bàn tay. <A> nói bằng TIẾNG VIỆT giọng của MỘT BÉ GÁI 5 TUỔI, cao, trong, non nớt (KHÔNG phải giọng người lớn): "<câu>".
> TRONG LÚC <A> nói, <B> giữ nguyên <trạng thái>. CHỈ SAU KHI <A> nói xong, <B> mới <phản ứng>. Chỉ một giọng nói, không nhạc nền, không chữ trong hình.

Câu "TRONG LÚC… CHỈ SAU KHI…" là thứ buộc phản ứng đến sau lời. Muốn nhấn một chữ: "nói CHẬM, ngừng một nhịp trước <cụm>, nhấn mạnh từng chữ".

## Bẫy đã gặp (video "thành công nhân", 15/10/2026 — mỗi dòng là một lần làm lại thật)

| Lỗi | Cách phòng |
|---|---|
| Em bé nhảy từ trái sang phải, đổi mặt/tóc; anh bị đẩy sang trái (giây 17–19). Do prompt có "quay đầu nhìn anh" — Veo hiểu là đi sang | Khoá vị trí trái/phải, "chỉ cử động đầu/nét mặt/tay", kiểm dải khung 1 fps |
| Phản ứng (đơ, lè lưỡi) đến trước câu thoại | Cặp "TRONG LÚC… CHỈ SAU KHI…"; kiểm dải khung |
| Giọng bé đổi sang giọng người lớn ở một clip | `do-cao-do-giong.py`; sinh lại clip với "KHÔNG phải giọng người lớn" |
| Chuyển cảnh "sượng": mỗi cảnh từ một ảnh riêng, giữa các clip im lặng tuyệt đối | Nối khung (bước 5) + nền âm thanh liên tục (script tự thêm) + fade theo cặp |
| Phụ đề lỗi dấu ("v?t", "?i"): font Arial Rounded Bold thiếu glyph tiếng Việt | Tahoma Bold / Arial Bold (đã kiểm). Luôn render thử chữ có ơ ấ ạ ở |
| Thẻ kết tĩnh "xấu lắm" | HyperFrames (`the-ket-hyperframes.sh`) |
| Dấu ✦ Flow ở góc dưới phải | `delogo=x=570:y=1130:w=60:h=60` (720×1280) |
| WebM nền trong suốt mất alpha khi chồng | Nạp bằng `-c:v libvpx-vp9 -i layer.webm` (decoder mặc định bỏ alpha) |
| Cảnh mở: nhân vật mặc khác ở cảnh sau (váy hoa vs sườn xám có mèo) | Ghi rõ trang phục trong prompt ảnh khung đầu cảnh mở; kiểm lưới ảnh |
| `run_flow wait=false` mất tăm / Muse kẹt "Still sending" | `wait=true` lần đầu; ảnh để thư mục cho phép; tải lại trang Muse (xem `video-hoc-tieng-trung-muse`) |
