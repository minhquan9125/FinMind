# WBS08 — đã nạp 34 quan hệ APPROVED ngày 05/11/2026

**Cập nhật sau lượt nạp này:** ba ca N18/N30/N40 đã được dựng bản nhập có provenance, kiểm lại LIVE và nạp vào phiên mới riêng; router đã nối và kiểm HTTP thật. Xem [biên bản bổ sung và runtime](WBS12-approved37-runtime-20261105.md). Các giới hạn ở cuối tài liệu này phản ánh thời điểm nạp 34 ca ban đầu.

Người dùng yêu cầu kiểm tra lại rồi nạp Neo4j. Đã hoàn tất lúc khoảng 15:46 (UTC+7).
Phạm vi là writer WBS08 từ envelope đã review, chưa phải nghiệm thu pipeline WBS09 qua review store.

| Thành phần | Kết quả |
|---|---|
| Neo4j | VPS qua tunnel `127.0.0.1:17687`, database `neo4j` |
| Graph version mới | `95260e20-ea3f-4d76-9ae5-185356cd437d` |
| Batch | `approved34-bcc55a4824a3` |
| Trạng thái | READY |
| Thực thể | 19 |
| Cạnh | 34: 30 HAS_SUBSIDIARY, 4 HAS_ASSOCIATE |
| Corpus | `b2550a0b-c423-5c50-9b15-6fb6af12e2c6` |
| Index | `ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d` |
| Người review trong envelope | `Codex-AI-assisted-WBS06-review` — giữ nguyên thông tin gốc |

## Đầu vào và preflight

ZIP `WBS06_REVIEW_NHAN_20261105.zip`, SHA256 `bcc55a4824a34bb184ee26a5e56aa6fd0870d2d66d07c569cb28427066afc354`. CRC và 150 hash file khớp. Chọn đúng 34 envelope APPROVED, đối chiếu ID/hash/mapping/reviewer/thời điểm với quyết định trong gói.

Các envelope riêng lẻ có tám entity ID mang các bộ alias khác nhau. Vì fingerprint entity của writer bao gồm aliases, không dùng vòng lặp nạp từng envelope như hướng dẫn ban đầu. Đã tái sử dụng `merge_envelopes()` để hợp nhất alias trong một batch; không có conflict hoặc nhóm quan hệ trùng, giữ nguyên toàn bộ 34 relation ID, thuộc tính, thời gian, review và evidence. Không sửa ZIP hoặc envelope gốc.

PostgreSQL LIVE: `PostgresSourceReader` + `compare_source` xác minh 176/176 evidence reference trên 33 chunk riêng biệt, kiểm version/hash/locator/quote. Transaction `read_only=on`, isolation `repeatable read`; không ghi PostgreSQL. Review store đã có bảng, nhưng không tìm thấy quyết định tương ứng 34 reviewed candidate ID; chưa đồng bộ quyết định vào store.

Neo4j trước nạp: bốn phiên READY đã tồn tại (gồm graph 13 cạnh cũ, graph chức vụ hai cạnh và hai fixture smoke); không có relation ID nào trùng với 34 ID cần nạp. Các constraint Sprint 4 đã có. Không sửa schema hoặc dùng lại version cũ.

## Thao tác và đối chiếu

- `Sprint4GraphStore.ingest_batch()` ghi một batch nguyên tử vào UUID mới, trạng thái BUILDING.
- Trước publish: kiểm đúng hash batch, entity count, relation ID, chiều, toàn bộ thuộc tính, thời gian và evidence. Toàn phiên có đúng 34 cạnh/34 ID riêng và 19 entity.
- Thử nạp lại cùng batch: `created=false`, không tạo trùng.
- Công bố đúng danh sách một batch thành READY.
- Sau publish: chạy script độc lập `verify_sprint4_graph.py`, kết quả `passed=true`, `errors=[]`, 34/34 cạnh khớp.
- So fingerprint dữ liệu Sprint 4 cũ trước/sau (GraphVersion, GraphBatch, GraphEntity, GRAPH_RELATION): không đổi. Hash `37c250f6975734e9177eeee35cfcd4c8c1e077472d7652c6c42cae10ee88fd44`.

Input hash của batch đã chuẩn bị: `2e45aa41deaa1305433808546ea893b9c86478ee61187ab622d84df6c0f3af31`.

Receipt và đầu vào tái lập local: `backend/.tmp/wbs08-approved34-import-20261105/`, gồm `approved-batch.json`, `preflight.json`, `live-preflight.json`, `duplicate-preflight.json`, `old-graph-snapshot.json`, `load-receipt.json`, `graph-counts.json`. Các file này bị Git ignore; không có mật khẩu trong receipt.

Kiểm tra lại bằng lệnh chỉ đọc từ gốc repo khi tunnel mở:

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m backend.scripts.verify_sprint4_graph --input backend/.tmp/wbs08-approved34-import-20261105/approved-batch.json --version 95260e20-ea3f-4d76-9ae5-185356cd437d --batch-id approved34-bcc55a4824a3 --env-file backend/.env.neo4j-vps
```

Xem graph trong Neo4j Browser:

```cypher
MATCH p=(:GraphEntity)-[:GRAPH_RELATION {
  graph_version_id:'95260e20-ea3f-4d76-9ae5-185356cd437d'
}]->(:GraphEntity)
RETURN p;
```

## Phần còn lại

N18/N30/N40 đã có biên bản APPROVED nhưng chưa có ba envelope APPROVED riêng tại máy trong lượt này, nên chưa nạp. Đặc biệt N40 phải dùng bản duyệt có evidence nối tiếp, không đổi trạng thái proposal PENDING để thay thế. Chín ca CMG không nằm trong batch này.

Chưa kích hoạt registry r3, chưa sửa cấu hình phiên graph của router, chưa ghi review store hoặc xác nhận E2E/WBS17. Việc thêm phiên mới vào phạm vi trả lời cần cấu hình và kiểm retrieval riêng; READY trong Neo4j không tự cập nhật mọi ứng dụng đang chạy.
