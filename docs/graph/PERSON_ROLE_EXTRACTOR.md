# Trích xuất quan hệ người – chức vụ – doanh nghiệp

## Đã triển khai

`backend/src/person_role/extractor.py` nhận envelope contract 2.1.0 có entities/mentions từ WBS02. Hàm `normalize_and_extract` có thể gọi trực tiếp bộ chuẩn hóa được bàn giao. Bộ chuẩn hóa và schema gốc nằm tại `backend/src/person_role/contract`, giữ nguyên nội dung và có hash xuất xứ.

Đầu ra gồm envelope quan hệ và báo cáo các đoạn chưa đủ điều kiện kết luận. Không gọi API LLM, không tự ghi database hoặc Neo4j. Có thể phát sinh ứng viên APPOINTS, DISMISSES, HOLDS_ROLE khi cùng đoạn có đúng một người, một doanh nghiệp, một chức vụ và khẳng định rõ. HOLDS_ROLE chỉ phản ánh nội dung nguồn, không xác nhận hiện còn giữ chức.

Mỗi ứng viên giữ tên chức vụ gốc (`position`), mã chuẩn hóa nội bộ (`position_code`), quote, mention IDs, locator và offset trên toàn bộ chunk.text. Mã chức vụ là mapping cục bộ, chưa phải canonical ID chức vụ do registry chung xác nhận. ID quan hệ ổn định trong cùng corpus/index/source/đoạn. Không sửa ID thực thể của WBS02.

Ngày sau cụm “từ/kể từ” có đầy đủ ngày/tháng/năm được lưu dưới `effective_date_proposed`; không tự suy ra năm hoặc lấp khoảng thời gian. Người duyệt xác nhận trước khi điền temporal và công bố. Tất cả đầu ra PENDING, assertion_status UNCERTAIN.

## Chạy

Tại thư mục FinMind/backend, dùng Python của môi trường dự án đã cài requirements.txt:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/extract_person_roles.py --input "duong-dan/envelope-da-co-mentions.json" --output-dir "duong-dan/ket-qua-moi"
```

Nếu input chưa có entities/mentions/relations, thêm `--normalize --registry "duong-dan/company.registry.json"`. Thư mục kết quả phải chưa tồn tại để tránh ghi đè; sinh `candidates.json` và `audit.json`.

## Giới hạn cần thấy rõ

- Chưa tự ghép bảng OCR, dòng bị cắt, nhiều người/nhiều chức vụ hoặc nhiều công ty trong cùng đoạn; ghi lý do trong audit.
- Đề cử, xin từ nhiệm, dự kiến, phủ định, điều kiện không được chuyển thành quan hệ đã xảy ra. Từ nhiệm đã xảy ra được đưa vào audit vì bộ quan hệ chức vụ hiện tại không có loại sự kiện riêng cho nó.
- Không suy công ty từ tiêu đề lặp lại của chunk; thiếu doanh nghiệp rõ trong đoạn sẽ chưa sinh quan hệ.
- Không tạo page giả cho tin tức không phân trang. Contract hiện tại yêu cầu page thật.
- Kiểm tra schema/span/hash chunk không thay thế đọc lại snapshot nguồn và kiểm tra source_sha256 trên database.
- Chưa nghiệm thu 21 mẫu nguồn thật, chưa đo precision/recall, chưa kiểm tra đồng bộ Neo4j. Chưa được đánh dấu hoàn thành toàn bộ task.

## Kiểm thử

Cập nhật 29/10/2026: đã audit đủ 21 mẫu tại `outputs/person-role-real-audit-20261029/run3/Bao_cao.md`.
14 mẫu BCTN dựng lại và kiểm tra nguồn từ manifest lưu thành công; 7 mẫu NEWS thiếu trang vật lý nên không chuyển thành envelope DB contract 2.1.0. Đây không phải kiểm tra trực tiếp nguồn VPS.

Bộ quan hệ tự động vẫn chưa sinh ứng viên trên các mẫu thật: chưa đạt khả năng truy hồi quan hệ. Đã bổ sung `review.py` tạo 32 mục đề xuất cho người duyệt với tên/chức vụ, sự kiện, ngày được nhắc đến và chứng cứ chính xác. `review_items.json` là phiếu hỗ trợ duyệt, KHÔNG phải envelope quan hệ hợp lệ để ghi graph_extractions/Neo4j. Các ID của phiếu không phải canonical entity IDs. Ca có nhiều chức vụ, ngữ cảnh công ty chưa xác minh vẫn được gắn cờ; không lấp ID hoặc trang giả.

Chạy lại audit tại FinMind/backend (sau khi cài requirements):

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/audit_person_roles_saved_sources.py --output-dir ../outputs/person-role-audit-moi
```

Script cần manifest, bộ 21 mẫu và registry bàn giao tại các đường dẫn đã ghi trong mã. Thư mục đầu ra phải chưa tồn tại.

15 test mới kiểm tra hướng cạnh, chức vụ gốc, ngày, mơ hồ, phủ định, nguồn hỏng, trang thiếu, tính ổn định và không công bố ứng viên. 51 test của gói bàn giao cũng đã chạy lại thành công. Mẫu DB CTG trang 1 chạy qua luồng chuẩn hóa/trích xuất và sinh 0 quan hệ, phù hợp nội dung chữ ký số; đây chỉ là ca âm tính.
