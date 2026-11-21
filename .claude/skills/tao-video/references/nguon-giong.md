# Nguồn giọng — menu hỏi người dùng (free tự nhiên xếp đầu)

Khoá API lưu/kiểm bằng `scripts/khoa.py` (file `~/.tao-video/.env`, không dán khoá vào chat). Nghe thử một giọng: `scripts/giong-mau.py <nguon> [ten]`.

Gợi ý cho người mới: **ElevenLabs** (free 10.000 ký tự/tháng) hoặc **OpenAI** (nạp 5 USD) — khoá lấy nhanh, giọng tự nhiên, cùng khoá làm luôn giọng → chữ. Gemini free nhưng chỉ ~3 lượt/phút. Link lấy khoá: `python scripts/khoa.py kiem`.

Luật: **luôn hỏi**, chỉ đưa giọng free **nghe tự nhiên**. Giọng nghe như robot thì bỏ
khỏi menu chính dù free (ý người dùng 10/2026).

| # | Nguồn | Cách gọi | Free | Ghi chú |
|---|---|---|---|---|
| 1 | **Gemini TTS** | API · `"nguon":"gemini"` | free tier, cần `GEMINI_API_KEY` | Tự nhiên, chỉnh được cách đọc qua `phong_cach`. Giọng: `Kore` (nữ, ấm), `Aoede` (nữ, nhẹ), `Charon` (nam, trầm), `Puck` (nam, tươi). Bản free Google có thể dùng dữ liệu để cải thiện → kịch bản nhạy cảm thì đừng dùng. |
| 2 | **Vbee web** | GaBee flow `vbee-tts` → `"nguon":"file"` | 3.000 ký tự/ngày | Giọng Việt bản xứ, có miền Bắc/Nam/Huế. Dùng giọng "nâng cao (Beta)": Ngọc Huyền, Anh Khôi, Tường Vy, Hương Giang… [VIP] bị khoá. Profile GaBee đã đăng nhập Vbee. |
| 3 | **Soniox** (giọng `Linh`) | API · `"nguon":"soniox"` | trả phí rẻ, cần `SONIOX_API_KEY` | Đọc tiếng Việt chuẩn, có **thẻ cảm xúc** chèn vào lời: `[warm]` `[sad]` `[calm]` `[excited]` `[slowly]`… Thẻ phải viết **tiếng Anh**, tối đa 2 thẻ trước một cụm, thẻ lạ sẽ bị đọc thành tiếng → chạy `kiem-giong.py`. Dự án "Những con số trên tường" dùng giọng này, người dùng khen. |
| 3b | OpenAI `gpt-4o-mini-tts` (`nova`) | API · `"nguon":"openai"` | trả phí, cần `OPENAI_API_KEY` | Điều cảm xúc qua `phong_cach` (instructions). Chữ tiếng Anh như "code" đọc lệch → viết "dòng lệnh". **Đừng dùng `tts-1-hd`**: đọc thiếu chữ. |
| 4 | ElevenLabs | API · `"nguon":"eleven"`, `"ten"`: voice_id (mặc định `SAz9YHcvj6GT2YYXdXww`; tìm giọng khác ở elevenlabs.io → Voices, chép Voice ID), model `eleven_turbo_v2_5` + `language_code: vi` (multilingual_v2 KHÔNG có tiếng Việt — đọc sai, đo 15/10/2026) | free 10.000 ký tự/tháng, **không thương mại** | Cần `ELEVENLABS_API_KEY`. Giọng tự nhiên nhất nhóm trả phí, đọc tiếng Việt được |
| 5 | Tự thu / nguồn khác | `"nguon":"file"` | — | Thả `giong/<id>.mp3`. |
| – | Edge TTS (Microsoft) | `"nguon":"edge"` | free, không key | `vi-VN-HoaiMyNeural`, `vi-VN-NamMinhNeural`. Chỉ dùng làm **giọng nháp** để canh nhịp nếu người dùng chê robot. |

## Gemini — ví dụ

```json
"giong": {"nguon": "gemini", "ten": "Kore", "phong_cach": "Đọc tự nhiên, ấm áp như người Việt kể chuyện"}
```
Model mặc định `gemini-3.8-flash-tts`. Gemini đọc chậm hơn Edge/Vbee ~40% → video dài hơn.

## Vbee qua GaBee — tạo từng cảnh

Gọi tuần tự, mỗi cảnh một lần, `filename` = id cảnh, rồi chép về `giong/`:

```
run_flow("vbee-tts", profile_id=<profile đã login Vbee>, headless=true,
         vars={"text": "<loi cảnh 01>", "voice": "Ngọc Huyền nâng cao (Beta)", "speed": "1.05", "filename": "01"})
→ output.audio_path = <Downloads>/vbee-tts/01.mp3  →  cp vào du-an/giong/01.mp3
```
Tốc độ 1.05–1.1 hợp lồng tiếng video ngắn. 

## Kiểm giọng — bắt buộc trước khi dựng

`python scripts/kiem-giong.py kich-ban.json` — máy nghe lại từng file (qua `chu-tu-giong.py`), so với lời gốc,
báo cảnh dưới 0,85. Bắt được đọc thiếu chữ, đọc sai, thẻ cảm xúc lọt thành tiếng. Tên riêng/từ tiếng Anh hay bị
nghe sai → tự nghe lại cảnh bị báo trước khi tạo lại.

## Giọng → chữ có mốc thời gian (phụ đề, chia cảnh)

`python scripts/chu-tu-giong.py <file mp3/mp4> [--nguon …]` → `<tên>.chu.json` (từng từ + từng câu, giây) và `<tên>.srt`.
Cần khi lời nói KHÔNG do `giong.py` sinh ra: giọng tự thu, clip có thoại sẵn (Flow/Veo/Muse), video có sẵn cần phụ đề,
hoặc muốn chia cảnh theo câu. Giọng TTS của skill thì `dung-video.py` đã tự căn.

| Nguồn | Khoá | Đo thật 15/10/2026 (11,7s giọng Việt) |
|---|---|---|
| **Soniox** (`stt-async-v5`) | `SONIOX_API_KEY` | 7,2s · đúng hết chữ + dấu câu · mốc từng từ — **khuyên dùng** |
| OpenAI (`whisper-1`) | `OPENAI_API_KEY` | 4,2s · đúng chữ nhưng mất dấu câu · mốc từng từ |
| ElevenLabs (Scribe v2) | `ELEVENLABS_API_KEY` | **1,1s** · đúng hết chữ + dấu câu · mốc từng từ (đo 15/10/2026) — nhanh nhất |
| Gemini (`gemini-2.5-flash`) | `GEMINI_API_KEY` (free tier) | 5,5s · đúng hết · mốc theo CÂU, từ chia đều — đủ cho phụ đề cụm |
| whisper chạy trên máy | — | 17,8s · sai 3 chữ ("ông vàng", "chít lá") · **chỉ dùng khi máy đã có, ĐỪNG cài** (nặng hàng GB) |

Bỏ `--nguon` thì script tự chọn theo thứ tự trên, theo khoá đang có. Soniox xoá file ghi âm khỏi máy chủ ngay sau khi chép.

## Thêm nguồn mới

API: thêm một hàm `tts_<ten>()` vào `scripts/giong.py` + một dòng bảng trên.
Web: dựng flow GaBee trả về `audio_path`, dùng như Vbee (`"nguon":"file"`).
