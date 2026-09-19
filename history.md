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
