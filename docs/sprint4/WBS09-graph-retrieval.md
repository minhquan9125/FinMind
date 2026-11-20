# WBS09 – tích hợp nhánh trích xuất và graph retrieval

Trạng thái 03/11/2026: **xong code (09.1–09.4), đã nối gate WBS06
(`backend/src/graph_review`)**. Đã tái tạo envelope V4 của Nhân (13 APPROVED, ID khớp
handoff) và chạy thử toàn luồng: gate WBS06 thật + nguồn DB thật + review store bộ nhớ
+ Neo4j giả → `READY`, 13/13 cạnh. Chưa nạp Neo4j thật: review store chung chưa có trên DB.

## Luồng

```
envelope 2.1.0 (doanh nghiệp / chức vụ / sự kiện)
  -> merge_envelopes          09.1 + 09.2  backend/src/graph/wbs09_pipeline.py
  -> graph_review.build_gate  WBS06: đọc lại review store + nguồn, ràng buộc digest envelope
  -> Sprint4GraphStore        WBS08, một batch cho mỗi lần build
  -> đối chiếu cạnh Neo4j = tập APPROVED -> publish READY
  -> RelationRetrieval        09.4         backend/src/graph/relation_retrieval.py
  -> LiveGraphAdapter         hybrid router (find_relationships, find_subsidiaries,
                              resolve_event_entities, expand_market_context)
```

## Quy tắc

- Mọi envelope phải qua `validate_envelope` và **cùng** `corpus_id`/`dataset_version`.
  BCTN và News khác index nên build thành **graph version riêng**; retrieval nhận
  nhiều version cùng lúc.
- `graph_version_id` dùng chung cho review store và Neo4j (UUID). `build_gate` chạy trên
  **từng envelope gốc, không sửa**; chặn khi quan hệ APPROVED không có hoặc khác bản đã
  duyệt, gate thuộc version khác hoặc quá 60 giây.
- Thực thể cùng `entity_id`: tên, `identity_key`, trạng thái, thuộc tính phải trùng; `aliases`
  được hợp nhất (mỗi BCTN có cách viết tên riêng, ví dụ TCB 2024/2025).
- Review store có ID APPROVED mà envelope không có → không nạp (`missing_in_envelopes`).
- **Không sửa nội dung quan hệ đã duyệt** (WBS06 ràng buộc theo digest). Gộp trùng:
  cùng loại, chủ thể, đối tượng, thời gian, thuộc tính định danh (`position`,
  `cooperation_scope`, `participant_role`) và cùng thuộc tính → graph giữ một cạnh
  (`relation_id` nhỏ nhất); các ID còn lại kèm evidence riêng nằm trong `merged` của receipt.
- Chuyển WBS06 (`conflicts_for_wbs06`), không nạp:
  - `RELATION_ID_COLLISION`: một `relation_id` mang hai nội dung (ví dụ năm báo cáo khác).
  - `ATTRIBUTE_MISMATCH`: cùng sự kiện nhưng thuộc tính khác (ví dụ tỷ lệ sở hữu).
  - `ENTITY_CONFLICT`: cùng `entity_id` nhưng nội dung thực thể khác giữa extractor.
- Document/chunk cùng ID mà nội dung khác → dừng build.
- Retrieval chỉ đọc version `READY`; 1–2 hop; `limit` ≤ 200; timeout ≤ 30 giây
  (mặc định 5); lọc theo thực thể, loại quan hệ, khoảng ngày. Cạnh chỉ có `as_of`
  phải nằm trong khoảng; cạnh có `valid_from/valid_to` chỉ cần giao khoảng.

## Chạy

```powershell
# Không đụng DB/Neo4j: chỉ gộp và báo cáo
.venv/Scripts/python.exe -X utf8 -m backend.scripts.run_wbs09_graph build `
  --input company.json --input person.json --input event.json `
  --version <graph-uuid> --receipt receipt.json --dry-run
# Bỏ --dry-run: đọc review store/nguồn (chỉ đọc, DATABASE_URL), nạp + publish Neo4j
.venv/Scripts/python.exe -X utf8 -m backend.scripts.run_wbs09_graph --env-file backend/.env.neo4j-vps `
  build --input nhan-v4.json --version <graph-uuid> --receipt receipt.json
.venv/Scripts/python.exe -X utf8 -m backend.scripts.run_wbs09_graph --env-file backend/.env.neo4j-vps `
  query --version <graph-uuid> --entity CMP-00e0481af8b436b4645f --type HAS_SUBSIDIARY --hops 1
```

Bật cho hybrid router: `SPRINT4_GRAPH_VERSIONS=<graph-uuid>[,…]`; ticker → entity lấy từ
`SPRINT4_COMPANY_REGISTRY` (mặc định `backend/src/sprint4_runtime/company.registry.json`).

## Tái tạo envelope V4 của Nhân (chỉ đọc DB)

Chạy 3 lệnh mục 7 `docs/sprint4/wbs06/WBS06_HANDOFF_NHAN.md` với `DATABASE_URL` trỏ VPS
qua tunnel `127.0.0.1:15433`. Kết quả ở `backend/.tmp/nhan-reviewed/approved-review-*.json`.
Trường `review.reviewer` do script ghi là `WBS06-offline-proposal-for-user-acceptance`,
không phải tên người duyệt.

Sửa kèm trong WBS06: `graph_review.gate.core` coi thiếu `assertion_status` và `None` là
như nhau. Trước đó `from_envelope` luôn có khóa này còn bản duyệt từ `from_handoff` thì
không, nên gate từ chối mọi envelope của Nhân.

## Kiểm thử

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest backend.tests.test_wbs09_graph_pipeline
```

Đủ ba loại quan hệ, gộp trùng không sửa bản duyệt, va chạm ID, thuộc tính lệch, hai
chức vụ là hai cạnh, chặn trộn corpus, gate WBS06 (thiếu duyệt, sai version), review
store thừa ID, cạnh Neo4j lệch thì không publish, chạy lại cùng `batch_id`, giới hạn
hop/limit/timeout, chỉ đọc READY, adapter trả evidence.

## Còn chặn 09.5

| Loại | Trạng thái WBS06 (handoff 02/11) | Còn thiếu |
|---|---|---|
| Doanh nghiệp (Nhân) | 13 APPROVED (TCB, ELC), 10 REJECTED | Envelope V4 đã tái tạo; chưa ghi 13 quyết định vào review store |
| Chức vụ (Vũ) | 185 APPROVED nội dung, 2 REJECTED | 184 endpoint `source_scoped` (contract chặn), 87 thiếu thời gian; chưa ghi review store |
| Sự kiện (Quân) | 0/139 APPROVED | Extractor chưa xuất contract 2.1.0; lỗi Q01–Q12 |

Chung: `public.graph_review_results` / `graph_review_audit` chưa có trên VPS (WBS07).
