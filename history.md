# History thay đổi code

### [2026-10-23] WBS34 — mẫu E2E vector retrieval Q03 trên corpus-v4

- **File(s):** `backend/scripts/audit_vector_e2e.py`, `backend/tests/test_audit_vector_e2e.py`, `docs/embedding/WBS34-vector-e2e.md`, `history.md`.
- **Mục tiêu:** Theo một bài tin FPT từ membership corpus, chunk/locator, vector và nguồn đã ghim đến kết quả top 5 của API; có ca sai phạm vi và đối chiếu chạy lặp. Script chỉ đọc Supabase, báo cáo JSON cục bộ trong `backend/.tmp`.
- **Kiểm chứng:** Bài Q03 có 8 chunk hiện hành; 8/8 đúng ID, vị trí, hash nguồn và 1024 chiều. Vector tạo lại từ một chunk đã xác minh có cosine `1.0` với vector DB. Q03 trả đúng bài và ba dữ kiện ở hạng 1/5; hai lượt retrieval cho cùng ID, lọc sai công ty/kỳ rỗng. Route HTTP thử qua ASGI client trả 200/5 hit, cả 5 xác minh nguồn. 10/10 check của script và 49 test liên quan đạt.
- **Giới hạn:** Chưa chạy lại writer corpus-v4 trên DB thật vì repo hiện chưa có lệnh tái nạp release `db-corpus-v2`; test idempotence writer `db-v1` và biên bản WBS17 là bằng chứng riêng, không được tính thành rerun v4. Không chấm toàn bộ Golden40 hay câu trả lời cuối. Cần owner luồng tạo v4 cung cấp cách rerun an toàn hoặc DB dev cùng release để hoàn tất điều kiện này.

---

### [2026-10-23] Kiểm tra bộ 40 câu mới của Huyền trên corpus-v4

- **File(s):** `bo cau hoi cua huyen 40 cau.md` (bộ đề mới được bàn giao); báo cáo thử cục bộ `backend/.tmp/huyen-golden40-corpus-v4-audit.json` được Git ignore. Lượt này không sửa thuật toán retrieval hay dữ liệu DB.
- **Cách chạy:** Đọc đủ Q01–Q40, dùng câu hỏi mới để tìm top 5 trên corpus-v4 `33d33730-0f0a-5274-a7f8-8d32a6be07e8` ở các câu tin/tài chính; thử Q11–Q20 qua SQL giá hiện có. Các truy vấn DB là chỉ đọc. Không dùng parser/phạm vi cứng của Golden v6 cũ để chấm bộ mới.
- **Kết quả vector:** Q01–Q09 và Q31–Q38 đều có 5 hit/câu, 0 lỗi dựng nguồn. Q31, Q32, Q34–Q38 có chỉ tiêu và số tương ứng trong top 5; Q33 có đúng `RETAINED_EARNINGS` ở hạng 5 nhưng chunk hiển thị `20,370,550.28 triệu VND` đã làm tròn, không còn số VND nguyên chính xác của đáp án. Q35/Q38 cần ghép hai đoạn. Tin Q06/Q07 khác dấu phân cách số/ngày so với đáp án; cần chuẩn hóa trước khi so khớp chữ.
- **Giới hạn bộ đề/DB:** Q10 ghi 224 bài, trong khi DB hiện có 234 bài (119 CafeF, 115 FireAnt). Q11–Q20 chạy được SQL nhưng chỉ Q14/Q17/Q20 khớp số tham khảo không vướng khác phạm vi; Q16 ra NLG -24,26% nhưng so trên 13 mã, không phải 6 mã của bộ đề. Q11/Q12/Q13/Q15/Q18/Q19 lệch số hoặc phạm vi: API đọc toàn bộ bảng giá hiện có (21.523 phiên), còn đáp án Huyền dựa tập 737 phiên. Cùng ngày Q11/Q15/Q19 còn có giá khác, cần đối chiếu snapshot nguồn. Corpus-v4 không chứa PDF cho Q21–Q29; Q30/Q40 là ca từ chối chưa có luồng trả lời để chấm; Q39 cần tính toán hai kỳ. FPT 2026-Q4 có 0 chunk trong corpus-v4 nhưng đó chưa phải kiểm chứng tính năng từ chối.
- **Kết luận:** Đây là kiểm tra retrieval/nguồn và khả năng của endpoint hiện tại, không phải 40/40 câu trả lời đúng. WBS20/WBS25 tiếp tục ở trạng thái review cho đến khi chốt tiêu chí nghiệm thu và snapshot dữ liệu; không đánh dấu Golden40 mới đã pass.

---

### [2026-10-23] Đọc nguồn corpus-v4 trên nhánh Nhân

- **Sai gì:** Index v4 trên Supabase đã có chunk `db-financial-v4`, nhưng reader của branch Nhân chỉ hỗ trợ đến v3; Q31–Q38 tìm được 40 hit nhưng tất cả báo `UNSUPPORTED_VERSION`. Chỉ thêm nhãn v4 vẫn lệch fingerprint vì v4 dùng nguồn và metadata lịch sử khác bảng live.
- **Tại sao sửa:** Chuyển đường đọc nguồn v4 từ `backup-demo`: lấy payload gốc đã ghim trong `raw_payloads`, dùng metadata release để dựng lại và kiểm tra membership/hash. Ghép riêng vào index v4 để giữ nguyên các thay đổi WBS20/WBS30 và đường đọc v2/v3.
- **Ảnh hưởng:** Chỉ thay đọc kết quả index v4, không ghi Supabase, không đổi vector/chunk, không merge toàn bộ `backup-demo`. Thêm các module reader nguồn dùng chung và renderer v4; audit Golden dùng được đường đọc này. File kết quả local nằm trong `.tmp`.
- **Kiểm chứng:** Bộ 55 test code/API/reader và bộ 53 test chunking/edge-case/API tài liệu qua. Audit Q31–Q38 trên corpus-v4: 8 câu × 5 hit, 0/40 lỗi dựng nguồn, lọc sai công ty/kỳ rỗng. API thử với vector đã lưu trả 200/5 hit và trace success. Đây là kiểm chứng nguồn/retrieval mẫu, chưa chấm đúng đáp án 40 câu Golden. Chi tiết: `docs/embedding/WBS25-corpus-v4-source-recheck.md`.

---

### [2026-10-22] Cho phép thử index v2 qua API tìm kiếm có lọc

- **File(s):** `backend/src/api/routers/search.py`, `backend/src/documents/schemas.py`, `backend/tests/test_filtered_search_api.py`, `docs/embedding/WBS20-WBS25-filtered-baseline.md`, `history.md`.
- **Sai gì:** API `/api/search/filtered` luôn chọn index v1 theo cấu hình, nên gọi Q31–Q32 trên Swagger không kiểm tra được các chunk tài chính thuộc v2. Ví dụ request cũ còn ghi sai `doc_type` là `FINANCIAL_REPORT`; giá trị trong DB là `FINANCIAL_STATEMENT`.
- **Tại sao sửa:** Người dùng cần thử chính Q31–Q32 trên dữ liệu v2 bằng backend API, không chỉ bằng script audit.
- **Ảnh hưởng:** Request có thể truyền `index_version_id` v2 đã ghim; bỏ trống vẫn dùng v1 như trước. ID khác bị từ chối 400. Chỉ tìm kiếm read-only, không sửa schema/vector hoặc chuyển trạng thái index/corpus. V2 vẫn là phiên `BUILDING` để thử, chưa nghiệm thu.
- **Kiểm chứng:** 22 test API/reader liên quan đạt. Chạy backend cổng 8765 với model cache offline, gửi Q31 và Q32 qua HTTP thật: cả hai trả 409 `SOURCE_CHANGED`, đúng lỗi nguồn tài chính đã thấy trong audit. Một lần thử trước đó trả 500 do môi trường bị chặn khi truy cập Hugging Face để tải/kiểm tra model; bật offline với cache đã có mới đến bước truy vấn DB.

---

### [2026-10-22] WBS20/WBS25: chỉ mục HNSW, tìm vector có lọc và kiểm tra Golden

- **File(s):** `supabase/migrations/20261020000100_text_chunks_hnsw.sql`; `backend/src/documents/repository.py`, `schemas.py`, `price_queries.py`; `backend/src/api/routers/search.py`; `backend/scripts/benchmark_pgvector.py`, `audit_golden_q01_q20.py`, `diagnose_golden_price_recall.py`, `audit_golden_price_sql.py`, `golden_v6.py`, `audit_golden_v6.py`, `fixtures/wbs20_filtered_questions.json`; `backend/tests/test_api_search.py`, `test_source_result_reader.py`, `test_filtered_search_api.py`, `test_filtered_vector_search.py`, `test_golden_v6.py`, `test_price_queries.py`; `Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md`; `docs/embedding/WBS20-WBS25-filtered-baseline.md`, `results/wbs20-pgvector-benchmark.json`, `results/golden-q01-q20-audit.md`; `history.md`.
- **Sai gì:** Chưa có truy vấn vector giới hạn theo công ty/kỳ/loại tài liệu và chưa có phép đo cố định để so sánh HNSW. Bộ audit cũ chỉ đọc định dạng Golden trước v6. Reader chưa chọn đúng renderer tài chính v3 từ locator; lọc kỳ chưa xét `locator_json.period_code`.
- **Tại sao sửa:** WBS20 cần chỉ mục và baseline; WBS25 cần trả đúng chunk trong phạm vi yêu cầu, kèm điểm và nguồn. Golden v6 cần công cụ kiểm tra riêng để phân biệt truy xuất kỹ thuật với đáp án được duyệt.
- **Ảnh hưởng:** Thêm migration HNSW cosine và `POST /api/search/filtered` cho các chunk hiện hành của một `index_version_id`, lọc công ty/kỳ/loại tài liệu; thêm `POST /api/search/price` dùng SQL chỉ đọc cho câu hỏi giá có cấu trúc. Bổ sung script benchmark, audit Golden và tài liệu kết quả. API filtered hiện tự chọn index theo cấu hình backend, nên thử qua Swagger **không tương đương** audit v2 chọn index tường minh. Không thay đổi dữ liệu nguồn hay tự đăng ký corpus-v2.
- **Kiểm chứng:** 28 test liên quan đạt, `git diff --check` đạt. Audit chỉ đọc Golden v6 xác nhận 40 câu gồm 27 vector, 9 tính toán, 2 tra dòng giá, 2 từ chối. 10 câu tin Q01–Q10 truy xuất được 5 hit có phạm vi/câu và không lỗi dựng nguồn trong mẫu; đây **chưa phải** 10 câu đạt đáp án chính thức vì thiếu gold evidence đã duyệt. 8 câu tài chính Q31–Q38 có 40/40 top hit mẫu bị chặn do fingerprint nguồn hiện tại khác lúc lập index. 22 câu còn lại chưa được audit vector này chấm. Corpus-v2 còn trạng thái BUILDING/chưa đăng ký; chưa nghiệm thu Golden v6 hoặc retrieval v2. Chi tiết giới hạn ở tài liệu baseline và báo cáo audit.
- **Git:** commit `ab44d09` trên nhánh `nhan-sprint-321` chứa các file code/tài liệu trên; mục history này được bổ sung sau commit đó.

---

### [2026-10-19] Ngừng ghi text cho chunk nguồn mới, giữ text cũ

- **File(s):** `backend/src/documents/db_ingest.py`, `backend/src/documents/corpus_manifest.py`, `backend/src/documents/retention.py`, `backend/tests/test_db_ingest.py`, `supabase/migrations/20261019000000_nullable_source_chunk_text.sql`, `supabase/reset_and_rebuild.sql`, `docs/embedding/source-locator-v2.md`, `history.md`.
- **Sai gì:** Luồng source ingest vẫn sao chép text vào text_chunks dù reader đã dựng lại từ nguồn; manifest/retention chưa xử lý trường hợp text NULL.
- **Tại sao sửa:** Người dùng đồng ý tiếp tục bước ngừng ghi mới trong tiến trình bỏ text. Ghi NULL cho chunk source mới có locator v2, manifest dùng reader và retention tính được vector khi text NULL.
- **Ảnh hưởng:** Đã nới nullable trên Supabase với CHECK yêu cầu v2 khi NULL, đồng bộ reset file. Không xóa text cũ hoặc cột, không đổi vector/ID/metadata hiện có; upload word-window-v1 vẫn giữ text. Cần cập nhật/restart backend các máy trước khi dùng writer mới. Nguồn lịch sử chưa đầy đủ, reader fail-closed nếu nguồn đổi/mất.
- **Kiểm chứng:** 60 test đạt. So fingerprint 2.051 bản ghi trước/sau migration không đổi. Thử text NULL đọc lại nguồn đúng, NULL thiếu locator bị từ chối; rollback lượt thử. Cuối cùng vẫn 2.051/2.051 bản ghi có text.

---

### [2026-10-19] API trả nội dung dựng từ nguồn cho locator v2

- **File(s):** `backend/src/documents/repository.py`, `backend/src/documents/schemas.py`, `backend/src/api/routers/search.py`, `backend/src/api/routers/documents.py`, `backend/src/main.py`, `backend/tests/test_source_result_reader.py`, `backend/tests/test_api_search.py`, `docs/embedding/source-locator-v2.md`, `history.md`.
- **Sai gì:** API vẫn trả chunk_text trực tiếp và tính index word-window-v1 ngay cả tài liệu DB db-v1; page bắt buộc số nguyên dù nguồn DB không có trang PDF.
- **Tại sao sửa:** Tiếp tục quy trình đã chốt: đọc nội dung theo locator v2 từ Supabase trước khi tính tới bỏ text. Dựng nguồn, kiểm tra hash và so với text hiện có; nguồn lệch/mất thì trả lỗi 409 reason_code thay vì dùng bằng chứng cũ âm thầm.
- **Ảnh hưởng:** Search/chunk details/vocab dùng reader chung trong transaction chỉ đọc snapshot nhất quán. DB chọn db-v1, upload cũ giữ word-window-v1 và DB text có kiểm tra hash. Page chấp nhận null. Không xóa/đổi schema, không ghi dữ liệu, không bỏ chunk_text, không đổi retention/corpus; backend đang chạy cần restart. API search vẫn theo document_id, chưa phải corpus-aware search đầy đủ.
- **Kiểm chứng:** 61 test đạt; kiểm tra HTTP search/chunk/vocab với pool Supabase chỉ đọc đều 200 trên mẫu 4 nhóm hiện có. Dùng vector thật đã lưu làm truy vấn để kiểm tra pgvector/bộ đọc, không tuyên bố đánh giá chất lượng semantic model hoặc tài chính API end-to-end.

---

### [2026-10-19] Làm mới 3 hồ sơ và backfill locator v2 hiện hành

- **File(s):** `backend/scripts/backfill_source_locators.py`, `backend/tests/test_backfill_source_locators.py`, `docs/embedding/source-locator-v2.md`, `history.md`.
- **Sai gì:** 3 chunk hồ sơ FPT/MBB/VCB lệch nguồn sau khi bổ sung ngành; 2.045 chunk còn lại chưa có reconstruction metadata trong DB.
- **Tại sao sửa:** Người dùng đồng ý tiếp tục để chuẩn bị đọc nội dung từ nguồn Supabase. Kiểm tra citation/corpus trước khi cập nhật; backfill chỉ khi khớp text/hash/ID và locator nguồn.
- **Ảnh hưởng:** Đã tạo 3 vector mới bằng model ghim, supersede/liên kết 3 chunk cũ (đều thuộc corpus-v1); không xóa bản cũ hay sửa manifest. Đã cập nhật locator_json của 2.045 chunk, giữ nguyên mọi cột còn lại. API search và chunk_text vẫn như cũ; chưa thực hiện xóa cột hoặc lịch sử.
- **Kiểm chứng:** 39 test đạt; backfill đối chiếu fingerprint tất cả trường ngoài locator không đổi. DB có 2.048 hiện hành với v2 và 3 superseded; 2.051/2.051 còn text. Chạy lại read-only: 2.048 khớp nguồn, 0 cập nhật cần thiết.

---

### [2026-10-19] Locator v2 và bộ đọc nội dung từ nguồn Supabase

- **File(s):** `backend/src/documents/db_chunking.py`, `backend/src/documents/db_source.py`, `backend/src/documents/source_signature.py`, `backend/src/documents/chunk_reconstruction.py`, `backend/tests/test_chunk_reconstruction.py`, `docs/embedding/source-locator-v2.md`, `history.md`.
- **Sai gì:** Locator cũ chỉ định bài/dòng nhưng thiếu cấu hình tái tạo và fingerprint nguồn; chưa có hàm dựng lại đúng nội dung chunk để đối chiếu với text đang lưu.
- **Tại sao sửa:** Người dùng chỉ chốt chuẩn hóa locator và bộ lấy nội dung từ nguồn Supabase. Bổ sung contract source-locator-v2, khoảng dòng/ký tự, cấu hình chunker và hash phiên bản mục chuẩn hóa; viết hàm SELECT nguồn và dựng lại đoạn, từ chối nguồn đổi/mất/hash sai.
- **Ảnh hưởng:** Giữ text/hash/chunk ID và các khóa locator cũ; chunk mới có thêm metadata reconstruction. Chưa cập nhật DB, chưa xóa chunk_text, chưa chuyển API search, không dùng file ngoài và không sửa retention. Hash nguồn không phải archive lịch sử; locator cũ chưa tự chuyển sang v2.
- **Kiểm chứng:** 78 test đạt. Chỉ đọc Supabase xác nhận 2.045/2.048 chunk khớp nội dung; 3 hồ sơ FPT/MBB/VCB lệch do nguồn đã bổ sung ngành. Truy vấn đích mẫu cả 5 nhóm nguồn đạt; tài chính chỉ thử trên chunk mới dựng trong bộ nhớ, chưa có chunk lưu. Chi tiết contract/giới hạn trong `docs/embedding/source-locator-v2.md`.

---

### [2026-10-16] Bổ sung hồ sơ công ty còn trống khi nhập tài chính clean

- **File(s):** `backend/scripts/import_clean_financials.py`, `history.md`.
- **Sai gì:** Công ty đã tồn tại được dùng lại ID nhưng importer bỏ qua ngành/sector đang NULL dù file clean có dữ liệu.
- **Tại sao sửa:** Bổ sung trường thiếu từ nguồn clean, không ghi đè hồ sơ đã có.
- **Ảnh hưởng:** Hàm ensure_company dùng CASE để chỉ điền NULL/chuỗi trắng ở tên, ngành, sector và sàn; giữ ID, is_active và trường có giá trị. Cờ --companies-only chỉ xử lý hồ sơ, không nhập lại tài chính hay sửa schema. Chỉ dùng 10 mã có file nguồn, không đoán ngành CTR/MSN/NLG.
- **Kiểm chứng:** 3 test importer đạt. Đã commit transaction DB bổ sung 5 ô: FPT ngành/sector, VCB ngành/sector, MBB sector. Đối chiếu toàn bộ companies xác nhận mọi giá trị có sẵn giữ nguyên; chạy lại không đổi dữ liệu. CTR/MSN/NLG còn thiếu vì không có file clean trong bộ này. Không sửa số liệu tài chính hoặc chunk/vector.

---

### [2026-10-16] Viết lại README cho thành viên clone và chạy ứng dụng

- **File(s):** `README.md`, `history.md`.
- **Sai gì:** README trộn hướng dẫn backend chung 8000 với server độc lập 8001, tài khoản mock và đường dẫn máy cá nhân; thiếu các bước tạo .venv, SDK, môi trường và xử lý lỗi sau clone.
- **Tại sao sửa:** Thành viên cần một quy trình thống nhất từ cài lần đầu đến `cd backend` / `npm run dev`, frontend localhost:5173 và tự kiểm tra API.
- **Ảnh hưởng:** Chỉ cập nhật tài liệu. Giữ phần ingest/Supabase và ghi chú Vector RAG phía dưới; không chạy server, cài thư viện hay đổi DB. Nêu rõ Google client ID backend hiện lấy từ biến môi trường terminal.

---

File này ghi lại mọi lần sửa/bổ sung code trong dự án. Mỗi mục bắt buộc có 3 phần: **Sai gì**, **Tại sao sửa**, **Ảnh hưởng**.

Quy trình bắt buộc trước khi sửa:
1. Đọc code liên quan + các nơi gọi/import đến nó (grep/search) để xác định phạm vi ảnh hưởng.
2. Đánh giá rủi ro: có breaking change với module khác không (API, schema data, biến môi trường, tên hàm/class...).
3. Thực hiện sửa.
4. Ghi lại vào file này theo template bên dưới, kèm ngày và file/dòng liên quan.

---

### [2026-10-16] Backend auth đọc thêm cấu hình .env ở gốc repo

- **File(s):** `backend/src/core/config.py`, `backend/tests/test_env_config.py`, `history.md`.
- **Sai gì:** Settings chỉ đọc `backend/.env` nhưng máy này lưu DATABASE_URL trong `.env` gốc; backend dùng database localhost mặc định và lỗi ConnectionRefusedError khi khởi động. Các script chunk/manifest đọc cả hai nên vẫn chạy được, dễ hiểu nhầm DB đã kết nối thì auth cũng chạy.
- **Tại sao sửa:** Backend cần đọc cùng cấu hình kết nối với script dữ liệu.
- **Ảnh hưởng:** Đọc `.env` gốc rồi `backend/.env` (backend ưu tiên), biến môi trường tiến trình vẫn ưu tiên cao nhất. Không sao chép hay in mật khẩu, không sửa cấu hình DB thật.
- **Kiểm chứng:** 14 test auth/cấu hình đạt; backend khởi động với Supabase, health qua Vite proxy trả 200; hai route login/register nhận request và trả 422 với body rỗng. Tạo user, xác minh mật khẩu, tạo session/JWT trên DB thật trong transaction rollback đều đạt, không giữ tài khoản thử.

---

### [2026-10-16] Bổ sung dependency backend đăng nhập Google

- **File(s):** `backend/requirements.txt`, `history.md`.
- **Sai gì:** Router auth import `google.oauth2` và `google.auth.transport` nhưng chưa khai báo `google-auth`. Python trên máy cũng chưa cài PyJWT nên backend lỗi `ModuleNotFoundError: jwt` trước khi mở API.
- **Tại sao sửa:** Backend cần đầy đủ dependency auth để khởi động; thiếu dependency Google làm hỏng cả đăng nhập email vì router được import cùng ứng dụng.
- **Ảnh hưởng:** Thêm `google-auth>=2,<3`; dùng `requests` đã có trong requirements. Không thay đổi tài khoản, mật khẩu, schema hay dữ liệu người dùng.

---

## Template

### [2026-10-16] Thêm lệnh npm chạy nhanh trong backend

- **File(s):** `backend/package.json`, `backend/scripts/run-backend.mjs`, `README.md`, `history.md`.
- **Sai gì:** Lệnh backend dài, dễ nhầm thư mục và đường dẫn Python giữa các máy.
- **Tại sao sửa:** Người dùng muốn dùng `npm run ...` sau khi clone và cài đặt.
- **Ảnh hưởng:** Theo yêu cầu người dùng, `cd backend` rồi `npm run dev` (hoặc `npm start`) dùng Python trong `.venv` gốc để chạy `src.main:app` ở 8000 với một worker. Thiếu .venv sẽ báo hướng dẫn, không dùng Python toàn máy hoặc tự cài thư viện. Không đổi API hay DB; không còn package chạy npm ở gốc.

---

### [2026-10-16] Ghép API giá/tin vào backend chính cổng 8000

- **File(s):** `backend/src/main.py`, `frontend/src/pages/companies/marketDataApi.js`, `backend/tests/test_unified_app.py`, `README.md`, `history.md`.
- **Sai gì:** Auth ở 8000 nhưng frontend gọi giá/tin mặc định sang 8001; phải mở thêm server và dễ lỗi khi quên chạy.
- **Tại sao sửa:** Người dùng yêu cầu dùng chung backend. Đăng ký market router trong main và tái dùng lifespan collector/news, đảm bảo đóng DB cả khi khởi động collector thất bại.
- **Ảnh hưởng:** Frontend mặc định gọi `/api/market-data` cùng origin, dùng proxy Vite hiện có sang 8000. Vẫn hỗ trợ URL API tường minh qua biến môi trường. Backend chung chạy một worker vì collector có khóa độc quyền; server standalone 8001 vẫn còn cho nhu cầu riêng nhưng không chạy đồng thời. Không đổi schema hay dữ liệu Supabase.
- **Kiểm chứng:** 23 test auth, vòng đời backend chung, API dữ liệu và API live đạt; frontend build thành công.

---

### [YYYY-MM-DD] Tiêu đề ngắn gọn

- **File(s):** đường dẫn file
- **Sai gì:** mô tả lỗi/thiếu sót cụ thể
- **Tại sao sửa:** lý do, nguyên nhân gốc
- **Ảnh hưởng:** những module/file/chức năng khác có thể bị ảnh hưởng (hoặc "Không ảnh hưởng gì ngoài file này")

---

### [2026-10-16] WBS16: manifest phiên bản corpus từ chunk đã ingest

- **File(s):** `backend/src/documents/corpus_manifest.py`, `backend/scripts/freeze_corpus.py`, `backend/tests/test_corpus_manifest.py`, `docs/embedding/WBS16-corpus-manifest.md`, `history.md`.
- **Sai gì:** Đã ingest toàn bộ nguồn nhưng chưa có danh sách chunk đóng băng và chưa đăng ký `corpus_versions`/`corpus_documents`; index version chỉ mô tả cấu hình, không chốt tập dữ liệu.
- **Tại sao sửa:** Cần corpus ID, hash và snapshot nội dung/locator để các thành viên đối chiếu đúng phiên bản khi test. Cùng dữ liệu tạo cùng ID; thay thành viên/nội dung/locator tạo phiên bản khác.
- **Ảnh hưởng:** Thêm CLI mặc định chỉ đọc và xuất JSON; `--apply` đăng ký hai bảng corpus trong transaction, từ chối ghi đè nhãn và file khác nội dung. Không đổi schema, chunk/vector, API, crawler hay retention. Khi chốt có khóa SHARE ngắn hạn trên documents/text_chunks. Snapshot JSON phải được giữ/bàn giao; WBS25 phải dùng chunk ID trong manifest để cô lập corpus. Chưa có bảo vệ chunk corpus khỏi retention; xem giới hạn trong tài liệu.
- **Kiểm chứng:** 85 test manifest/chunking/ingest/embedding/locator/retention đạt; xuất thật 249 tài liệu / 2.048 chunk từ Supabase, ID `7c2ea700-fd01-5adc-a467-af4fea532741`. Đã đăng ký `corpus-v1` vào Supabase; chạy lại trả `already_registered`, đối chiếu đủ 249 liên kết tài liệu và hash, không ghi thêm hay đổi phiên bản cũ. Manifest cục bộ: `backend/.tmp/corpus-v1.manifest.json`.

---

### [2026-10-16] Bỏ qua cache và báo cáo test sinh tự động

- **File(s):** `.gitignore`, `history.md`.
- **Sai gì:** Các thư mục `pytest-cache-files-*` do pytest tạo xuất hiện trong workspace và làm `git status` báo lỗi quyền truy cập khi quét file tạm.
- **Tại sao sửa:** Cache và báo cáo coverage chỉ phục vụ máy chạy test, không cần đưa lên Git.
- **Ảnh hưởng:** Thêm quy tắc ignore cho cache pytest và file coverage. `.env`, virtualenv và `backend/.tmp/` đã được ignore từ trước; không thay đổi các file đang được Git theo dõi.

---

### [2026-10-16] WBS17: đối chiếu full corpus Supabase với pgvector

- **File(s):** `backend/src/documents/db_ingest.py`, `backend/tests/test_db_ingest.py`, `docs/embedding/WBS17-ingest-2026-10-16.md`, `history.md`.
- **Sai gì:** Sau WBS12, pgvector mới có tập nghiệm thu hai tài liệu; chưa có đối chiếu theo toàn bộ nguồn Supabase và log số chunk hợp lệ/thiếu theo từng loại.
- **Tại sao sửa:** WBS17 cần thấy corpus hiện có được lưu đủ vector và metadata đúng index, đúng tài liệu, truy lại được nguồn; lần chạy lại phải có log hoàn tất và không tính lại embedding cho nội dung đã lưu.
- **Ảnh hưởng:** Ingest giờ bỏ qua embedding khi toàn bộ hash hiện hành của tài liệu khớp, vẫn cập nhật locator; nếu DB đổi giữa bước kiểm tra và ghi thì từ chối vector placeholder trước khi sửa chunk. Không đổi API hay schema live. Đã cập nhật 6 hồ sơ công ty, bổ sung giá và chỉ số còn thiếu; 234 bài tin đã được nhóm nạp trước đó. Lệnh `--apply` full chạy xong **249/249 tài liệu, 2.048 chunk đầu vào, 0 lỗi**. Đối chiếu DB: 2.048/2.048 chunk hiện hành khớp, 0 sai lệch, 0 trùng vị trí, 0 vector/locator không hợp lệ; chạy lại giữ nguyên ID và `created_at`. Truy vấn pgvector bằng vector FPT trả đúng chunk FPT với khoảng cách 0; 63 test liên quan đạt. `observations` vẫn rỗng nên chưa có chunk tài chính.

---

### [2026-10-15] Đồng bộ file reset schema với contract chunk hiện tại và cập nhật 6 hồ sơ công ty

- **File(s):** `supabase/reset_and_rebuild.sql`, `history.md`.
- **Sai gì:** File reset còn tạo `text_chunks` thiếu `locator_json`, `superseded_at`, `superseded_by_chunk_id` và dùng chỉ mục unique đầy đủ cũ. Nếu dựng một database mới chỉ bằng file này, code ingest hiện tại sẽ lỗi hoặc không giữ được chunk cũ cùng vị trí. Supabase đang lưu locator FPT theo khóa nhãn tiếng Việt cũ.
- **Tại sao sửa:** Schema dựng mới cần tương thích các migration `20261014000200`/`20261014000300`; 6 hồ sơ công ty cần khóa locator dạng `MÃ:tên_cột` để bộ resolver WBS11 truy về nguồn.
- **Ảnh hưởng:** Chỉ sửa file reset; **không chạy file reset trên Supabase dùng chung**. Đã chạy ingest từ bảng `companies` trên Supabase cho CTR, FPT, MBB, MSN, NLG, VCB: 6/6 tài liệu/chunk thành công, vector 1024 chiều, locator đúng khóa cột. FPT giữ nguyên `chunk_id`, nội dung, `created_at` và vector; 5 công ty còn lại là chunk mới. Phần full-load WBS17 được ghi riêng ở mục ngày 16/10.

---

### [2026-10-15] Ngày trong tiêu đề chunk tin tức tính theo giờ Việt Nam (UTC+7), không theo UTC

- **File(s) sửa:** `backend/src/documents/db_chunking.py`, `backend/tests/test_db_chunking_sources.py`, `history.md`
- **Sai gì / Thiếu gì:** Ngày của tin lấy `published_at.date()` theo UTC, nên tin đăng sau 17:00 UTC (tức sáng hôm sau ở Việt Nam) bị ghi lùi một ngày trong tiêu đề chunk. Khoảng 15% tin lệch so với `chunks_thu.json`.
- **Tại sao sửa:** Leader/nhóm chốt dùng giờ Việt Nam. Người dùng hỏi theo ngày Việt Nam, và đây là ngày hiển thị trên báo.
- **Ảnh hưởng:**
  - Tin có `published_at` kèm múi giờ được đổi sang UTC+7 (offset cố định, VN không có giờ mùa hè) trước khi lấy ngày; dữ liệu không kèm múi giờ giữ nguyên.
  - Chữ tiêu đề đổi ở các tin lệch ngày, nên `content_hash` và `chunk_id` của các chunk đó đổi. Theo phương án B, chunk cũ được giữ và đánh dấu thay thế (tin tức không bị retention xoá); các tin còn lại không đổi.
  - Cần chạy lại ingest tin tức để DB cập nhật; chunk bị đổi sẽ phải nhúng lại.
  - Test: 153 pass, 1 lỗi có sẵn ở `test_json_ingest`.

---

### [2026-10-15] WBS11 bước 3: script kiểm tra locator `verify_locators.py` và sửa so sánh ngày trong bộ giải

- **File(s):** `backend/scripts/verify_locators.py` (mới), `backend/src/documents/locator_resolver.py` (sửa), `backend/tests/test_locator_resolver.py`, `history.md`
- **Sai gì / Thiếu gì:** Chưa có cách chạy kiểm tra locator trên dữ liệu thật. Khi chạy lần đầu trên Supabase, bộ giải lỗi vì asyncpg không nhận chuỗi cho `$2::date`.
- **Tại sao sửa:** WBS11 cần báo cáo ~20 chunk mẫu. Sửa so sánh thành `trade_date::text = $2` nên không phụ thuộc kiểu tham số.
- **Ảnh hưởng:**
  - Script chỉ đọc DB (SELECT), không ghi. Dùng: `py -X utf8 backend/scripts/verify_locators.py --chunks <file chunk> [--per-table N] [--report file.md]`.
  - Kết quả mẫu 4 chunk mỗi bảng: giá 4/4, chỉ số 4/4, tin tức 4/4, hồ sơ công ty 4/4 (sau khi chunk lại với khoá mới; file `tat_ca_chunks.json` cũ vẫn mang khoá cũ nên 0/4).
  - Báo cáo tài chính chưa kiểm tra được vì bảng `observations` đang rỗng.
  - Tin tức mới kiểm tra bài/url tồn tại, chưa so được từng đoạn `pN`.
  - Test: 15 test locator pass.

---

### [2026-10-15] WBS11 bước 2: bộ giải locator (từ chunk tìm lại dòng nguồn và kiểm tra)

- **File(s) thêm:** `backend/src/documents/locator_resolver.py`, `backend/tests/test_locator_resolver.py` (file mới, không sửa file nào có sẵn), `history.md`
- **Sai gì / Thiếu gì:** Locator có `source_table`, `source_id`, `row_keys` nhưng chưa có code nào biến chúng thành truy vấn tìm dòng nguồn, cũng chưa có cách kiểm tra chunk khớp nguồn.
- **Tại sao sửa:** WBS11 yêu cầu mỗi chunk truy ngược được về dòng nguồn để dùng làm trích dẫn (evidence).
- **Ảnh hưởng:**
  - `resolve_locator` trả về các truy vấn chỉ đọc (observations, news_articles, price_bars, market_index_bars, companies); `verify_chunk` chạy chúng và báo lỗi nếu thiếu dòng hoặc chữ chunk không nhắc tới ngày/mã/giá trị của dòng đó.
  - Không ghi DB, không đổi schema, không đổi chunk_id. Chưa có script nào gọi module này (bước 3).
  - Test: 14 test mới pass.

---

### [2026-10-15] WBS11 bước 1: khoá dòng của hồ sơ doanh nghiệp trỏ tới đúng cột trong bảng companies

- **File(s) sửa:** `backend/src/documents/db_chunking.py`, `backend/tests/test_db_chunking_sources.py`, `history.md`
- **Sai gì / Thiếu gì:** Khoá dòng của hồ sơ doanh nghiệp là `<mã>:<nhãn tiếng Việt>` (ví dụ `FPT:Sàn niêm yết`), không tra ngược được về cột nguồn.
- **Tại sao sửa:** WBS11 cần locator của mỗi chunk resolve được về đúng dòng/cột nguồn. Khoá mới là `<mã>:<tên cột>` (ví dụ `FPT:exchange`).
- **Ảnh hưởng:**
  - Chỉ đổi `row_keys` trong locator. Chữ chunk, `content_hash`, `chunk_id` không đổi, không phải nhúng lại.
  - Chunk hồ sơ doanh nghiệp đã có trên DB sẽ được làm mới `locator_json` ở lần ingest sau (cơ chế làm mới locator đã thêm cùng ngày).
  - Khoá dòng giá (`price_id`), chỉ số (`<mã>:<ngày>`) và tin (`p1`, `p2`) giữ nguyên vì đã tra được; dòng tổng kết tháng `<mã>:<YYYY-MM>:summary` giữ nguyên và sẽ được resolver hiểu là "cả tháng".
  - Test: 137 test pass, 1 lỗi có sẵn từ trước ở `test_json_ingest`, không liên quan.

---

### [2026-10-15] Thêm "loại tin" vào locator của chunk tin tức và làm mới locator khi nội dung không đổi

- **File(s) sửa:** `backend/src/documents/db_chunking.py`, `backend/src/documents/db_ingest.py`, `backend/tests/test_db_ingest.py`, `history.md`
- **Sai gì / Thiếu gì:**
  1. Chunk tin tức chưa có thông tin loại tin (công bố chính thức, kết quả kinh doanh, chiến lược, diễn biến giá, bình luận), nên truy xuất không lọc/ưu tiên được nguồn đáng tin.
  2. `write_chunks` bỏ qua chunk có nội dung không đổi, nên metadata nằm ngoài chữ (locator_json) không bao giờ được cập nhật cho chunk cũ.
- **Tại sao sửa:** Leader/nhóm đồng ý thêm loại tin. Đặt trong `locator` (không đổi chữ chunk) nên `chunk_id` và vector không đổi, không cần nhúng lại.
- **Ảnh hưởng:**
  - Locator tin tức có thêm `news_type`, `news_priority` (1 = công bố chính thức … 5 = bình luận), `classifier` (`news-type-v1`). Phân loại theo luật từ tiêu đề, không dùng mô hình.
  - Chạy lại ingest sẽ chỉ `UPDATE locator_json` cho chunk cũ, không chèn chunk mới, không đánh dấu thay thế, không nhúng lại.
  - Chữ chunk và `chunk_id` không đổi (có test). Nhân (WBS12) cần biết vì `db_ingest.py` có thêm một lệnh UPDATE.
  - Test: 50 test liên quan pass.

---

### [2026-10-15] Chính sách dọn chunk giá và chỉ số đã bị thay thế sau 30 ngày (chống phình dữ liệu của phương án B)

- **File(s) mới:** `backend/src/documents/retention.py`, `backend/scripts/cleanup_superseded_chunks.py`, `backend/tests/test_retention.py`
- **Thiếu gì:** Phương án B giữ lại chunk cũ mỗi khi nội dung chunk đổi. Với **giá và chỉ số**, mỗi ngày giao dịch có vài chunk của tháng hiện tại đổi nội dung (dòng "Tổng kết tháng" và dòng ngày mới), nên chunk cũ tích tụ đều đặn. Ước tính (chưa đo trên database thật): mỗi chunk ~6 đến 10 KB gồm cả vector 4 KB và chỉ mục; giữ lại cho 6 mã khoảng 3.000 hàng mỗi năm, nếu mở rộng 100 mã thì khoảng 50.000 hàng mỗi năm (~400 MB), trong khi gói Supabase Free giới hạn 500 MB.
- **Tại sao thêm:** Leader/nhóm chốt: chunk giá và chỉ số bị thay thế được xóa định kỳ sau 30 ngày. Tin tức và báo cáo tài chính ít khi đổi và là nguồn trích dẫn nên giữ nguyên.
- **Chính sách:**
  | Loại tài liệu (`documents.doc_type`) | Chunk đã bị thay thế |
  |---|---|
  | `PRICE_HISTORY` (giá cổ phiếu), `MARKET_INDEX` (chỉ số) | **Xóa sau 30 ngày** |
  | `NEWS`, `FINANCIAL_STATEMENT`, `COMPANY_PROFILE` | **Không bao giờ xóa** (code từ chối nếu truyền vào) |
  | Mọi loại, nếu còn bị `evidence` trỏ tới | **Không xóa** (giữ trích dẫn hợp lệ) |
  Điều kiện đầy đủ: `superseded_at` có giá trị, cũ hơn N ngày, thuộc loại cho phép, không có dòng `evidence` nào trỏ tới `chunk_id`.
- **Cách chạy (từ thư mục gốc `FinMind`, cần `DATABASE_URL`):**
  ```powershell
  py -X utf8 backend/scripts/cleanup_superseded_chunks.py            # chỉ báo cáo, KHÔNG xóa (mặc định)
  py -X utf8 backend/scripts/cleanup_superseded_chunks.py --apply    # xóa thật
  py -X utf8 backend/scripts/cleanup_superseded_chunks.py --days 60 --apply
  ```
  In ra số chunk và dung lượng ước tính theo từng loại. Nên đặt lịch chạy mỗi ngày bằng Windows Task Scheduler (hoặc `pg_cron` của Supabase), **sau khi** đã áp dụng migration `20261014000300`. Script tự kiểm tra cột `superseded_at` có tồn tại, thiếu thì dừng và báo.
- **Ảnh hưởng:**
  - Chỉ **thêm file mới**, không đổi code đang chạy; chưa có gì tự động xóa vì mặc định là chạy thử và chưa đặt lịch.
  - Chỉ xóa hàng trong `text_chunks` (vector và chữ của chunk cũ). Không đụng `documents`, `index_versions`, `evidence`, bảng nguồn.
  - Chunk giá cũ bị xóa nghĩa là **không truy ngược được nội dung giá của một ngày cũ từ chunk đó**; nếu câu trả lời cũ đã trích dẫn nó thì chunk được giữ (điều kiện `evidence`).
  - Dung lượng mỗi ngày dọn được tính theo `pg_column_size(embedding) + length(chunk_text)`, chưa tính chỉ mục.
  - `ON DELETE`: `superseded_by_chunk_id` không có khóa ngoại nên xóa chunk cũ không ảnh hưởng chunk thay thế.
- **Kiểm chứng:** 42 test đạt (test mới: chạy thử không xóa; xóa đúng tham số; từ chối loại được bảo vệ; số ngày phải >= 1; SQL luôn có điều kiện `superseded_at`, tuổi và `NOT EXISTS evidence`). **Chưa chạy trên database thật.**
- **Giới hạn / việc còn lại:** chưa đặt lịch tự động; chưa đo dung lượng thật của Supabase (`pg_database_size`); chưa có chính sách cho tin tức nếu cần dọn sau này.

---

### [2026-10-15] WBS12: nghiệm thu vector và metadata trên hai tài liệu FPT thật

- **File(s):** `docs/embedding/WBS12-acceptance-2026-10-15.md`, `docs/embedding/WBS12-pgvector.md`, `backend/scripts/chunk_from_supabase.py`, `backend/src/documents/db_ingest.py`.
- **Sai gì:** Hướng dẫn WBS12 chưa phản ánh migration supersede mới; SQL ví dụ chưa lọc chunk đã bị thay. CLI ghi "Đã ghi N chunk" cả khi chạy lại không chèn hàng mới, dễ nhầm số chunk xử lý với số hàng được thêm. Trước đó mới kiểm chứng một hồ sơ FPT, chưa có biên bản nghiệm thu tập nhiều chunk với phạm vi cố định.
- **Tại sao sửa:** Task yêu cầu chứng minh vector 1024 chiều, metadata truy ngược đúng tài liệu/index, chạy lại không trùng, quy tắc supersede và số liệu đầu vào/thành công/lỗi trên Supabase thật. Sửa nhãn log cho đúng ý nghĩa, cập nhật hướng dẫn và lưu biên bản đối chiếu để nhóm review.
- **Ảnh hưởng:** Không đổi schema hay hành vi ghi; chỉ sửa nhãn CLI và tài liệu. Tập nghiệm thu từ Supabase gồm hồ sơ FPT (1 chunk) và lịch sử giá FPT (34 chunk), cùng index `1e029e66-0adf-53ac-8f28-431ed7312745`. Hai lần chạy: 35/35 chunk xử lý thành công, 0 lỗi, DB có 35 chunk hiện hành đúng phạm vi; `chunk_id` và `created_at` không đổi. Phép thử supersede trên DB thật dùng transaction rollback nên không để lại bản ghi thử. Full-load là bước riêng; manifest/cô lập corpus thuộc WBS16.

---

### [2026-10-14] Giữ nguyên chunk_id khi nội dung đổi: chunk cũ bị "thay thế" thay vì bị ghi đè (quyết định của leader, phương án B)

- **File(s) mới:** `supabase/migrations/20261014000300_text_chunks_supersede.sql`
- **File(s) sửa:** `backend/src/documents/db_ingest.py` (hàm `write_chunks`), `backend/src/documents/repository.py` (3 câu SQL), `backend/tests/test_db_ingest.py`
- **Sai gì:** Khi nạp lại tài liệu mà nội dung chunk đã đổi, câu `ON CONFLICT ... DO UPDATE SET chunk_id = EXCLUDED.chunk_id` đổi luôn **khóa chính** `chunk_id` của hàng cũ. Bảng `evidence` có khóa ngoại `chunk_id` → `text_chunks`, nên:
  1. khi đã có trích dẫn, lần nạp lại bị database từ chối (vi phạm khóa ngoại) và tài liệu đó không cập nhật được;
  2. nếu cho đổi được, trích dẫn cũ sẽ trỏ vào nội dung khác với nội dung đã trích.
  Ngoài ra khi một vị trí chunk không còn tồn tại, code `DELETE` chunk đó (cũng bị chặn bởi khóa ngoại nếu có trích dẫn).
- **Tại sao sửa:** Leader chốt phương án B: **không đổi chunk cũ, tạo chunk mới khi nội dung đổi**. Như vậy một trích dẫn luôn trỏ đúng đoạn văn bản tại thời điểm nó được trích, và vẫn truy vết được lịch sử nội dung.
- **Cách hoạt động mới (mỗi tài liệu, trong một transaction):**
  | Tình huống | Xử lý |
  |---|---|
  | Cùng vị trí, cùng `content_hash` | Không ghi gì |
  | Cùng vị trí, nội dung đổi | Chunk cũ gán `superseded_at` và `superseded_by_chunk_id`; **chèn chunk mới** với `chunk_id` mới |
  | Vị trí không còn nữa | Chunk cũ gán `superseded_at` (không xóa) |
  | Nội dung quay về bản cũ | Hồi sinh chunk đã bị thay có cùng `chunk_id` (bỏ `superseded_at`) thay vì chèn trùng khóa chính |
- **Thay đổi schema (migration `20261014000300`):** thêm `superseded_at timestamptz` và `superseded_by_chunk_id uuid`; **bỏ** chỉ mục duy nhất `uq_text_chunks_index_document_chunk` (áp dụng cho mọi hàng) và thay bằng chỉ mục duy nhất **một phần** `uq_text_chunks_current_position` trên `(index_version_id, document_id, chunk_index) WHERE superseded_at IS NULL`, để chunk cũ và chunk mới cùng vị trí tồn tại song song.
- **Ảnh hưởng:**
  - **Thứ tự bắt buộc: chạy migration `20261014000300` TRƯỚC khi chạy hoặc deploy code mới.** Code mới tham chiếu cột `superseded_at`; thiếu cột thì `repository.py` và `db_ingest.py` báo lỗi. Migration chưa được áp dụng lên Supabase PRODUCTION ở thời điểm ghi mục này.
  - **Mọi truy vấn ĐỌC `text_chunks` phải lọc `superseded_at IS NULL`** để không trả chunk đã bị thay. Đã thêm bộ lọc vào `repository.get_chunks` và `repository.vector_search`; **các truy vấn mới viết sau này (WBS15, WBS25 của Nhân) phải tự thêm điều kiện này**.
  - `repository.insert_chunks` (luồng upload PDF/JSON): `ON CONFLICT` thêm `WHERE superseded_at IS NULL` để khớp chỉ mục một phần; hành vi cập nhật tại chỗ giữ nguyên.
  - `evidence.chunk_id` vẫn là khóa ngoại tới `text_chunks`; chunk cũ được giữ nên trích dẫn cũ luôn hợp lệ.
  - **`supabase/reset_and_rebuild.sql` và migration gốc `20260929...` vẫn tạo chỉ mục duy nhất đầy đủ**; sau khi dựng lại database phải chạy tiếp migration `20261014000200` rồi `20261014000300`.
  - Dung lượng: mỗi lần nội dung đổi giữ thêm một hàng (chữ + vector 4 KB). Với quy mô vài nghìn chunk không đáng kể; cần chính sách dọn chunk cũ nếu nội dung đổi liên tục.
  - `--apply` vẫn thuộc WBS12 của Nhân và vẫn khóa bằng `--confirmed-with-nhan`.
- **Kiểm chứng:** test nhóm chia chunk, embedding, ghi database, API tìm kiếm và upload JSON: 58 đạt; toàn bộ `backend/tests` từ thư mục gốc: **116 đạt, 1 lỗi có từ trước** (`test_json_ingest::test_financial_json_to_pages_statement_drops_none_values`, kỳ vọng mã chữ thường, đã ghi ở mục 2026-09-27, không liên quan). Test mới: không ghi gì khi không đổi; chunk đổi thì bị thay và chèn mới (không dùng lại `chunk_id` cũ, không có lệnh `SET chunk_id` hay `DELETE`); vị trí biến mất thì bị thay không bị xóa; nội dung quay về thì hồi sinh. **Chưa chạy trên database thật.**

---

### [2026-10-14] WBS12: lưu vector và locator nguồn vào Supabase pgvector

- **File(s):** `supabase/migrations/20261014000200_pgvector_chunk_metadata.sql`, `backend/src/documents/db_ingest.py`, `backend/scripts/chunk_from_supabase.py`, `backend/tests/test_db_ingest.py`, `docs/embedding/WBS12-pgvector.md`.
- **Sai gì:** Supabase đang thiếu khóa duy nhất `(index_version_id, document_id, chunk_index)` mặc dù code `ON CONFLICT` dùng khóa này; `embedding` vẫn nullable; `text_chunks` không có chỗ lưu `DbChunk.locator`. Lệnh `--apply` trước đây có thể báo thành công dù một nguồn đọc lỗi hoặc tài liệu ghi lỗi, và lần upsert cập nhật lại `created_at`.
- **Tại sao sửa:** Cần lưu vector 1024 chiều cùng nguồn chính xác, ghi lại an toàn và xác minh được. Migration khôi phục các khóa/ràng buộc đã có trong schema gốc, thêm `locator_json` cho row keys, đồng thời làm lệnh ghi báo lỗi rõ ràng.
- **Ảnh hưởng:** `text_chunks` thêm cột `locator_json` (nullable cho luồng upload cũ); vector, document ID, index version ID và chunk index được yêu cầu không NULL. Tạo chỉ mục unique cho vị trí chunk và `documents.sha256`. `db_ingest.py` ghi locator JSON và giữ nguyên `created_at` khi rerun; `--apply` thoát mã lỗi nếu nguồn hoặc tài liệu lỗi. API upload cũ vẫn có thể bỏ trống locator. Không đổi crawler, chunker, model, frontend hoặc Neo4j.
- **Kiểm chứng:** 35 test liên quan đạt. Migration đã áp dụng trên Supabase; trước khi ghi, `documents`, `text_chunks`, `index_versions` đều 0 dòng. Ghi thật một hồ sơ FPT cho 1 tài liệu, 1 chunk, 1 index version; vector 1024 chiều, norm gần 1, locator có `source_table=companies`, source ID và `row_keys`; truy vấn pgvector trả đúng chunk. Chạy lại cùng lệnh vẫn 1/1/1, `chunk_id` và `created_at` không đổi.
- **Giới hạn:** WBS12 mới kiểm chứng một tài liệu hoàn chỉnh, chưa ingest toàn bộ 1.950 chunk (WBS17). API search cũ dùng `word-window-v1` nên chưa thấy index `db-v1` (WBS25).

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
# 2026-10-19: Bỏ cột text_chunks.chunk_text theo xác nhận của người dùng

- Người dùng chấp nhận mất khả năng đọc lại 3 chunk lịch sử FPT/MBB/VCB thuộc corpus-v1.
- Đã áp dụng migration 20261019000100_drop_chunk_text.sql; bỏ cột và constraint liên quan, không xóa dòng chunk/vector.
- Đối chiếu nguồn chính xác cho 2.048 chunk hiện hành trước migration; fingerprint các trường còn lại của toàn bộ 2.051 dòng giữ nguyên sau migration.
- Bộ đọc/ghi, manifest, retention, script backfill, schema rebuild và ERD đồng bộ với việc bỏ cột.
- Upload mới dùng bản nguồn PDF/JSON gốc trong raw_payloads hiện có; locator upload-source-v1; không thêm bảng, không lưu text chunk trùng lặp.
- 80 test đạt; đọc mẫu nguồn của 4 nhóm sau DROP COLUMN thành công. Không khởi động server, không commit/push.
- Các máy chạy backend cần cập nhật code và restart vì schema không tương thích code cũ còn dùng chunk_text.

---

### [2026-10-20] WBS19: sửa năm lỗi chunker tài chính và kiểm tra dữ liệu cào mới

- **Vấn đề và thay đổi:**
  1. Tiêu đề tài chính không còn tự gán mọi giá trị là triệu VND.
  2. Từng dòng có đơn vị trống hoặc SOURCE_NATIVE ghi “đơn vị chưa xác minh”; không tự quy đổi số.
  3. Cùng report_id nhưng period_code khác nhau: báo lỗi rõ kỳ và báo cáo, không dựng chunk.
  4. Cùng report_id nhưng symbol khác nhau: báo lỗi rõ hai mã công ty, không dựng chunk.
  5. observation_id trùng trong đầu vào, kể cả giữa nhóm/báo cáo: báo lỗi; không tự bỏ dòng, cộng số hoặc tạo tham chiếu mơ hồ.
- **File chính:** backend/src/documents/db_chunking.py, db_source.py, chunk_reconstruction.py;
  backend/tests/test_clean_financial_chunk_edge_cases.py, test_chunk_reconstruction.py.
- **Tương thích:** chunk tài chính mới dùng db-financial-v3; giữ bộ dựng db-v1 và db-financial-v2 để đọc chunk đã lưu theo phiên bản locator. Chỉnh cách ghi đơn vị làm thay đổi chữ/hash/ID và cách đóng gói chunk mới, không tự cập nhật vector cũ.
- **Collector:** collect_financial_data.py bị thụt lề dư bốn khoảng trắng trên toàn module, gây IndentationError từ dòng 1. Đã bỏ lớp thụt lề dư; không thay logic API/retry/chuẩn hóa/ghi file. CLI run_financial_pipeline.py --help chạy được.
- **Công cụ kiểm tra:** backend/scripts/check_financial_flow.py kiểm tra dữ liệu đã có và đọc Supabase; check_new_financial_flow.py cào mới vào thư mục thử riêng rồi chạy clean, bộ đọc nhập và chunk. Cả hai không ghi database hoặc gọi embedding.
- **Dữ liệu đang có:** 10 công ty, 419 báo cáo, 72.096 observations trên Supabase; đọc bằng READ ONLY REPEATABLE READ, tạo 13.003 chunk trong bộ nhớ. Đủ mã dòng, không lặp ID, dựng lại đúng nội dung/hash; không chunk trên 130 từ.
- **Dữ liệu vừa cào:** Entrade/Vietcap, 20/10/2026 08:41 UTC; 10/10 công ty đạt, hợp 429 kỳ/báo cáo, 72.524 giá trị tài chính giữ sau clean, 13.126 chunk. Không mất/lặp dòng, toàn bộ chunk dựng lại đúng hash, không chunk trên 130 từ. Đây là kiểm tra chức năng, chưa xác minh đơn vị/phương pháp của nhà cung cấp.
- **Giá nguồn:** 21.298 phiên hợp lệ; bộ chuẩn hóa hiện có loại 18 bản ghi trùng ngày hoặc OHLC không hợp lệ và ghi cảnh báo. Không tự điền các kỳ tài chính nguồn không trả.
- **Kiểm thử:** bộ backend liên quan 90 passed; FinancialCleaner 15 passed, 1 failed vì thiếu .agent-state/source-hashes.json, nên chưa chứng minh được tính bất biến so với baseline lịch sử. Không tạo baseline mới để giả làm bằng chứng cũ.
- **Ảnh hưởng:** dữ liệu cào thử nằm riêng tại backend/.tmp/new-financial-flow/20261020T084108964907Z/. Không ghi đè data/raw, data/normalized hoặc bộ clean chuẩn; không INSERT/UPDATE/DELETE Supabase, không đổi schema, không tạo embedding hoặc kiểm tra tìm kiếm bằng dữ liệu mới. Chưa kiểm tra INSERT thực tế của lượt cào mới.
- **Báo cáo:** docs/embedding/WBS19-clean-chunker-test-20261020.md,
  financial-flow-check-20261020.md và financial-flow-fresh-data-20261020.md.

### [2026-10-20] Bàn giao corpus-v1 cho WBS20 và đối chiếu danh mục chỉ tiêu

- Manifest gốc backend/.tmp/corpus-v1.manifest.json còn nguyên: 249 tài liệu, 2.048 chunk, chunker db-v1, index_version_id 1e029e66-0adf-53ac-8f28-431ed7312745, manifest_sha256 e9391c8af33b64888ea7b7c386a526110c35aab7fc2c469366e648f41c393f41. Không tạo lại bằng chunker mới.
- Làm rõ ghi chú ngày 19/10: ba chunk hồ sơ cũ FPT/MBB/VCB không dựng lại được từ nguồn sống đã đổi, nhưng nội dung cũ vẫn có trong manifest đóng băng. Khi benchmark giữ đúng membership; không tự loại ba chunk chỉ vì superseded. Cần xác nhận vector cũ của đủ 2.048 ID truy vấn được trước khi đo WBS20; manifest không chứa vector.
- Đã hướng dẫn người dùng add manifest bằng git add -f vì thư mục .tmp bị ignore. Ảnh git show do người dùng gửi xác nhận commit a5d8b5a trên task_3 chứa manifest và các file WBS19/collector; chưa xác nhận commit đó đã lên nhánh remote đích.
- Bảng nối danh mục cục bộ: 234/348 mã đã nối tên/định nghĩa theo bộ tiêu chí người dùng cung cấp; 35 mã chưa được giữ, 79 mã còn cần xác minh phạm vi/công thức hoặc mục tương đương. Lượt rà 134 mã bổ sung 41 cách nối; không tự thay quyết định Excel, không chứng nhận đơn vị hay cho phép quy đổi số API.
- Code đối chiếu danh mục và báo cáo còn riêng, không đồng nghĩa đã nằm trong commit WBS19. Không sửa Supabase, formatter hoặc vector để áp dụng bảng nối này.

### [2026-10-20] Chuẩn bị corpus-v2, giữ nguyên corpus-v1

- Theo yêu cầu tạo corpus-v2, thêm prepare_corpus_v2.py và kiểm tra bằng test_prepare_corpus_v2.py (2 passed).
- Đã đóng băng nội dung từ năm bộ đọc nguồn Supabase trong transaction chỉ đọc: 675 tài liệu, 15.058 chunk; gồm 419 báo cáo tài chính/13.003 chunk, 234 tin/1.750 chunk, 6 lịch sử giá/204 chunk, 13 hồ sơ/13 chunk, 3 chỉ số/88 chunk.
- File backend/.tmp/corpus-v2.content.manifest.json; canonical manifest_sha256: 86e880eef3b39ddf2515951252025a8f58e700f80416ba24d6fabfe324362bd7. Đủ mã dòng, ID chunk không trùng và dựng lại đúng nội dung/hash cho toàn bộ chunk. Hash toàn file corpus-v1 trước/sau giữ nguyên.
- Đây là CONTENT_FROZEN_AWAITING_VECTOR_INGEST, không phải manifest corpus đã đăng ký/vector-ready. Không ghi DB, không chạy embedding. Chưa bao gồm file UPCOMINDEX cục bộ hoặc dữ liệu mới cào chưa nhập nguồn Supabase.
- Phải tạo index riêng và xử lý versioning ingest/search trước khi ghi chunk financial v3; không tái dùng index corpus-v1 hoặc nhầm source_chunk_id với khóa text_chunks. Chi tiết tại docs/embedding/corpus-v2-handoff.md.

### [2026-10-22] Thử retrieval theo corpus-v2 đã đăng ký

- **Sai gì:** API `/api/search/filtered` và audit Golden v6 trước đây chỉ chọn `index_version_id`; cùng một index có thể gắn nhiều corpus, nên chưa chứng minh kết quả nằm trong corpus-v2 cụ thể.
- **Tại sao sửa:** Thêm `corpus_version_id` cho API và audit, tra index của corpus `FROZEN`/`ACTIVE` trong DB và giới hạn tìm kiếm bằng `corpus_documents.document_id` cùng `document_hash`. Có test cho phạm vi corpus và các ID không hợp lệ.
- **Ảnh hưởng:** Chỉ thay truy vấn đọc và hướng dẫn test; không ghi DB, không sửa vector. Luồng chọn index cũ vẫn dùng được. Kiểm tra nguồn/hash khi dựng lại chunk vẫn giữ nguyên, nên dữ liệu nguồn đã đổi vẫn có thể trả `SOURCE_CHANGED`.
- **Kiểm tra:** 16 test API/repository/Golden qua; audit DB thật ở chế độ read-only trên corpus ID `232fbd29-355f-5a77-ba28-a06b8d5ceb40` chạy đủ 40 câu. Q01–Q10 có hit và dựng nguồn được; Q31–Q38 có hit nhưng mọi hit thử đều lỗi dựng nguồn. Các câu còn lại không được chấm bởi nhánh vector. Không khẳng định bộ Golden đã đạt.
- **HTTP thật:** Q03 qua `/api/search/filtered` trả 200/5 hit theo corpus ID mới; Q31 trả 409 `SOURCE_CHANGED`. Không thay đổi database khi thử.

### [2026-10-22] Thêm preview SOURCE_CHANGED cho thử nghiệm retrieval

- **Sai gì:** Khi nguồn tài chính thay tên hiển thị sau khi lập chỉ mục, `/api/search/filtered` trả 409; người kiểm thử không xem được những đoạn nguồn hiện tại mà 5 vector đã tìm tới.
- **Tại sao sửa:** Thêm cờ `preview_source_changed` mặc định `false`, yêu cầu `corpus_version_id`. Chỉ khi kiểm tra nghiêm ngặt gặp `SOURCE_CHANGED`, backend dựng chữ hiện tại theo locator và `row_keys`, rồi trả `source_verified=false` cùng mã cảnh báo; sai định danh hoặc locator vẫn bị chặn.
- **Ảnh hưởng:** Chỉ endpoint filtered-search có chế độ xem trước; không thay đổi dữ liệu, embedding hay kiểm tra mặc định. Chữ preview chưa xác minh với vector cũ nên không dùng làm bằng chứng hoặc đáp án chính thức. 49 test liên quan qua; HTTP Q31 thử bật cờ trả 200/5 hit đều chưa xác minh, tắt cờ trả 409.

### [2026-10-22] WBS30 — log timing và lỗi filtered vector retrieval

- **Sai gì:** `/api/search/filtered` trả kết quả hoặc lỗi nhưng chưa để lại trace có thời gian embedding/truy vấn, số hit, điểm và mã lỗi; ca 0 hit dễ bị hiểu nhầm là lỗi.
- **Tại sao sửa:** Ghi một JSONL trace mỗi lần endpoint chạy, gồm `trace_id`, UTC, phạm vi lọc đã giới hạn, index/corpus ID, timing, số hit và `{chunk_id, score}` hoặc mã lỗi. Không lưu câu hỏi, nội dung chunk, locator, secret hoặc exception message.
- **Ảnh hưởng:** Log ở console và `backend/.tmp/retrieval-traces.jsonl` (đã ignore); không ghi Supabase, không đổi response hay logic chunk. Chỉ áp dụng cho filtered vector endpoint. File local cần được quản lý dung lượng khi vận hành dài hạn.
- **Kiểm chứng:** Test helper/API và HTTP thật trên Q03 có 5 hit, lọc `NOPE` trả 0 hit, Q31 trả 409 `SOURCE_CHANGED`; cả ba có trace, và không thấy câu hỏi hoặc chunk text trong JSONL. Chi tiết: `docs/embedding/WBS30-retrieval-trace.md`.

### [2026-10-22] Bổ sung số hit trước khi xác minh nguồn cho WBS30

- **Sai gì:** Khi SQL đã tìm được chunk nhưng dựng lại nguồn báo `SOURCE_CHANGED`, trace cũ ghi `hit_count: null` và không có điểm, gây nhầm với lỗi chưa chạy tìm kiếm.
- **Tại sao sửa:** Repository chuyển riêng `{chunk_id, score}` của các hàng SQL đã xếp hạng cho trace trước bước kiểm tra nguồn. Trace phân biệt `hit_count` (SQL tìm được) với `returned_hit_count` (API trả thành công); lỗi trước SQL vẫn có `hit_count: null`.
- **Ảnh hưởng:** Chỉ thêm dữ liệu chẩn đoán vào log local/console của `/api/search/filtered`; không đổi kết quả API, dữ liệu nguồn hay Supabase. Trace không chứa câu hỏi, nội dung chunk hoặc thông tin kết nối.
- **Kiểm chứng:** 28 test liên quan API, repository và trace qua. Thử đường đi SQL → kiểm tra nguồn → trace trên DB thật bằng vector đã lưu trong index (không tải model): HTTP 409, SQL tìm 5 hit/5 điểm, không có kết quả trả, `SOURCE_CHANGED`. Đây không phải phép đo chất lượng embedding theo câu hỏi.

### [2026-10-27] Làm lại nguồn News FireAnt cho 10 mã

- Crawler hỗ trợ chọn `--source fireant` và thư mục xuất riêng từ lệnh tổng. Script nạp Supabase lọc FireAnt và 10 mã, có chế độ thay `news_articles` trong một transaction, từ chối xóa nếu tập mới rỗng.
- Đã cào 10 bài/mã theo hạn mức mặc định của README, gộp còn 85 URL. Trước khi thay bảng đã sao lưu 234 bản ghi tại `backend/.tmp/news_articles_before_fireant_20261027.json` (không đưa lên Git).
- Sau khi nạp, DB có 85 bài FireAnt, 0 CafeF, 0 bài ngoài 10 mã, 0 URL trùng, 0 bài rỗng và 85/85 bài có payload. Bảng chunk/index/corpus cũ chưa được thay trong task này; nhóm sẽ lập chỉ mục lại sau.
- Kiểm thử: 3 test bộ lọc/nạp và toàn bộ 27 test crawler qua; bản nạp thử báo 85 bài trước khi ghi DB.

### [2026-10-27] Bổ sung link tệp đính kèm FireAnt

- Crawler lấy `files[].fileContentUrl` từ API chi tiết bài FireAnt vào `attachments`, loại link lặp và giá trị không phải URL HTTP(S). Có test bài có/không có tệp.
- Đã sao lưu 10 JSON cũ tại `backend/.tmp/fireant_before_attachments_20261027`, đọc lại 85 bài FireAnt và nạp bằng upsert, không xóa bảng. Supabase còn 85 bài; 36 bài có 36 link đính kèm. Bài ELC `42008571` lưu link PDF `https://mobiv2.fireant.vn/News/NewsAttachedFile/1909857` trong cả `news_articles` và payload nguồn liên kết.
- 12 test của `test_stock_news_collector.py` qua. Không tải nội dung PDF và không thay chunk/index/corpus.

### [2026-10-29] WBS03 — trích xuất ứng viên quan hệ từ BCTN (đang review)

- Tích hợp runtime contract 2.1.0 và registry do Hưng bàn giao; adapter đọc chunk BCTN thuộc corpus đã chọn trong transaction PostgreSQL chỉ đọc, dựng lại text từ snapshot nguồn và kiểm tra hash. Mỗi BCTN xuất một JSON với `document_version` chung của snapshot; không OCR/chia chunk lại, không ghi database hoặc Neo4j.
- Extractor rule-based tạo ứng viên sở hữu, công ty con, liên kết, hợp tác ở trạng thái `PENDING`, giữ `document_id`, `chunk_id`, locator và câu chứng minh. Rule bỏ qua phủ định, dự kiến, quan hệ quá khứ và tên không đủ rõ; WBS06 quyết định duyệt/từ chối.
- Chạy trên corpus frozen có 20 BCTN, 15.398 chunk hiện hành: 20 JSON hợp lệ, 1 ứng viên `PENDING` cần người kiểm duyệt. Audit offline chỉ ra các ca OCR/bố cục bảng và tên chưa resolve; chi tiết tại `docs/sprint4/WBS03-relation-gap-audit.md`. Chưa có tập nhãn gold nên chưa đo được precision/recall và chưa đánh dấu WBS03 hoàn thành.
- Kiểm thử: 22 unit test WBS03 qua; đầu ra và audit local nằm trong `backend/.tmp/` và không đưa lên Git.

### [2026-10-29] WBS08 — bộ ghi graph Sprint 4

- Thêm `Sprint4GraphStore` riêng với graph tài chính/giá hiện có. Đầu vào là contract 2.1.0, chỉ đưa quan hệ `APPROVED` cùng thực thể liên quan vào Neo4j; giữ ID, chiều quan hệ, phiên, thời gian và evidence/locator.
- Mỗi batch được ghi trong một transaction, chạy lại cùng dữ liệu là no-op, ID trùng nhưng nội dung khác bị chặn. Phiên graph ở `BUILDING` đến khi đối chiếu đủ danh sách batch và công bố `READY`; truy vấn chỉ đọc phiên READY.
- Thêm constraint/index, fixture, CLI và hướng dẫn ở `docs/sprint4/WBS08-graph-store.md`. 8 test WBS08 và 22 test WBS03 liên quan qua.
- Ngày 30/10: dựng Neo4j Community 2026.10.1 trong container riêng trên VPS, cổng chỉ bind localhost, kết nối qua SSH tunnel. Thử fixture trên Neo4j thật: 2 node/1 cạnh APPROVED, PENDING không tạo cạnh, chạy lại không trùng, publish thiếu batch bị chặn, đọc lại đúng ID/chiều/evidence ở phiên READY. CLI hỗ trợ `--env-file` riêng; 30 test liên quan qua. Chỉ ghi dữ liệu thử vào Neo4j mới, không ghi PostgreSQL. Chưa chạy tích hợp quan hệ BCTN thật đã duyệt.

### [2026-10-30] WBS03 — đọc corpus BCTN mới bằng release alias

- Vũ bàn giao `release_identity.py` và `annual_source_reader.py`. Reader WBS03 dùng bộ kiểm tra binding chính thức thay so sánh trực tiếp source document ID với release document ID; vẫn xác minh source release, snapshot, trang, chunk ID và content hash. Không sửa locator hay database.
- Chạy PostgreSQL chỉ đọc trên corpus `b2550a0b-c423-5c50-9b15-6fb6af12e2c6`: 20/20 BCTN, 17.664/17.664 chunk dựng lại thành công, 20 envelope hợp contract; trích được 8 ứng viên PENDING. ELC 2024 trang 14 đã có chữ Smartek; 5/8 đối tượng chưa resolve. Hai BCTN TCB khác năm dùng cùng relation ID cho TCB–TCBS, cần quy tắc gom evidence/định danh trước khi nạp Neo4j.
- 32 test liên quan WBS03/WBS08 qua. Đầu ra ở `backend/.tmp/wbs03-vps-web-elc-20261030/` (ignore). Chưa có nhãn gold hay duyệt WBS06 nên chưa nghiệm thu độ chính xác và chưa ghi quan hệ BCTN thật vào graph.

### [2026-10-30] WBS03 — cải tiến từ gói đối chiếu thủ công của Hưng

- Bổ sung nhận tên pháp lý xuống dòng và danh sách công ty con/liên kết tiếp tục qua chunk cùng trang trong `relation_extractor.py`; dùng resolver/registry chung, giữ heading cùng tên trong evidence và mọi ứng viên `PENDING`. Không sửa contract, registry, database hoặc Neo4j.
- Chạy lại offline trên 20 envelope BCTN đã xác minh trước đó: 14 ứng viên `PENDING` (trước là 8); bốn ca dương tính P01–P04 có đúng cặp/loại quan hệ, bốn ca âm tính N01–N04 không sinh cạnh giữa cặp bị cấm. Chưa gán tỷ lệ/ngày từ chunk hoặc sơ đồ khác; tên thiếu canonical ID vẫn unresolved.
- 28 test WBS03 qua, gồm ca tên xuống dòng, danh sách nhiều chunk, mã viết tắt và cùng xuất hiện không có quan hệ. Đây là đối chiếu giới hạn theo gói Hưng, chưa phải precision/recall toàn corpus hay phê duyệt WBS06. Chi tiết tại `docs/sprint4/WBS03-BCTN-relation-candidates.md`.
- Xuất 20 JSON offline mới vào `backend/.tmp/wbs03-hung-review-20261030/` (14 ứng viên; thư mục local bị Git ignore). Rà từng ứng viên trong `docs/sprint4/WBS03-14-candidate-review-20261030.md`: 12 cặp có Hưng đối chiếu nguồn, 2 cặp ELC→VFT và ELC→Tập đoàn Thương mại Hà Nội cần hỏi thêm; ba tên TechAMC, BIC và Smartek cần sửa cách lấy tên trong WBS03. Không đổi trạng thái `PENDING`.

### [2026-10-30] WBS03 — tích hợp registry r1 Hưng bàn giao

- Xác minh 19/19 thành viên ZIP theo SHA256; giữ nguyên registry cũ 1.430 ID, thêm bản có phiên `company.registry.20261030.r1.json` với 1.440 ID. Chỉ đổi mặc định của hai CLI WBS03 sang bản mới, không sửa resolver/contract WBS02 hoặc database.
- Chặn nhận nhầm “Chủ sở hữu” thành động từ sở hữu; dùng alias đã verified trong heading TechAMC để tránh trùng ứng viên tên cụt; cắt phần giải thích khỏi tên Smartek; thêm mẫu câu rõ “Smartek là công ty con của Datanova”.
- Chạy lại offline 20 JSON BCTN đã xác minh: 17 ứng viên PENDING, 16 đối tượng resolved, BIC còn unresolved vì bảng tách cột và ticker thiếu ngữ cảnh resolver. Hai ca ELC→VFT/Hà Nội được Hưng xác nhận trong gói mới; hai ca mới theo năm TCB 2025→TechAMC và VCB 2025→VCBL cần đối chiếu tay. 29 test WBS03 qua. Kết quả chi tiết tại `docs/sprint4/WBS03-registry-r1-review-20261030.md`; đầu ra local trong `backend/.tmp/wbs03-registry-r1-20261030/`. Không ghi PostgreSQL/Neo4j, không đổi review state.

### [2026-10-30] WBS03 — tự đối chiếu hai ứng viên BCTN 2025

- Đối chiếu TCB→TechAMC với chunk trang 160 (mục công ty con) và trang 84 (vốn góp của Techcombank); đối chiếu VCB→VCBL với chunk trang 18 (sở hữu 100%) và trang 41 (danh sách công ty con) trong hai snapshot đã ghim. Không suy ngày bắt đầu quan hệ từ ngày nghị quyết và chưa tự gắn tỷ lệ vào JSON.
- Cập nhật `docs/sprint4/WBS03-registry-r1-review-20261030.md`. Cả hai ứng viên vẫn `PENDING`; BID→BIC vẫn `unresolved` do ngữ cảnh bảng/ticker. Đây là rà bằng chứng trên JSON BCTN đã đọc trước đó, chưa phải duyệt WBS06 hay đo precision/recall toàn corpus. Không đọc/ghi database hoặc Neo4j trong lượt này.
