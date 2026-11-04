# Tích hợp Person Registry WBS02 r2

Ngày 04/11/2026, tích hợp gói WBS02_PERSON_REGISTRY_20261104_r2 của Hưng vào bước chuẩn hóa trước khi trích quan hệ. Runtime upstream nằm riêng tại backend/src/wbs02_person_registry; không ghi đè validator/resolver hiện có. Các file upstream được sao chép nguyên văn và giữ manifest nguồn trong backend/resources/person_role/wbs02-r2.

Kết quả triển khai mới nhất: 2 quan hệ TCB đã APPROVED trong PostgreSQL, nạp Neo4j thành phiên READY và đọc lại thành công. Phiên: 93567c73-7bc7-5076-b609-0515980d37d7. Bằng chứng thực thi ở outputs/wbs02-person-registry-20261104/reviewed-tcb/readback.json. Các mục mô tả chặn/chưa nạp dưới đây là lịch sử trước khi hoàn tất bước xuất; không suy đây là toàn bộ nhân sự hoặc chức vụ hiện tại.

## Đính chính sau kiểm tra trước khi duyệt

Cập nhật tiếp ngày 04/11: đã xử lý hai lượt nhắc trong SQLite làm việc và bổ sung profile thời gian 2.2.0; hai quyết định review PostgreSQL đã APPROVED, gate nguồn thật đạt. Xem GRAPH_MONTH_PRECISION_2_2.md và receipt tại outputs/wbs02-person-registry-20261104/reviewed-tcb để biết kết quả xuất Neo4j. Các mô tả vướng mắc dưới đây ghi lại tình trạng trước bước sửa, không phải trạng thái hiện hành.

Ba ứng viên của mẫu ban đầu không đồng nghĩa ba quan hệ đúng hoặc đủ điều kiện duyệt. Kiểm tra trực tiếp phát hiện câu ghép cột “Tiến sĩ Lottner được bổ nhiệm làm Tổng Giám đốc Ông Phạm Quang Thắng...” khiến extractor gán nhầm Phạm Quang Thắng làm đối tượng bổ nhiệm. Đã thêm guard và test hồi quy, bản này chuyển sang abstention; không ghi thành quyết định từ chối nghiệp vụ.

Đầu ra sửa ở outputs/wbs02-person-registry-20261104/tcb-corrected: 2 ứng viên HOLDS_ROLE (Nguyễn Thu Lan, Hồ Hùng Anh), 37 abstention. Các lượt nhắc của 2 ứng viên này chưa được registry duyệt đúng span, dù cùng tên có ID xác minh ở các span khác; không tự chuyển ID. Mốc chức vụ trên nguồn là tháng 04/2024 và 05/2008, chưa có ngày chính xác để điền temporal ISO ngày theo contract hiện tại. Không thêm ngày 01 theo suy đoán.

Người dùng đã xác nhận duyệt trong hội thoại. Chưa có cập nhật APPROVED trong database hoặc ghi Neo4j do preflight còn cảnh báo identity/thời gian/thuộc tính. Chi tiết nguồn và kết quả WBS06 ở approval-corrected-preflight.json. Cần áp dụng quyết định danh tính cho đúng lượt nhắc và thống nhất hỗ trợ độ chính xác tháng hoặc tìm nguồn có mốc ngày đủ căn cứ. Không dùng báo cáo năm hoặc thời điểm duyệt thay ngày hiệu lực.

Sau sửa: 37 test đạt, 4 skipped. Các số 3 quan hệ/36 abstention/36 test trong mục lịch sử dưới đây là kết quả trước sửa; verification.json cũ là receipt kiểm nguồn mẫu, không phải receipt APPROVED.

## Kết quả kiểm tra

- Bản sao 17 file nguồn/dữ liệu khớp manifest upstream. Toàn gói gốc đã đối chiếu 20/20 file.
- SQLite có 10 Person, 21 lượt nhắc được xác minh, 938 lượt nhắc chờ duyệt.
- Mẫu Techcombank áp dụng đủ 21 ngữ cảnh đã duyệt vào 10 ID; hai Nguyễn Anh Tuấn giữ hai ID riêng.
- Reader VPS xác minh lại 24 chunk thuộc mẫu, đúng corpus/index/document/hash/locator. Kết quả SOURCE_VERIFIED_DRY_RUN.
- Trích được 3 quan hệ PENDING và 36 trường hợp abstention của bộ quy tắc; không khẳng định đã trích đủ nhân sự từ mẫu.
- 36 test tích hợp/hồi quy đạt; 4 skipped do thiếu fixture, không tính là đạt. 11 test upstream đạt.
- Chưa ghi PostgreSQL hoặc Neo4j. Định danh Person được xác minh không thay thế bước duyệt quan hệ WBS06.

Biên bản tái lập: outputs/wbs02-person-registry-20261104/verification.json; đầu ra nguồn thật: live-source-check/result.json.

## Chạy trích quan hệ từ envelope có sẵn

Chạy PowerShell tại thư mục FinMind. Chọn output-dir mới mỗi lần.

```powershell
$env:PYTHONPATH='backend'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe backend/scripts/extract_person_roles.py --input backend/resources/person_role/wbs02-r2/examples/tcb.resolve.input.json --normalize --registry backend/resources/person_role/wbs02-r2/company.registry.json --person-store backend/resources/person_role/wbs02-r2/person.registry.sqlite --output-dir outputs/person-registry-run-moi
```

--person-store bắt buộc đi cùng --normalize. Adapter mở SQLite mode=ro, chỉ áp dụng quyết định khớp pin nguồn và span. Người cùng tên ở nguồn chưa có quyết định vẫn unresolved. Đổi text/locator trong cùng snapshot bị chặn. Mẫu không được dùng như dữ liệu vừa cào mới.

## Chạy từ chunk đăng ký trong PostgreSQL

Mở tunnel PostgreSQL 15433 rồi chạy; thay CHUNK_UUID_THAT bằng chunk ID thuộc corpus đang pin.

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe backend/scripts/run_wbs03_pipeline.py --corpus b2550a0b-c423-5c50-9b15-6fb6af12e2c6 --chunk CHUNK_UUID_THAT --person-store backend/resources/person_role/wbs02-r2/person.registry.sqlite --output outputs/wbs03-person-run-moi
```

Mặc định kiểm nguồn và dry-run. Thêm --apply chỉ khi cần lưu draft WBS03 sau khi đã xem đầu ra. Không kết hợp --person-store với --input hoặc --review-candidates; envelope đã có kết quả phải được kiểm riêng, không giải lại ID sau khi trích quan hệ.

## BCTN mới và duyệt danh tính

Resolver đọc không tự ghi vào SQLite. Pipeline có envelope contract 2.1.0 mới thì gọi CLI ingest rõ ràng:

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe -m src.wbs02_person_registry.person_registry --db backend/resources/person_role/wbs02-r2/person.registry.sqlite ingest --input DUONG_DAN_ENVELOPE_MOI.json --company-map DUONG_DAN_COMPANY_MAP.json
.\.venv\Scripts\python.exe -m src.wbs02_person_registry.person_registry --db backend/resources/person_role/wbs02-r2/person.registry.sqlite pending --output outputs/person-cho-duyet-moi.json
```

Người duyệt kiểm nguồn rồi dùng lệnh review của upstream với mention-id, reviewer, reason và expected-revision. Không chuyển các lượt chờ duyệt sang resolved theo tên, không tạo ngày hiệu lực từ năm báo cáo. Sau ingest/review SQLite thay đổi có chủ đích, phải xuất snapshot và biên bản mới; manifest r2 chỉ mô tả bản bàn giao ban đầu.

Các bảng person/source/mention/decision và view latest thuộc SQLite registry cục bộ. Chúng không phải các bảng PostgreSQL mới. Chưa triển khai lịch chạy tự động hoặc thay pipeline chat/phiên graph đang phục vụ.
