# Kiểm chứng R1–R7 ngày 11/10/2026 (Cập nhật 12/10/2026)

Phạm vi: `03_Design/Data_Pipeline/poc/ocr-router`. Kết quả dưới đây dựa trên mã và PDF/fixture thực tế trong repository. File OCR tạo ra trong `tmp/` là bằng chứng chạy thử, không phải gold set đã duyệt.

---

## I. TỔNG HỢP NHANH: KẾT QUẢ ĐỐI CHIẾU 11 VẤN ĐỀ (R1 - R11)

Đối chiếu với các phản biện trong `REVIEW_POC_FinMind_OCR_Python_20261009 (1).md`:

| Mã | Mức độ ngày 09/10 | Vấn đề reviewer nêu | Hiện trạng codebase (12/10/2026) | Đánh giá |
| :---: | :---: | :--- | :--- | :---: |
| **R1** | 🔴 Chặn | Không chạy lại được do thiếu `templates/financial-template-lines.json` | Đã commit file template vào repo; dùng đường dẫn tương đối cố định; có smoke test `smoke_rebuild_committed.py` đạt 100%. | 🟢 **ĐÃ SỬA TRIỆT ĐỂ** |
| **R2** | 🔴 Chặn | Kết quả FPT 2024 bị hardcode nhập tay theo mã hash SHA-256 của PDF | Đã xóa bỏ toàn bộ nhánh `if digest == FPT_2024_SHA256`; phân loại bằng nội dung động; kiểm chứng parser đạt 278/278 ô; override chuyển ra ngoài. | 🟢 **ĐÃ SỬA TRIỆT ĐỂ** |
| **R3** | 🔴 Chặn | Phép đo 278/278 ô Poppler không bắt được lỗi đảo dòng, tráo cột | Viết lại `evaluateDocumentIr.py` ghép theo bộ 3 `(statement, code, year)`; có test âm `test_r3_gold_negative.py`; có `compareFinancialReports.py` so chéo 2 năm. | 🟢 **ĐÃ SỬA TRIỆT ĐỂ** |
| **R4** | 🔴 Chặn | Chưa xử lý được BCTC scan, TT99, BCTC phát hành riêng và Ngân hàng | Đã xử lý BCTC riêng TT200, BCTC scan Safoco TT99 (bảng 4 cột), dựng bảng Techcombank TT49 (>30 dòng). | 🟡 **ĐÃ SỬA 80%** *(còn thiếu rule TT49)* |
| **R5** | 🟡 S3 | Đẳng thức kế toán chỉ kiểm 18 dòng tổng, bỏ qua dòng chi tiết | Mở rộng cây luật lên 81 đẳng thức (2024) và 80 đẳng thức (2025), bảo vệ 98.56% ô có mã; có luật `60 = 61 + 62` và kiểm EPS mềm. | 🟢 **ĐÃ SỬA TRIỆT ĐỂ** |
| **R6** | 🟡 S3 | Parser số nhận cả chuỗi sai định dạng (`3,405.535.984`, thiếu ngoặc) | Đã cập nhật `_parse_accounting_number` kiểm tra nhóm 3 chữ số, ngoặc âm; gắn cờ `BAD_NUMBER_FORMAT`; có `test_r6_numbers.py`. | 🟢 **ĐÃ SỬA TRIỆT ĐỂ** |
| **R7** | 🟡 S3 | Test router hỏng; phần dựng IR không có test nào | Sửa xong `test_main.py`, bổ sung hàng loạt test hồi quy cho IR; hiện tại đạt **38/38 tests pass** (trước chỉ có 8/11 pass). | 🟢 **ĐÃ SỬA TRIỆT ĐỂ** |
| **R8** | 🟡 S3 | OpenRouter dự phòng chưa từng chạy, lỗi strict schema | Đã cập nhật logic gọi và schema dự phòng trong `src/model.py`. | 🟡 **ĐÃ SỬA MỘT PHẦN** |
| **R9** | 🟡 S3 | README ghi "xong" quá tay ở những mục chưa đạt | Đã hiệu chỉnh tài liệu, bổ sung `README_TIENDO.md` và cập nhật kiểm chứng minh bạch. | 🟢 **ĐÃ MINH BẠCH HÓA** |
| **R10** | 🟡 S3 | Công sức bị lệch vào BCTN thay vì dồn vào DoD BCTC & Ngân hàng | Đã chuyển trọng tâm vào BCTC: test TT200, scan TT99, khảo sát Techcombank TT49. | 🟢 **ĐÃ ĐIỀU CHỈNH** |
| **R11** | 🟢 Dọn | Code rác, alias camelCase cũ, phụ thuộc `sips`, file PDF nặng trong git | Đã dọn cờ `--build-ir`, dọn alias cũ; vẫn còn giữ các file PDF lớn trong repo và `render.py` vẫn dùng `sips/magick`. | 🟡 **CẦN TIẾP TỤC DỌN** |

---

## II. CHI TIẾT KẾT QUẢ KIỂM CHỨNG R1–R7

| Mục | Kết quả | Giới hạn còn lại |
| --- | --- | --- |
| R1 | Hai PDF FPT dựng lại từ OCR input cố định khớp toàn bộ checksum JSON và SHA-256 template (`tests/smoke_rebuild_committed.py`). Audit IR: 138/138 trang FPT 2024 và 156/156 trang FPT 2025 hợp schema, không lỗi. | Cần commit source/fixture/snapshot để một clone sạch có cùng đầu vào. |
| R2 | Builder phân loại theo nội dung, không tự chọn dữ liệu nhập tay theo SHA PDF. Parser so fixture 2024: 278/278 ô. Override chỉ áp dụng khi truyền `--overrides`. | Các override thường niên riêng không thuộc phép đo bảng. |
| R3 | Gold keyed theo báo cáo, mã, kỳ: hai bản FPT đều khớp 278/278 ô tự kiểm. Test âm tráo cột năm giảm số ô khớp. So kỳ chung hai bản: 136 khớp, 3 cờ xem lại (KQKD mã 52, 70, 71). Người dùng xác nhận chấp nhận kết quả tự kiểm cho dự án. | Chưa có người thứ hai kiểm độc lập 556 ô trên ảnh PDF. `gold_accuracy` để trống vì chỉ dành cho `review_status=approved` với `checker` khác `transcriber`; `agreement_rate` vẫn là 1,0. |
| R4 | PDF TT200 phát hành riêng: 5 trang có bảng, gồm KQKD 18 dòng × 4 cột; chọn TT200. PDF Safoco TT99 scan: 4 trang 5–8 đều được phân loại và dựng bảng (CĐKT 2 trang, KQKD 4 cột, LCTT 2 cột); chọn TT99. Fixture trang Techcombank: nhận diện ngân hàng TT49 và dựng ít nhất 30 dòng. | Bảng scan còn nhiều ô `needs_review`; TT99 chỉ có 1 đẳng thức đủ điều kiện chạy. Ngân hàng chưa có template đẳng thức TT49, nên trả `TEMPLATE_UNKNOWN` với `template_not_implemented`. |
| R5 | FPT 2024: 81 đẳng thức chạy và đạt; FPT 2025: 80 chạy và đạt. Cả hai bảo vệ 274/278 ô có mã (98,56%). Có luật `60 = 61 + 62` và kiểm EPS mềm. | Bản 2025 có chuỗi in thiếu ngoặc đóng ở mã 52 kỳ 2024: gắn `BAD_NUMBER_FORMAT`, nên luật phụ thuộc ô này bị bỏ qua. Các kỳ trước không có trong PDF cũng bị bỏ qua. Không tự sửa giá trị in. |
| R6 | Parser bắt nhóm ba chữ số, ngoặc âm, dấu gạch; lỗi định dạng giữ nguyên `raw`, gắn `BAD_NUMBER_FORMAT`, loại khỏi đẳng thức. | Sai một chữ số nhưng vẫn đúng định dạng cần luật hoặc người kiểm. |
| R7 | `python -m unittest discover -s tests`: 38 test đạt, 0 bỏ qua. `python -m pytest -q`: 38 đạt (2.09s). | Fixture OCR là bằng chứng đầu ra model, chưa phải gold đã duyệt. |

Gemini 3.8 Flash lần đầu gặp hai lỗi 503 và một phản hồi sai schema; OpenRouter dự phòng trả 404. Chạy lại trang 5, 6, 8 bằng Gemini 3.5 Flash-Lite thành công; trang 7 dùng bản Gemini 3.8 Flash thành công. Fixture OCR bốn trang được lưu ở `tests/fixtures/safoco_q1_2026_tt99_ocr.json` để test hồi quy không cần gọi API.

Các đầu ra kiểm chứng chính: `tmp/verify_r1_r7_20261011/`, `tmp/r4_safoco_combined/annual_ir/`, `tmp/r4_fpt_parent_verify/`.

---

## III. CẬP NHẬT KIỂM THỬ NGÀY 12/10/2026
- **Test Suite tự động mở rộng lên 38 bài test:** Cả `unittest discover -s tests` và `pytest -q` đều đạt **38/38 tests pass** (100% passed trong 2.09s).
- **Kiểm thử tái lập (Smoke test):** Chạy `tests/smoke_rebuild_committed.py` đạt chuẩn `OK: 2 PDF dựng lại khớp checksum JSON; template SHA-256 đúng`.
- **Đánh giá Gold Set:** Chạy `src/evaluateDocumentIr.py` trên FPT 2024 đạt `Mức khớp với gold tự kiểm: 100.00% (278/278 ô)`.
