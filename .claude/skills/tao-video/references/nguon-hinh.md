# Nguồn hình — flow GaBee có sẵn

Đều cần `profile_id` đã đăng nhập (gọi `list_profiles`, hỏi người dùng nếu chưa rõ).
Lấy đường dẫn file từ `output` / `output_paths`, chép về `canh/<id>.png|mp4`.
Xem tham số đầy đủ bằng `get_flow(id)` khi lần đầu dùng.

## Chạy nhanh, không treo (đo thật 12/10/2026, video "Con số trên tường", Muse + Cloak1)

Một video 4 nhân vật + 4 bối cảnh + 17 cảnh từng mất hơn nửa tiếng vì treo và chạy nối đuôi.

| Việc | Cách làm | Nguồn đo |
|---|---|---|
| **Số tab** | **2 tab song song trên 1 profile**: 2 ảnh xong trong ~60–86s (nối đuôi: 2 × ~90s). 3 tab: 1/3 lượt lỗi `type_failed` → dùng 2 | 12/10/2026, 2 lần chạy 2 tab đều ra ảnh |
| **Chỉ có 1 profile đăng nhập** | Dùng đúng profile đó, đừng mở profile khác (không có phiên đăng nhập) | người dùng chỉ login Cloak1 |
| **Tab gác cổng (quan trọng nhất)** | Trước khi chạy loạt ảnh: `open_page` mở 1 tab `https://muse.ai/thread/new` trên profile và **giữ nguyên suốt loạt** (chiếm 1/3 chỗ, còn đúng 2 chỗ cho 2 lượt). Không có tab này, khi lượt trước vừa xong và đóng tab, browser hết tab → log worker ghi `hot pool: đóng browser ... (hết tab)` → mọi lượt đang khởi động chết `browser has been closed` ở giây 8–15 (thấy 5 lần). Có tab gác cổng thì 2 lượt liền sống và ra ảnh. Xong loạt thì `close_tab` | 12/10/2026, log `~/Library/Application Support/com.beeflow.app/logs/worker.log` |
| **Bắn 2 lượt** | Cách nhau ~15–20s; kiểm lượt 1 còn `running` rồi bắn lượt 2 | 12/10/2026 |
| **Thư mục được phép** | GaBee chỉ đọc ảnh tham chiếu trong thư mục đã cho phép (Cài đặt → "Thư mục được phép"). Để ảnh cảnh trong `~/Downloads/tao-video-kho/<bo>/canh/`, KHÔNG để trong thư mục dự án. Vi phạm → worker trả **400**, mà `run_flow wait=false` vẫn báo `started` rồi `get_run_status` ra `unknown` — mất 3 lượt, ~10 phút mới ra nguyên nhân. Nghi lỗi → chạy `wait=true` một lần để đọc lỗi thật, hoặc `grep run-flow worker.log` | 12/10/2026 |
| **Lẫn ảnh đính kèm giữa 2 tab** | Có lượt Muse tự báo "ảnh đính kèm lần này là ảnh của cảnh khác" (cảnh 11, 12) → cảnh 12 ra sai bối cảnh (máy CRT nhà quê thay vì văn phòng laptop). Nghi do 2 tab bắn sát nhau. Cách làm: **luôn ghép ảnh lưới soi cả loạt**; cảnh sai thì tạo lại riêng, **chạy một mình một tab**, ghi rõ "KHÔNG có <thứ sai>" trong prompt. Cảnh cần chính xác bối cảnh thì bắn lệch ≥ 30s | 12/10/2026, 2 lần thấy trong 17 cảnh |
| **Nối nhiều ảnh** | Cảnh nối: nhân vật + ảnh cảnh trước là đủ (ảnh cảnh trước đã chứa bối cảnh); bỏ ảnh bối cảnh để còn ≤ 3 ảnh đính kèm | 12/10/2026 |
| **Cắt sớm** | Lượt quá **150s** chưa ra ảnh → `stop_run` rồi chạy lại. Từng để treo 8 phút mới cắt | 12/10/2026 |
| **Canh ảnh — BẮT BUỘC dùng script** | `Monitor(command="bash ~/.claude/skills/tao-video/scripts/canh-anh-muse.sh", timeout_ms=1800000)`. Script in `NEW …` khi có ảnh và **`IM-LANG 150s` khi 150s không có ảnh nào** → gặp dòng này thì `get_run_status` mọi run đang chạy, quá 150s thì `stop_run` + bắn lại. Monitor chỉ báo ảnh mới là **không đủ**: lượt treo không sinh ảnh nên im lặng, agent tưởng đang chạy và ngồi chờ (bản v1 "Con số trên tường" 12/10/2026: cảnh 17 là lượt cuối, treo 4 phút, người dùng phải nhắc "bạn bị kẹt"). Monitor hết hạn 30 phút → bật lại nếu còn lượt. Đừng `get_run_status` lặp | 12/10/2026 v1 |
| **Muse hỏi lại / tạo hỏng, flow vẫn chờ 5 phút** | Flow `muse-image` chờ ảnh tới 5 phút kể cả khi Muse đã trả lời bằng chữ (hỏi lại) hoặc báo hỏng. Xem nguyên nhân thật: tab gác cổng → panel Activity của Muse ghi từng lượt (`Generation failed …`). `ghep-prompt.py` mở đầu mọi prompt bằng "Vẽ ngay 1 ảnh, không hỏi lại… ảnh đính kèm khác mô tả thì làm theo chữ"; viết prompt tay cũng phải có câu này | 12/10/2026 v1: 25/27 lượt ra ngay, 1 lượt `Generation failed` |
| **Ảnh tham chiếu mâu thuẫn mô tả → hỏng** | Cảnh "tường nay đã sơn lại trắng" mà đính ảnh bối cảnh tường cũ chi chít số → `Generation failed`. Bỏ ảnh bối cảnh, chỉ giữ ảnh nhân vật + tả chữ → ra sau 70s. Cảnh "nhiều năm sau / đã đổi khác" thì **không** đính ảnh bối cảnh cũ (để trống `boi_canh`) | 12/10/2026 v1 cảnh 17 |
| **Muse có trí nhớ xuyên thread** | Muse tự đặt tên nhân vật ("Minh", "Linh"), nhớ "ref đã chốt của series", hay báo "ảnh đính kèm không khớp" dù kết quả vẫn đúng (3/17 cảnh). Đừng tin lời Muse, **tin ảnh lưới**. Có thể kéo nhân vật dự án cũ sang → mỗi prompt luôn tả đủ nhân vật bằng chữ | 12/10/2026 v1 |
| **Đừng đóng cửa sổ** | Đóng cửa sổ Cloak1 (hoặc `close_browser`) khi đang chạy → mọi lượt chết `browser has been closed`. Quay màn hình thì dặn người dùng để yên cửa sổ | 12/10/2026 |
| **Xếp thứ tự** | Cảnh `noi_tiep` cần ảnh cảnh trước. Xếp các cặp: độc lập chạy cùng nhau, cảnh nối chạy sau cảnh gốc (vd 01+05 → 02+06 → 03+07) | 12/10/2026 |
| **Proxy** | Cờ `has_proxy` của `list_profiles` KHÔNG đáng tin (Cloak1 báo `false` mà thực có proxy). Xem thật trong `~/Library/Application Support/com.beeflow.app/beeflow-settings.json` (`proxyId`). Đo mạng trực tiếp (ping) không phản ánh đường qua proxy | 12/10/2026 |
| **Phần chưa kiểm chứng** | Nghi `type_failed` do tab tranh focus khi gõ cùng lúc; chưa đo lại riêng. Ảnh Muse ra 3:2 chứ không đúng 16:9 → cắt khi dựng | 12/10/2026 |

Ảnh nhân vật/bối cảnh: chạy 2 tab cho xong cả 8 ảnh trong khoảng 6 phút, đừng nối đuôi từng ảnh.

## Ảnh (kiểu "ảnh → kể chuyện")

| Flow | Hợp với | Ghi chú |
|---|---|---|
| **`dola-image`** | **free, nhiều lượt** — mặc định cho người mới; giữ nhân vật tốt khi đính ảnh tham chiếu, có `aspect_ratio` | ~55s/ảnh, 1600×2848 (đo 15/10/2026, 4/4 cảnh đạt). File lưu thẳng `~/Downloads/dola_*.png` (xem `output_paths`) |
| `gemini-image` | ảnh đời thường, sản phẩm, có ảnh tham chiếu | nhanh, không có tham số tỉ lệ → ghi "dọc 9:16" trong prompt |
| `chatgpt-image-v2` | chữ trong ảnh, minh hoạ, giữ nhân vật | có tham số tỉ lệ khung → đặt 9:16. Tài khoản free HẾT LƯỢT nhanh và flow không báo — chỉ thấy lượt treo (xem SKILL.md bước 5) |
| `muse-image` | phong cách điện ảnh | chờ tối đa 5 phút |
| API: `scripts/anh-api.py gemini "mô tả" canh/01.png --khung 9:16 --tham-chieu nv.png` (hoặc `openai`) | người dùng có khoá, không cần đăng nhập web | Gemini mặc định `gemini-3.1-flash-image`; OpenAI `gpt-image-1` (trả phí) |

**Kiểm kết quả:** flow có thể báo `ok` mà `media_result` rỗng → đọc `media_result.count/paths`,
mở thử ảnh bằng Pillow trước khi dùng.

### Mẹo prompt đã kiểm chứng (dự án "Những con số trên tường")

| Mẹo | Vì sao |
|---|---|
| Luôn có `no readable text, no watermark` (ghép-prompt đã tự thêm) | model hay vẽ chữ giả lên biển hiệu, sách |
| Màn hình máy tính: `with no legible words` | không thì ra chữ méo trông giả |
| Biểu cảm tiết chế: `calm thinking expression, not a dramatic gasp` | mặc định model vẽ cảm xúc quá lố |
| Tả ánh sáng + thời điểm: `late afternoon light rakes across the plaster` | ảnh có hồn hơn hẳn |
| **Cần chữ tiếng Việt trong ảnh** (tên trên tường, biển hiệu) | Muse không vẽ được (chạy 6 phút rồi `no_media`) → tạo ảnh không chữ, **ghép chữ thật bằng Pillow**. Font viết tay: Patrick Hand / DancingScript đủ dấu; Caveat, Bradley Hand **thiếu chữ ư** |
| Nhân vật nhiều độ tuổi | mỗi tuổi một mô tả cố định riêng trong bộ (vd `Minh-nho`, `Minh-lon`) |

Giữ nhân vật nhất quán: tạo 1 ảnh nhân vật trước, đính làm ảnh tham chiếu cho các cảnh sau.
Prompt luôn ghi rõ "khung dọc 9:16" (hoặc 16:9) để đỡ bị cắt mất chủ thể.

## Clip (kiểu "clip → ghép")

| Flow | Độ dài | Ghi chú |
|---|---|---|
| `google-flow-anh-thanh-video` | 10s, 720p, **có tiếng** | **Khuyên dùng khi cần nhân vật cố định**: ảnh khung đầu → clip, giữ đúng mặt/bối cảnh; profile đã đăng nhập Google Flow, ~100–120s/clip; dấu ✦ góc dưới phải → `delogo`. Quy trình đầy đủ: `clip-co-giong-san.md` |
| `muse-video` | ~10s, có tiếng | đính ảnh làm khung đầu — **nhưng Muse có thể không nhận ảnh** (báo "chưa đồng bộ") rồi tự lấy ảnh cũ → đổi người (15/10/2026). Nhiều cảnh thì giao cả kịch bản qua `muse-ask` rồi `muse-thread-lay-video` (xem skill `video-hoc-tieng-trung-muse`) |
| `google-flow-veo3` | Veo 3.1 / Omni | có thể trả `queued` + link dự án → chạy lại sau |
| `meta-ai-video` | ngắn | |
| **`dola-video`** | free | ưu tiên thử trước khi dùng nguồn trả phí |

Clip dài hơn câu đọc thì tự cắt; ngắn hơn thì tự lặp. Clip có thoại sẵn và không cần
lời đọc → bỏ `loi`, đặt `"giu_tieng": true`.

## Hình người dùng tự có

Chép thẳng vào `canh/`. Ảnh ngang dùng cho khung dọc sẽ bị cắt hai bên — báo trước.
