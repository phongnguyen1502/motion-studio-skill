# Đạo diễn tự động — người dùng chỉ đưa ý tưởng, skill lo phần còn lại

Nguồn: dự án "Những con số trên tường" (12/10/2026). Người dùng đưa cùng một ý tưởng cho hai bên:
bản DeepSeek ra video điện ảnh (Ghibli vẽ tay, mỗi cảnh một góc máy, ánh sáng có chủ ý, thẻ tiêu đề + thẻ kết,
2 bài nhạc, phụ đề rời) còn bản đầu của skill này ra ảnh chibi cùng một cỡ khung, chữ to, không nhạc.
Cùng công cụ vẽ (Muse), cùng giọng (Soniox) → khoảng cách nằm ở **đạo diễn**, không ở công cụ.

**Luật gốc:** người dùng không có chuyên môn video/thiết kế. Cái gì họ **không nói**, skill **tự quyết** theo
file này, đừng hỏi lại và đừng để mặc định cho model vẽ. Chỉ hỏi những thứ họ mới biết: giọng đọc, chuyện thật nào không được bịa.

## 1. Việc phải làm trước khi tạo ảnh (≤ 1 phút, ghi vào `kich-ban.json`)

1. **Mở rộng ý tưởng nếu mỏng** ("chưa đủ chạm"): thêm chi tiết cụ thể, một hình ảnh lặp lại đầu–cuối,
   một khoảnh khắc im lặng. KHÔNG bịa sự việc nếu người dùng kể chuyện thật — lập bảng "ràng buộc sự thật" (xem `viet-loi-binh.md`).
2. **Chọn phong cách** (`phong_cach`) theo bảng dưới, trừ khi người dùng đã nói. Ghi **nguyên một câu** để dán vào MỌI prompt ảnh.
3. **Lập danh sách cảnh có đạo diễn**: mỗi cảnh một dòng `loai_khung` + `anh_sang` (xem mục 2–3).
4. **Chọn nhạc + thẻ đầu/kết** (mục 4).

## 2. Phong cách tự chọn (khi người dùng không nêu)

| Thể loại | Phong cách mặc định (dán nguyên vào prompt) |
|---|---|
| Kể chuyện đời thường, hoài niệm, cảm xúc | `Tranh minh hoạ phong cách phim hoạt hình Ghibli vẽ tay điện ảnh, màu nước đậm chất, ánh sáng có chủ ý` |
| Truyện thiếu nhi, hài nhẹ | `minh hoạ sách thiếu nhi màu nước, nét mềm, màu pastel ấm` (chibi chỉ khi người dùng đòi) |
| Giới thiệu sản phẩm / công nghệ | `ảnh điện ảnh, ánh sáng mềm, màu phim, chiều sâu trường ảnh nông` |
| Lịch sử / tâm linh / trang nghiêm | `tranh sơn dầu cổ điển, ánh sáng nến, tông trầm` |

Người dùng nói "chibi / hoạt hình / 3D / anime…" thì theo họ, nhưng vẫn áp mục 3–4 (đa dạng khung hình).
Một video = **một phong cách**, không trộn.

## 3. Mỗi cảnh một khung hình, một ánh sáng (đây là chỗ ăn tiền)

**Luật khung:** không có 2 cảnh liền nhau cùng loại khung. Trong một video ≥ 17 cảnh phải có đủ:

| Loại khung | Dùng khi | Câu chèn vào prompt |
|---|---|---|
| **Toàn cảnh mở đầu** | cảnh đầu, đổi địa điểm | `TOÀN CẢNH rộng, nhiều chiều sâu, nhân vật nhỏ trong khung` |
| **Cận chi tiết (vật/tay)** | khoảnh khắc ý tưởng, viết, gõ | `CẬN CẢNH bàn tay đang …, trường ảnh nông` |
| **Qua vai** | nhân vật nhìn một thứ | `QUA VAI: nhân vật quay lưng tiền cảnh, nhìn vào …` |
| **Trung cảnh** | đối thoại, hành động | `trung cảnh ngang hông` |
| **Cận mặt** | cảm xúc đỉnh | `CẬN MẶT, ánh sáng hắt lên một bên` |
| **Toàn cảnh kết** | cảnh cuối, lặng | `TOÀN CẢNH rộng, nhân vật nhỏ xíu hoặc vắng bóng` |

**Luật ánh sáng:** mỗi cảnh ghi **giờ + nguồn sáng + tương phản màu**: `nắng chiều xiên có bụi lấp lánh`,
`đêm trăng + ánh xanh của màn hình + đèn bàn vàng`, `sương sớm xanh lạnh, một ô cửa sáng vàng`.
Có đường cong cảm xúc: mở = ấm → trăn trở = lạnh/tối → giải tỏa = vàng rực → kết = lặng, ấm nhạt.

**Không "giữ góc máy như ảnh trước".** Câu đó (từng nằm trong `ghep-prompt.py` cho cảnh `noi_tiep`) khiến 3 cảnh liền
cùng một khung. Giữ nhân vật bằng **ảnh tham chiếu nhân vật** + mô tả chữ cố định; góc máy luôn do cảnh quyết định.
Cảnh cần liền mạch hành động trong cùng một căn phòng thì ghi "cùng căn phòng, cùng ánh sáng, nhưng đổi sang khung X".

## 4. Thẻ đầu, thẻ kết, nhạc (luôn có, người dùng khỏi phải nhớ)

| Mục | Mặc định | Khoá `kich-ban.json` |
|---|---|---|
| Thẻ đầu 5s | ảnh cảnh đẹp nhất làm tối + tên video serif + 1 dòng phụ | `"the_dau": {"hinh":"canh/02.png","dong":["NHỮNG CON SỐ","TRÊN TƯỜNG"],"phu":"…","giay":5}` |
| Thẻ kết 6–7s | câu chốt của chuyện (không phải "cảm ơn đã xem") | `"the_ket": {"hinh":"canh/17.png","dong":["…"],"phu":"…","giay":6}` |
| Nhạc | **2 bài** nhẹ, nối crossfade 4s, mỗi bài đưa về -31 LUFS, tự hạ khi có giọng | `"nhac": ["a.mp3","b.mp3"], "nhac_lufs": -31` |
| Ghi công nhạc | Kevin MacLeod = CC BY 4.0 → ghi vào mô tả video | xem SKILL.md "Nhạc nền free" |

Chọn nhạc theo cảm xúc: hoài niệm → *Dreamy Flashback*, *Almost in F* (incompetech.com). Bài đã tải lưu ở
`~/Downloads/tao-video-kho/nhac/` dùng lại cho video sau. Chưa có file nhạc thì **tìm và hỏi người dùng cho tải**
(tải file cần họ đồng ý), đừng bỏ trống rồi đợi họ đưa.

## 5. Phụ đề (người dùng chê chữ to, 12/10/2026)

- **Khổ ngang 16:9: chữ nhỏ, sát dưới** — 50px trên khung cao 1080, cách đáy 7%, không đậm, viền mảnh. Đã sửa lỗi cỡ chữ
  tính theo chiều rộng (làm khổ ngang to gấp 1,78 lần).
- **Khổ dọc 9:16:** 84px, cách đáy 27% (tránh nút TikTok).
- Luôn xuất `video.srt` đi kèm; truyện cảm xúc muốn sạch hình thì `"phu_de": {"bat": false}`.
- Người dùng chưa nói gì: truyện kể chuyện dài → **bật chữ nhỏ**; clip ngắn TikTok → chữ to dọc.

## 6. Kiểm trước khi đưa người dùng xem

Ghép **một ảnh lưới** tất cả cảnh và tự chấm (đừng đưa xem khi chưa qua):
- [ ] không có 2 cảnh liền cùng loại khung; có ít nhất 1 cận chi tiết, 1 qua vai, 1 toàn cảnh rộng
- [ ] ánh sáng đổi theo cảm xúc, không phải toàn một màu
- [ ] nhân vật cùng mặt/áo/tóc; cảnh sai bối cảnh thì tạo lại riêng cảnh đó (một tab, nói rõ "KHÔNG có …")
- [ ] có thẻ đầu, thẻ kết, nhạc; chữ phụ đề không che mặt nhân vật

## 7. Tốc độ thao tác trình duyệt (đừng để người dùng chờ)

Xem `nguon-hinh.md` mục "Chạy nhanh, không treo": mở tab gác cổng, 2 tab song song cách nhau ~15s,
ảnh tham chiếu để trong thư mục kho, canh bằng Monitor, quá 150s thì cắt. Khi chạy tự động: lập sẵn toàn bộ prompt
vào `prompts.json` TRƯỚC khi mở trình duyệt, để mọi lệnh chạy liên tục không dừng suy nghĩ giữa các ảnh.
