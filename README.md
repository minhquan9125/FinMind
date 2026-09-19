# FinMind

Nền tảng dữ liệu & tra cứu tài chính chứng khoán Việt Nam. Repo gồm 3 phần:

- **`backend/`** — FastAPI + PostgreSQL/pgvector: module Vector RAG (upload PDF/JSON → chia chunk → embed bằng BAAI/bge-m3 → tìm kiếm ngữ nghĩa).
- **`frontend/`** — React + Vite + Tailwind: giao diện upload tài liệu và tìm kiếm.
- **`data_pipeline/`** — Script cào dữ liệu giá + báo cáo tài chính 8 mã CP (FPT, VNM, HPG, VCB, MWG, VIC, TCB, SSI) từ Entrade/VietCap, chuẩn hóa và kiểm toán chất lượng.

Kết quả cào sẵn nằm ở `data/raw/` (dữ liệu thô) và `data/normalized/` (đã chuẩn hóa).

---

## Cách 1 — Chạy bằng Docker Compose (khuyến nghị)

**Yêu cầu:** Docker Desktop.

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000 (health check: `GET /api/health`)
- Postgres/pgvector: cổng 5432 (user/pass/db đều là `finmind`, xem `docker-compose.yml`)

Compose tự tạo schema (`backend/scripts/init_postgres_schema.sql`, `init_pgvector.sql`) và mount sẵn thư mục `data/` vào container backend (dùng cho tính năng "Import ticker" ở bước dưới).

**Lưu ý lần chạy đầu:** container backend sẽ tải model `BAAI/bge-m3` (~2.2GB) từ Hugging Face — cần mạng ra `huggingface.co` và có thể mất vài phút.

---

## Cách 2 — Chạy thủ công (không có Docker)

Dùng khi máy không có Docker. Cần tự cài PostgreSQL 16 + extension [pgvector](https://github.com/pgvector/pgvector) (trên Windows không có Docker, cách dễ nhất là cài qua [Postgres.app](https://www.postgresql.org/download/) rồi build/cài pgvector theo hướng dẫn của repo đó).

### 1. Database

```bash
psql -U postgres -c "CREATE USER finmind WITH PASSWORD 'finmind';"
psql -U postgres -c "CREATE DATABASE finmind OWNER finmind;"
psql -U finmind -d finmind -f backend/scripts/init_postgres_schema.sql
psql -U finmind -d finmind -f backend/scripts/init_pgvector.sql
```

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # sửa DATABASE_URL nếu Postgres không chạy trên localhost:5432
uvicorn src.main:app --reload --port 8000
```

Kiểm tra: `curl http://localhost:8000/api/health` → `{"status": "ok"}`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Mở http://localhost:5173. `.env.local` đã có sẵn `VITE_API_BASE_URL=http://localhost:8000`.

### 4. Chạy test backend

```bash
cd backend
pip install pytest fastapi asyncpg pgvector numpy pypdf httpx pydantic-settings python-multipart
pytest -q
```

Bộ test dùng embedder giả + mock DB nên không cần Postgres thật để pass (xem `backend/tests/test_api_search.py`).

---

## Nạp dữ liệu vào Vector RAG

Ngoài upload PDF thủ công trên UI, backend còn nhận **JSON**:

- **Import 1 trong 8 mã có sẵn** — nút "Import {SYMBOL}" trên UI, hoặc gọi thẳng:
  ```bash
  curl -X POST http://localhost:8000/api/documents/import-symbol/SSI
  ```
  Đọc trực tiếp `data/normalized/SSI.json`, không cần upload file.
- **Upload JSON bất kỳ** — chọn file `.json` ở ô upload trên UI, hoặc:
  ```bash
  curl -X POST http://localhost:8000/api/documents/json -F "file=@duong/dan/file.json"
  ```

Cả hai đều chunk hóa + embed + lưu vào Postgres giống hệt luồng PDF (không dùng LLM sinh câu trả lời — kết quả tìm kiếm là trích xuất nguyên văn, xếp hạng bằng embedding BAAI/bge-m3 + pgvector).

**Xuất chunk + embedding ra file (không cần Postgres chạy)** — hữu ích để chia sẻ dữ liệu đã embed cho người khác dùng mà không cần dựng DB:

```bash
cd backend
python scripts/export_chunks.py SSI FPT   # hoặc không truyền gì để xuất cả 8 mã
```

Kết quả lưu ở `data/chunks/{SYMBOL}.chunks.json`. Cảnh báo: bước embed chạy trên CPU khá chậm (~15-20 phút/mã tùy máy) vì cần chạy model BAAI/bge-m3 thật.

---

## Cào dữ liệu mới (data_pipeline)

```bash
cd data_pipeline
pip install -r requirements.txt
python src/scrapers/direct_vn_collector.py     # cào + chuẩn hóa, ghi vào data/raw/ và data/normalized/
python tests/audit_pipeline.py                  # đối chiếu RAW vs NORMALIZED, kiểm tra nghiệp vụ (OHLCV, cân đối kế toán)
```

---

## Ghi chú / giới hạn đã biết

- Các module Structured Retrieval, Neo4j/Hybrid Graph-Vector, Evidence Gate, Answer Verification trong đề xuất dự án **chưa được xây dựng** — xem `readmerepair.md`.
- Lịch sử các lần sửa/thêm code, kèm lý do và phạm vi ảnh hưởng: xem `history.md`.
- Income statement/Balance sheet/Cash flow trong dữ liệu JSON dùng mã field nội bộ của nhà cung cấp (`isaNN`, `bsaNN`, `cfaNN`...) chưa có bảng chú giải — tìm kiếm ngữ nghĩa trên 3 phần này kém chính xác hơn Prices/Ratios.
