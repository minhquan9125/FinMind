# Bàn giao Sprint 4 của Nhân — WBS03, WBS08, WBS12

Ngày 04/11/2026. Nhánh làm việc: `nhan-sprint-411`. Tài liệu này mô tả phần đã
chạy và phần còn phụ thuộc nhóm; không thay quyết định kiểm duyệt WBS06.

## Phiên dữ liệu dùng để đối chiếu

| Thành phần | Giá trị |
| --- | --- |
| Corpus BCTN | `b2550a0b-c423-5c50-9b15-6fb6af12e2c6` |
| Index | `ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d` |
| Graph version | `s4-bctn-b2550a0b-v4-20261102` (`READY`) |
| Batch đã nạp | `approved-13-v4` |

## WBS03 — trích xuất quan hệ doanh nghiệp từ BCTN

Lệnh `backend/scripts/extract_bctn_from_db.py` đọc chunk thật của corpus trên
từ PostgreSQL trong transaction chỉ đọc, dùng `sprint4_runtime/bctn_source.py`
và `db_adapter.py` để dựng lại chữ/nguồn, rồi `relation_extractor.py` cùng
registry WBS02 để tạo JSON ứng viên. Lượt kiểm tra mới nhất: **20 BCTN,
17.664 chunk xác minh, 23 ứng viên `PENDING`**; không OCR hoặc tạo vector lại.
WBS06 của Huyền đã thẩm định 23 ứng viên: **13 APPROVED, 10 REJECTED**. WBS03
không tự đổi trạng thái này. Kết quả trích xuất local nằm trong
`backend/.tmp/wbs03-candidates-20261103-gapcheck/` (Git ignore); danh sách và
lý do duyệt có trong [bàn giao WBS06](wbs06/WBS06_HANDOFF_NHAN.md).

Chạy lại trích xuất **chỉ đọc PostgreSQL** từ thư mục gốc repo khi tunnel
PostgreSQL cổng `15433` đang mở (chọn thư mục output mới vì script không ghi đè):

```cmd
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\extract_bctn_from_db.py --corpus-version-id b2550a0b-c423-5c50-9b15-6fb6af12e2c6 --output-dir backend\.tmp\wbs03-handoff-rerun
```

Đã kiểm tra khoảng trống CMG/FPT/CTG trong
[ghi chú khoảng trống](WBS03-gapcheck-20261104.md) và lập
[gói đối chiếu 10 ca](WBS03-rejected-followup-20261104.md)
cho 10 ca bị từ chối. Mười ca đó **chưa được duyệt lại**; không tính là cạnh
graph. Chưa có nhãn gold toàn bộ corpus để đo precision/recall của extractor.

## WBS08 — lưu quan hệ đã duyệt vào Neo4j

`backend/scripts/prepare_sprint4_review_batch.py` chuẩn bị một batch từ 13
envelope V4 WBS06 mà không sửa gói gốc. `backend/scripts/ingest_sprint4_graph.py`
gọi `graph/sprint4_store.py` để ghi 12 entity, 13 cạnh đã duyệt; công bố phiên
`READY` sau khi đối chiếu. Chạy lại cùng batch không tạo cạnh trùng.

Đối chiếu trực tiếp Neo4j ngày 04/11: **13/13 ID APPROVED của WBS06 có trong
graph, 0 thiếu, 0 thừa, 0 trùng**; tất cả thuộc batch `approved-13-v4`.
`verify_sprint4_graph.py` kiểm ID, chiều, loại, thời gian, thuộc tính, evidence
và hash batch: `passed=true`, `errors=[]`. Không có 10 ứng viên REJECTED trong
phiên graph này. Chi tiết thao tác ở
[biên bản WBS03–WBS08](WBS03-WBS08-review-v4-status-20261103.md).

Có thể chạy lại **lệnh kiểm tra chỉ đọc** từ thư mục gốc repo, khi SSH tunnel
Neo4j cổng `17687` đang mở:

```cmd
backend\.venv\Scripts\python.exe -X utf8 -m backend.scripts.verify_sprint4_graph --input backend\.tmp\wbs08-v4-prepared\approved-batch.json --version s4-bctn-b2550a0b-v4-20261102 --batch-id approved-13-v4 --env-file backend\.env.neo4j-vps
```

`approved-batch.json` và `.env.neo4j-vps` là file local không đưa lên Git;
người nhận cần dựng lại batch từ gói WBS06 và cấu hình kết nối riêng nếu chạy
trên máy khác. Review store WBS07 chưa được xác nhận đã ghi quyết định vào DB;
không coi batch Neo4j hiện tại là kết quả full-load WBS09 qua review store.

## WBS12 — nối nhánh GRAPH vào Hybrid Router

API `POST /api/hybrid-router/run` nhận câu hỏi, dùng intent/slots của router,
ánh xạ ticker vào canonical ID, gọi `RelationRetrieval` trên graph `READY`,
rồi `PostgresSourceReader` đọc lại nguồn đã ghim theo ID. Chỉ khi corpus/index,
document/chunk, locator, hash và quote đều khớp mới trả
`source_verified=true`. API trả `data` là đường quan hệ và `evidence` là
citation; đây là **đầu ra kiểm thử retrieval**, chưa phải câu trả lời văn xuôi.
Code nằm chủ yếu trong `src/api/routers/hybrid_router.py`,
`src/retrieval_orchestration/hybrid_router/adapters.py`, `graph_source.py`,
`src/graph/relation_retrieval.py` và `src/graph_review/sources.py`.

Kiểm tra tự động: **179 test qua** cho graph/source/router, gồm nguồn lệch,
hash/locator sai, thiếu reader, timeout, graph chưa READY, kỳ sai và phạm vi
nhiều công ty. Kiểm tra HTTP thật của nhóm phát triển: TCB 2025 `GRAPH/OK`
với **2 quan hệ/4 citation**, ELC 2024 `GRAPH/OK` với **7 quan hệ/43 lượt
evidence**, FPT 2025 và TCB 2001 `GRAPH/NO_DATA`. Người dùng đã chạy lại API
qua Swagger và xác nhận kết quả TCB/ELC hiển thị ổn ngày 04/11. Bảy quan hệ
ELC gồm **5 công ty con, 2 công ty liên kết**; 43 lượt evidence dùng **10
chunk nguồn khác nhau**, do nhiều cạnh dùng chung đoạn chứng minh.

`source_verified=true` xác nhận chữ đọc lại khớp snapshot đã ghim, không tự
chứng minh mọi diễn giải nghiệp vụ ngoài quyết định WBS06. Cách chạy backend,
request mẫu và giới hạn lỗi ghi trong
[hướng dẫn WBS12](WBS12-graph-router-live.md). Có thể chạy lại bộ test trọng tâm
từ thư mục gốc repo; test dùng mock, **không ghi database**:

```cmd
backend\.venv\Scripts\python.exe -X utf8 -m pytest backend\tests\test_graph_source_replay.py backend\tests\test_wbs09_graph_pipeline.py backend\tests\test_sprint4_graph_adapter.py backend\tests\test_hybrid_router.py backend\tests\test_live_adapters.py -q -p no:cacheprovider
```

Để kiểm tra bằng Swagger, giữ cả hai tunnel mở, chạy backend theo hướng dẫn
WBS12 rồi gửi ví dụ sau tới `POST /api/hybrid-router/run`:

```json
{
  "question": "TCB có những công ty con nào?",
  "context": {"companies": ["TCB"], "periods": ["2025"]}
}
```

Kỳ vọng `route=GRAPH`, `status=OK`, `data_count=2`, `evidence_count=4`.
Đổi câu hỏi sang “ELC có những công ty con và công ty liên kết nào?” và scope
`ELC`/`2024` để xem 7 quan hệ; API không tạo câu trả lời văn xuôi.

## Phần chưa nằm trong bàn giao này

- WBS17/B1–B2: chưa có benchmark chung và kết quả đầy đủ VECTOR/GRAPH/BOTH.
- Chức vụ và sự kiện chưa được chứng minh trên graph thật ở phiên BCTN này.
- Mười ứng viên WBS06 REJECTED cần Huyền thẩm định lại khi có nguồn bổ sung;
  chỉ quan hệ APPROVED mới có thể nạp vào một graph version mới.
- Các thay đổi WBS12 và tài liệu ngày 04/11 hiện ở working tree của nhánh
  `nhan-sprint-411`; cần commit/push khi bàn giao qua Git.
