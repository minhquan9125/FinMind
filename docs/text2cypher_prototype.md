# Text2Cypher prototype

Prototype này dùng `Text2CypherRetriever` của package chính thức
`neo4j-graphrag` để kiểm tra luồng:

```text
Câu hỏi tiếng Việt
  -> LLM sinh Cypher
  -> kiểm tra read-only
  -> Text2CypherRetriever chạy EXPLAIN
  -> Neo4j thực thi truy vấn đọc
  -> API trả Generated Cypher và records thô
```

Prototype chưa dùng Vector RAG, Hybrid RAG hoặc LLM thứ hai để viết câu trả lời cuối.

## 1. Schema được cung cấp cho LLM

Service chỉ khai báo các thành phần đang tồn tại trong graph:

- Nodes: `Company`, `Dataset`, `ReportingPeriod`, `FinancialReport`, `Metric`,
  `Observation`, `PriceBar`.
- Relationships: `HAS_DATASET`, `HAS_REPORT`, `FOR_PERIOD`, `HAS_OBSERVATION`,
  `OF_METRIC`, `HAS_PRICE`.
- Giá trị tài chính nằm ở `Observation.value` và `Observation.value_json`.
- Ba mã balance sheet dùng cho bộ câu hỏi thử là `bsa53` (tổng tài sản),
  `bsa54` (nợ phải trả) và `bsa78` (vốn chủ sở hữu).

Graph hiện không có ngành của doanh nghiệp. Câu hỏi "FPT thuộc ngành nào?" được giữ
lại để kiểm tra fallback: truy vấn phải trả `industry = null` và ghi chú thiếu dữ liệu,
không được tự tạo thuộc tính `Company.industry`.

## 2. Cài dependency

Tại thư mục gốc repo, dùng shared virtual environment theo `AGENTS.md`:

```powershell
& "$HOME\.venv\Scripts\python.exe" -m pip install -r backend/requirements.txt
```

Package được tích hợp là `neo4j-graphrag[openai]`. `Text2CypherRetriever` không cần
embedding hoặc vector index.

## 3. Cấu hình `.env`

Thêm các biến sau vào file `.env` ở thư mục gốc. Không commit file này.

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD='YOUR_LOCAL_PASSWORD'
NEO4J_DATABASE=neo4j

OPENAI_API_KEY='YOUR_OPENAI_API_KEY'
GRAPH_LLM_MODEL=gpt-4o-mini
```

Có thể thay `GRAPH_LLM_MODEL` bằng model OpenAI mà tài khoản được phép sử dụng.

## 4. Khởi động Neo4j và nạp dữ liệu

Mở Docker Desktop, sau đó chạy:

```powershell
docker compose up -d
docker compose ps
```

Nếu graph local chưa có FPT:

```powershell
& "$HOME\.venv\Scripts\python.exe" -B -m backend.src.graph.ingest --input data/normalized/FPT.json
```

## 5. Chạy backend

Mở terminal tại thư mục gốc repo:

```powershell
& "$HOME\.venv\Scripts\python.exe" -m uvicorn backend.src.main:app --reload --host 127.0.0.1 --port 8000
```

Kiểm tra API trực tiếp:

```powershell
$body = @{ question = "Tổng tài sản FPT quý 2/2026 là bao nhiêu?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/graph/query `
  -ContentType "application/json" -Body $body
```

Response:

```json
{
  "question": "Tổng tài sản FPT quý 2/2026 là bao nhiêu?",
  "cypher": "MATCH ... RETURN ...",
  "records": [],
  "error": null
}
```

Nếu LLM sinh Cypher sai, cấu hình thiếu hoặc Neo4j không kết nối được, API giữ cùng
response envelope và điền thông báo vào `error`.

## 6. Chạy frontend

Mở terminal thứ hai:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Mở URL Vite hiển thị trong terminal, thường là `http://127.0.0.1:5173`.
Vite chuyển tiếp `/api` sang backend ở `http://127.0.0.1:8000`.

Giao diện có sáu câu hỏi mẫu, ô nhập câu hỏi, Generated Cypher, Query Result và Error.

## 7. Bảo vệ read-only

Cypher do LLM sinh được kiểm tra trước khi truyền cho retriever. Prototype chỉ nhận
`MATCH`, `OPTIONAL MATCH`, `WHERE`, `WITH` và `RETURN`. Nó chặn comment, nhiều statement,
`ORDER BY`, `SKIP`, `LIMIT`, procedure và các lệnh ghi, gồm:

```text
CREATE MERGE DELETE DETACH DELETE SET REMOVE DROP
```

Package `neo4j-graphrag` còn chạy `EXPLAIN` và kiểm tra query type là read-only trước
khi thực thi câu Cypher thật. Nên cấp cho ứng dụng một Neo4j user chỉ có quyền đọc khi
đưa prototype ra ngoài môi trường local.

## 8. Chạy test

```powershell
& "$HOME\.venv\Scripts\python.exe" -m unittest `
  backend.tests.test_text2cypher_service `
  backend.tests.test_graph_query_api -v
```

Test dùng LLM mock và Neo4j driver mock ở biên thực thi, nên không tiêu tốn API token
và không cần Neo4j server đang chạy.
