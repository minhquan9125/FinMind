# WBS12 – kiểm tra nhánh GRAPH trên dữ liệu thật

**Trạng thái bàn giao ngày 04/11/2026:** Người dùng đã kiểm tra qua Swagger
hai câu TCB 2025 và ELC 2024, xác nhận kết quả hiển thị ổn. TCB trả 2 quan hệ
với 4 citation; ELC trả 7 quan hệ một hop (5 công ty con, 2 công ty liên kết)
với 43 lượt evidence, nhưng chỉ 10 chunk nguồn khác nhau vì nhiều cạnh dùng
chung bằng chứng. JSON dài vì API trả cả quan hệ và citation để kiểm thử,
chưa sinh câu trả lời ngắn. Xem [biên bản bàn giao ba task](Nhan-WBS03-WBS08-WBS12-handoff-20261104.md).

Ngày 03/11/2026. Nhánh `nhan-sprint-411` đã nối truy vấn quan hệ WBS09 với bước
đọc lại nguồn PostgreSQL trước khi trả citation trong Hybrid Router. Đây là bước
kiểm tra GRAPH trên 13 quan hệ BCTN đã có trong Neo4j; chưa phải benchmark B1/B2
hoặc nghiệm thu các nhóm chức vụ, sự kiện chưa nạp graph.

## Luồng chạy

`intent/slots` → ticker được đối chiếu với WBS02 registry và tên công ty chính thức
trong `companies` → `RelationRetrieval` chỉ đọc graph version `READY` →
`PostgresSourceReader` dựng lại từng chunk từ corpus đã ghim trong một transaction
chỉ đọc → so document/chunk/corpus/index version, locator, hash và quote → trả
quan hệ, đường đi và citation. Chỉ khi **mọi** bằng chứng đều khớp mới có
`source_verified=true`. Thiếu nguồn hoặc lệch bất kỳ bằng chứng nào thì trả lỗi,
không trả một phần kết quả. `PENDING` không được nạp vào graph READY.

`/api/hybrid-router/run` hiện trả thêm `data` và `evidence` cho mỗi adapter result
để kiểm tra trực tiếp; các trường `data_count`/`evidence_count` vẫn giữ nguyên.
Không có thao tác ghi PostgreSQL hoặc Neo4j trong luồng truy vấn.

## Chạy từ CMD

Giữ hai SSH tunnel PostgreSQL (`15433`) và Neo4j (`17687`) đang mở. File
`backend/.env.neo4j-vps` chứa thông tin Neo4j và phải nằm ngoài Git. File
`backend/.env` chứa `DATABASE_URL` tới PostgreSQL qua cổng `15433`.

Từ thư mục gốc repo, đối chiếu batch graph với envelope duyệt (chỉ đọc):

```cmd
backend\.venv\Scripts\python.exe -X utf8 -m backend.scripts.verify_sprint4_graph --input backend\.tmp\wbs08-v4-prepared\approved-batch.json --version s4-bctn-b2550a0b-v4-20261102 --batch-id approved-13-v4 --env-file backend\.env.neo4j-vps
```

File `approved-batch.json` là dữ liệu bàn giao đã dựng tại máy này trong
`backend/.tmp/` và không nằm trên Git; cần tái tạo từ WBS06 nếu thử trên máy khác.

```cmd
cd backend
.venv\Scripts\python.exe -X utf8 -c "import os,uvicorn; from dotenv import load_dotenv; load_dotenv('.env.neo4j-vps',override=True); os.environ['SPRINT4_GRAPH_VERSIONS']='s4-bctn-b2550a0b-v4-20261102'; os.environ['HYBRID_ROUTER_MODE']='live'; os.environ['FINMIND_LIVE_ENABLED']='0'; os.environ['RESEARCH_WARMUP_ENABLED']='false'; uvicorn.run('src.main:app',host='127.0.0.1',port=8000)"
```

Mở `http://127.0.0.1:8000/docs`, chọn `POST /api/hybrid-router/run`. Ví dụ:

```json
{
  "question": "TCB có những công ty con nào?",
  "context": {"companies": ["TCB"], "periods": ["2025"]}
}
```

Thử thêm `ELC`/`2024` để xem quan hệ ELC, `FPT`/`2025` để xem `NO_DATA`,
hoặc `TCB`/`2001` để kiểm tra lọc sai thời gian. Kỳ không hợp lệ trả
`GRAPH_UNSUPPORTED_PERIOD`; phiên graph thiếu/chưa `READY` trả `GRAPH_NOT_READY`
thay vì ngụy trang thành kết quả rỗng. Router vẫn quyết định GRAPH,
VECTOR hay BOTH từ câu hỏi thực tế; kiểm tra trường `route` trước khi đánh giá
kết quả GRAPH. Nếu route khác GRAPH, có thể dùng `/test` để xem quyết định và
đối chiếu bộ câu hỏi WBS10; không nên đổi nhãn kết quả bằng tay.

## Kết quả đã kiểm chứng

- Test offline graph/source/router: 179 pass; có ca nguồn sai, hash/locator sai,
  thiếu reader, timeout, kỳ sai, graph chưa sẵn sàng, phạm vi nhiều công ty và
  API serialization.
- Neo4j VPS: graph version trên `READY`, 13 quan hệ đã duyệt. Truy vấn WBS09 thật
  cho TCB 5 đường một hop, ELC 7 đường một hop (không lọc kỳ). Kiểm tra phiên
  không tồn tại trả `all_versions_ready=False`.
- Đối chiếu trực tiếp ngày 04/11: toàn phiên graph có đúng 13 `relation_id`
  `review:` của bảng APPROVED WBS06, 0 thiếu, 0 thừa, 0 ID trùng; tất cả nằm
  trong batch `approved-13-v4`. `verify_sprint4_graph.py` kiểm thêm chiều cạnh,
  thuộc tính, evidence và hash batch: `passed=true`, 0 lỗi. Không có cạnh từ
  10 ứng viên REJECTED. Phiên READY trả `all_versions_ready=True`, phiên giả
  không tồn tại trả `False` trên Neo4j thật.
- PostgreSQL VPS: đọc lại thật thành công 20 citation của TCB và 43 citation của
  ELC trong các đường trên. HTTP thật `POST /api/hybrid-router/run` với classifier
  production trả: TCB 2025 `GRAPH/OK` 2 đường/4 citation; ELC 2024 `GRAPH/OK`
  7 đường/43 citation; FPT 2025 và TCB 2001 `GRAPH/NO_DATA`. Lần kiểm tra HTTP
  dùng cổng thử 8012, tắt collector thị trường và research warmup để cô lập nhánh
  GRAPH; đã dừng server sau khi kiểm tra.

Các ca HTTP trên chứng minh đường GRAPH, chưa đo chất lượng định tuyến toàn bộ
bộ câu hỏi hoặc route BOTH. WBS17 cần bộ câu hỏi/gold do Huyền duyệt và kết quả
VECTOR/GRAPH/BOTH trên cùng cấu hình. WBS09 full-load qua review
store WBS07 cũng còn phụ thuộc bảng review và quyết định được lưu trong DB.
Khi câu hỏi chứa nhiều công ty, adapter hiện trả
`GRAPH_MULTI_COMPANY_SCOPE_UNSUPPORTED` để tránh trả nhầm hợp các quan hệ riêng
của từng công ty thành quan hệ giữa họ; cần WBS10/WBS09 chốt kiểu truy vấn đa
thực thể trước khi hỗ trợ ca này.
