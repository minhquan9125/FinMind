# Báo cáo kiểm tra trích dẫn và chuẩn hóa câu trả lời B1

**Thời gian thực hiện:** 2026-10-19

**Tích hợp:** `src.documents.locator_resolver` của Vũ & `src.documents.b1_citation_verifier`


## 1. Tổng quan các ca kiểm tra

| Ca mẫu | Loại nguồn | Số nhận định | Verified | Ungrounded | Conflicting | Citation mở được | Trạng thái |
|---|---|---|---|---|---|---|---|
| `B1-CASE-01-FULL` | FULL_SOURCES | 2 | 2 | 0 | 0 | 2 | ĐẠT (Sạch claim vô nguồn) |
| `B1-CASE-02-MISSING` | MISSING_SOURCES | 2 | 1 | 1 | 0 | 1 | ĐẠT (Sạch claim vô nguồn) |
| `B1-CASE-03-CONFLICTING` | CONFLICTING_SOURCES | 2 | 0 | 0 | 2 | 2 | ĐẠT (Sạch claim vô nguồn) |

## 2. Chi tiết từng ca kiểm tra và kết quả hiệu chỉnh

### Ca: `B1-CASE-01-FULL` (FULL_SOURCES)

- **Câu hỏi:** *Cho biết sàn niêm yết và giá đóng cửa của FPT ngày 2026-09-29?*

- **Câu trả lời ban đầu:**
  > Cổ phiếu FPT thuộc CTCP FPT hiện niêm yết trên sàn HOSE [EVID-FPT-PROFILE]. Vào phiên giao dịch ngày 2026-09-29, cổ phiếu FPT có giá đóng cửa đạt 63.200 đồng [EVID-FPT-PRICE-20260929].

- **Câu trả lời sau hiệu chỉnh (Bước 3):**
  > Cổ phiếu FPT thuộc CTCP FPT hiện niêm yết trên sàn HOSE. [EVID-FPT-PROFILE] Vào ngày 2026-09-29, cổ phiếu FPT có giá đóng cửa đạt 63.200 đồng. [EVID-FPT-PRICE-20260929]

- **Các citation mở được locator:**

  - Mã `[EVID-FPT-PROFILE]`: Bảng `companies`, Khóa: `['FPT:company_name', 'FPT:exchange']`
  - Mã `[EVID-FPT-PRICE-20260929]`: Bảng `price_bars`, Khóa: `['FPT:2026-09-29']`

---

### Ca: `B1-CASE-02-MISSING` (MISSING_SOURCES)

- **Câu hỏi:** *Cho biết sàn niêm yết của FPT và dự phóng lợi nhuận sau thuế quý 4/2026?*

- **Câu trả lời ban đầu:**
  > Cổ phiếu FPT thuộc CTCP FPT niêm yết trên sàn HOSE [EVID-FPT-PROFILE]. Dự kiến quý 4/2026 FPT sẽ đạt lợi nhuận sau thuế kỷ lục 3.500 tỷ đồng và mục tiêu giá 95.000 đồng/cp.

- **Câu trả lời sau hiệu chỉnh (Bước 3):**
  > Cổ phiếu FPT thuộc CTCP FPT niêm yết trên sàn HOSE. [EVID-FPT-PROFILE] Đối với thông tin 'FPT dự kiến đạt lợi nhuận sau thuế quý 4/2026 là 3.500 tỷ đồng và giá mục tiêu 95.000 đồng/cp.': Hiện tại chưa đủ bằng chứng tài chính hoặc dữ liệu chưa được công bố chính thức trong hệ thống để xác nhận.

- **Các citation mở được locator:**

  - Mã `[EVID-FPT-PROFILE]`: Bảng `companies`, Khóa: `['FPT:company_name', 'FPT:exchange']`

---

### Ca: `B1-CASE-03-CONFLICTING` (CONFLICTING_SOURCES)

- **Câu hỏi:** *Đánh giá triển vọng bán lẻ và thị phần của FPT?*

- **Câu trả lời ban đầu:**
  > FPT khẳng định vị thế tuyệt đối và bứt phá không rủi ro khi FPT Shop đạt thứ 11 nhà bán lẻ tin cậy nhất châu Á [EVID-FPT-RETAIL-11], không có bất kỳ thách thức nào từ thị trường tiêu dùng.

- **Câu trả lời sau hiệu chỉnh (Bước 3):**
  > Về triển vọng của FPT, các nguồn phân tích hiện có sự khác biệt: Bảng xếp hạng Brand Conviction Index ghi nhận FPT Shop đứng thứ 11 trong Top nhà bán lẻ tin cậy châu Á [EVID-FPT-RETAIL-11]. Tuy nhiên, CTCK Mirae Asset nhấn mạnh động lực cốt lõi đến từ AI và thị trường quốc tế (Nhật/EU), đồng thời lưu ý sức mua ngành bán lẻ nội địa vẫn đối mặt thách thức [EVID-FPT-MIRAE-AI]. Do có sự khác biệt giữa các kênh phân tích, nhà đầu tư cần thận trọng và tiếp tục theo dõi báo cáo định kỳ.

- **Các citation mở được locator:**

  - Mã `[EVID-FPT-RETAIL-11]`: Bảng `news_articles`, Khóa: `['p0']`
  - Mã `[EVID-FPT-MIRAE-AI]`: Bảng `news_articles`, Khóa: `['p0']`

---
