# Hướng đầu tư của người dùng trong chat (thiết kế ngắn)

Ngày: 19/11/2026 · Người yêu cầu: Hưng · Loại: thay đổi nhỏ

## Mục đích

Chat phân tích cổ phiếu theo đúng hướng đầu tư của người hỏi (ngắn hạn/kỹ thuật hay dài hạn/cơ bản) thay vì trả lời giống nhau cho mọi người, và nhớ hướng đó trong suốt cuộc chat.

## Hiện trạng

- `market_request()` (`backend/src/retrieval_orchestration/live_research.py` ~dòng 172–180) chọn `focus` cho câu phân tích: `TECHNICAL` khi có chữ "xu hướng", `FINANCIAL` khi có "tài chính/BCTC" + "phân tích/đánh giá…", còn lại `STOCK`.
- `grounded.py` dùng `ANALYSIS_FOCUS[focus]` để quyết định nhóm ý và thứ tự trong câu trả lời.
- Focus chỉ dựa vào từ khoá của **câu hiện tại**, không nhớ qua lượt, không nói cho người dùng biết.

## Mục tiêu

1. Nhận ra cách nói của nhà đầu tư. So khớp trên chữ đã bỏ dấu và nhận cả khi viết không dấu. Từ dễ nhầm nghĩa chỉ nhận theo cụm.
   - **Ngắn hạn → `TECHNICAL`:**
     - Phong cách: lướt sóng, ngắn hạn, trading, trade, swing, đầu cơ, đánh nhanh, ăn nhanh, chốt lời nhanh, T+ (T+2, T+3).
     - Phân tích kỹ thuật: kỹ thuật, phân tích kỹ thuật, chart, đồ thị giá, biểu đồ giá, nến, mẫu hình.
     - Vùng giá: vùng hỗ trợ, ngưỡng hỗ trợ, kháng cự, điểm vào, điểm ra, breakout, bứt phá.
     - Động lượng: momentum, đà tăng, đà giảm, dòng tiền ngắn hạn.
     - Chỉ báo: RSI, MACD, Bollinger, SMA, EMA, đường trung bình.
   - **Dài hạn → `FINANCIAL`:**
     - Phong cách: dài hạn, trung dài hạn, đầu tư giá trị, đầu tư tăng trưởng, nắm giữ, giữ lâu, buy and hold, tích sản, tích lũy dài hạn.
     - Phân tích cơ bản: phân tích cơ bản, yếu tố cơ bản, nền tảng doanh nghiệp, sức khỏe doanh nghiệp, sức khỏe tài chính.
     - Cổ tức và định giá: cổ tức, dividend, định giá, P/E, P/B.
     - Chất lượng: tăng trưởng bền vững, lợi nhuận bền vững, biên lợi nhuận, dòng tiền kinh doanh, đòn bẩy, nợ vay, an toàn vốn, chất lượng tài sản, nợ xấu.
   - Câu có từ của **cả hai** nhóm ("ngắn hạn và dài hạn") thì không đổi focus, giữ `STOCK`.
2. Nhớ hướng trong phiên:
   - Người dùng tự nêu ("tôi đầu tư dài hạn", "mình hay lướt sóng") thì lưu `scope['_investor_focus'] = {'focus': ..., 'source': 'STATED'}`.
   - Giữ hướng đó qua các lượt, cùng cơ chế với `_last_question`.
3. Áp dụng: câu phân tích không tự nêu hướng thì dùng hướng đã nhớ thay cho `STOCK`. Câu tự nêu hướng khác thì thắng và cập nhật hướng đã nhớ.
4. Minh bạch: câu trả lời phân tích có một dòng đầu, ví dụ "Phân tích theo hướng dài hạn (cơ bản), theo bạn đã nêu. Muốn đổi, hãy nói 'phân tích theo hướng ngắn hạn'."
5. Tin nhắn chỉ nêu hướng, không có câu hỏi ("tôi đầu tư dài hạn") được trả lời bằng xác nhận ngắn, không truy xuất. Ví dụ: "Đã ghi nhận: các phân tích sau sẽ theo hướng dài hạn (cơ bản)."
6. "Phân tích chung" hoặc "bỏ hướng đầu tư" xoá hướng đã nhớ, quay về `STOCK`.

## Không làm (non-goals)

- Không nhớ qua các cuộc chat khác nhau và không lưu vào hồ sơ tài khoản (phương án C, để sau).
- Không hỏi khẩu vị rủi ro, quy mô vốn hay danh mục.

## Tuyệt đối không (anti-goals)

- Không biến hướng đầu tư thành khuyến nghị mua/bán. Bộ kiểm intent vẫn từ chối "nên mua/bán", "giá mục tiêu", "có nên đầu tư".
- Hướng đầu tư chỉ đổi phần **nhấn mạnh** (nhóm ý, thứ tự), không đổi dữ liệu hay kết luận.

## Phương án đã cân nhắc

- A. Chỉ mở rộng từ khoá theo từng câu: nhỏ nhưng quên ngay ở câu sau.
- **B. A + nhớ trong phiên (đã chọn):** dùng lại cơ chế ngữ cảnh `scope` sẵn có, không cần DB.
- C. B + lưu vào hồ sơ tài khoản: cần bảng, API và UI `/profile` mới. Để sau.

## Quyết định của người làm (Claude), cần kiểm khi đọc

- Danh sách từ khoá ở mục 1 do mình đề xuất và đã được duyệt ngày 19/11. Các chỉ tiêu (ROE, nợ xấu…) vẫn đi tuyến BCTC như cũ khi câu hỏi hỏi đúng một số liệu. Chúng chỉ quyết định hướng đầu tư khi người dùng tự nêu hướng, hoặc khi câu đã đi vào nhánh phân tích.
- Hướng chỉ được ghi nhớ khi người dùng **tự nêu**. Câu hỏi có từ khoá kỹ thuật ("xu hướng VCB") chỉ đổi focus cho câu đó, không ghi nhớ, để tránh đoán sai về người dùng từ một câu hỏi lẻ.
- Không mở rộng điều kiện kích hoạt phân tích. Hướng đã nhớ chỉ áp dụng khi câu hỏi đã đi vào nhánh phân tích như hiện nay, để không làm lệch các tuyến BCTC, BCTN và tin tức đang chạy đúng.
- Kiểm thử: unit test cho phần nhận diện và ghi nhớ; chạy lại bộ 70 câu để chắc không tụt điểm.
