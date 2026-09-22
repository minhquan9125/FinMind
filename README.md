# FinMind — Vector RAG

Chunk + BAAI/bge-m3 embedding + PostgreSQL/pgvector similarity search — FastAPI backend, React (Vite) frontend. Đây là baseline Vector RAG (cấu hình B1) cho dữ liệu tài chính chứng khoán Việt Nam.

## Kiến trúc

```
FinMind/
├── backend/          FastAPI — upload/import tài liệu → chunk → embed → lưu Postgres, và API search
├── frontend/         React + Vite + Tailwind — giao diện upload/import/search
├── data_pipeline/     Script cào dữ liệu tài chính thô từ nguồn (không bắt buộc để chạy web)
├── data/
│   ├── raw/          Dữ liệu thô đã cào (8 mã: FPT, HPG, MWG, SSI, TCB, VCB, VIC, VNM)
│   └── normalized/   Dữ liệu đã chuẩn hoá — backend đọc trực tiếp qua nút "Import" trên frontend
└── docker-compose.yml
```

Dữ liệu chunk + vector embedding **không lưu ra file** — chúng được lưu trong PostgreSQL (bảng `document_chunks`, có cột `vector(1024)` nhờ extension `pgvector`), nằm trong Docker volume `postgres_data`.

## Yêu cầu cài đặt (prerequisites)

Cần cài trước khi chạy, chọn 1 trong 2 cách chạy bên dưới sẽ quyết định bạn cần cài gì:

| Công cụ | Bắt buộc cho | Ghi chú |
|---|---|---|
| **Docker Desktop** | Cách A (chạy toàn bộ bằng Docker) | Bật engine chạy được (`docker info` không lỗi) |
| **Python 3.11+** | Cách B (chạy backend local) | Dự án dùng 3.11 (Dockerfile) / đã test với 3.12 |
| **Node.js 18+** | Cách B (chạy frontend local) | Kèm `npm` |
| **Docker Desktop** (chỉ Postgres) | Cách B | Vẫn cần Postgres/pgvector — dùng Docker cho riêng service này là đơn giản nhất |

Không bắt buộc cài PostgreSQL/pgvector thủ công trên máy — cả 2 cách đều dùng image `pgvector/pgvector:pg16` qua Docker.

### Cài Docker Desktop (cần cho cả 2 cách)

**Trên Windows** — Docker Desktop chạy trên nền WSL2, cần bật WSL2 trước:

1. Bật tính năng WSL2 (mở PowerShell **với quyền Administrator**, chạy):
   ```powershell
   wsl --install
   ```
   Lệnh này tự bật các Windows Feature cần thiết (Virtual Machine Platform, WSL) + cài kernel WSL2 + bản Linux mặc định (Ubuntu). Nếu máy yêu cầu **khởi động lại (restart) Windows** thì restart rồi chạy tiếp bước dưới.
2. Kiểm tra WSL2 đã sẵn sàng:
   ```powershell
   wsl --status
   ```
   Phải thấy `Default Version: 2`. Nếu không, chạy `wsl --set-default-version 2`.
3. Vào BIOS/UEFI bật **Virtualization** (Intel VT-x / AMD-V) nếu máy chưa bật sẵn — đây là nguyên nhân phổ biến nhất khiến bước 1 hoặc Docker Desktop báo lỗi không khởi động được. Cách vào BIOS tùy hãng máy (thường nhấn F2/F10/Del lúc khởi động).
4. Tải và cài Docker Desktop tại https://www.docker.com/products/docker-desktop/ . Lúc cài, để mặc định tùy chọn **"Use WSL 2 instead of Hyper-V"** (đã tick sẵn ở bản mới).
5. Mở app Docker Desktop lên, đợi tới khi biểu tượng cá voi ở khay hệ thống hết chạy loading (engine khởi động xong).

**Trên macOS / Linux** — không cần WSL, chỉ cần tải và cài trực tiếp tại https://www.docker.com/products/docker-desktop/ (macOS) hoặc cài Docker Engine theo hướng dẫn distro tương ứng (Linux, ví dụ Ubuntu: https://docs.docker.com/engine/install/ubuntu/).

**Kiểm tra đã chạy được chưa (mọi hệ điều hành):**
```bash
docker --version
docker info
```
Nếu `docker info` báo lỗi kiểu "cannot connect to the Docker daemon" / "pipe not found" nghĩa là app Docker Desktop chưa mở hoặc chưa khởi động xong — mở app lên rồi thử lại.

### Cài Python (chỉ cần nếu chạy Cách B)

1. Tải bản 3.11 trở lên tại https://www.python.org/downloads/
2. Khi cài trên Windows, nhớ tick vào ô **"Add python.exe to PATH"** ở màn hình cài đặt đầu tiên
3. Kiểm tra:
   ```bash
   python --version
   pip --version
   ```
   (Trên một số máy dùng lệnh `python3`/`pip3` thay vì `python`/`pip`.)

### Cài Node.js (chỉ cần nếu chạy Cách B)

1. Tải bản LTS (18 trở lên) tại https://nodejs.org/
2. Kiểm tra:
   ```bash
   node --version
   npm --version
   ```

## Cách A — Chạy toàn bộ bằng Docker Compose (đơn giản nhất)

```bash
docker compose up -d --build
```

Lệnh này dựng và chạy cả 3 service: `postgres`, `backend`, `frontend`. Lần đầu build sẽ khá lâu vì:
- Backend cài `sentence-transformers`/`torch` (dùng để embed).
- Model `BAAI/bge-m3` (~2.2GB) sẽ tự tải từ Hugging Face **ở lần request đầu tiên gọi tới embedding**, không phải lúc build image — máy cần có mạng lúc đó.

Sau khi các container "healthy" (`docker compose ps`):
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000 (health check: `GET /api/health`)
- Postgres: `localhost:5432` (user/pass/db: `finmind` / `finmind` / `finmind`)

Dừng lại: `docker compose down` (thêm `-v` nếu muốn xoá luôn dữ liệu Postgres đã lưu).

## Cách B — Chạy local (dev, để sửa code + hot reload)

### 1. Chạy Postgres (dùng Docker, chỉ 1 service)

```bash
docker compose up -d postgres
```

Chờ đến khi healthy:
```bash
docker compose ps
```

### 2. Chạy backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

Backend đọc cấu hình mặc định trong [backend/src/config.py](backend/src/config.py) — đã trỏ sẵn `DATABASE_URL=postgresql://finmind:finmind@localhost:5432/finmind` phù hợp chạy local. Nếu muốn override, copy [backend/.env.example](backend/.env.example) thành `backend/.env` rồi sửa.

**Lưu ý quan trọng:** `backend/.env` hiện có trong repo đang set `DATABASE_URL` trỏ tới host `postgres` (dùng cho mạng nội bộ Docker Compose) — nếu chạy backend local (không qua Docker) mà vẫn giữ nguyên file `.env` này, backend sẽ **không kết nối được Postgres** (vì `postgres` không resolve được ngoài mạng Docker). Cách xử lý:
- Xoá/đổi tên tạm `backend/.env`, để backend dùng default trong `config.py` (đã đúng cho local), hoặc
- Set biến môi trường ghi đè trước khi chạy uvicorn:
  ```bash
  # Windows PowerShell
  $env:DATABASE_URL = "postgresql://finmind:finmind@localhost:5432/finmind"
  # macOS/Linux
  export DATABASE_URL=postgresql://finmind:finmind@localhost:5432/finmind
  ```

Kiểm tra backend sống: `curl http://localhost:8000/api/health` → `{"status":"ok"}`.

### 3. Chạy frontend

```bash
cd frontend
npm install
npm run dev
```

Mặc định Vite chạy ở http://localhost:5173, đã cấu hình gọi backend tại `http://localhost:8000` qua [frontend/.env.local](frontend/.env.local) (`VITE_API_BASE_URL`).

## Test thử sau khi chạy

1. Mở http://localhost:5173
2. Upload 1 file PDF/JSON, hoặc chọn mã cổ phiếu có sẵn (FPT, HPG, MWG, SSI, TCB, VCB, VIC, VNM) ở dropdown rồi bấm **Import** — dữ liệu lấy từ `data/normalized/{MÃ}.json`
3. Sau khi import xong, dùng ô search để test tìm kiếm ngữ nghĩa (Vector RAG) trên nội dung vừa nạp

## Kiểm tra dữ liệu đã lưu (debug)

```bash
docker exec -it finmind-postgres-1 psql -U finmind -d finmind

# trong psql:
SELECT filename, page_count, created_at FROM documents;
SELECT chunk_index, page, left(text, 80) FROM document_chunks ORDER BY chunk_index LIMIT 10;
```

## Chạy test

```bash
cd backend
pytest
```

## Biến môi trường chính (backend)

Xem đầy đủ + comment giải thích tại [backend/.env.example](backend/.env.example). Các giá trị quan trọng:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | `postgresql://finmind:finmind@localhost:5432/finmind` | Kết nối Postgres |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Model embedding đa ngôn ngữ (Việt + Anh), ~2.2GB, tải từ Hugging Face lần đầu |
| `EMBEDDING_DIM` | `1024` | Phải khớp cột `vector(1024)` trong schema — đổi model thì phải đổi cả schema + re-embed toàn bộ |
| `CHUNK_WORDS` / `CHUNK_STRIDE` | `130` / `100` | Kích thước / độ chồng lấn của mỗi chunk |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | CORS — origin được phép gọi API |
| `FINANCIAL_DATA_DIR` | `../data/normalized` (local) / `/app/data/normalized` (Docker) | Nơi backend đọc file JSON khi dùng nút Import theo mã |

## Phạm vi hiện tại (đã làm / chưa làm)

Module này **chỉ** implement Vector RAG baseline (B1): upload/import → chunk → embed → search bằng similarity vector. Các phần sau **chưa** có trong repo này: Structured Retrieval, nhánh Hybrid Graph-Vector (Neo4j), Evidence Gate, Answer Verification, và sinh câu trả lời bằng LLM (Gemini) — câu trả lời trả về hiện tại là trích xuất nguyên văn (extractive), không phải văn bản do LLM viết lại.
