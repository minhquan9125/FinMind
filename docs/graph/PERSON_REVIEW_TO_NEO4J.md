# Tiếp nhận dữ liệu nhân sự và xuất Neo4j qua WBS06

## Triển khai ngày 03/11/2026

Đã tạo `public.graph_review_results`, `public.graph_review_audit`, bảng nội bộ giữ trạng thái từ chối `graph_review_candidate_state`; mở rộng `quarantine_records` bằng các cột mà repository WBS06 cần. Không sửa payload/định danh/quyết định của bộ metadata cũ.

Phiên tiếp nhận PostgreSQL: `89631a45-d8fe-532b-b190-dd74fff75811`, trạng thái `EXTRACTED_PENDING`.

| Kết quả | Số bản |
|---|---:|
| Đã lưu PENDING | 126 |
| Đã lưu REJECTED theo báo cáo WBS06 | 2 |
| Chặn ở bước chuyển đổi bằng chứng, chưa ghi thành terminal rejection | 59 |
| Tổng đầu vào | 187 |
| APPROVED trong review store | 0 |
| Nhân sự được nạp Neo4j | 0 |

185 APPROVED trong Markdown là kết luận kiểm nội dung nguồn, khác quyết định review ứng dụng. Các lỗi adapter của 59 bản không phủ định kết luận nội dung đó. Bản gốc, SOURCE_CONFLICT và metadata cũ vẫn giữ nguyên.

Đã commit và kiểm bằng kết nối mới: 128 bản review, 128 audit ban đầu, 128 dòng quarantine; không còn bản probe. Giữ nguyên dữ liệu công ty/phiên Neo4j đang có. Receipt tại `outputs/person-neo4j-publish-20261103/intake/`.

## Các bảo đảm

- Mỗi nguồn được replay qua PostgresSourceReader, giữ document/corpus/index/hash/locator thật. Không tạo chunk hoặc trang PDF giả.
- Công ty chỉ resolve theo registry đã kiểm và ticker khớp duy nhất. Người source_scoped vẫn unresolved nếu chưa có mapping được kiểm.
- Snapshot as_of là thời điểm quan sát nội dung, không biến thành ngày bổ nhiệm. Không lấy report_year tạo ngày 31/12 hoặc điền ngày hiện tại.
- Role `finmind_graph_intake` chỉ tiếp nhận PENDING/REJECTED; có quyền khóa dòng cho repository nhưng không được UPDATE hay tự APPROVED/DELETE. Audit append-only.
- Trạng thái REJECTED được giữ ở DB trên từng candidate, kể cả giữa nhiều graph version; row state chống race khi dùng repeatable-read. Probe kiểm reset/duyệt lại/đổi payload đã rollback.
- Đường legacy `GraphMetadataRepository.record_review` cũng đã chặn mở lại REJECTED tại Python và DB bằng migration `20261103_legacy_review_terminal.sql`. Probe live rollback xác nhận không đổi số quyết định legacy (vẫn 0). Không đồng bộ giả quyết định từ Markdown vào legacy.
- Có một user audit tự động **inactive, không mật khẩu, không role ứng dụng**, tên `graph_intake_service`, chỉ để đáp ứng FK audit. Không giả làm người duyệt, không cấp đăng nhập/admin.
- `publish_reviewed_people.py` chỉ dùng approval đã lưu, revalidate nguồn qua WBS06, kiểm contract 2.1.0, qua WBS09 rồi mới gọi writer. Không có approval thì không mở kết nối Neo4j và không tạo phiên READY rỗng.

## Chạy

Từ FinMind, dùng môi trường dự án và mở tunnel PostgreSQL 15433. Lần triển khai schema cần tài khoản migration có quyền tạo role/bảng; không dùng quyền này cho API chat.

```powershell
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe backend/scripts/intake_person_reviews.py
# Dry-run: nguồn thật và phép lưu/đọc/quyền thật, sau đó rollback toàn transaction.
.\.venv\Scripts\python.exe backend/scripts/intake_person_reviews.py --apply
.\.venv\Scripts\python.exe backend/scripts/verify_person_review_intake.py
.\.venv\Scripts\python.exe backend/scripts/publish_reviewed_people.py
# --apply ở publisher mới cho phép ghi Neo4j nếu gate đạt.
```

Credentials Neo4j lấy từ môi trường tiến trình `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`; không lưu mật khẩu vào các artifact hoặc Git. PostgreSQL dùng cấu hình hiện có qua helper dsn().

Migration có thể replay; ID candidate phụ thuộc nội dung/adapter và nguồn, ID phiên phụ thuộc hash báo cáo/registry. Chạy lại cùng dữ liệu không tạo thêm review/audit. Đổi identity/claim tạo bản đầu vào mới để duyệt lại, không sửa ngầm candidate cũ.

## Phần chưa hoàn thành để nạp thật

1. WBS02/WBS06 đối chiếu định danh người. Mẫu `person-registry-TO_VERIFY.json` cố ý để `verified=false`, `identity_key=null`. Không bật tất cả thành true chỉ để qua gate. Mỗi mapping được kiểm có canonical entity ID, identity_key, tên/alias và `source_entity_ids` được nối đúng.
2. Registry bổ sung đã kiểm có thể truyền bằng `--registry <file.json>`; CLI giữ registry công ty mặc định và hợp nhất mapping bổ sung, từ chối định danh xung đột. Không yêu cầu cập nhật trực tiếp source_scoped trong bảng metadata cũ.
3. Giải quyết cảnh báo định danh/thời gian, thu hẹp quote/ràng buộc đúng người cho các đoạn trang/bảng. Lưu review qua PostgresReviewStore bằng role reviewer, actor đã xác thực và revision đúng. Reviewer không được bỏ qua lỗi nguồn hoặc các cảnh báo identity/time.
4. `conversion-blocked.json` là 59 đầu vào cần sửa cách biểu diễn bằng chứng, có origin_extraction_id; không phải 59 bản REJECTED nghiệp vụ. Nhãn lịch sử chưa được contract hỗ trợ phải mở rộng contract thống nhất trước, không đổi thành HOLDS_ROLE/DISMISSES tùy tiện.
5. Contract 2.1.0 hiện yêu cầu PDF page nguyên dương cho db_text_span. Nguồn web không có trang cần source profile được thống nhất; publisher sẽ chặn thay vì gán trang giả.
6. Chạy lại publisher sau khi có approval hợp lệ; kiểm receipt READY, node/cạnh, truy ngược nguồn, idempotency trước bàn giao. Bước này chưa đạt ở lần triển khai hiện tại.

Chưa có UI/endpoint review mới trong phạm vi lượt này; không cập nhật trạng thái bằng SQL tùy ý. Không commit dump, candidates chứa toàn văn hoặc `.env`. Thay đổi code chưa commit/push.
