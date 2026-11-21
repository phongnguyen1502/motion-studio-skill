---
name: tao-video
description: 'Dựng video ngắn hoàn chỉnh (ra file video.mp4, khổ dọc 9:16 hoặc ngang 16:9 cho TikTok/Reels/Shorts) từ ảnh hoặc clip AI: kịch bản theo cảnh, nhân vật và bối cảnh giữ giống nhau xuyên suốt (có kho nhân vật dùng lại), lời đọc, nhạc nền, tiếng động, tiêu đề, phụ đề kiểu TikTok. Hai chế độ: tự động hoàn toàn hoặc từng bước có điểm duyệt. Nguồn hình tuỳ ý (Muse, Gemini, ChatGPT, Google Flow/Veo, Dola, Meta AI qua GaBee, hoặc file có sẵn), kể cả clip đã có thoại và nhép miệng sẵn từ Flow/Veo. Dùng khi người dùng nói "làm video", "tạo video", "video TikTok/Reels/Shorts", "ghép ảnh thành video", "ghép clip AI", "video kể chuyện", "tiểu phẩm", "lồng tiếng", "thêm giọng đọc/phụ đề cho video", "giữ nhân vật giống nhau", "video tự quay", "video quay sẵn", "video người nói", "cắt chỗ vấp", "cắt khoảng lặng", "chèn hiệu ứng vào video quay", hoặc "/tao-video". KHÔNG dùng cho video đồ hoạ chuyển động/animation dựng bằng code, intro, quảng cáo motion (→ motion-studio), hay khi chỉ cần viết prompt/storyboard mà không dựng video (→ ai-video-prompt-writer). Lệnh con: "/tao-video setup" (cài đặt + chạy thử lần đầu) và "/tao-video huong-dan" (hướng dẫn nhanh); gõ gần đúng cũng nhận (cai dat, cài đặt, thiet lap, huong dan, hướng dẫn, help).'
---

# /tao-video

**Giọng → chữ có mốc thời gian** (giọng tự thu, clip có thoại sẵn, chia cảnh theo câu): `scripts/chu-tu-giong.py`
— Soniox / OpenAI / Gemini, xem `references/nguon-giong.md`. Không cài whisper.
**Windows: gõ `python`, KHÔNG gõ `python3`** (python3 trên Windows mở Microsoft Store — "Python was not found").
`SKILL_DIR` = thư mục chứa file này. Lệnh mẫu ghi `~/.claude/skills/tao-video/…` (Claude Code); agent khác
(Codex, Gemini, Cursor…) thay bằng chỗ đã cài skill. Khoá API: `scripts/khoa.py` (`~/.tao-video/.env`).
**`<Downloads>` và `<KHO>`**: chạy `python SKILL_DIR/scripts/kho.py --downloads` / `python SKILL_DIR/scripts/kho.py` một lần
đầu phiên để biết đường dẫn thật (`<KHO>` = `<Downloads>/tao-video-kho`). Windows cho chuyển Downloads sang ổ khác
(vd `E:\Downloads`), nên **đừng gõ `~/Downloads`**: thư mục đó có thể không còn, sẽ sinh kho rỗng mới ở ổ C.

## Lệnh con — kiểm đối số TRƯỚC, rồi mới vào quy trình

Đối số (không cần gõ đúng, bỏ dấu/hoa thường đều được):

| Đối số có | Làm |
|---|---|
| `setup`, `cai dat`, `cài đặt`, `thiet lap`, `kiểm tra`, `test` | đọc `references/setup.md` rồi chạy từng bước, dừng ở bước nào chưa ✅ |
| `huong-dan`, `huong dan`, `hướng dẫn`, `help`, `?` | đọc `references/huong-dan.md`, nói lại gọn bằng lời đơn giản |
| trống hoặc là kịch bản/ý tưởng | vào quy trình làm video bên dưới. Nếu chưa có `<KHO>/setup-ok.json` → nhắc 1 câu "chưa setup, nên chạy `/tao-video setup` trước", rồi vẫn làm nếu người dùng muốn |

Ba khâu, khâu nào cũng ra **file đặt đúng chỗ** rồi khâu sau dùng. Hình và giọng thay
nguồn thoải mái; khâu dựng cố định.

```
du-an/
├── kich-ban.json      ← nguồn sự thật duy nhất (mẫu: references/kich-ban-mau.json)
├── canh/01.png|mp4    ← ① hình
├── giong/01.mp3       ← ② giọng (mỗi cảnh có lời một file)
├── nhac.mp3           ← nhạc nền (người dùng đưa, hoặc bỏ trống)
└── video.mp4          ← ③ kết quả
```

## Kiểu "video quay sẵn" (người nói trước máy: tự quay, MC, clip AI có thoại)

Không viết kịch bản, không làm hình: video đã có. `scripts/dung-video-quay.py`, 2 bước, giữa hai bước là việc của agent:

1. `python scripts/dung-video-quay.py chuan-bi <video> <du-an> [--den <giây hết phần nói>] [--giu-sau] [--loi loi.txt] [--sua "sai=đúng;…"]`
   → nghe lời trên máy (faster-whisper, không tốn API), **cắt từ đệm (ờ, ừm…), lời lặp, khoảng lặng > 0,45 s**, đưa về
   1080×1920 canh theo mặt, dò mặt → `cut.mp4`, `timing.json`, `cat.txt` (đọc lại chỗ đã cắt), `fx-plan.json` nháp.
   - Video có **thẻ kết / đoạn nhạc cuối** không nói: `--den <giây bắt đầu đoạn đó> --giu-sau` → giữ nguyên, nối lại cuối.
   - Có kịch bản thì đưa `--loi` (mỗi câu một dòng): phụ đề đúng chính tả. Không có: đọc lời máy nghe, sửa bằng `--sua`
     (máy hay sai tên riêng/từ hiếm: "môn người" → "muôn người"). Hỏi người dùng nếu không chắc chữ nào đúng.
2. **Agent điền `fx-plan.json`** theo `~/.claude/skills/motion-studio/references/fx-library.md` + `assets/fx/hieu-ung.json`:
   bộ gợi ý chấm theo từ khoá nên hay chọn hiệu ứng số liệu — **đổi theo tinh thần nội dung** (video tâm tình/kể chuyện:
   gạch-thay, chữ đập, trích dẫn, danh sách, nhãn dán; ít số). 5–8 hiệu ứng/phút, câu không hiệu ứng để phụ đề tự chạy.
   Điền đúng lời nói, xoá `_dien`, thêm `"highlight"` (cụm tô màu trong phụ đề). Theme: `kinh` hợp hầu hết video quay.
3. `python scripts/dung-video-quay.py anh <du-an> 3,8,15,…` → `render/stills/9x16/luoi.png` (hiệu ứng + phụ đề đè lên
   khung hình thật). XEM: chữ đè mặt, đè nhau, sai chính tả. Sửa rồi xem lại.
4. `python scripts/dung-video-quay.py dung <du-an> [--nhac nhac.mp3]` → `video.mp4` (lớp hiệu ứng + phụ đề kiểu TikTok,
   tiếng hiệu ứng, nhạc nền tự nhỏ khi có lời, chuẩn -14 LUFS, + phần giữ nguyên ở cuối).

Cần skill **motion-studio** (thư viện hiệu ứng) và môi trường `~/.motion-studio/asr-venv` có faster-whisper + opencv
(`pip install opencv-python-headless`); script tự chuyển sang Python đó. Đã chạy thử: clip MC AI 40 s
+ thẻ kết 6,5 s (21/11/2026). Thời gian: nghe lời ~1 phút, lớp hiệu ứng ~2,5 s xử lý cho 1 s video.

## Hai chế độ — hỏi ở đầu

- **Tự động hoàn toàn** (`"che_do": "tu-dong"`): người dùng chỉ đưa ý tưởng hoặc kịch bản,
  chỉ hỏi đúng 1 lần ở đầu (giọng, khổ, nhạc), rồi chạy hết 7 bước, tự kiểm ở mỗi ⛳ và
  tự làm lại cảnh hỏng (tối đa 2 lần/cảnh), cuối cùng gửi video + ảnh lưới.
- **Từng bước** (`"che_do": "tung-buoc"`): dừng ở mỗi ⛳, đưa thứ để duyệt, chờ "ok"/sửa.

## Quy trình (⛳ = điểm duyệt)

0. **Đạo diễn tự động — LÀM TRƯỚC MỌI THỨ, đọc `references/dao-dien-tu-dong.md`.** Người dùng không có chuyên môn
   video/thiết kế: cái gì họ không nói (phong cách, góc máy, ánh sáng, thẻ đầu/kết, nhạc, cỡ phụ đề) thì **tự quyết**,
   đừng hỏi và đừng để model vẽ tự do. Mỗi cảnh ghi `loai_khung` + `anh_sang`; không 2 cảnh liền cùng loại khung;
   luôn có thẻ đầu, thẻ kết, 2 bài nhạc; phụ đề khổ ngang chữ nhỏ. Đây là chỗ khác biệt giữa video "ổn" và video "đẹp"
   (12/10/2026: cùng Muse + Soniox, bản chưa có bước này thua hẳn bản có góc máy/ánh sáng/nhạc).
1. **Kịch bản** → `kich-ban.json` (mẫu `references/kich-ban-mau.json`; ví dụ thật đã ra video, đủ `loai_khung`,
   `anh_sang`, `loi_doc`, thẻ đầu/kết, 2 bài nhạc: `references/vi-du-that-con-so-tren-tuong-v1.json`). Viết theo
   `references/viet-loi-binh.md` (chuyện cụ thể, không quảng cáo/dạy đời, đếm từ ra thời lượng).
   **Chốt kịch bản xong mới làm hình** — làm ảnh trước rồi sửa kịch bản từng phải làm lại 7 ảnh. Mỗi cảnh: `loi`,
   `mo_ta_hinh` có **cầu nối** với cảnh trước, `nhan_vat`, `boi_canh`, `noi_tiep`, `chuyen`.
   Kiểu **ảnh → kể chuyện** (`"kieu":"anh"`) hay **clip → ghép** (`"kieu":"clip"`). ⛳ duyệt kịch bản.
2. **Bộ nhân vật + bối cảnh** — xem `references/nhat-quan-va-noi-canh.md`. Có bộ hợp trong
   kho `<KHO>/` → hỏi dùng lại. Chưa có → tạo ảnh tham chiếu từng
   nhân vật/bối cảnh, lưu bộ. ⛳ duyệt ảnh nhân vật + bối cảnh.
3. **Chọn giọng — BẮT BUỘC hỏi, không tự chọn.** Menu `references/nguon-giong.md`
   (chỉ giọng free nghe tự nhiên ở đầu). Người mới: tạo mẫu 1 câu cho 2–3 giọng để nghe. ⛳
4. **Thử 1–2 cảnh**: `python scripts/ghep-prompt.py kich-ban.json` → `prompts.json`;
   tạo hình cảnh 01 và một cảnh `noi_tiep` theo `references/nguon-hinh.md`. ⛳ duyệt độ giống
   + độ mượt trước khi tốn lượt cho cả loạt.
5. **Hạn mức free — kiểm TRƯỚC khi bắn cả loạt.** Mỗi nguồn web free đều có trần lượt/ngày (ChatGPT free hết lượt ảnh
   rất nhanh; Gemini giọng ~3 lượt/phút + trần ngày). Bắn **1 lượt** trước, ra ảnh rồi mới bắn tiếp. Lượt nào quá 150s mà
   chưa xong → `stop_run`, `open_page` trang đó + `snapshot_page` xem có thông báo hết lượt ("limit", "hết lượt", "upgrade")
   không; hết thì **dừng mọi lượt đang xếp hàng của nguồn đó** và đổi nguồn (Dola free), đừng chờ tiếp. Ca thật 15/10/2026:
   ChatGPT hết lượt, 4 lượt xếp hàng treo ~6 phút, người dùng phải nhắc "chatgpt hết limit rồi bạn ko biết hả".
   **Tạo hết hình**: mở **tab gác cổng** (`open_page`) rồi chạy **2 tab song song trên profile đã login**,
   bắn cách nhau ~15–20s, ảnh tham chiếu đặt trong thư mục kho (GaBee không đọc thư mục dự án), canh bằng
   `scripts/canh-anh-muse.sh` (báo ảnh mới **và** báo `IM-LANG` khi 150s không có ảnh — monitor chỉ báo ảnh
   mới thì lượt treo im lặng, agent ngồi chờ không hay), quá 150s thì `stop_run` — chi tiết đo thật ở `references/nguon-hinh.md` mục "Chạy nhanh, không treo".
   Dùng cho cả bước ② (nhân vật/bối cảnh), đừng nối đuôi từng ảnh.
   Clip: lấy khung cuối ngay sau khi tải (lệnh trong nhat-quan-va-noi-canh.md). Ghép ảnh
   lưới xem một lần, cảnh lệch thì tạo lại riêng cảnh đó. ⛳
   **Clip có giọng sẵn (Flow/Veo)** → làm theo `references/clip-co-giong-san.md` (không theo bước 6–7 bên dưới): **bắt buộc nối khung**
   giữa các cảnh liền mạch, khoá vị trí trái/phải trong prompt, phản ứng đến SAU lời, kiểm từng clip (dải khung + `scripts/do-cao-do-giong.py`)
   trước khi ghép bằng `scripts/dung-clip-co-giong.py`. Nguồn: video "thành công nhân" 15/10/2026 — bỏ qua các bước này thì làm lại 3 lần.
6. **Giọng**: `python scripts/giong.py kich-ban.json` (Vbee/tự thu: `"nguon":"file"`, thả
   `giong/<id>.mp3`; sửa một câu: xoá file đó rồi chạy lại).
   **Kiểm giọng**: `python scripts/kiem-giong.py kich-ban.json` — máy nghe lại, báo cảnh đọc thiếu/sai.
   **Nháp**: `python scripts/dung-video.py kich-ban.json --nhap` → ⛳ gửi người dùng xem.
7. **Bản thật**: `python scripts/dung-video.py kich-ban.json` → `video.mp4`.
   **Báo tiến độ khi dựng (cả nháp lẫn thật):** chạy nền, ghi log, rồi canh bằng
   `Monitor(command="tail -n0 -F dung.log | grep --line-buffered -E 'Bước|XONG|Error|Traceback'")` và báo
   người dùng từng mốc: "Bước 1/3 · dựng cảnh 9/19 (47%)", "Bước 2/3 · nối cảnh 60%", "Bước 3/3 · trộn tiếng + phụ đề 90%".
   Báo trước thời lượng ước tính: video 4 phút 1080p mất ~13 phút (đo 12/10/2026: code cũ 18 phút). Đừng im lặng chờ — người dùng từng
   phải hỏi "render lâu thế, tới đâu rồi" (video "Con số trên tường" v1, 12/10/2026).
   Hỏi: lưu kịch bản này làm **khuôn** vào bộ (`<bo>/khuon/<ten>.json`) để lần sau làm
   tiếp tập mới chỉ cần đổi lời + hành động.

## Tiết kiệm token

- Không đọc lại script; chỉ sửa `kich-ban.json` rồi chạy lại.
- Chỉ đọc file reference của nguồn đã chọn.
- Kiểm hình bằng **một** ảnh ghép 3 khung, không đọc từng frame:
  `ffmpeg -i video-nhap.mp4 -vf "select='eq(n\,30)+eq(n\,200)+eq(n\,420)',scale=240:-1,tile=3x1" -frames:v 1 -fps_mode passthrough khung.png`
  (ffmpeg bản mới đã bỏ `-vsync` — "Unrecognized option 'vsync'", máy Windows 15/10/2026)

## Khoá trong kich-ban.json

| Khoá | Ý nghĩa | Mặc định |
|---|---|---|
| `khung` | `[1080,1920]` dọc · `[1920,1080]` ngang | 9:16 |
| `tieu_de`, `tieu_de_giay` | tiêu đề vàng trên nền đen, đầu video | không có · 3s |
| `giong` | `{nguon, ten, toc_do, phong_cach, model}` — xem nguon-giong.md | edge |
| `nhac`, `nhac_lufs` | file nhạc nền; độ to đích (đo LUFS bài nhạc rồi tự bù, sau đó tự hạ khi có giọng) | không · -30 |
| `sfx_mo_dau`, `sfx_chuyen_canh`, `sfx_db` | tên tiếng động (kho bên dưới) hoặc đường dẫn | không · không · -14 |
| `phu_de` | `{bat, so_chu, co, cao, chu_hoa, mau, font}` | bật · 4 chữ/cụm · 84 · 0.27 |
| `dem`, `vao` | giây nghỉ sau mỗi câu · giây chờ đầu cảnh rồi mới đọc (để không đè lúc chuyển cảnh) | 0.35 · 0.3 |
| `chuyen_mac_dinh`, `canh[].chuyen` | chuyển cảnh: `cat` `hoa` `den` `trang` `truot` `truot-len` `zoom` `tron` | hoa |
| `canh[].chuyen_dong` | ảnh tĩnh: `vao` `ra` `trai` `phai` `len` `xuong` `dung` (ảnh có chữ cần đọc) | xoay vòng vao→phai→ra→trai |
| `canh[].giay` | độ dài cảnh không lời (hoặc kéo dài cảnh có lời) | 3 |
| `canh[].giu_tieng` | giữ tiếng gốc clip khi cảnh không có `loi` (clip Muse có thoại) | false |
| `phong_cach` | một câu phong cách dán vào MỌI prompt ảnh (ghi đè `bo.json`) | tự chọn theo thể loại (dao-dien-tu-dong.md §2) |
| `canh[].loai_khung`, `canh[].anh_sang` | khung hình + giờ/nguồn sáng của cảnh, đi thẳng vào prompt ảnh bởi `ghep-prompt.py` | xoay vòng toàn/trung/cận/qua vai |
| `the_dau`, `the_ket` | thẻ tiêu đề/kết: `{hinh, dong:[…], phu, giay}`, ảnh cảnh làm tối + chữ serif | — (nên luôn có) |
| `nhac` | một file, hoặc **danh sách 2 bài** nối crossfade 4s, mỗi bài đưa về `nhac_lufs` | — (nên luôn có, -31) |
| `phu_de.srt` | xuất `video.srt` đi kèm | true. Khổ ngang: chữ 50px, cách đáy 7%; khổ dọc 84px, 27% |
| `canh[].loi_doc` | lời **kèm thẻ cảm xúc** `[warm] [slowly]…` chỉ để máy đọc (Soniox); `loi` giữ sạch cho phụ đề. Thiếu thì đọc `loi` (video "Con số trên tường" 12/10/2026: nhét thẻ vào `loi` thì thẻ hiện lên phụ đề) | = `loi` |
| `canh[].sfx` | tiếng động riêng cho cảnh này | theo chung |

Tiếng động có sẵn (kho media-use): `whoosh`, `whoosh-short`, `whoosh-cinematic`,
`impact-bass-1`, `impact-bass-2`, `riser`, `pop`, `sparkle`, `chime`, `ping`, `click`,
`glitch-1..3`, `typing`, `notification`.

## Nhạc nền free

- **Pixabay Music**: không cần ghi công. **Kevin MacLeod (incompetech.com)**: CC BY 4.0, **bắt buộc ghi công**
  ("<Tên bài> — Kevin MacLeod (incompetech.com), CC BY 4.0") vào mô tả video.
- Nhiều bài nhạc trong một video: script đo LUFS từng bài — hai bài từng lệch 12 LU làm nửa sau gần như tắt tiếng.

## Bẫy đã gặp

- **Windows — ghi `kich-ban.json` bằng công cụ Write/Edit của agent hoặc Python, ĐỪNG bằng PowerShell** (`Set-Content`,
  heredoc trong file .ps1): PowerShell 5.1 đọc tiếng Việt trong .ps1 không BOM thành chữ rác → phụ đề ra "Viá»‡t".
  Script của skill đọc JSON được cả khi có BOM (utf-8-sig). Đo trên máy Windows thật 15/10/2026.
- **Windows — dựng video**: đường dẫn `C:\…` trong bộ lọc ffmpeg phải đổi `/` và thoát dấu `:` hai lớp (`loc_path`
  trong dung-video.py); thiếu là "No option name near '/Windows/Fonts'". Đã sửa 15/10/2026.
- **Tiếng động** (`sfx_*`) lấy từ skill media-use — máy không có thì skill bỏ qua tiếng đó và dựng tiếp.

- **Ảnh chuyển động bị giật** (bản DeepSeek "Những con số trên tường"): zoompan ffmpeg làm tròn toạ độ →
  nhích bậc. Đã thay bằng Pillow tính toạ độ lẻ + chuyển động có đà: giật 0,22 → 0,07, nhanh gấp 8.
- **Tiêu đề bị giật**: chữ vẽ vào ảnh rồi cho zoom theo → chữ rung. Chữ luôn là lớp phủ ASS đứng yên,
  không bao giờ đi qua bước chuyển động.
- Âm thanh ra **96 kHz** do `loudnorm` → script ép 48 kHz. `loudnorm` chỉ trên nhánh giọng, không cả bản trộn.
- Giọng lệch dần về cuối phim nếu quên trừ phần chồng chuyển cảnh → script tự tính mốc.

- Edge TTS thỉnh thoảng trả "No audio received" → `giong.py` tự thử lại 3 lần và
  không để lại file rỗng.
- Flow `vbee-tts` từng tải nhầm file của lần chạy trước (dòng cũ vẫn ghi "Vừa xong") →
  đã sửa 12/10/2026 (đánh dấu dòng cũ trước khi tạo). Thấy 2 file giọng giống hệt thì kiểm md5.
- Phụ đề chia theo độ dài chữ trong khoảng giọng đọc, không nghe máy → câu có khoảng
  ngừng dài thì lệch nhẹ; tách thành 2 cảnh nếu cần khớp chặt.
- **Phụ đề/thẻ kết tĩnh trông "rẻ"**: dùng HyperFrames — phụ đề động (chữ bật từng từ, `{Y:CHỮ}` vàng to nảy) là lớp WebM nền trong suốt
  (`scripts/dung-clip-co-giong.py --phu-de hyperframes`, mẫu `assets/phu-de-hyperframes/`), thẻ kết `scripts/the-ket-hyperframes.sh`.
  Nguồn: video "thành công nhân" 15/10/2026, người dùng chê thẻ kết "xấu lắm" và gợi ý HyperFrames.
- **Font thiếu dấu tiếng Việt** (Arial Rounded Bold, Trebuchet): chữ ra "v?t", "?i". Dùng Tahoma Bold/Arial Bold và render thử "ơ ấ ạ ở ự" trước.
- **Muse không nhận ảnh đính kèm** (báo "ảnh chưa đồng bộ") → tự lấy ảnh cũ, đổi người giữa các cảnh. Cần nhân vật cố định: ảnh khung đầu + Flow (`clip-co-giong-san.md`).
