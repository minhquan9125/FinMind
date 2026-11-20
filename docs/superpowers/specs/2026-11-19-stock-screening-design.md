# Chat: lọc mã theo dữ kiện (thiết kế ngắn)

Ngày: 19/11/2026 · Người yêu cầu: Hưng · Loại: thay đổi nhỏ · Phương án và hai chỉnh sửa đã được duyệt trong chat ngày 19/11.

## Mục đích

Người dùng hỏi "mã/doanh nghiệp/công ty nào đang phát triển, đang tăng, ngon, đáng đầu tư". Chat không hỏi lại "công ty nào?" hay từ chối nữa, mà trả về **danh sách mã xếp theo dữ kiện** kèm lý do và nguồn.

## Hiện trạng

- "mã nào đang xu hướng" / "đang phát triển tốt": `MISSING_COMPANY`, hỏi lại công ty.
- "mã nào đáng đầu tư": bộ kiểm intent từ chối (`INTENT_OUT_OF_SCOPE`).
- Dữ liệu có sẵn:
  - Xu hướng giá 20/60/200 phiên cho mọi mã có giá: `get_price_trend(pool, symbol)`, nhãn `UP`, `DOWN`, `SIDEWAYS`, `UNCLEAR`, `INSUFFICIENT_DATA`, kèm `return_percent` và `close_vs_sma_percent`.
  - Sức khỏe BCTC cho 10 mã: `get_financial_health(pool, symbol)`, `signals.revenue_yoy_percent` và `profit_yoy_percent` có `value` và `status`.

## Hành vi

1. **Nhận diện** câu lọc mã: có chủ thể "mã nào / cổ phiếu nào / doanh nghiệp nào / công ty nào / những mã / các mã" (viết có dấu hoặc không dấu) đi kèm từ chỉ trạng thái tốt: đang tăng, xu hướng (tăng), phát triển, tăng trưởng, ngon, tốt, mạnh, khỏe, đáng đầu tư, nên đầu tư, triển vọng. Câu đã nêu tên một công ty cụ thể thì không thuộc loại này.
2. **Tính trực tiếp từ DB, không qua Gemini** (giống câu hỏi giá), nên không bịa số.
   - **Xu hướng tăng** theo từng khung: ngắn hạn 20 phiên, trung hạn 60 phiên, dài hạn 200 phiên. Liệt kê mã có nhãn `UP`, xếp theo lợi suất giảm dần. Mỗi mã kèm lợi suất và giá so với đường trung bình, ví dụ "FPT (+6,2% trong 20 phiên, giá trên SMA20 3,1%)".
   - **Tăng trưởng so với cùng kỳ (BCTC đã đối chiếu)**: mã có `profit_yoy_percent` hoặc `revenue_yoy_percent` dương và status `complete` hoặc `provisional`, kèm kỳ báo cáo.
   - Nhóm không có mã nào thì ghi rõ: "Chưa có mã nào …" hoặc "Chưa đủ số liệu BCTC đã đối chiếu để so sánh tăng trưởng".
   - Dòng đầu: "Lọc theo dữ kiện đến ngày dd/mm/yyyy:".
   - Dòng cuối: nguồn (giá giao dịch hằng ngày trong cơ sở dữ liệu; BCTC đã đối chiếu).
   - **Không** thêm câu miễn trừ cuối danh sách, vì câu đó luôn hiện dưới ô chat.
3. **Theo hướng đầu tư:** người dùng đã nêu dài hạn (`FINANCIAL`) thì nhóm tăng trưởng BCTC lên trước; còn lại xu hướng giá lên trước.
4. Câu "đáng / nên đầu tư" chạy trước bộ kiểm intent, nên trả về danh sách này thay vì bị từ chối. Câu "nên mua/bán **mã X**", "giá mục tiêu" vẫn bị từ chối như cũ.

## Không làm

- Không chấm điểm tổng hợp hay xếp hạng "mã tốt nhất".
- Không đưa giá mục tiêu, không dự báo.
- Không lọc theo ngành hay theo điều kiện tùy chọn (ví dụ "ROE > 15%").

## Phương án đã cân nhắc

- **A. Tính trực tiếp từ DB (đã chọn):** nhanh, không bịa số, dùng lại `get_price_trend` và `get_financial_health`.
- B. Gom dữ liệu rồi để Gemini viết lời: văn mượt hơn nhưng chậm, tốn token, và khó kiểm hàng chục con số cùng lúc.

## Quyết định của người làm (Claude)

- Chỉ đưa vào danh sách xu hướng các mã có nhãn `UP`. Mã `SIDEWAYS` hoặc `UNCLEAR` không đưa vào.
- Danh sách mã lấy từ các mã có giá trong DB (`PriceAnalytics.symbols()`).
- Mã đọc lỗi thì bỏ qua và ghi số mã bị bỏ qua, không làm hỏng cả câu trả lời.
