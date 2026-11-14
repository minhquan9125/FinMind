# Đánh giá R3 — FPT 2024 và 2025

Ngày đánh giá: 11/10/2026. Phạm vi: 3 báo cáo tài chính chính (`balance_sheet`, `income_statement`, `cash_flow`) trong `annual_ir/table`; không bao gồm bảng thuyết minh hoặc bảng nội dung thường niên.

## Cách đo

Đọc hai workbook trong thư mục này và so từng dòng với ô IR theo `(statement, code, period_end, period_type, pdf_page)`. Giá trị `value_raw` phải khớp chuỗi gốc trong ô. Mẫu số gồm cả ô thiếu, sai trang, sai kỳ, mơ hồ, chưa giải quyết và tham chiếu không hợp lệ. File 2024 dùng **số trang in trên báo cáo** (146–154), tương ứng PDF 148–156; file 2025 dùng **số trang PDF** (165–172). Bộ đánh giá chấp nhận cả hai kiểu locator khi tra trang, nhưng vẫn ghi trang PDF thực vào kết quả.

| PDF      | Cân đối kế toán | Kết quả kinh doanh | Lưu chuyển tiền tệ |       Tổng khớp | Tỷ lệ khớp Excel |
| -------- | -------------------: | -------------------: | ---------------------: | ----------------: | ------------------: |
| FPT 2024 |              166/166 |                46/46 |                  66/66 | **278/278** |   **100,00%** |
| FPT 2025 |              166/166 |                46/46 |                  66/66 | **278/278** |   **100,00%** |

Không có ô thiếu, sai trang, sai kỳ, mơ hồ, ô IR thừa hoặc kỳ không nhận diện được ở hai bộ 278 ô. Kết quả chi tiết theo từng ô nằm trong `r3_2024_result.json` và `r3_2025_result.json`.

Đã so toàn bộ 67 file trang và `table/index.json` của `annual_ir/table` với `annual_ir_dynamic/table` cho từng PDF: các file tương ứng giống byte. Do đó kết quả R3 trên bảng BCTC áp dụng cho cả hai thư mục đầu ra này.

## Ô năm 2025 đã được đối chiếu lại

- PDF trang **169** (số in 168), `income_statement`, mã **52**, kỳ so sánh `2024-12-31`.
- Workbook ban đầu có `(280.683.727.283)`, trong khi IR và ảnh PDF 2025 đều là `(280.683.727.283`.
- Sau khi người dùng sửa `value_raw` trong workbook về đúng chuỗi in trên PDF, chạy lại cho **278/278**. PDF 2024 in cùng số liệu với dấu ngoặc đóng; không dùng bản 2024 để tự sửa chuỗi gốc của PDF 2025.

## Kiểm tra R3 phát hiện sai dòng/cột

Trên **bản sao tạm** của IR 2024, tráo giá trị cột 2024 giữa mã 110 và 111: còn **276/278**, báo đúng hai mã sai. Đảo hai giá trị cột 2024/2023 của mã 110: còn **276/278**, báo đúng hai kỳ sai. File IR gốc và hai workbook không bị sửa trong thử nghiệm này.

## Đối chiếu cùng kỳ giữa hai báo cáo

Cột so sánh năm 2024 trong báo cáo 2025 có **136 ô khớp, 3 ô lệch** với cột năm 2024 của báo cáo 2024. Ba ô lệch là KQKD mã 52, 70 và 71; xem `cross_period.issues` trong `r3_2025_result.json`. Cờ `CROSS_PERIOD_MISMATCH` chỉ yêu cầu xem lại, vì khác biệt có thể do lỗi đọc hoặc số so sánh được trình bày lại.

## Giới hạn chứng cứ

Hai workbook hiện đã ghi `transcriber` và `review_status=self_checked` cho đủ 278 ô mỗi bản. Kết quả 278/278 được báo là `agreement_rate=1.0`, `review_method=self_checked`; `gold_accuracy` và `human_approved` chỉ được công bố sau khi **người thứ hai** kiểm độc lập toàn bộ ô. Chương trình kiểm SHA-256 của PDF với `table/index.json`; cột `document_sha256` trong workbook là tùy chọn và được kiểm nếu có. Trạng thái tự kiểm là xác nhận của người làm gold set; chương trình không thể tự chứng minh quá trình đối chiếu với ảnh PDF. Sau khi người khác kiểm độc lập, thêm `checker` khác `transcriber` và dùng `review_status=approved`.

## Chạy lại

Từ gốc repo, dùng Python của môi trường đã cài `openpyxl`:

```powershell
py src/evaluateDocumentIr.py
```

Script đọc `Gold_Set/evaluations.json`, chạy cả hai năm, ghi `cell_evaluation.json` vào từng `annual_ir/` và cập nhật `Gold_Set/r3_2024_result.json`, `Gold_Set/r3_2025_result.json`. Nó mặc định chỉ đo R3, không cần `pdftotext` của Poppler. Mã thoát 1 nghĩa là có ô lệch; mã 2 nghĩa là không thể đánh giá ít nhất một tài liệu. Vẫn có thể truyền PDF và tùy chọn riêng để đánh giá một file.
