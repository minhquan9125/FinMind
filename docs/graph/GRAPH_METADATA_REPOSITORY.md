# Repository metadata graph trên PostgreSQL VPS

**Cập nhật:** đã bổ sung intake contract WBS03 2.1.0 ở `WBS03_DATABASE_PIPELINE.md`. Intake lưu draft riêng qua `graph_metadata.wbs03_envelopes` và các bảng public graph/evidence; không đổi bộ assertion source-bound mô tả dưới đây. Ghi chú chưa có adapter envelope bên dưới là phạm vi của lớp `GraphMetadataRepository`, không phải thiếu điểm tích hợp ở toàn dự án.

## Phạm vi

Migration `docker/postgres/migrations/20261030_graph_metadata.sql` bổ sung schema `graph_metadata` cho các bảng graph hiện có. Không đổi hoặc xóa extraction/evidence lịch sử, không chunk lại, không ghi Neo4j. Chỉ kiểm thử trên VPS PostgreSQL; chưa áp dụng hoặc kiểm thử dịch vụ Supabase.

Ba loại phiên bản độc lập:

- `metadata_schema_version=1.0.0`: cấu trúc lưu metadata bổ sung.
- `extraction_contract_version`: định dạng đầu vào. Dữ liệu backfill dùng `source-bound-person-role-v2`; đích phối hợp WBS03 là contract 2.1.0 nhưng chưa chuyển thành envelope 2.1.0.
- `graph_version_id`: UUID của một bộ quan hệ; liên kết riêng `corpus_version_id` và `index_version_id`.

Không gọi dữ liệu backfill là đã qua `validate_envelope` của WBS03. Đặc biệt FORMER_ROLE, RESIGNS, REQUESTS_RESIGNATION được giữ như nhãn lịch sử mở rộng; không ánh xạ tùy tiện sang HOLDS_ROLE hoặc DISMISSES. Repository này hỗ trợ ba nhãn lịch sử cùng HOLDS_ROLE/APPOINTS/DISMISSES; chưa hỗ trợ các loại quan hệ sở hữu/hợp tác của WBS03.

## Các bảng bổ sung

| Bảng | Vai trò |
|---|---|
| versions | Khóa ngoại graph/corpus/index, schema version, contract version, manifest hash và provenance |
| entities | Entity ID có phạm vi graph; tên, loại, trạng thái phân giải, thuộc tính |
| assertions | Liên kết extraction có sẵn với subject/object entity; payload và hash bất biến |
| source_chunks | Liên kết extraction với chunk thật; hash và kiểm tra membership corpus/index |
| reviews | Nhật ký append-only PENDING/APPROVED/REJECTED/QUARANTINED, reason, note, role thực thi và thời gian |

Ràng buộc khóa ngoại ghép ngăn liên kết entity/extraction sai phiên. Trigger kiểm tra hướng cạnh, tên với bản graph gốc, corpus/index, document và chunk hash. Có index tra subject/object, corpus/index, chunk, lịch sử review. Identity đã tồn tại chỉ được chấp nhận khi nội dung giống hệt; khác nội dung bị từ chối.

Entity người backfill chỉ có identity trong nguồn tài liệu, không khẳng định một danh tính toàn cục. Company entity có phạm vi graph, gắn mã công ty. Tất cả để `source_scoped`, không tự coi `resolved`. Tổng 169 entity là số entity có phạm vi nguồn/phiên, không phải 169 người.

## Repository

Module: `backend/src/person_role/metadata_repository.py`.

```python
from src.person_role.metadata_repository import GraphMetadataRepository

async with connection.transaction():
    repository = GraphMetadataRepository(connection)
    # Kết nối/pool cần dùng role theo đúng chức năng, không chạy runtime bằng admin.
    record = await repository.read_assertion(extraction_id)
    # record gồm payload, sources, reviews, review_status.
```

`register_version` đăng ký phiên và pin provenance. `put_assertion` nhận extraction đã tồn tại, hai entity, payload và chunk bindings; lưu nguyên tử. Đây không phải API tạo extraction WBS03 mới từ envelope. Khi tích hợp WBS03 cần adapter validate envelope và mapping extraction/chunk thực trước khi gọi repository; không giả chunk ID hoặc bbox.

`read_assertion` kiểm hash payload, membership và hash nguồn hiện hành, trả lịch sử review. Không có review thì trạng thái PENDING. `record_review` cần decision/reason_code/note rõ ràng, ghi actor từ current_user trong DB; actor là role DB, chưa phải hồ sơ người dùng UI.

Approval cần role reviewer, hai endpoint resolved có identity_key, nguồn SOURCE_VERIFIED và cơ sở thời gian. Các nhãn lịch sử ngoài contract chưa được APPROVED qua cơ chế này. Các entity backfill source_scoped không được tự APPROVED. Nhật ký review không tự thay g.validation_status, không tự xuất Neo4j. Quarantine là quyết định trong nhật ký metadata; không ghi giả vào `public.quarantine_records` và không xóa dữ liệu nguồn.

## Quyền và RLS

| Role NOLOGIN | Quyền metadata |
|---|---|
| finmind_graph_reader | SELECT |
| finmind_graph_writer | SELECT + INSERT phiên/entity/assertion/source; không sửa/xóa/review |
| finmind_graph_reviewer | SELECT + INSERT review; không sửa payload |

Tất cả bảng metadata bật ENABLE và FORCE ROW LEVEL SECURITY. Các role không superuser/BYPASSRLS. Không có SECURITY DEFINER để bỏ qua chính sách. Reader có SELECT nguồn graph/document/chunk/corpus/index qua policy riêng; không có quyền ghi nguồn từ migration này. Quyền developer cũ trên public vẫn còn, migration không thu hẹp quyền developer cũ. Không cấp reviewer cho developer hoặc chat runtime mặc định.

`finmind_developer` được kế thừa writer; `finmind_chat_runtime` được kế thừa reader. Cấu hình backend đang dùng admin không tự đổi sang role hạn chế bởi migration này; khi tích hợp repository vào pool, nhóm phải chọn role runtime tương ứng. Test đã SET LOCAL ROLE bằng đúng role runtime để kiểm tra quyền thực tế, không dùng kết quả admin để kết luận RLS.

## Chạy và kiểm tra

Từ thư mục FinMind, PYTHONPATH trỏ backend, tunnel VPS 15433 đang mở:

```powershell
.\.venv\Scripts\python.exe backend/scripts/inspect_graph_metadata.py
.\.venv\Scripts\python.exe backend/scripts/apply_graph_metadata.py
# Không --apply: thử migration/repository/quyền, sau đó rollback.
.\.venv\Scripts\python.exe backend/scripts/apply_graph_metadata.py --apply
.\.venv\Scripts\python.exe backend/scripts/verify_graph_metadata.py
```

Script backfill dành riêng graph hiện tại, không thay thế migration runner tổng quát. Review probe và thay đổi quyền probe đều rollback; không để lại review giả. Script apply chỉ commit sau khi các kiểm tra hoàn tất. Evidence ở `outputs/graph-metadata-20261030/`.

Không rollback bằng DROP CASCADE: schema metadata có thể có review thật sau nghiệm thu. Nếu cần hoàn tác vận hành, thu hồi membership metadata rồi dùng backup/migration được duyệt; giữ nguyên audit. Backup `vps-backup-20261030-121747` là trước migration này.
