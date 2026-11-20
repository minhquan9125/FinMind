# Thời gian chính xác đến tháng trong contract 2.2.0

Ngày 04/11/2026 bổ sung profile xuất graph 2.2.0 cho nguồn chỉ ghi tháng và năm. Contract 2.0.0 và 2.1.0 giữ quy tắc ngày cũ; chúng không tự nhận các giá trị tháng. Runtime WBS02 r2 upstream không bị sửa.

Ví dụ temporal:

```json
{"as_of":null,"valid_from":"2024-04","valid_to":null,"valid_from_precision":"month"}
```

Các trường as_of, valid_from, valid_to vẫn bắt buộc trong envelope. Giá trị YYYY-MM cần trường tương ứng có hậu tố _precision bằng month; ngày đầy đủ có thể dùng day hoặc bỏ hậu tố. Không khai báo precision khi giá trị NULL. Validator kiểm tháng hợp lệ, ngày lịch, thứ tự khoảng thời gian; WBS06 còn đối chiếu tháng với đoạn nguồn nguyên văn. Không lấy năm báo cáo làm ngày hiệu lực.

JSON Schema mới ở backend/src/sprint4_runtime/contract.v2_2.schema.json và backend/src/person_role/contract/contract.v2_2.schema.json. Hai validator ứng dụng chọn profile theo schema_version; schema 2.1.0 cũ không bị thay đổi.

Neo4j lưu valid_from nguyên văn YYYY-MM cùng valid_from_precision=month. Các thuộc tính _lower và _upper là biên tính toán cho bộ lọc khoảng thời gian, không phải ngày sự kiện đã được nguồn xác nhận. Retrieval dùng các biên này để không bỏ sót tháng khi truy vấn theo ngày, đồng thời trả về precision để bên sử dụng trình bày đúng mức chắc chắn.

Giá trị valid_to NULL là chưa biết ngày kết thúc, không chứng minh chức vụ vẫn còn hiệu lực hiện tại. Hai quan hệ TCB có ghi limitations về phạm vi lịch sử; không dùng riêng chúng để kết luận chức vụ hiện nay.

## Triển khai hai quan hệ TCB

Phiên graph: 93567c73-7bc7-5076-b609-0515980d37d7.

Đã nạp thành công vào Neo4j ngày 04/11/2026, trạng thái READY: 2 cạnh HOLDS_ROLE. Đọc lại xác nhận tên, công ty, thuộc tính, bằng chứng và độ chính xác tháng; truy vấn cửa sổ ngày trong tháng cũng đạt. Receipt: reviewed-tcb/publish-receipt.json; kết quả đối chiếu PostgreSQL và Neo4j: reviewed-tcb/readback.json. Mỗi review có 2 audit; không tạo thêm phê duyệt khi chạy lại.

- Nguyễn Thu Lan — Phó Chủ tịch HĐQT Techcombank, nguồn BCTN 2024 trang PDF 54 ghi từ tháng 4/2024.
- Hồ Hùng Anh — Chủ tịch HĐQT Techcombank, nguồn BCTN 2024 trang PDF 53 ghi từ tháng 05/2008.

Đã nối đúng hai lượt nhắc với Person ID trong bản sao SQLite làm việc, dựa đồng thời vào tên, tài liệu, công ty, chức vụ và bằng chứng có sẵn. Bản SQLite bàn giao gốc giữ nguyên. Mỗi quan hệ có candidate ID mới, không thay ứng viên bất biến hoặc hồi sinh bản bị từ chối.

Hai review PostgreSQL đã APPROVED qua kiểm nguồn trực tiếp và có audit ban đầu + audit xác nhận. Xác nhận của người dùng trong workspace được ghi qua tài khoản proxy audit không hoạt động, không mật khẩu, không gán quyền đăng nhập hay vai trò administrator ứng dụng; không mạo nhận một tài khoản người dùng đã đăng nhập.

Sửa repository cập nhật dòng quarantine hiện có bằng UPDATE, thay vì INSERT ON CONFLICT vốn đòi quyền INSERT mà reviewer không có. Migration 20261104_graph_review_quarantine_lookup.sql cấp SELECT đúng cột review_id cần cho điều kiện UPDATE; không mở quyền tạo ứng viên cho reviewer.

Phương án cấp SELECT snapshot lâu dài cho graph_reader đã bị automatic approval review từ chối và không được áp dụng. Công cụ xuất dùng role WBS03 hiện có finmind_graph_writer trong transaction read-only để replay snapshot bằng quyền đã cấp sẵn; không thay quyền snapshot lâu dài.

## Tái lập bước xuất

Chạy tại FinMind, mở tunnel PostgreSQL 15433 và Neo4j 17687. Truyền NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE qua môi trường tiến trình, không ghi mật khẩu vào repo.

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe backend/scripts/publish_reviewed_people.py --intake outputs/wbs02-person-registry-20261104/reviewed-tcb --source-role finmind_graph_writer
.\.venv\Scripts\python.exe backend/scripts/publish_reviewed_people.py --intake outputs/wbs02-person-registry-20261104/reviewed-tcb --source-role finmind_graph_writer --apply
.\.venv\Scripts\python.exe backend/scripts/readback_reviewed_tcb_neo4j.py
```

Phải xem publish-receipt.json và readback.json để xác định phiên đã READY hay chưa; APPROVALS_COMMITTED chỉ chứng minh review PostgreSQL đã lưu, không chứng minh Neo4j đã nhận. Câu Cypher kiểm tra ở outputs/wbs02-person-registry-20261104/reviewed-tcb/Xem_tren_Neo4j.cypher.

Kiểm thử trước ghi review: 85 passed, 4 skipped do thiếu fixture. Sau cập nhật schema/export xử lý lỗi: 12 test mục tiêu đạt. Chưa commit hoặc push các thay đổi.
