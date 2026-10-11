# Kiểm chứng R1–R7 ngày 11/10/2026

Phạm vi: `03_Design/Data_Pipeline/poc/ocr-router`. Kết quả dưới đây dựa trên mã và PDF/fixture thực tế trong repository. File OCR tạo ra trong `tmp/` là bằng chứng chạy thử, không phải gold set đã duyệt.

| Mục | Kết quả | Giới hạn còn lại |
| --- | --- | --- |
| R1 | Hai PDF FPT dựng lại từ OCR input cố định khớp toàn bộ checksum JSON và SHA-256 template (`tests/smoke_rebuild_committed.py`). Audit IR: 138/138 trang FPT 2024 và 156/156 trang FPT 2025 hợp schema, không lỗi. | Cần commit source/fixture/snapshot để một clone sạch có cùng đầu vào. |
| R2 | Builder phân loại theo nội dung, không tự chọn dữ liệu nhập tay theo SHA PDF. Parser so fixture 2024: 278/278 ô. Override chỉ áp dụng khi truyền `--overrides`. | Các override thường niên riêng không thuộc phép đo bảng. |
| R3 | Gold keyed theo báo cáo, mã, kỳ: hai bản FPT đều khớp 278/278 ô tự kiểm. Test âm tráo cột năm giảm số ô khớp. So kỳ chung hai bản: 136 khớp, 3 cờ xem lại (KQKD mã 52, 70, 71). Người dùng xác nhận chấp nhận kết quả tự kiểm cho dự án. | Chưa có người thứ hai kiểm độc lập 556 ô trên ảnh PDF. `gold_accuracy` để trống vì chỉ dành cho `review_status=approved` với `checker` khác `transcriber`; `agreement_rate` vẫn là 1,0. |
| R4 | PDF TT200 phát hành riêng: 5 trang có bảng, gồm KQKD 18 dòng × 4 cột; chọn TT200. PDF Safoco TT99 scan: 4 trang 5–8 đều được phân loại và dựng bảng (CĐKT 2 trang, KQKD 4 cột, LCTT 2 cột); chọn TT99. Fixture trang Techcombank: nhận diện ngân hàng TT49 và dựng ít nhất 30 dòng. | Bảng scan còn nhiều ô `needs_review`; TT99 chỉ có 1 đẳng thức đủ điều kiện chạy. Ngân hàng chưa có template đẳng thức TT49, nên trả `TEMPLATE_UNKNOWN` với `template_not_implemented`. |
| R5 | FPT 2024: 81 đẳng thức chạy và đạt; FPT 2025: 80 chạy và đạt. Cả hai bảo vệ 274/278 ô có mã (98,56%). Có luật `60 = 61 + 62` và kiểm EPS mềm. | Bản 2025 có chuỗi in thiếu ngoặc đóng ở mã 52 kỳ 2024: gắn `BAD_NUMBER_FORMAT`, nên luật phụ thuộc ô này bị bỏ qua. Các kỳ trước không có trong PDF cũng bị bỏ qua. Không tự sửa giá trị in. |
| R6 | Parser bắt nhóm ba chữ số, ngoặc âm, dấu gạch; lỗi định dạng giữ nguyên `raw`, gắn `BAD_NUMBER_FORMAT`, loại khỏi đẳng thức. | Sai một chữ số nhưng vẫn đúng định dạng cần luật hoặc người kiểm. |
| R7 | `python -m unittest discover -s tests`: 35 test đạt, 0 bỏ qua. `python -m pytest -q`: 35 đạt. | Fixture OCR là bằng chứng đầu ra model, chưa phải gold đã duyệt. |

Gemini 3.8 Flash lần đầu gặp hai lỗi 503 và một phản hồi sai schema; OpenRouter dự phòng trả 404. Chạy lại trang 5, 6, 8 bằng Gemini 3.5 Flash-Lite thành công; trang 7 dùng bản Gemini 3.8 Flash thành công. Fixture OCR bốn trang được lưu ở `tests/fixtures/safoco_q1_2026_tt99_ocr.json` để test hồi quy không cần gọi API.

Các đầu ra kiểm chứng chính: `tmp/verify_r1_r7_20261011/`, `tmp/r4_safoco_combined/annual_ir/`, `tmp/r4_fpt_parent_verify/`.
