# History thay đổi code

File này ghi lại mọi lần sửa/bổ sung code trong dự án. Mỗi mục bắt buộc có 3 phần: **Sai gì**, **Tại sao sửa**, **Ảnh hưởng**.

Quy trình bắt buộc trước khi sửa:
1. Đọc code liên quan + các nơi gọi/import đến nó (grep/search) để xác định phạm vi ảnh hưởng.
2. Đánh giá rủi ro: có breaking change với module khác không (API, schema data, biến môi trường, tên hàm/class...).
3. Thực hiện sửa.
4. Ghi lại vào file này theo template bên dưới, kèm ngày và file/dòng liên quan.

---

## Template

### [YYYY-MM-DD] Tiêu đề ngắn gọn

- **File(s):** đường dẫn file
- **Sai gì:** mô tả lỗi/thiếu sót cụ thể
- **Tại sao sửa:** lý do, nguyên nhân gốc
- **Ảnh hưởng:** những module/file/chức năng khác có thể bị ảnh hưởng (hoặc "Không ảnh hưởng gì ngoài file này")

---

### [2026-10-14] Thêm quy trình Supabase → chia chunk → nhúng vector (WBS06) và hướng dẫn chạy cho cả nhóm

- **File(s) mới (commit 7eb5a9c, ngày 13/10):** `backend/src/documents/db_chunking.py`, `backend/src/documents/db_source.py`, `backend/src/documents/db_ingest.py`, `backend/scripts/chunk_from_supabase.py`, `backend/tests/test_db_chunking.py`, `backend/tests/test_db_chunking_sources.py`, `backend/tests/test_db_ingest.py`
- **File(s) sửa trong ngày 14/10:** `backend/scripts/chunk_from_supabase.py` (thêm `--vectors-out`, gọi `EmbeddingService` đúng chữ ký mới), `backend/src/documents/db_ingest.py` (dùng `embed_chunks()` của Nhân)
- **Thiếu gì:** Chunker cũ (`chunking.py`) chỉ chia từ file PDF theo cửa sổ 130 từ, gộp mọi khoảng trắng nên **xé hàng bảng số liệu** và mỗi chunk không có mã định danh, không biết thuộc tài liệu/dòng dữ liệu nào. Dữ liệu giá, chỉ số, tin tức và hồ sơ công ty đã nằm trong Supabase nhưng chưa có đường nào đưa thành chunk và vector. Mục "Cách chạy" của nhóm cũng chưa có.
- **Tại sao thêm:** WBS06 yêu cầu chunk không rỗng, không lặp ID, không xé bảng. Dữ liệu đã chuẩn hóa nằm trong database nên chia thẳng từ bảng chính xác hơn đoán ranh giới từ PDF. Nối với `embed_chunks()` (WBS07 của Nhân) để một lệnh đi từ Supabase tới vector.
- **Nguyên tắc chia chunk:**
  1. Đơn vị không cắt là một **dòng** (một ngày giá, một chỉ tiêu, một đoạn văn). Chunk luôn gồm nguyên các dòng.
  2. **Tiêu đề lặp ở mọi chunk** (công ty, loại báo cáo, kỳ, phạm vi, đơn vị): con số không bao giờ tách khỏi kỳ và đơn vị.
  3. Tối đa ~130 từ mỗi chunk (tiêu đề tính vào). Đoạn văn quá dài cắt theo câu, câu quá dài mới cắt theo từ.
  4. `chunk_id` ổn định (uuid5 từ nội dung và vị trí): chạy lại ra cùng mã; đổi một giá trị thì chỉ chunk chứa nó đổi mã.
  5. Mỗi chunk có `locator.row_keys` trỏ về dòng gốc (`price_id`, `observation_id`) hoặc `article_id` + `url`.
- **Nguồn dữ liệu đọc (chỉ SELECT):** `companies`, `financial_reports` + `reporting_periods` + `observations` + `metrics`, `price_bars` + `price_indicators`, `market_index_bars`, `news_articles`.
- **Cách chạy (từ thư mục gốc `FinMind`):**

  Chuẩn bị một lần: file `.env` ở gốc có `DATABASE_URL` (lấy từ leader, **không commit**); `pip install -r backend/requirements.txt`; lần đầu nhúng vector sẽ tải mô hình bge-m3 (~2,2 GB) vào `C:\Users\<tên>\.cache\huggingface`.

  ```powershell
  # 1. (Tùy chọn) Cào tin mới. Cần scrapling: pip install -r data_pipeline/scrapers/requirements.txt
  python -B -X utf8 data_pipeline/scrapers/run_news_pipeline.py --symbols FPT --limit 5 --only-symbols

  # 2. Đưa tin lên Supabase: chạy thử trước, rồi ghi thật (chạy lại an toàn, không nhân đôi)
  py -X utf8 backend/scripts/ingest_market_news_to_supabase.py --only news
  py -X utf8 backend/scripts/ingest_market_news_to_supabase.py --only news --apply

  # 3. Chỉ xem chia chunk (không ghi gì, vài giây)
  py -X utf8 backend/scripts/chunk_from_supabase.py

  # 4. Kéo từ Supabase, chia chunk, nhúng vector, lưu ra file (KHÔNG ghi database)
  py -X utf8 backend/scripts/chunk_from_supabase.py --vectors-out backend/.tmp/tat-ca-vectors.json

  # 5. KHÔNG THUỘC TASK CHUNK. Ghi database (documents + text_chunks + index_versions) là
  #    WBS12 của Nhân. Lệnh này bị khóa: chỉ chạy khi đã thống nhất với Nhân và leader.
  py -X utf8 backend/scripts/chunk_from_supabase.py --apply --confirmed-with-nhan
  ```

  Tùy chọn: `--source all|companies|financial|prices|indices|news` (mặc định `all`), `--symbol FPT VCB` (lọc theo mã; **bỏ ra thì lấy hết**, kể cả chỉ số và tin chung), `--limit N` (số bài tin tối đa, `0` = lấy hết), `--max-words 130`, `--out file.json` (chỉ chunk), `--vectors-out file.json` (chunk + vector), `--apply --confirmed-with-nhan` (ghi database, **thuộc WBS12 của Nhân**, bị khóa nếu thiếu cờ xác nhận), `--batch-size`, `--model`.
- **Các file được ghi ở đâu:**

  | Lệnh | Nơi ghi |
  |---|---|
  | `chunk_from_supabase.py` (không cờ) | Không ghi file nào |
  | `--out X.json` | Đường dẫn X (chỉ chunk). Đặt ở gốc `FinMind` thì **Git theo dõi**, đừng commit |
  | `--vectors-out X.json` | Đường dẫn X (chunk + vector, ~45 MB cho toàn bộ). Đặt trong `backend/.tmp/` (đã `.gitignore`) |
  | `--apply --confirmed-with-nhan` | Bảng `index_versions`, `documents`, `text_chunks` trên Supabase (WBS12 của Nhân) |
  | `embed_chunks_batch.py` | `backend/.tmp/embedding-batch-results.json` (mặc định) |
  | Crawler tin | `data_pipeline/scrapers/data/tin_tuc_theo_ma/<MÃ>/<nguồn>/<ngày>.json` và `reports/pipeline/*` |

- **Kết quả đo ngày 14/10 (dữ liệu thật trên Supabase):**
  - Toàn bộ nguồn: **1.950 chunk**, nhúng vector **1.950/1.950 thành công, 0 lỗi**, 1024 chiều, độ dài L2 = 1,0000, mất khoảng 14 phút trên CPU (~0,4 đến 0,57 giây/chunk).
  - Theo nguồn: tin 1.652 chunk (224 bài), giá 204 (6 mã), chỉ số 88 (3 chỉ số), hồ sơ công ty 6, **báo cáo tài chính 0**.
  - Chỉ tin FPT: 270 chunk từ 32 bài, gồm 10 bài mới cào ngày 14/10 (đã tải lên Supabase).
  - Thử tìm kiếm 10 câu: 3 câu không tính vì bài chưa có trên Supabase lúc đó; trong **7 câu hợp lệ: top-1 đúng 4/7, top-3 đúng 5/7**.
- **Ảnh hưởng:**
  - Chỉ thêm file mới và tùy chọn mới; **không đổi** `chunking.py`, API `/api/documents`, `/api/search`, schema database hay giao diện. Đường PDF cũ vẫn chạy.
  - **Phạm vi task của Vũ (WBS06) dừng ở chunk** (`--out`, `--vectors-out`). Việc ghi `documents` và `text_chunks` lên database là **WBS12 và WBS17 của Nhân**. Phần ghi trong `db_ingest.py` và cờ `--apply` chỉ là **bản tham khảo để Nhân dùng lại**; vì vậy `--apply` bị khóa, phải thêm `--confirmed-with-nhan` mới chạy. Phần ghi mới được kiểm thử bằng đối tượng giả, **chưa chạy trên database thật**.
  - Dùng `index_versions` với `chunker_version = db-v1`; API tìm kiếm hiện tính index version theo `word-window-v1`, nên **API tìm kiếm cũ chưa thấy chunk mới** (cần thống nhất ở WBS25).
  - Nhãn mô hình ghi vào `index_versions` là `BAAI/bge-m3@5617a9f61b02` (24 ký tự), xem mục sửa nhãn ngay bên dưới.
- **Hạn chế đã biết (cần xử lý sau):**
  1. **`observations` đang trống (0 dòng)**: chưa có chunk báo cáo tài chính; phần bảng số liệu mới kiểm tra bằng dữ liệu mẫu. Cần nạp bằng `backend/scripts/ingest_to_supabase.py --apply` (đã có 10 file trong `data/normalized`).
  2. **Câu hỏi theo ngày cụ thể** (ví dụ "giá FPT ngày 6/10/2026") lên vị trí #7 đến #10 thay vì #1: mỗi chunk gộp 4–5 ngày và định dạng ngày khác nhau (`6/10/2026` so với `2026-10-06`). Cần bộ lọc theo công ty và ngày (WBS25) hoặc thêm ngày dạng đọc được vào dòng giá.
  3. **Tên thường gọi**: chunk công ty chỉ ghi "Ngân hàng TMCP Ngoại thương Việt Nam", câu hỏi "Vietcombank" không khớp. Cần thêm tên gọi tắt.
  4. Câu hỏi **không dấu** làm kết quả kém hơn rõ rệt; nên chuẩn hóa câu hỏi.
  5. `char_start/char_end` tính trong phần thân của từng mục (không phải trong PDF).
  6. Chưa chia `market_live_snapshots` (bảng điện đổi mỗi 5 giây) và chưa xử lý "bài bị xóa khỏi nguồn".
- **Kiểm chứng:** 37 test liên quan đạt (chia chunk, ghi database, embedding). Dữ liệu thử: 10 bài FPT cào ngày 14/10 → 98 chunk → 98 vector.

---

### [2026-10-14] Sửa lỗi nhãn mô hình embedding (52 ký tự > cột 50) và dọn 6 điểm trong code embedding theo lô (WBS07)

- **File(s) sửa:** `backend/src/core/config.py`, `backend/src/documents/embeddings.py`, `backend/src/documents/batch_embeddings.py`, `backend/scripts/embed_chunks_batch.py`, `backend/tests/test_embedding_config.py`, `backend/tests/test_batch_embeddings.py`, và hai file do Vũ viết cho phần chia chunk từ Supabase: `backend/src/documents/db_ingest.py`, `backend/scripts/chunk_from_supabase.py`
- **Sai gì:**
  1. **Lỗi chặn:** `Settings.embedding_model_ref` = `BAAI/bge-m3@<40 ký tự SHA>` dài **52 ký tự**, trong khi cột `index_versions.embedding_model` là `varchar(50)`. Mọi nơi ghi nhãn này (`routers/documents.py` qua `repository.ensure_index_version`) sẽ bị PostgreSQL từ chối khi ghi lên Supabase. Test không bắt được vì dùng đối tượng giả.
  2. `EmbeddingService.__init__` đổi chữ ký thành `(model_name, revision, device, batch_size)`: lời gọi kiểu cũ `EmbeddingService(model, "cpu")` gán nhầm `revision="cpu"` mà không báo lỗi lúc tạo, đến lúc tải mô hình mới lỗi.
  3. Số chiều vector 1024 được khai báo ở ba nơi: `Settings.embedding_dim`, `batch_embeddings.EMBEDDING_DIM`, `db_ingest.EMBEDDING_DIM`; đổi mô hình sẽ dễ sửa lệch.
  4. `embed_chunks_batch.py --batch-size N` chỉ đổi lô ngoài; lô trong của `model.encode` vẫn dùng `settings.embedding_batch_size` nên chỉnh tham số không có tác dụng như kỳ vọng.
  5. Chunk trùng `chunk_id` bị ghi vào danh sách `failed` (và làm script thoát mã 1) dù không phải lỗi embedding.
  6. Không có giới hạn độ dài text: bge-m3 nhận tối đa 8192 token, text dài hơn bị cắt âm thầm.
  7. (Code của Vũ) `db_ingest.py` tự viết lại vòng embed riêng, không có thử lại từng chunk như `embed_chunks()`; `chunk_from_supabase.py` gọi `EmbeddingService` theo chữ ký cũ.
- **Tại sao sửa:**
  - Mục 1 chặn WBS12 (lưu vector vào pgvector): sẽ lỗi ngay lần ghi đầu tiên lên Supabase. Dùng 12 ký tự đầu SHA (`BAAI/bge-m3@5617a9f61b02`, 24 ký tự) vẫn phân biệt được bản mô hình, vẫn đúng ý "ghim phiên bản để không trộn vector".
  - Mục 2: đặt `revision` thành tham số **bắt buộc theo từ khóa** để gọi sai chữ ký báo `TypeError` ngay thay vì lỗi muộn.
  - Mục 3 đến 6: một nguồn sự thật cho số chiều, hành vi tham số đúng như tên, tách "bỏ qua" khỏi "lỗi", không cắt text âm thầm.
  - Mục 7: dùng một đường duy nhất `embed_chunks()` để cả hai script có cùng cách thử lại và kiểm tra vector.
- **Thay đổi cụ thể:**
  - `config.py`: `embedding_model_ref` trả `f"{model}@{revision[:12]}"`.
  - `embeddings.py`: `__init__(self, model_name, *, revision, device="cpu", batch_size=8)`.
  - `batch_embeddings.py`: `EMBEDDING_DIM = get_settings().embedding_dim`; thêm `MAX_TEXT_CHARS = 20_000` và tham số `max_chars` (text dài hơn vào `failed`, không thử lại); `BatchEmbeddingResult` thêm `skipped` cho ID trùng.
  - `embed_chunks_batch.py`: `batch_size` truyền cả cho `EmbeddingService`; kết quả JSON thêm `skipped_count`, `skipped`; mã thoát chỉ theo `failed`.
  - `db_ingest.py`: `embed_all()` gọi `embed_chunks()`; `EMBEDDING_DIM` lấy từ `batch_embeddings`.
  - `chunk_from_supabase.py`: gọi `EmbeddingService(model_name=..., revision=..., ...)` và dùng `settings.embedding_model_ref` làm nhãn index version.
- **Ảnh hưởng:**
  - **Đã kiểm tra các nơi gọi** bằng grep (`EmbeddingService(`, `embedding_model_ref`, `EMBEDDING_DIM`): chỉ có `embeddings.get_embedding_service()`, `embed_chunks_batch.py`, `chunk_from_supabase.py` và test gọi `EmbeddingService`; các nơi gọi đều dùng tham số theo từ khóa nên không vỡ.
  - **`index_version_id` đổi giá trị** vì được tính từ `embedding_model_ref` (`routers/documents.py` dòng 54, 199, 241 và `routers/search.py` dòng 38). Tài liệu đã nạp trước đó theo nhãn cũ sẽ không còn khớp index version mới, cần nạp lại. Thực tế nhãn 52 ký tự chưa ghi được vào database nên chưa có dữ liệu nào mang nhãn đó; nhãn trước commit WBS02 là `BAAI/bge-m3` thuần, nên dữ liệu cũ (nếu có) cũng cần nạp lại như `docs/embedding/README.md` đã nói.
  - `docs/embedding/bge-m3-v1.json` và `bge-m3-sample-v1.json` vẫn ghi `reference`/`model_ref` đầy đủ 40 ký tự SHA: **vẫn đúng** như tham chiếu đầy đủ, chưa sinh lại. Khi chạy lại `generate_embedding_sample.py`, trường `model_ref` sẽ ra nhãn ngắn.
  - File `backend/.tmp/embedding-batch-results.json` (không commit) từ nay có thêm `skipped_count` và `skipped`; script nào đọc file này cần bỏ qua hai khóa mới hoặc cập nhật.
  - `test_batch_embeddings.py`: test ID trùng đổi kỳ vọng từ `failed` sang `skipped`; thêm test text quá dài và test `revision` bắt buộc theo từ khóa. `test_embedding_config.py`: kỳ vọng nhãn ngắn và độ dài <= 50.
  - **Không đổi:** schema database, `repository.py`, `chunking.py`, API `/api/documents`, `/api/search`, giao diện.
  - **Kiểm chứng:** 37 test đạt (embedding, chia chunk, ghi database). Chạy thật `embed_chunks_batch.py --limit 16` với `BAAI/bge-m3@5617a9f61b02` trên CPU: 16/16 chunk thành công, 1024 chiều, độ dài vector (L2) bằng 1,0000, mỗi chunk gọi mô hình 1 lần, mất 46 giây. Chưa ghi gì vào database.
  - **Rủi ro còn lại:** (a) API tìm kiếm hiện tính index version theo bộ chia `word-window-v1`, còn chunk chia từ Supabase dùng `db-v1`, nên API tìm kiếm cũ chưa thấy chunk mới (cần thống nhất ở WBS25); (b) giới hạn 20.000 ký tự là ước lượng an toàn, chưa đo bằng tokenizer thật.
  - Các file `embeddings.py`, `batch_embeddings.py`, `embed_chunks_batch.py` và hai file test là code của Nhân (WBS02, WBS07): cần báo Nhân trước khi merge để tránh conflict.

---

### [2026-09-29] Sửa importer JSON tài chính theo ERD

- **File(s):** `backend/scripts/ingest_to_supabase.py`
- **Sai gì:** Importer cũ đọc báo cáo ở cấp cao nhất thay vì `financial_data` như JSON normalized hiện tại; ghi vào cấu trúc `industries/datasets/id` không khớp ERD đang dùng; và khi chạy sẽ kết nối/ghi database ngay, không có preflight schema hay chế độ dry-run.
- **Tại sao sửa:** Đồng bộ đường nạp OHLCV và báo cáo tài chính với các bảng `companies`, `sources`, `ingestion_jobs`, `raw_payloads`, `reporting_periods`, `financial_reports`, `metrics`, `observations`, `price_bars` trong ERD. Dùng UUID ổn định và upsert để chạy lại không nhân bản bản ghi; kiểm tra cột đích trước khi ghi.
- **Ảnh hưởng:** Importer mặc định chỉ lập kế hoạch dry-run; `--apply` mới mở kết nối và ghi dữ liệu. Chỉ nhận JSON `data/normalized`; yêu cầu database đã có schema khớp ERD. Các nguồn mới được ghi trạng thái `PENDING`/tắt cho tới khi được duyệt. Chưa chạy importer hoặc ghi vào database; Python chưa có trên PATH tại máy này.

---

### [2026-09-27] Nối Vector RAG với các bảng Supabase riêng

- **File(s):** `backend/src/repository.py`, `backend/src/db.py`, `backend/src/json_ingest.py`, `backend/requirements.txt`, `backend/scripts/init_postgres_schema.sql`, `backend/scripts/init_pgvector.sql`
- **Sai gì:** Repository Vector RAG dùng `documents.id` và bảng `document_chunks`, xung đột với schema tài chính đã có trên Supabase; bảng RAG riêng vừa được tạo là `rag_documents` và `rag_document_chunks`. Cấu hình pgvector adapter chưa ưu tiên schema `public`. Nhãn PE/PB/PS hiển thị thành mã viết liền. Torch 2.5.1 bị Transformers chặn khi tải checkpoint `.bin` vì giới hạn bảo mật.
- **Tại sao sửa:** Cho API ingest/search dùng đúng các bảng RAG tách riêng, tương thích extension vector cài ở `public`, tránh chạm vào bảng tài chính; hiển thị nhãn định giá dễ đọc và ghim Torch 2.6.0 theo ngưỡng bảo mật của Transformers.
- **Ảnh hưởng:** Vector RAG repository và SQL bootstrap dùng các tên `rag_*`; không đổi bảng tài chính. Smoke check Supabase thực hiện trong transaction và rollback, không để lại hàng thử. Nhóm test backend liên quan: 20 pass, 1 fail do assertion cũ kỳ vọng mã fallback chữ thường trong khi mapping hiện hành chuẩn hóa chữ hoa. Không ingest dữ liệu chứng khoán thật.

---

### [2026-09-19] Review toàn bộ code (backend, data_pipeline, frontend) — không sửa code

- **File(s):** toàn bộ `backend/src/*`, `data_pipeline/src/*`, `data_pipeline/tests/audit_pipeline.py`, `frontend/src/api.js`, `.env`, `backend/.env`, `data_pipeline/.env`, `frontend/.env.local`, `.gitignore`, `docker-compose.yml`
- **Sai gì:**
  1. `data_pipeline/src/ingest.py` rỗng (0 byte), không được import ở bất kỳ đâu trong repo (đã grep toàn bộ).
  2. `.env` (root), `backend/.env`, `data_pipeline/.env`, `frontend/.env.local` đang bị track trong git từ commit `ceaebbf` (initial structure), mâu thuẫn với comment trong `.gitignore` nói ý định là không commit `.env` thật (chỉ ignore `.env.local.bak`). Hiện tại nội dung các file này không chứa secret thật (chỉ placeholder `finmind:finmind` hoặc rỗng).
  3. Backend Vector RAG (main.py, config.py, db.py, embeddings.py, repository.py, routers/, schemas.py, chunking.py, text_analysis.py) và data_pipeline (pipeline_quality.py, direct_vn_collector.py, audit_pipeline.py) không phát hiện bug logic — SQL dùng parameterized query, xử lý NaN/Infinity/atomic write JSON đều đúng.
- **Tại sao sửa:** Không sửa. Đã hỏi và được xác nhận:
  - `ingest.py`: giữ nguyên, để trống (có thể dùng làm entrypoint sau này).
  - `.env` bị track: chỉ cảnh báo, không đổi git tracking (vì hiện chưa có secret thật nên rủi ro tức thời thấp).
- **Ảnh hưởng:** Không có thay đổi nào được áp dụng, nên không ảnh hưởng runtime. Rủi ro còn tồn đọng (cần theo dõi): nếu sau này ai điền secret thật vào các file `.env` đang bị track rồi commit, secret sẽ lộ vào lịch sử git. Khi đó cần `git rm --cached` các file này + thêm vào `.gitignore` + rotate secret đã lộ (nếu có).

---

### [2026-09-19] Thêm input JSON (dữ liệu tài chính) cho Vector RAG — không dùng LLM sinh câu trả lời

- **File(s) mới:** `backend/src/json_ingest.py`, `backend/tests/test_json_ingest.py`, `backend/tests/test_api_documents_json.py`
- **File(s) sửa:** `backend/src/routers/documents.py`, `backend/src/config.py`, `backend/.env`, `backend/.env.example`, `docker-compose.yml`, `frontend/src/api.js`, `frontend/src/components/UploadPanel.jsx`
- **Sai gì / Thiếu gì:** Backend Vector RAG trước đó chỉ nhận input là PDF (`POST /api/documents`), không có cách nào nạp dữ liệu JSON tài chính đã cào sẵn ở `data/normalized/*.json` (8 mã CP) vào hệ thống tìm kiếm.
- **Tại sao thêm:** Yêu cầu của người dùng (2026-09-19): input là dữ liệu JSON, và **không** dùng LLM tự sinh câu trả lời (tốn token) — AI chỉ đóng vai trò lọc/xếp hạng dữ liệu liên quan (đúng như embedding BAAI/bge-m3 + pgvector đã làm), câu trả lời vẫn là trích xuất nguyên văn (extractive), không phải văn bản do LLM viết lại.
- **Đã làm:**
  1. `json_ingest.py`: chuyển JSON thành danh sách `Page` (tái dùng lại `chunking.build_chunks()` có sẵn, không viết lại logic windowing):
     - Giá cổ phiếu (`price_history`) → gộp theo tháng, câu tiếng Việt dễ đọc (mở/đóng cửa, cao/thấp, tổng KLGD).
     - Chỉ số tài chính (`ratios`) → 1 page/kỳ, tên field có nghĩa (P/E, P/B, ROE, ROA...) dịch sang tiếng Việt qua dict `RATIO_LABELS`.
     - Income statement/Balance sheet/Cash flow → 1 page/kỳ, dùng `key: value` thô vì mã field (`isaNN`, `bsaNN`, `cfaNN`) không có bảng chú giải trong repo (đã hỏi và được xác nhận chấp nhận hạn chế này).
     - `generic_json_to_pages()`: fallback cho JSON bất kỳ (không đúng schema chuẩn hóa của data_pipeline) — tự tìm list-of-object để chunk theo record, hoặc dump nguyên văn nếu không nhận diện được cấu trúc.
  2. `routers/documents.py`: tách phần chung (chunk → embed → lưu DB) của `upload_document` cũ ra hàm `_ingest_pages()`, dùng lại cho 2 endpoint mới:
     - `POST /api/documents/json` — upload 1 file JSON bất kỳ.
     - `POST /api/documents/import-symbol/{symbol}` — đọc thẳng `data/normalized/{SYMBOL}.json` từ đĩa, không cần upload thủ công.
  3. `config.py`: thêm `financial_data_dir` (mặc định `../data/normalized`, đúng quy ước các default khác trong file — giả định chạy `cd backend && uvicorn ...`); `docker-compose.yml` mount `./data:/app/data:ro` vào backend + set `FINANCIAL_DATA_DIR=/app/data/normalized` để endpoint import-symbol dùng được cả khi chạy qua Docker.
  4. Frontend: `UploadPanel.jsx` nhận thêm `.json`, tự route sang API JSON theo phần mở rộng file; thêm dropdown chọn 1 trong 8 mã (danh sách trùng `TARGET_SYMBOLS` trong `direct_vn_collector.py`) + nút "Import" gọi endpoint import-symbol.
  5. Sửa `_fmt()`: số tiền lớn (>= 1000) format dạng `1,234,567` thay vì ký hiệu khoa học `1.235e+6` — dễ đọc và dễ khớp tìm kiếm hơn.
  6. Test: 14 test mới (`test_json_ingest.py` test logic thuần, `test_api_documents_json.py` test API qua `TestClient` với fake embedder + mock repository, theo đúng pattern có sẵn của `test_api_search.py`). Đã cài tạm `pytest/fastapi/asyncpg/pgvector/numpy/pypdf` (môi trường trước đó chưa có) để chạy toàn bộ 25 test — **25/25 pass**. Đã chạy thử `financial_json_to_pages` trên `data/normalized/SSI.json` thật: 168 page → 1077 chunk, nội dung tiếng Việt hiển thị đúng.
- **Ảnh hưởng:**
  - `upload_document` (luồng PDF cũ) được refactor nhưng hành vi/response giữ nguyên 100% — đã chạy lại `test_api_search.py` + toàn bộ test cũ, không có test nào fail.
  - Bảng `document_chunks` không đổi schema; cột `page` (vốn là "số trang PDF") giờ được dùng lại cho JSON với ý nghĩa khác ("mã section": 0=giá, 1=ratios, 2=income, 3=balance, 4=cashflow) — không phá cấu trúc DB, chỉ đổi ý nghĩa ngữ cảnh của giá trị.
  - **Rủi ro vận hành cần lưu ý:** ingest 1 mã CP đầy đủ (~8 năm giá + BCTC) tạo ra khoảng ~1000+ chunk cần embed bằng BAAI/bge-m3 chạy CPU → có thể mất vài phút/mã, x8 mã sẽ lâu hơn. Đây là giới hạn vốn có của việc không dùng LLM tóm tắt/nén dữ liệu trước khi embed, không phải bug.
  - Chất lượng tìm kiếm ngữ nghĩa cho 3 phần Income/Balance/Cashflow sẽ kém hơn Prices/Ratios do dùng mã field thô, đã được người dùng xác nhận chấp nhận — cần bổ sung bảng chú giải mã sau này nếu muốn cải thiện.
  - Chưa đụng đến `search.py`/luồng tìm kiếm — search vẫn hoạt động y hệt cũ trên mọi loại document (PDF hay JSON), vì đều đi qua cùng bảng `document_chunks`.

---

### [2026-09-24] Chuyển đổi mô hình môi trường: Docker chỉ chạy Database (Postgres + Neo4j), Backend & Frontend chạy trên Windows

- **File(s) sửa:** `docker-compose.yml`, `backend/requirements.txt`, `backend/.env`, `history.md`
- **Sai gì / Thiếu gì:**
  1. `docker-compose.yml` cố gắng build toàn bộ Backend Python bên trong Linux container, gặp tình trạng nghẽn mạng nghiêm trọng (tốc độ tải pip chỉ đạt ~12 kB/s), khiến quá trình tải gói PyTorch/sentence-transformers kéo dài hàng giờ và dễ lỗi timeout.
  2. Dự án có module đồ thị tri thức Neo4j (`backend/src/graph/`) nhưng thiếu service `neo4j` trong `docker-compose.yml`, đồng thời `backend/requirements.txt` thiếu driver `neo4j>=5.15.0`.
  3. `backend/.env` đang trỏ đến đường dẫn container `/app/data/normalized` thay vì đường dẫn tương đối máy host `../data/normalized`.
- **Tại sao sửa:** 
  - Yêu cầu của người dùng muốn dùng Neo4j và chuyển đổi việc chạy backend/frontend sang Windows native để tận dụng tối đa tốc độ mạng của máy, tránh việc phải đóng gói Linux container cồng kềnh khi đang phát triển (development).
  - Tối ưu hóa kiến trúc: Docker chỉ đảm nhận chạy các cơ sở dữ liệu đã đóng gói sẵn (PostgreSQL 16 + pgvector và Neo4j 5 Community), không phải build image.
- **Ảnh hưởng:**
  - `docker-compose.yml` giờ chỉ khởi chạy 2 container cơ sở dữ liệu: `postgres` (port 5433, đổi từ 5432 để tránh xung đột với service PostgreSQL có sẵn trên Windows của máy host) và `neo4j` (port 7474 giao diện web, port 7687 bolt). Khởi động cực nhanh (chỉ vài chục giây).
  - Backend (FastAPI) và Frontend (Vite React) sẽ được chạy trực tiếp trên máy Windows thông qua PowerShell, hỗ trợ Hot Reload và tải thư viện nhanh.
  - Không có breaking change về mặt logic code hay schema dữ liệu.
