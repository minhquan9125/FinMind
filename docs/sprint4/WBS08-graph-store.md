# WBS08 – lưu graph Sprint 4 vào Neo4j

## Quy ước để nhóm tích hợp

Đầu vào là **envelope JSON contract 2.1.0** của WBS01/WBS02. Không đọc PDF,
OCR, chia chunk hay đổi schema PostgreSQL. `graph_version_id` là ID của **một
lần xây graph**; `corpus_id` và `dataset_version` đến nguyên từ envelope.
Mỗi envelope được nạp với một `batch_id` ổn định (nên dùng ID tài liệu hoặc
ID extraction do WBS07 cấp). WBS07/WBS09 chỉ cần truyền hai ID này khi gọi
`Sprint4GraphStore.ingest_batch(...)`.

Khóa thực thể Neo4j là hash của `[graph_version_id, entity_id]`; khóa cạnh là
hash của `[graph_version_id, relation_id]`. `relation_id` là khóa extraction
trong contract, **không tự tạo ID mới**. Cạnh `GRAPH_RELATION` đi từ
`subject_id` sang `object_id`, thuộc tính `relation_type` giữ đúng tên quan hệ
contract. Với `COOPERATES_WITH`, contract đã chuẩn hóa chiều theo ID. Các
thực thể có label `Company`, `Person` hoặc `Event` và `GraphEntity`.

Chỉ relation có review `APPROVED` được ghi. Contract dùng chung kiểm tra
reviewer, thời điểm, endpoint, bằng chứng và các thuộc tính bắt buộc trước khi
ghi. `PENDING`/`REJECTED` vẫn ở hệ kiểm duyệt PostgreSQL; lô không có cạnh
được duyệt vẫn được ghi nhận là đã xử lý. Cạnh lưu `relation_id`, `source_batch_id`,
`corpus_id`, `index_version_id`, thời gian, reviewer và `evidence_json` gồm
`document_id`, `chunk_id`, `document_version`, locator và quote. Đây là dữ liệu
để WBS09 đọc lại nguồn, không thay thế việc kiểm tra nguồn từ PostgreSQL.

Một lô và toàn bộ cạnh/node của nó nằm trong **một transaction**. Lỗi sẽ
rollback lô; chạy lại cùng `batch_id` và JSON là no-op, nội dung khác bị chặn.
Một phiên giữ trạng thái `BUILDING` đến khi `publish` nhận **đúng toàn bộ**
danh sách batch dự kiến; chỉ phiên `READY` được `get_ready_relations` trả về.
Sau khi READY, phiên bất biến. Khi review/nguồn thay đổi, xây phiên mới, không
ghi đè phiên cũ. WBS09 chịu trách nhiệm xác định danh sách lô hoàn chỉnh và
chỉ công bố khi các bước đối chiếu ngoài Neo4j cũng đạt.

## Chạy thử trên Neo4j

Đặt `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` trong
`backend/.env`, hoặc dùng `--env-file` để chỉ tới file cấu hình riêng. File
chứa mật khẩu phải được giữ ngoài Git. Dùng database thử nghiệm; fixture có
công ty giả.
Từ thư mục gốc repo, trong PowerShell:

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.ingest_sprint4_graph ingest --input backend/tests/fixtures/wbs08_graph_contract.json --version wbs08-local-v1 --batch-id fixture-report
backend/.venv/Scripts/python.exe -m backend.scripts.ingest_sprint4_graph status --version wbs08-local-v1
backend/.venv/Scripts/python.exe -m backend.scripts.ingest_sprint4_graph publish --version wbs08-local-v1 --expected-batch fixture-report
```

Nếu chạy Neo4j trên VPS, mở SSH tunnel trong một cửa sổ riêng (không công bố
cổng Neo4j ra Internet):

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:17687:127.0.0.1:7687 -L 127.0.0.1:17474:127.0.0.1:7474 nhan@160.250.181.10
```

Cấu hình file riêng đã ignore `backend/.env.neo4j-vps` với
`NEO4J_URI=bolt://127.0.0.1:17687`, `NEO4J_USER=neo4j`, mật khẩu được cấp
riêng và `NEO4J_DATABASE=neo4j`. Thêm `--env-file backend/.env.neo4j-vps`
**trước** `ingest`, `status` hoặc `publish` trong các lệnh trên. Mở
`http://127.0.0.1:17474` để xem Neo4j Browser khi tunnel đang chạy.

Chạy lại lệnh `ingest` đầu tiên sẽ trả `created: false`. Thử `publish` với
thêm `--expected-batch missing-report` sẽ báo lỗi và giữ trạng thái BUILDING.
Sau READY, kiểm tra bằng Neo4j Browser:

```cypher
MATCH (v:GraphVersion {id:'wbs08-local-v1'}) RETURN v.status;
MATCH (s:GraphEntity)-[r:GRAPH_RELATION {graph_version_id:'wbs08-local-v1'}]->(o:GraphEntity)
RETURN s.entity_id, r.relation_type, o.entity_id, r.relation_id, r.evidence_json;
```

Fixture gồm một quan hệ APPROVED và một PENDING; Neo4j phải có **một cạnh**.
Unit test không đụng database:

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m unittest backend.tests.test_sprint4_graph_store -q
```

## Đối chiếu một batch BCTN thật sau khi được duyệt

WBS06 cần bàn giao **envelope contract 2.1.0 đầy đủ** với ít nhất một relation
`APPROVED`, có reviewer, thời điểm review và các thuộc tính contract yêu cầu.
`WBS03-23-candidate-review.json` chỉ là gói để review; không phải đầu vào nạp
graph. Không tự sửa `PENDING` thành `APPROVED` để chạy thử.

Sau khi nạp batch vào **phiên graph mới** và công bố đủ danh sách batch là
`READY`, dùng đúng `graph_version_id` và `batch_id` đã nạp:

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.verify_sprint4_graph --input <approved-envelope.json> --version <graph-version-id> --batch-id <batch-id> --env-file backend/.env.neo4j-vps
backend/.venv/Scripts/python.exe -X utf8 -m unittest backend.tests.test_sprint4_graph_store backend.tests.test_verify_sprint4_graph -q
```

Lệnh `verify_sprint4_graph.py` chỉ dùng truy vấn đọc. Nó kiểm phiên `READY`,
corpus/index, hash và số lượng của batch, rồi so từng cạnh `APPROVED` theo
`relation_id`, chiều subject/object, loại, thuộc tính, thời gian và toàn bộ
`evidence_json` (document ID, chunk ID, locator, quote). Kết quả `passed: true`
mới là đối chiếu Neo4j với envelope đã duyệt; lỗi trả `passed: false` và mã
thoát khác 0. Nó không đối chiếu PDF hoặc nguồn PostgreSQL lần nữa — bước đó
thuộc reader/kiểm nguồn trước khi duyệt.

Ngày 30/10/2026 đã thử ghi/đọc trên Neo4j Community `2026.10.1` chạy riêng
trên VPS: nạp batch lần đầu có 2 node và 1 cạnh APPROVED; chạy lại cùng batch
không tạo trùng; batch chỉ có PENDING tạo 0 cạnh; `publish` thiếu batch bị
chặn; công bố đủ batch trả `READY` và đọc lại đúng một cạnh cùng ID, chiều và
evidence. Đã thử lại CLI sau khi cập nhật code trên phiên
`wbs08-smoke-20261030b`, nạp 2 node/1 cạnh, công bố và đọc lại cạnh đúng.
30 test liên quan WBS03/WBS08 qua. Đây là kiểm thử **fixture** của GraphStore,
chưa phải nghiệm thu chất lượng extraction BCTN hay ingest quan hệ thật đã
được WBS06 duyệt.
