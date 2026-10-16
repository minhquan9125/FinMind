# FinMind

## Hướng dẫn chạy sau khi clone — Windows / PowerShell

Ứng dụng dùng **hai terminal**: backend chung ở **8000**, frontend ở **5173**. Backend đã ghép đăng ký/đăng nhập, tài liệu/tìm kiếm và API giá/tin; **không cần chạy server 8001**. Các lệnh bên dưới dùng đường dẫn tương đối, không phụ thuộc tên người dùng hoặc ổ đĩa của người viết.

### 1. Chuẩn bị máy

- Cài Python **3.12**, bật **Add python.exe to PATH** khi cài.
- Cài Node.js LTS có npm và Git. Mở lại terminal sau khi cài.
- Nhận cấu hình Supabase và Google OAuth của nhóm qua kênh riêng.

Kiểm tra:

```powershell
python --version
node --version
npm.cmd --version
```

Nếu `python` không nhận, thử `py -3.12 --version`. Có thể thay `python` ở bước tạo môi trường bằng `py -3.12`, hoặc dùng `& "đường-dẫn-tới-python.exe"`. Không tiếp tục cài dependency khi bước tạo `.venv` chưa thành công.

### 2. Clone và cài lần đầu

```powershell
git clone https://github.com/minhquan9125/FinMind.git
cd FinMind
```

Nếu nhóm làm trên nhánh khác mặc định, chuyển sang đúng nhánh leader yêu cầu trước khi cài. Nhánh cần có `backend/package.json`, `backend/scripts/run-backend.mjs` và bản `main.py` đã ghép market API.

Các lệnh sau chạy tại **gốc FinMind**, nơi có `backend`, `frontend`, `README.md`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
npm.cmd --prefix frontend ci
```

Dependency embedding có Torch nên lần cài đầu có thể tải nhiều GB. Chờ lệnh kết thúc thành công. Không cần `npm install` trong backend: package đó chỉ là lệnh gọi Python. `.venv` phải nằm tại **FinMind/.venv**, không phải `backend/.venv`; không cần activate.

Để tải giá mới từ vnstock/KBS trên máy mới, cài thêm SDK vào chính môi trường này:

```powershell
.\.venv\Scripts\python.exe -m pip install -r data_pipeline/ScrapersOHLCV/requirements/vnstock.txt
```

Nếu SDK yêu cầu xác thực hoặc hạn mức, thực hiện theo hướng dẫn của SDK/nhóm. Không có SDK thì dữ liệu đã lưu vẫn đọc được, nhưng chức năng tải lịch sử/cập nhật giá mới có thể thất bại. Xem thêm [hướng dẫn giá/tin](backend/src/market_data/README.md).

### 3. Cấu hình kết nối

Tạo **`.env` tại gốc FinMind**, cùng cấp `backend` và `frontend`:

```dotenv
DATABASE_URL=chuoi_ket_noi_Supabase_do_nhom_cung_cap
JWT_SECRET_KEY=khoa_JWT_do_nhom_cung_cap
```

Thay các giá trị mẫu bằng cấu hình thật, không để nguyên placeholder. Backend đọc `.env` gốc rồi `backend/.env` (nếu có); giá trị trong `backend/.env` được ưu tiên. Biến môi trường terminal ưu tiên cao hơn cả hai file. Nếu vô tình giữ `backend/.env` cũ trỏ localhost, sửa/xóa cấu hình cũ đó. Database dùng chung đã có schema: **không chạy reset database** để khởi động ứng dụng.

Không commit `.env`, mật khẩu hoặc khóa JWT. Không cần cài PostgreSQL/Neo4j local để chạy luồng đăng nhập và giá/tin này khi dùng Supabase của nhóm.

**Nếu dùng đăng nhập Google:**

Tạo `frontend/.env.local` với client ID do nhóm cung cấp:

```dotenv
VITE_GOOGLE_CLIENT_ID=client_id_cua_nhom.apps.googleusercontent.com
```

Router Google hiện đọc `GOOGLE_CLIENT_ID` từ môi trường tiến trình. Trong terminal backend, đặt cùng client ID trước khi chạy npm:

```powershell
$env:GOOGLE_CLIENT_ID='client_id_cua_nhom.apps.googleusercontent.com'
```

Không điền Google client secret vào frontend. Người quản lý OAuth phải cho phép **http://localhost:5173** trong **Authorized JavaScript origins** của đúng client ID. Luôn mở địa chỉ này để tránh `origin_mismatch`; `127.0.0.1` và cổng 5174 là origin khác. Đăng nhập email/mật khẩu không cần cấu hình Google.

Bỏ cấu hình `VITE_MARKET_DATA_API_URL` cũ trỏ cổng 8001 nếu có trong các file môi trường frontend. Mặc định frontend gọi `/api` qua proxy Vite sang 8000. Sau khi sửa môi trường, dừng và chạy lại server.

### 4. Chạy hằng ngày

**Terminal 1 — backend:** mở terminal tại gốc FinMind rồi chạy:

```powershell
cd backend
npm run dev
```

Đợi thấy `Application startup complete` và địa chỉ **http://127.0.0.1:8000**. Lệnh tự dùng Python trong `.venv` gốc; có thể dùng `npm start` thay thế. Backend chỉ chạy một worker vì collector giá dùng khóa độc quyền.

**Terminal 2 — frontend:** mở terminal mới tại gốc FinMind rồi chạy:

```powershell
cd frontend
npm run dev -- --host localhost --port 5173 --strictPort
```

Mở **http://localhost:5173/**. Giữ cả hai terminal chạy. `--strictPort` giúp báo lỗi cổng bận thay vì tự chuyển 5174. Nếu PowerShell chặn `npm.ps1`, dùng `npm.cmd run dev` với các tham số tương ứng, không cần đổi execution policy.

Dùng tài khoản thật: đăng ký trước hoặc đăng nhập tài khoản nhóm đã cấp; không dùng thông tin mock trong giao diện để coi là tài khoản DB thật. Nhấn **Ctrl+C** ở mỗi terminal để dừng. Khi sửa code backend, dừng và chạy lại `npm run dev`; lệnh này hiện không tự reload.

### 5. Kiểm tra sau khi chạy

| Địa chỉ | Kết quả mong đợi |
|---|---|
| http://localhost:5173/ | Giao diện FinMind |
| http://127.0.0.1:8000/api/health | `{"status":"ok"}` |
| http://127.0.0.1:8000/docs | Swagger có cả auth và market-data |
| http://localhost:5173/api/market-data/news?limit=2 | JSON tin tức qua proxy frontend |
| http://localhost:5173/api/market-data/stocks/FPT/ohlcv?limit=5 | JSON giá FPT đã lưu |

Trên Tổng quan, bấm chỉ số để tải biểu đồ. Trang doanh nghiệp lấy lịch sử giá và tin theo mã; nguồn không có dữ liệu sẽ hiện trạng thái trống. Cập nhật mới phụ thuộc mạng, SDK và hạn mức nguồn. Cache mới nằm ở `.agent-state/market-data/`; không cần chạy crawler riêng để mở giao diện.

### 6. Khi pull code mới

Dừng server bằng Ctrl+C, pull đúng nhánh của nhóm, rồi cập nhật dependency tại gốc FinMind:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
npm.cmd --prefix frontend ci
```

Sau đó chạy lại hai terminal ở bước 4. Giữ `.env` và `.venv` của từng máy, không sao chép môi trường Python từ máy khác. Nếu `npm ci` báo `EPERM` ở `esbuild.exe`, dừng Vite trước rồi chạy lại.

### 7. Lỗi thường gặp khi khởi động

| Lỗi | Kiểm tra / xử lý |
|---|---|
| `Python was not found` | Python chưa có trên PATH; dùng `py -3.12` hoặc đường dẫn Python của máy để tạo `.venv`. |
| Không tìm thấy `.venv/Scripts/python.exe` | Tạo `.venv` ở gốc FinMind; không tạo trong backend. |
| `Missing script: dev` / không tìm thấy package.json | Backend: đứng trong `FinMind/backend`; frontend: trong `FinMind/frontend`. Kiểm tra đã pull file chạy npm mới. |
| `npm.ps1 ... running scripts is disabled` | Dùng `npm.cmd` thay `npm`. |
| `ModuleNotFoundError: jwt`, `pwdlib`, `google`... | Cài lại `backend/requirements.txt` bằng Python trong `.venv` gốc. |
| `Failed to resolve import @react-oauth/google` | Dừng Vite, chạy `npm.cmd ci` trong frontend, bật lại. |
| Backend lỗi kết nối localhost / connection refused | Kiểm tra DATABASE_URL và thứ tự ưu tiên `.env`; chờ backend startup thành công trước khi đăng nhập. |
| Backend lỗi kết nối Supabase | Kiểm tra mạng, chuỗi kết nối, mật khẩu và cấu hình do leader cấp. Không in chuỗi có mật khẩu vào log công khai. |
| Cổng 5173 hoặc 8000 đang dùng | Dừng server cũ bằng Ctrl+C trong terminal đã mở nó; chỉ giữ một frontend và một backend. |
| `400: origin_mismatch` khi đăng nhập Google | Mở đúng `http://localhost:5173`; nhờ người quản lý OAuth thêm origin này cho client ID đang dùng. |
| Collector lock đang được giữ | Dừng backend 8001/bản backend khác; chỉ chạy main 8000, một worker. Không xóa lock khi server khác còn chạy. |
| Giao diện báo không kết nối API | Kiểm tra backend 8000 và health; xóa URL frontend cũ trỏ 8001, khởi động lại Vite. |

Các phần dưới là thao tác ingest dữ liệu riêng, **không phải bước bắt buộc để mở ứng dụng**.

## Đưa dữ liệu giá/tin lên Supabase

> **Người đăng:** dinhhuynhvu12 · **Ngày đăng:** 08/10/2026 20:41 (giờ Việt Nam, UTC+7) · Nhánh: `feature/supabase-market-news-ingest`

Dữ liệu của `data_pipeline/ScrapersOHLCV` (giá) và `data_pipeline/scrapers` (tin) có thể lưu lên Supabase. Database này là **PRODUCTION dùng chung**, vì vậy hỏi leader trước khi chạy `--apply`.

### Cấu hình kết nối (mỗi máy làm một lần)

Tạo file `.env` ở thư mục gốc `FinMind` (cùng cấp `backend`) với một dòng. Lấy chuỗi từ leader hoặc nút **Connect** của Supabase:

```text
DATABASE_URL=postgresql://postgres.<mã-dự-án>:<MẬT_KHẨU>@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres
```

- Mật khẩu có ký tự đặc biệt hoặc dấu cách phải mã hóa URL (dấu cách là `%20`, `@` là `%40`).
- `.env` đã được Git bỏ qua. **Không commit, không gửi mật khẩu lên nhóm công khai.**
- Thư viện cần có: `py -m pip install asyncpg python-dotenv`. Môi trường biểu đồ (`.agent-state/vnstock-venv`) cài bằng `pip install -r data_pipeline/ScrapersOHLCV/requirements/db.txt`.

### Bước 1 — Tạo bảng (một lần cho mỗi database)

Mở Supabase → **SQL Editor** → **New query**, dán nội dung rồi **Run**, theo thứ tự:

1. `supabase/migrations/20261008000000_add_news_articles.sql` (bảng `news_articles`)
2. `supabase/migrations/20261008000100_add_market_extras.sql` (bảng `price_indicators`, `market_index_bars`, `market_live_snapshots`)

Hai file chỉ dùng `CREATE ... IF NOT EXISTS`, chạy lại không sao. Bảng gốc (`price_bars`, `companies`, `raw_payloads`, `ingestion_jobs`) đã có từ `20260929000000_schema_from_supplied_erd.sql`. **Không** chạy `supabase/reset_and_rebuild.sql` trên database dùng chung vì file này xóa toàn bộ schema.

### Bước 2 — Nạp dữ liệu đã có trong file JSON

Chạy tại thư mục gốc `FinMind`. Lệnh không có `--apply` chỉ chạy thử, không kết nối database:

```powershell
py -X utf8 backend/scripts/ingest_market_news_to_supabase.py                      # chạy thử
py -X utf8 backend/scripts/ingest_market_news_to_supabase.py --only prices --apply
py -X utf8 backend/scripts/ingest_market_news_to_supabase.py --only news --apply
```

- Tùy chọn: `--symbol VCB FPT` (chỉ vài mã), `--no-overwrite` (giữ giá đã có trong `price_bars`, không ghi đè).
- Giá được lưu nguyên giá trị gốc của vnstock/KBS (nghìn đồng, `price_scale = 1000`). Nguồn chưa xác nhận giá điều chỉnh hay chưa nên `is_adjusted = false`.
- Chỉ số (VNINDEX, VN30, HNXINDEX...) vào `market_index_bars`, không vào `price_bars`.
- Nếu thiếu bảng, script dừng và báo tên bảng, chưa ghi gì.

### Bước 3 — Crawler tự đẩy lên Supabase khi chạy

Khi `DATABASE_URL` có trong `.env`, mỗi lần crawler lưu file JSON thì module [data_pipeline/supabase_sink.py](data_pipeline/supabase_sink.py) đẩy thêm dữ liệu đó lên Supabase:

- Giá và chỉ báo (`data.json`), bảng điện (`live.json`) từ `ScrapersOHLCV`; tin từ `scrapers`.
- JSON **vẫn được giữ** làm bộ nhớ đệm, vì crawler đọc lại file để gộp dữ liệu.
- Lỗi database (thiếu bảng, mất mạng, sai mật khẩu) chỉ in cảnh báo `[supabase_sink]`, crawler vẫn chạy bình thường.
- Mỗi file giá chỉ đẩy tối đa **một lần mỗi 60 giây**, nên lần cập nhật cuối của phiên có thể lên web chậm khoảng 1 phút.
- Chỉ đẩy file nằm trong `ScrapersOHLCV/data/stocks/` và `scrapers/data/`; test dùng thư mục tạm không bị đẩy.
- Tắt đẩy lên database: đặt biến môi trường `FINMIND_DB_SINK=off`. Máy không có `DATABASE_URL` thì tự không đẩy.
- `live.json` chỉ giữ ảnh chụp mới nhất của mỗi mã (ghi đè), không lưu lịch sử.

### Kiểm tra trên web Supabase

**Table Editor** → chọn schema `public` → mở `price_bars`, `price_indicators`, `market_index_bars`, `market_live_snapshots`, `news_articles`. Hoặc chạy trong **SQL Editor**:

```sql
select 'price_bars' as bang, count(*) from price_bars
union all select 'price_indicators', count(*) from price_indicators
union all select 'market_index_bars', count(*) from market_index_bars
union all select 'market_live_snapshots', count(*) from market_live_snapshots
union all select 'news_articles', count(*) from news_articles;
```

### Lỗi thường gặp

| Thông báo                         | Cách xử lý                                                            |
| ----------------------------------- | ------------------------------------------------------------------------ |
| `password authentication failed`  | Sai mật khẩu hoặc tên user trong `DATABASE_URL`. Hỏi lại leader. |
| `Chua co bang ...`                | Chưa chạy file SQL ở Bước 1.                                        |
| `timeout` / `could not connect` | Mạng chặn cổng. Đổi mạng, hoặc dùng cổng 5432 (Session pooler). |
| `ModuleNotFoundError: asyncpg`    | Cài thư viện như phần cấu hình ở trên.                          |

## Ghi chú kiểm tra dữ liệu Vector RAG

Để Vector RAG chạy đúng với dữ liệu tài chính, cần kiểm tra và sửa các mục dưới đây. Theo rà soát code, có vài vấn đề về đơn vị và kỳ báo cáo; cần xử lý trước khi nạp BID vào Supabase.
Ưu tiên	Cần kiểm tra	Cách sửa

1. Đơn vị số tiền	/api/documents/json và /api/documents/import-symbol/{symbol} dùng _statement_pages() để tạo nội dung chunk. Hàm này hiện ghi giá trị VND thô mà không ghi đơn vị.	Thống nhất mọi đường ingest: số tiền thành triệu VND, ghi nhãn rõ, ví dụ TỔNG TÀI SẢN: 3.440.840.854 triệu VND.
2. Kỳ lưu chuyển tiền tệ	BCTC Q2 trình bày dòng tiền lũy kế từ 01/01 đến 30/06; JSON lại gắn nhãn 2026-Q2.	Ghi rõ basis là lũy kế 6 tháng. Nếu cần hỏi riêng dòng tiền quý 2, phải tính từ số lũy kế Q2 trừ số lũy kế Q1. Không dùng nhãn “Q2 riêng” cho số lũy kế.
3. Khác biệt số liệu	Một số giá trị JSON không khớp PDF, chẳng hạn bsb112, bsb113, isb29, cfa18.	Kiểm tra JSON thô và đúng phiên bản báo cáo crawler đã lấy. Chỉ sửa giá trị sau khi xác nhận nguồn và kỳ; không tự chọn số từ PDF khác phiên bản.
4. Ánh xạ mã chỉ tiêu	Tên map nhìn chung hợp lý nhưng vài mã nội bộ như nob66, nob69, nob70 chưa có định nghĩa rõ.	Chỉ map sang tên chuẩn khi có định nghĩa từ nguồn; nếu chưa rõ, giữ mã gốc và đánh dấu chưa xác minh.
5. Chunk không cắt mất ngữ cảnh	Dữ liệu tài chính có nhiều chỉ tiêu trong một kỳ; cần kiểm tra build_chunks() không tách số khỏi tên mã, kỳ hoặc đơn vị.	Mỗi chunk phải giữ đủ mã cổ phiếu, tên báo cáo, kỳ, basis, chỉ tiêu, giá trị và đơn vị.
6. Trùng dữ liệu khi nạp lại	Cần kiểm tra API có nhận diện tài liệu đã nạp hay có thể tạo nhiều bản/chunk trùng.	Đặt khóa chống trùng theo mã cổ phiếu + kỳ + phiên bản dữ liệu; khi cập nhật thì thay đúng bộ chunk cũ.
7. Embedding và tìm kiếm	Kiểm tra model tạo vector đúng 1024 chiều, cùng model cho lúc nạp và lúc tìm kiếm; chỉ mục dùng cosine phù hợp.	Nếu đổi model hoặc cách chuẩn hóa vector, phải tạo lại embeddings cho dữ liệu cũ trước khi tìm kiếm.

Thứ tự làm để chạy được:

1. Sửa cách tạo text để đơn vị và kỳ được ghi rõ, thống nhất giữa các endpoint ingest.
2. Sửa nhãn cash flow thành “lũy kế 6 tháng” hoặc xác nhận nguồn để phân biệt Q2 riêng.
3. Xác minh và xử lý các số liệu lệch nguồn.
4. Nạp lại BID sau khi xóa/thay bộ dữ liệu BID cũ, tránh tìm kiếm lẫn chunk cũ và mới.
5. Kiểm tra một câu hỏi mẫu như “Tổng tài sản BID tại 30/06/2026 là bao nhiêu?” để xác nhận kết quả trả về đúng số, kỳ và đơn vị.
   Trong đó, mục 1 là lỗi cần sửa trực tiếp để nội dung Vector RAG không gây hiểu sai. Mục 2–4 cần làm trước khi tin kết quả tài chính.
6. 


```
py-m uvicorn src.main:app --reload --port 8000
```
