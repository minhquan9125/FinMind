# readmerepair.md

Nhật ký các thay đổi/sửa lỗi trong repo FinMind. Mỗi mục ghi: sửa gì, sửa ở
đâu, vì sao sửa, và có ảnh hưởng tới code chỗ khác không.

---

## 2026-09-18 — Dựng module Vector RAG (backend + frontend) từ demo HTML

**Sửa gì:**
Chuyển `VectorRAG_Demo.html` (bạn gửi) — vốn chạy 100% trong trình duyệt,
không backend, dùng TF-IDF thuần JS để chấm điểm — thành một module đúng
kiến trúc trong `FinMind_Project_Proposal` (mục 9 - Technology Stack, ADR01,
ADR04): backend FastAPI + PostgreSQL/pgvector, frontend React/Tailwind, xếp
hạng kết quả tìm kiếm bằng embedding BAAI/bge-m3 thay vì TF-IDF.

**Vì sao:**
Bạn yêu cầu build lại đúng theo bộ công cụ trong tài liệu (backend + frontend
thật, có data lưu trữ) thay vì một file HTML demo chạy tạm trong trình duyệt.

**Sửa ở đâu (file mới, repo trước đó toàn bộ là file rỗng/scaffold):**

Backend (`backend/`):
- `requirements.txt` — fastapi, uvicorn, asyncpg, pgvector, sentence-transformers, pypdf, pytest...
- `src/config.py` — đọc cấu hình từ biến môi trường (DATABASE_URL, EMBEDDING_MODEL...)
- `src/db.py` — pool kết nối asyncpg + đăng ký codec pgvector
- `src/chunking.py` — trích PDF theo trang (pypdf) + chia chunk ~130 từ, overlap 100 từ — **port y hệt logic `extractPages`/`buildChunks` trong file JS gốc** để ranh giới chunk không đổi
- `src/text_analysis.py` — tokenize, loại stopword, tính TF/DF/IDF — giữ lại y hệt logic cũ, nhưng giờ **chỉ dùng để hiển thị** (bảng "chunk detail" và "vocabulary" trong UI), không còn dùng để chấm điểm tìm kiếm nữa
- `src/embeddings.py` — bọc `sentence-transformers`, load model BAAI/bge-m3 theo ADR04 (có thể đổi model qua biến môi trường cho việc test offline)
- `src/repository.py` — CRUD Postgres: tạo document, lưu chunk kèm vector, tìm kiếm bằng khoảng cách cosine của pgvector (`embedding <=> query`)
- `src/schemas.py` — Pydantic request/response
- `src/routers/documents.py` — `POST /api/documents` (upload+xử lý), `GET /api/documents/{id}/chunks`, `GET /api/documents/{id}/vocab`
- `src/routers/search.py` — `POST /api/search`
- `src/main.py` — khởi tạo FastAPI, CORS, lifecycle kết nối DB
- `scripts/init_postgres_schema.sql` — bảng `documents`, `document_chunks` (cột `embedding vector(1024)`)
- `scripts/init_pgvector.sql` — index HNSW cosine, tham số ghi rõ theo yêu cầu ADR01 (m=16, ef_construction=64)
- `Dockerfile`, `.env.example`, `.env` (giá trị mặc định, không có secret)
- `tests/test_chunking.py`, `tests/test_text_analysis.py`, `tests/test_api_search.py` — 11 test, **đã chạy `pytest`, cả 11 đều pass**

Frontend (`frontend/`):
- `package.json`, `vite.config.js`, `index.html`, `postcss.config.js`, `tailwind.config.js` — dựng project Vite + React + Tailwind (giữ đúng bảng màu của demo gốc)
- `src/main.jsx`, `src/App.jsx`, `src/index.css`, `src/api.js`
- `src/components/UploadPanel.jsx`, `PipelineStepper.jsx`, `SearchPanel.jsx`, `ChunkDetailPanel.jsx`, `VocabPanel.jsx` — dựng lại 4 khối UI của demo gốc (upload → search → chunk detail → vocabulary), nhưng giờ gọi API backend thay vì xử lý trong JS
- `.env.local` (`VITE_API_BASE_URL`), `Dockerfile`
- **Đã chạy `npm install` + `npm run build` thành công**, không lỗi

Gốc repo:
- `docker-compose.yml` — service `postgres` (image `pgvector/pgvector:pg16`), `backend`, `frontend`
- `.gitignore` — thêm rule cho `node_modules/`, `__pycache__/`, `dist/`...

**Có ảnh hưởng tới code chỗ khác không:**
Không — toàn bộ các file trên trước đó là file rỗng (scaffold), chưa có code
nào để ảnh hưởng. Các file/thư mục sau **chưa đụng tới**, vẫn để trống vì
nằm ngoài phạm vi module Vector RAG này:
- `data_pipeline/src/ingest.py`, `data_pipeline/requirements.txt`, `data_pipeline/.env` — pipeline ingest nguồn dữ liệu chính thức (Source Register, mục 7.1) là module khác
- `backend/scripts/init_neo4j_graph.cypher` — Neo4j/Hybrid Graph-Vector Retrieval (ADR02) chưa làm ở bước này; `docker-compose.yml` cũng chưa có service `neo4j`
- `backend/tests/test_citation_accuracy.py`, `test_data_quality.py`, `test_hallucination_rate.py`, `test_hybrid_benchmark.py` — test cho Citation Engine, Evidence Gate, Answer Verification, đánh giá B0-B3 (mục 6.5) — chưa có code tương ứng nên chưa viết test thật vào đây, để tránh đoán bừa
- `README.md`, root `.env` — không động vào

**Thay đổi thiết kế đáng chú ý (khác so với demo gốc):**
1. Chấm điểm tìm kiếm đổi từ TF-IDF cosine (JS, chạy trong trình duyệt) sang
   BAAI/bge-m3 dense embedding + pgvector cosine distance (chạy server) —
   đúng theo ADR04 trong tài liệu đề xuất. TF-IDF vẫn giữ lại nhưng chỉ để
   hiển thị từ khóa/bảng vocab, không dùng để xếp hạng nữa.
2. Dữ liệu giờ lưu bền trong PostgreSQL thay vì bộ nhớ trình duyệt (mất khi
   tắt tab) — đúng yêu cầu "có backend và frontend, có data" của bạn.
3. Pipeline 5 bước hiển thị trên UI được rút gọn còn 3 bước (Sending →
   Server processing → Ready) vì giờ chunk/token hóa/embedding chạy gộp
   trong 1 request backend, trình duyệt không còn thấy từng bước riêng lẻ
   như code JS cũ (không tự thêm API streaming/polling vì không nằm trong
   yêu cầu).

**Giới hạn đã biết / cần bạn tự chạy để xác nhận:**
- Model BAAI/bge-m3 (~2.2GB) tải từ Hugging Face lúc chạy lần đầu. Trong môi
  trường sandbox của mình, mạng ra `huggingface.co` bị chặn nên **chưa chạy
  được end-to-end thật với Postgres + model thật** ở đây — mình chỉ chạy được
  unit test (logic chunking/tokenize) và test API với embedding/DB giả lập
  (11/11 pass). Bạn cần chạy `docker compose up --build` trên máy/mạng có thể
  ra Hugging Face để xác nhận toàn luồng upload PDF → search hoạt động thật.
- Nếu máy bạn không tải được model `BAAI/bge-m3`, có thể tạm đổi
  `EMBEDDING_MODEL` trong `backend/.env` sang model nhỏ hơn (vd.
  `sentence-transformers/all-MiniLM-L6-v2`) để thử luồng chạy, nhưng lưu ý đó
  không phải model được chỉ định trong tài liệu (ADR04) nên chỉ nên dùng tạm
  để test, không dùng cho bản nộp.

---

## 2026-09-19 — Lấy riêng thư mục `data/` từ nhánh `quan` về nhánh `vu`

**Sửa gì:** Copy nguyên thư mục `data/` (16 file JSON, ~19MB: `data/raw/*_raw.json`
và `data/normalized/*.json` cho 8 mã CP: FPT, HPG, MWG, SSI, TCB, VCB, VIC, VNM)
từ nhánh `quan` sang nhánh `vu`, dùng `git checkout origin/quan -- data`.

**Vì sao:** Theo yêu cầu của thành viên trong nhóm — chỉ cần lấy phần data Quân
đã cào/chuẩn hóa để dùng, không lấy code `backend/`/`frontend`/`.agents` của
nhánh `quan` (2 thư mục đó đang trùng đường dẫn với module Vector RAG mới thêm
ở nhánh `vu`, merge nguyên nhánh sẽ dễ conflict).

**Ảnh hưởng tới code chỗ khác:** Không — chỉ thêm mới thư mục `data/` (trước đó
chưa tồn tại trên nhánh `vu`), không đụng tới `backend/`, `frontend/`,
`data_pipeline/` hay bất kỳ file nào khác.

---

## 2026-09-19 — Mang code scraper (crawler) từ nhánh `quan` về nhánh `vu`

**Sửa gì:**
Copy nguyên 3 file code cào/chuẩn hóa dữ liệu thật (không sửa nội dung) từ
nhánh `quan` sang nhánh `vu`, dùng `git checkout origin/quan -- data_pipeline`:
- `data_pipeline/src/pipeline_quality.py` — hàm chuẩn hóa/kiểm tra dữ liệu giá
  và báo cáo tài chính (`normalize_price_payload`, `normalize_financial_rows`,
  `validate_price_history`, ghi file JSON an toàn qua `atomic_write_json`).
- `data_pipeline/src/scrapers/direct_vn_collector.py` — script cào chính
  (`VietnamStockDataCollector`), gọi trực tiếp API Entrade (giá OHLCV) và
  VietCap/IQ (chỉ số tài chính, KQKD, CĐKT, lưu chuyển tiền tệ) cho 8 mã
  `TARGET_SYMBOLS = ["FPT","VNM","HPG","VCB","MWG","VIC","TCB","SSI"]` — đúng
  8 mã đã có sẵn trong `data/raw/` và `data/normalized/` (đã lấy về từ trước).
  Không đổi danh sách mã, theo đúng yêu cầu ("mã thì cứ như trên code đang
  demo, không cần nhiều mã").
- `data_pipeline/tests/audit_pipeline.py` — script tự kiểm toán, đối chiếu
  RAW vs NORMALIZED từng ô dữ liệu (không mất field, không tự chế field lạ)
  và kiểm tra logic nghiệp vụ (OHLCV hợp lệ, Tài sản = Nợ + Vốn CSH).
- Không copy `data_pipeline/.env`, `data_pipeline/requirements.txt`,
  `data_pipeline/src/ingest.py` — cả 3 file này rỗng (0 byte) ngay trên chính
  nhánh `quan`, không có nội dung để mang qua; `direct_vn_collector.py` không
  import gì từ `ingest.py` nên không bị thiếu chức năng.
- Không copy các file `__pycache__/*.pyc` đi kèm (bytecode biên dịch sẵn của máy
  Quân, không phải source code, `.gitignore` gốc của repo đã có sẵn rule
  `**/__pycache__/` để loại các file này) — đã `git rm --cached` sau khi
  `checkout` mang nhầm chúng theo.

**Vì sao:**
Bạn yêu cầu "chỉnh sửa code dựa vào dữ liệu data để cào" — để sửa được thì
trước tiên code cào phải có mặt ở nhánh `vu` (trước đó `vu` chỉ có *kết quả*
`data/` do Quân cào, chưa có code tạo ra nó). Đã kiểm tra: script tự chạy được
độc lập (không cần `ingest.py`), gói `requests` mà nó cần đã có sẵn trong
`requirements.txt` gốc ở thư mục gốc repo (không phải bản rỗng trong
`data_pipeline/`) nên không cần cài thêm gì.

**Đã kiểm tra:**
`python3 -m py_compile` cả 3 file — biên dịch sạch, không lỗi cú pháp.
Chưa chạy thật (`collector.run_all()`) vì cần gọi ra API bên ngoài
(Entrade, VietCap) — môi trường chạy lệnh này không có mạng ra ngoài để test
cào thật; bạn cần tự chạy trên máy có mạng bằng:
`cd data_pipeline/src/scrapers && python direct_vn_collector.py`

**Ảnh hưởng tới code chỗ khác:**
Không — chỉ thêm mới thư mục `data_pipeline/` (trước đó chưa tồn tại trên
nhánh `vu`), không đụng tới `backend/`, `frontend/`, `data/` hay bất kỳ file
nào khác. Chưa sửa nội dung logic bên trong các file này (đang giữ nguyên như
bản gốc của Quân) — sẽ chờ bạn nói rõ cụ thể cần sửa/thêm gì trước khi đổi.
