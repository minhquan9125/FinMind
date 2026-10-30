# Luồng WBS03 → PostgreSQL VPS

## Đã tích hợp

Chunk BCTN có sẵn trong frozen corpus → reader pin nguồn/replay/hash → envelope DB contract 2.1.0 → bộ chuẩn hóa WBS02 và rule WBS03 → validate envelope → kiểm tra lại nguồn trên VPS → lưu nguyên tử → đọc lại.

Không gọi AI/LLM, không chunk hoặc embedding lại, không tự APPROVED. Đầu ra trích xuất luôn là ứng viên PENDING. Luồng không tự xuất Neo4j hoặc kích hoạt graph mới cho chat.

Phạm vi adapter nguồn hiện tại: BCTN có trang PDF thật, đã đăng ký trong corpus/index trên VPS. Từ chối nguồn PDF offline/bbox chưa đăng ký và nguồn không có trang; không bịa số trang cho web. Contract DB source dùng document_id thực trong release, riêng locator reconstruction giữ source ID gốc và được reader kiểm tra ánh xạ.

`document_version` là source_view_sha256 của section, không phải UUID phiên graph. Các trang khác nhau có thể có source_view khác nhau; khi đó phải tách envelope theo source view, không ép chung document_version.

## Chạy từ FinMind

Python cần backend/requirements.txt; mở tunnel VPS 15433. Có thể dùng môi trường ảo của dự án:

```powershell
$env:PYTHONPATH = "$PWD\backend"

# Đã có file đầu ra WBS03 đúng contract 2.1.0: kiểm tra trước, chưa ghi.
.\.venv\Scripts\python.exe backend/scripts/run_wbs03_pipeline.py --input "duong-dan\wbs03-output.json" --output outputs/wbs03-run

# Lưu sau khi nguồn đã kiểm tra; kiểm tra lại nguồn luôn chạy trong bước lưu.
.\.venv\Scripts\python.exe backend/scripts/run_wbs03_pipeline.py --input "duong-dan\wbs03-output.json" --apply --output outputs/wbs03-run
```

Để đọc chunk đã có trong corpus và tự chạy rule:

```powershell
.\.venv\Scripts\python.exe backend/scripts/run_wbs03_pipeline.py --corpus b2550a0b-c423-5c50-9b15-6fb6af12e2c6 --chunk 8dccc6a1-792d-56a7-854b-1486d0f39987 --output outputs/wbs03-rule-run
```

Mặc định là strict extractor: chỉ tạo cạnh khi câu có liên kết người–công ty–chức vụ rõ ràng, có thể trả 0 cạnh. Không lấy header công ty để kết luận mọi người trong body làm cho công ty đó.

Nếu chủ động tạo phiếu ứng viên từ bảng BCTN để review, thêm `--review-candidates`. Chế độ này cho phép dùng bối cảnh công ty trong header nhưng giữ cờ UNCERTAIN/unverified; không phải kết quả đã chứng minh quan hệ. Registry mặc định đi kèm Git tại `backend/resources/person_role/company.registry.json`. Chế độ `--input` không phụ thuộc registry này.

Thêm `--apply` mới ghi DB. Nếu lần cào mới chưa có trong frozen corpus, phải hoàn thành bước đăng ký nguồn/corpus/chunk trước; không truyền thẳng JSON crawler tùy ý vào intake. Chưa tự lập lịch crawler hoặc sửa repository riêng của thành viên.

## Thành viên gọi trực tiếp trong code

```python
from src.person_role.wbs03_repository import WBS03Repository

# Dùng kết nối/pool được phép SET ROLE finmind_graph_writer,
# hoặc tài khoản kế thừa role writer. Không dùng role reviewer/admin cho runtime.
result = await WBS03Repository(connection).save(wbs03_envelope)
roundtrip = await WBS03Repository(connection).read(result['graph_version_id'])
assert roundtrip == wbs03_envelope
```

Nếu caller đang trong transaction, nên dùng repeatable_read cho cả luồng. Khi chưa có transaction, save tự mở repeatable_read. Không tái sử dụng instance cache giữa các release/transaction: tạo repository cho từng lượt xử lý. Hàm save validate structure và replay chunk thật trước khi ghi; read kiểm schema/hash envelope lưu. Quyền read của chat runtime không cho phép save.

## Lưu ở đâu

- `graph_metadata.wbs03_envelopes`: envelope đầy đủ, gồm original entity ID, aliases, resolution_status, mentions, relations, evidence, temporal và review. Schema version, corpus/index và hash tách riêng.
- `public.graph_versions`: một phiên `EXTRACTED_PENDING`, ID xác định từ nội dung envelope.
- `public.graph_extractions`: mỗi relation là một extraction với ID xác định, method WBS03, validation CONTRACT_VALIDATED, manual_check PENDING.
- `public.evidence`: bằng chứng từng relation, chunk thật, quote, locator, temporal, entity ID của WBS03, công ty/kỳ và URL nguồn lấy từ tài liệu trong DB.

Không gộp những ứng viên này vào 184 assertion source-bound đã đối chiếu ở schema metadata trước đó. Khi truy vấn phải pin graph_version_id. `CONTRACT_VALIDATED` không đồng nghĩa SOURCE_VERIFIED hoặc APPROVED.

Canonical name có thể null cho entity unresolved theo contract. Cột subject/object của graph dùng canonical name nếu có, nếu không dùng alias nguồn để hiển thị; không sửa canonical_name, identity_key hoặc trạng thái phân giải trong envelope.

Tất cả relation type hợp lệ của contract được kiểm bởi validator trước khi lưu. Bộ rule hiện chỉ trích các quan hệ người–chức vụ nó hỗ trợ. Intake không nhận envelope đã APPROVED/REJECTED: review là luồng riêng. Chưa có UI/endpoint duyệt các draft này.

## Bảo đảm và nghiệm thu

- Ghi graph/envelope/extraction/evidence trong một transaction.
- Retry cùng envelope ra cùng UUID, không nhân đôi.
- Sai snapshot hash, URI, text/locator, corpus/index hoặc source membership bị từ chối trước ghi.
- Role writer có INSERT draft giới hạn bởi RLS; reader chỉ đọc. Root envelope cũng ENABLE/FORCE RLS.
- Không nhận kết quả synthetic fixture để giả thành nguồn thật.

Test live: `backend/scripts/test_wbs03_pipeline_vps.py --apply`. Migration chỉ được commit sau khi test đạt; các probe dữ liệu rollback. Test có 9 ứng viên review từ chunk ELC thật. Bản chạy thực được lưu riêng và xác minh sau commit bằng `backend/scripts/verify_wbs03_draft.py`.

Evidence, kết quả chạy thực và SQL xem: `outputs/wbs03-pipeline-20261030/`. Backup tạo lúc 12:17 trước các migration metadata chưa bao gồm phần này.
