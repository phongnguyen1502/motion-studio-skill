# /tao-video setup — cài đặt + kiểm tra nguồn trước khi làm video

Mục tiêu: máy dựng được video, và có **ít nhất MỘT nguồn chạy được cho mỗi loại**:

| Loại | Bắt buộc? | Kiểm tới mức nào là ✅ |
|---|---|---|
| **Hình** (ảnh) | có (trừ khi người dùng tự có ảnh) | đã đăng nhập + tạo được 1 ảnh (hoặc gọi API ra ảnh) |
| **Giọng** | có (trừ video không lời) | tạo được **1 câu mẫu** và người dùng đã NGHE |
| **Video** (clip AI) | không — thiếu thì làm kiểu "ảnh → kể chuyện" | đã đăng nhập + **gửi được lệnh**. KHÔNG chờ clip ra (mất vài phút) |
| **Giọng → chữ** (mốc thời gian) | không — cần khi dùng giọng tự thu / clip có thoại sẵn | chép đúng câu giọng mẫu, có mốc từng từ |

Chạy **từng bước, dừng ở bước chưa ✅**, nói người dùng cần làm gì bằng lời đơn giản. Người dùng
không biết kỹ thuật: lệnh nào mình tự chạy được thì tự chạy, đừng bắt họ gõ.
`SKILL_DIR` = thư mục chứa SKILL.md này (Claude Code: `~/.claude/skills/tao-video`; agent khác: nơi đã cài).

## Bước 1 — Máy (không cần tài khoản)

```bash
python SKILL_DIR/scripts/kiem-moi-truong.py
```
Đồ nghề có thể đã được cài ngầm ở Prompt 1 workshop (`~/.gabee/cong-cu-video.log`). Bảng còn ❌ thì **cài luôn,
không hỏi lại** nếu người dùng đã đồng ý cài đồ nghề ở Prompt 1 (hoặc đã nói "cài luôn"); chưa đồng ý thì hỏi MỘT
lần cho cả lô. Cần: Python ≥ 3.9, Pillow, ffmpeg có libass, edge-tts **bản mới** (`pip install -U edge-tts` — bản
cũ bị Microsoft trả 403), thư mục kho `~/Downloads/tao-video-kho`. **Không cài whisper** (nặng hàng GB).
- Windows: `winget install --id Gyan.FFmpeg -e --silent --accept-source-agreements --accept-package-agreements`,
  rồi nạp lại PATH trong cùng cửa sổ: `$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')`.
  `winget install ffmpeg` (không `--id`) có thể hỏi chọn gói → treo.
- pip `--user` để lệnh `edge-tts` ngoài PATH: không sao, `giong.py` tự gọi `python -m edge_tts`.
Rồi dựng thử không cần mạng AI:

```bash
python SKILL_DIR/scripts/kiem-moi-truong.py --thu-dung
```
Mở `video.mp4` vừa ra cho người dùng xem có tiếng + phụ đề + chuyển cảnh không. ✅ = khâu dựng ổn.

## Bước 2 — GaBee + flow

| Kiểm | Cách | ❌ thì |
|---|---|---|
| Agent nối được GaBee | gọi `get_status(intent="tạo ảnh")` | "Mở app GaBee" · lỗi token → app GaBee → Cài đặt → API → bật "Cho phép agent kết nối" · không có tool `gabee` → cắm MCP (Prompt 1 của workshop / `gabee agent setup`) rồi **khởi động lại agent** |
| Có profile | kết quả `get_status` có ≥ 1 profile | bảo người dùng tạo 1 profile trong app (Hồ sơ → Tạo) |
| Có flow cần dùng | `list_flows(query="muse")`, `"gemini"`, `"vbee"`… | thiếu flow nào thì cài từ bộ workshop: đọc file `flows/<id>.json` rồi `save_flow(<id>, <nội dung>)` |

Thư mục kho nằm trong `~/Downloads` nên GaBee đọc được ảnh tham chiếu ở đó. **Đừng** để ảnh tham chiếu
trong thư mục dự án ngoài Downloads/Documents/Desktop/Pictures — GaBee chặn (400 `path_not_allowed`).

## Bước 3 — Hỏi người dùng chọn nguồn (MỘT lần, gộp ba câu)

Đưa menu, nói rõ cái nào free. Người dùng chọn được nhiều nguồn mỗi loại.

**Hình**
| Nguồn | Cách | Free | Trang đăng nhập |
|---|---|---|---|
| **Dola** | flow `dola-image` | **free, nhiều lượt** — khuyên dùng cho người mới (~55s/ảnh, giữ nhân vật tốt, ra đúng 9:16) | https://www.dola.com/chat/ |
| ChatGPT | flow `chatgpt-image-v2` | tài khoản free hết lượt ảnh rất nhanh | https://chatgpt.com |
| Gemini | flow `gemini-image` | free có hạn mức | https://gemini.google.com/app |
| Muse | flow `muse-image` | theo gói Muse | https://muse.ai/thread/new |
| Gemini API / OpenAI API | `scripts/anh-api.py` | Gemini có thể free tier; OpenAI trả phí | — cần khoá |
| Ảnh có sẵn | chép vào `canh/` | — | — |

**Giọng** — bảng đầy đủ ở `nguon-giong.md`.
| Giọng | Free? | Lấy khoá (đăng ký xong là về đúng trang tạo khoá) | Ghi chú |
|---|---|---|---|
| **ElevenLabs** | free 10.000 ký tự/tháng (không thương mại) | https://elevenlabs.io/app/sign-up → https://elevenlabs.io/app/settings/api-keys | tự nhiên nhất; cùng khoá làm luôn giọng → chữ |
| **OpenAI** (`gpt-4o-mini-tts`) | trả phí, nạp tối thiểu 5 USD (đủ hàng trăm video ngắn) | https://platform.openai.com/api-keys · nạp: https://platform.openai.com/settings/organization/billing | điều cảm xúc bằng lời dặn; cùng khoá làm luôn giọng → chữ + ảnh |
| Edge | free, không cần khoá | — | nghe hơi máy, dùng nháp hoặc khi chưa có khoá |
| Gemini TTS | free nhưng ÍT lượt (~3 lượt/phút, giới hạn ngày) | https://aistudio.google.com/apikey | skill tự chờ khi hết lượt, video nhiều cảnh sẽ chậm |
| Vbee web | free 3.000 ký tự/ngày | đăng nhập https://studio.vbee.vn trong GaBee | giọng Việt bản xứ |
| Soniox | trả phí rẻ | https://console.soniox.com | tiếng Việt chuẩn, thẻ cảm xúc |

**Giọng → chữ** (tuỳ chọn, cho phụ đề/chia cảnh từ giọng có sẵn, chép lời bài hát làm MV): Soniox (chính xác nhất) ·
OpenAI · ElevenLabs · Gemini. Dùng chung khoá với giọng ở trên — có khoá ElevenLabs hoặc OpenAI là có cả giọng lẫn chữ.

**Video** (tuỳ chọn)
| Nguồn | Flow | Trang đăng nhập |
|---|---|---|
| **Dola** (free) | `dola-video` | https://www.dola.com/chat/ |
| Muse | `muse-video` (có `submit_only`) | https://muse.ai/thread/new |
| Google Flow (Veo) | `google-flow-veo3`, `google-flow-anh-thanh-video` | https://flow.google.com/ |
| Gemini | `gemini-video` | https://gemini.google.com/app |
| Meta AI | `meta-ai-video` | https://www.meta.ai/ |

## Bước 4 — Khoá API (chỉ khi người dùng chọn nguồn cần khoá)

**Không bảo người dùng dán khoá vào ô chat** (khoá nằm lại trong lịch sử). Thay vào đó:
1. Chỉ chỗ lấy khoá (in ra bởi `khoa.py kiem`), bảo họ **copy** khoá.
2. Mình chạy `python SKILL_DIR/scripts/khoa.py luu GEMINI_API_KEY` — script đọc clipboard, ghi vào
   `~/.tao-video/.env` (0600), chỉ in độ dài + 4 ký tự cuối.
3. `python SKILL_DIR/scripts/khoa.py kiem` — gọi thử rẻ nhất (liệt kê model), báo ✅/❌ từng khoá.

## Bước 5 — Kiểm từng nguồn đã chọn

**Nguồn web (qua GaBee) — kiểm đăng nhập trước, rồi mới chạy flow:**
1. `open_page(url=<trang đăng nhập>, profile_id=<profile>, headless=false)` → giữ `tab_id`.
2. `snapshot_page(tab_id)`: thấy nút "Log in / Đăng nhập / Sign in" hoặc màn chọn tài khoản → bảo người
   dùng **tự đăng nhập trong cửa sổ vừa mở** (mình không nhập mật khẩu, không vượt captcha), chờ họ nói
   "xong", snapshot lại. Thấy ô soạn thảo/ô prompt và không có nút đăng nhập → ✅ đã đăng nhập.
   Một trang ChatGPT có cả ô nhập LẪN nút "Log in" = **chưa** đăng nhập.
3. `close_tab(tab_id)` khi xong (trừ khi sắp chạy loạt ảnh — giữ làm tab gác cổng).

**Hình web — tạo 1 ảnh thật** (bỏ qua nếu Prompt 1 đã tạo ảnh đầu tiên bằng nguồn này):
```
run_flow("<flow ảnh>", profile_id=<profile>, headless=false, wait=false,
         vars={"prompt": "một cậu bé cầm quả bóng đỏ, hoạt hình màu nước, nền kem trơn, không chữ"})
→ get_run_status(run_id) mỗi ~20s tới khi xong; quá 150s → stop_run, thử lại 1 lần
```
✅ khi `output.media_result` có đường dẫn ảnh và mở ra được → chép vào `~/Downloads/tao-video-kho/_thu/`.

**Hình API:** `python SKILL_DIR/scripts/anh-api.py thu gemini` (hoặc `openai`) — tốn 1 lượt, ra
`_thu/anh-api-<nguon>.png`. Gemini lỗi 429 = hết hạn mức free, không phải khoá sai.

**Giọng — luôn cho NGHE:**
```bash
python SKILL_DIR/scripts/giong-mau.py edge                 # free, không key
python SKILL_DIR/scripts/giong-mau.py gemini Kore          # Kore nữ ấm · Charon nam trầm · Puck nam tươi
python SKILL_DIR/scripts/giong-mau.py openai nova | eleven <voice_id> | soniox Linh
```
Script tự mở file mp3. Rồi kiểm luôn **giọng → chữ** trên chính file đó (nếu có khoá Soniox/OpenAI/Gemini):
`python SKILL_DIR/scripts/chu-tu-giong.py ~/Downloads/tao-video-kho/_thu/giong-<nguồn>.mp3` → ✅ khi chép ra đúng câu.
Vbee: `run_flow("vbee-tts", profile_id=…, headless=false, vars={"text": "Xin chào, đây là
giọng thử.", "voice": "Ngọc Huyền nâng cao (Beta)", "filename": "thu"})` → mở `output.audio_path`.
Hỏi người dùng thích giọng nào; ✅ khi họ đã nghe và chọn.

**Video — chỉ kiểm gửi được lệnh, KHÔNG chờ clip:**
- Muse: `run_flow("muse-video", profile_id=…, headless=false, vars={"prompt": "một chú mèo vươn vai bên cửa sổ, 5 giây", "submit_only": true})`
  → ✅ khi run xong `ok` (lệnh đã gửi, Muse đang làm — không cần chờ).
- Nguồn khác: kiểm đăng nhập như trên (thấy ô prompt là ✅). Không chạy flow video thật ở bước setup.

## Bước 6 — Chốt

Ghi `~/Downloads/tao-video-kho/setup-ok.json`:
```json
{"ngay": "<hôm nay>", "may": "ok", "dung_thu": "ok", "gabee": "ok", "profile": "<id>",
 "nguon_anh": ["chatgpt"], "nguon_giong": ["edge", "gemini:Kore"], "nguon_video": ["muse"],
 "giong_mac_dinh": "gemini:Kore", "chu_tu_giong": "soniox", "khoa": ["GEMINI_API_KEY"]}
```
In bảng tổng, ví dụ:
```
✅ Máy + dựng thử      ✅ GaBee + profile Cloak1
✅ Hình: ChatGPT (đã tạo ảnh thử)        ➖ Hình API: chưa có khoá
✅ Giọng: Gemini Kore (đã nghe), Edge    ✅ Video: Muse (gửi lệnh được)
→ Sẵn sàng. Dán kịch bản (hoặc ý tưởng) và gõ  /tao-video
```
Còn ❌ ở loại bắt buộc thì nói rõ làm gì để sửa, **đừng bảo "xong"**.

## Luật khi chạy setup

- Không nhập mật khẩu, không đăng nhập hộ, không vượt captcha — chỉ mở trang cho người dùng tự làm.
- Cài phần mềm (`pip`, `brew`, `winget`): người dùng đã đồng ý ở Prompt 1 thì cài luôn; chưa thì hỏi một lần cả lô.
- Mỗi bước ≤ vài phút; flow treo quá 150s thì `stop_run` và báo.
- Đã có `setup-ok.json` mà người dùng gõ lại: chỉ chạy lại bước 1 + 2 (kiểm nhanh), không tạo lại ảnh/giọng
  thử trừ khi họ muốn hoặc muốn thêm nguồn mới.
- Lỗi thường gặp:

| Lỗi | Nghĩa | Xử lý |
|---|---|---|
| `path_not_allowed` / "chưa được phép đọc file" | ảnh tham chiếu ngoài thư mục được phép | để ảnh trong `~/Downloads/tao-video-kho`, hoặc GaBee → Cài đặt → Thư mục được phép |
| `not_authenticated` | profile chưa đăng nhập trang đó | mở trang (`open_page`), người dùng tự đăng nhập |
| `blocked` | màn Cloudflare "Just a moment" (hay gặp khi chạy ẩn) | chạy `headless=false` |
| `ui_changed` | trang đổi giao diện, selector của flow không khớp | báo người dùng + giảng viên; dùng nguồn khác trong lúc chờ sửa flow |
| `type_failed` | không gõ được vào ô chat (chưa login hoặc chạy ≥ 3 tab cùng lúc) | kiểm login; chỉ chạy 2 tab |
| `browser has been closed` | browser hết tab nên bị đóng | mở tab gác cổng (`open_page`), đừng đóng cửa sổ |
| `run_quota_exceeded` | hết lượt chạy trong ngày của gói | đăng nhập GaBee / nâng gói |
| edge-tts 403 | edge-tts cũ | `pip install -U edge-tts` |
