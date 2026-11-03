# Đối chiếu WBS03 → WBS06 V4 → WBS08 (03/11/2026)

Nguồn kiểm tra: gói `WBS06_NHAN_13_APPROVED_V4_20261102.zip` Huyền bàn giao
trên máy Nhân và danh sách `WBS03-23-candidate-review.json` trong repo.
Bước kiểm tra ban đầu chỉ đọc file và không đổi review state. Sau đó Nhân xác
nhận được phép lưu 13 quan hệ và mở SSH tunnel Neo4j VPS.

Kết quả kiểm tra offline:

- Manifest có 13 envelope; SHA256 của cả 13 file khớp. Cả 13 ID ứng viên gốc
  xuất hiện trong danh sách 23 ứng viên WBS03; 13 ID bản duyệt là duy nhất.
- Cả 13 envelope qua `prepare_batch` của `Sprint4GraphStore`, mỗi envelope tạo
  một cạnh APPROVED dự kiến: 11 `HAS_SUBSIDIARY`, 2 `HAS_ASSOCIATE`.
- Huyền chốt nội dung 13 ca với tên và thời điểm trong gói V4. Gói không bao
  gồm quyết định lưu DB cho 10 ứng viên còn lại; không suy trạng thái của chúng
  chỉ từ sự vắng mặt trong gói này.
- Manifest V4 **tại lúc xuất gói** ghi `review_store_recorded=false`,
  `application_load_allowed=false`, `neo4j_ingested=false`, `database_writes=0`.
  Các giá trị này mô tả trạng thái cũ của gói, không tự cập nhật sau khi nạp.

WBS03 đã bàn giao đầu ra trích xuất 23 ứng viên, ID và bằng chứng nguồn; bước
APPROVED/REJECTED thuộc WBS06. Sau biên bản này, Nhân xác nhận trực tiếp 13 ca
được phép lưu vào Neo4j. Cờ `application_load_allowed=false` phản ánh trạng thái
gói lúc Huyền xuất, không phải lệnh cấm thay cho xác nhận mới này. Review store
vẫn chưa có bản ghi; cần báo rõ điều đó khi bàn giao/đánh giá WBS07.

Chuẩn bị nạp từ 13 envelope riêng đã lộ một xung đột: 3 canonical ID có danh
sách `aliases` khác nhau giữa các file, trong khi GraphStore yêu cầu cùng ID
có cùng fingerprint trong một phiên. `prepare_sprint4_review_batch.py` tạo một
envelope tổng hợp **không sửa ZIP gốc**: hợp danh sách alias cho từng canonical
ID, giữ nguyên các trường định danh khác và nguyên vẹn 13 quan hệ/evidence.
Đầu ra local Git-ignore: `backend/.tmp/wbs08-v4-prepared/approved-batch.json`
và `preflight.json`. Lô tổng hợp qua `prepare_batch`: 3 document, 19 chunk,
12 entity, 13 cạnh APPROVED; SHA256 ZIP và input hash ghi trong preflight.
Phiên graph `s4-bctn-b2550a0b-v4-20261102`, batch `approved-13-v4`.

## Kết quả ghi Neo4j VPS

- Trước khi ghi, phiên đích chưa tồn tại; kết nối đúng database `neo4j` qua
  tunnel `127.0.0.1:17687`.
- `ingest_batch` tạo **12 node và 13 cạnh**, trạng thái `BUILDING` với đúng
  corpus `b2550a0b-c423-5c50-9b15-6fb6af12e2c6` và index
  `ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d`.
- Đối chiếu chỉ đọc trước publish: 13/13 cạnh khớp ID, chiều, loại, thuộc
  tính, thời gian và evidence; khác biệt duy nhất là status `BUILDING` như dự kiến.
- Publish đúng một batch `approved-13-v4` thành `READY`.
  `verify_sprint4_graph.py` trả `passed: true`, `graph_relations: 13`,
  `errors: []`. Chạy lại cùng input trả `created: false`, không thêm cạnh.
- SHA256 ZIP nguồn: `9aeb4e53b857c3bb89d57d13afe40e4e608ac6ebbbb23b0ab09bf661d113fe54`.
  Input hash của batch tổng hợp:
  `ee87313c637e9022129eaf8378a23e010d5d62e3daf36aa59ec7f53e07a9ddd5`.

Đây là kết quả ghi/đọc Neo4j thật. Lượt này không đọc lại PostgreSQL, không
ghi review store, không sửa manifest V4 gốc và chưa nối graph retrieval WBS09
hoặc Hybrid Router live. Huyền/WBS07 cần đồng bộ trạng thái review store và
biên bản bàn giao với graph READY này; không coi cờ cũ trong ZIP là trạng thái
hiện tại của Neo4j.

Kiểm tra nhanh trong Neo4j Browser:

```cypher
MATCH (v:GraphVersion {id: 's4-bctn-b2550a0b-v4-20261102'})
RETURN v.status, v.corpus_id, v.index_version_id;

MATCH (s:GraphEntity)-[r:GRAPH_RELATION
  {graph_version_id: 's4-bctn-b2550a0b-v4-20261102'}]->(o:GraphEntity)
RETURN s.canonical_name, r.relation_type, o.canonical_name,
       r.relation_id, r.evidence_json;
```
