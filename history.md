# History thay đổi code

### [2026-10-22] Triển khai nguồn phiên bản dùng chung và kích hoạt corpus-v4

- Theo phê duyệt triển khai/test: ghi một metadata root dùng lại 43 payload gốc Supabase; đăng ký v4 FROZEN, index ACTIVE, 675 tài liệu/7.158 vector, membership 72.096 facts và 737 phiên giá. Không thêm chunk_text/bảng/cột; giữ các corpus cũ.
- Reader truy ngược locator về đúng nguồn đã ghim và giữ đầy đủ kiểm tra hash. Reader giá dùng raw bars lịch sử, không lấy OHLCV mới từ bảng live. Crawler giữ payload theo content ID cho lần ingest sau.
- Thêm lọc công ty/kỳ/chỉ tiêu rõ ràng trong câu hỏi tài chính, sau đó xếp hạng vector; dùng nhãn nguồn và alias tỷ suất/biên lợi nhuận, không thay số liệu hoặc tự chứng nhận đơn vị.
- Sửa cách cô lập cấu hình test và truy cập settings snapshot để tránh giữ nhầm getter giả lập khi import. 190 test hồi quy PASS dưới cấu hình v4; có cảnh báo deprecation thư viện.
- Audit DB và đọc nguồn chung 7.158/7.158 PASS; 43 truy vấn HTTP thật PASS về transport/source; 12 dòng evidence Q31–Q39 khớp đúng observation/kỳ/giá trị hiển thị. Q40 trả rỗng khi thiếu kỳ; corpus không tồn tại trả 409.
- Chuyển đúng bốn khóa backend/.env sang v4 sau các chốt kiểm tra; lưu bốn khóa cũ trong backend/.tmp, không thay bí mật kết nối/model. Chưa commit/push.
- Hướng dẫn mới: docs/CORPUS_V4_QUICK_START.md. Bằng chứng và giới hạn: outputs/corpus-v4-reuse-audit-20261022/Ket_qua_kiem_thu.md. Không chứng nhận toàn bộ 40 đáp án cuối, citation PDF hoặc đơn vị chưa xác minh chỉ từ HTTP 200.

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

### [2026-10-21] Bắt đầu nhúng và ghi vector corpus-v2 theo yêu cầu

- Người dùng yêu cầu thực hiện bước 2 (embedding/ingest v2). Thêm backend/scripts/ingest_corpus_v2.py, verify_corpus_v2_vectors.py và tests/test_ingest_corpus_v2.py. Sửa repository.resolve_result_rows chọn/cache renderer theo locator để đọc đúng financial v1/v2/v3.
- Đối chiếu toàn bộ 15.058 chunk snapshot với nguồn sống trước ingest: đúng nội dung/hash. Model BAAI/bge-m3 revision 5617a9f61b028005a4858fdac845db406aefb181 đã nạp và tạo vector 1024 chiều thật; CPU, không có CUDA.
- Ghi vào index riêng 434ef5e0-6516-578d-8d18-721d21347e01 (db-corpus-v2, BUILDING), document/chunk namespace riêng; chỉ INSERT dữ liệu mới, không đổi bảng nguồn, không ghi chunk_text, không UPDATE/supersede corpus-v1. Chỉ tái sử dụng vector cùng model và đúng content_hash; kiểm tra shape/finite trước ghi.
- Checkpoint đầu đã audit 120 vector lưu thật: hash, locator, số chiều và norm đạt. Đối chiếu 2.048 ID v1 vẫn còn đúng hash/số chiều, hash file manifest v1 không đổi. Chưa tuyên bố hoàn thành toàn bộ 15.058 vector.
- Đã chuyển worker sang chạy nền ẩn, có log, checkpoint/resume và session advisory lock chống chạy trùng. Worker tự audit toàn bộ sau khi nhúng xong. Tiến độ: backend/.tmp/corpus-v2-ingest-progress.json; log: corpus-v2-ingest.log; audit: corpus-v2-vector-audit.json; mã kết thúc: corpus-v2-worker-exit.json.
- 51 test ingest/manifest/reconstruction/versioning liên quan đạt. Chưa đăng ký corpus-v2 FROZEN, chưa đánh dấu benchmark-ready và chưa chạy B1/citation test; cần kiểm chứng đủ vector rồi xuất manifest lưu thật và giới hạn truy vấn đúng membership.

### [2026-10-21] Đối chiếu Golden Set với nguồn/vector hiện hành (chỉ đọc)

- Thêm audit_golden_sources.py và báo cáo docs/embedding/golden-source-audit-20261021.md; không sửa Golden Set, không chạy B1. Snapshot 09:29:34 giờ Việt Nam.
- Q01–Q09 khớp đủ 9 bài theo tiêu đề/ngày; Q15/Q17/Q19 có đúng phiên giá và vector active db-v1. Dựng lại 75 chunk tin/giá liên quan, nội dung/hash PASS.
- Q10: DB 234 bài (CafeF 119, FireAnt 115), khác tập Golden cố định 224. Các phép tính giá được đối chiếu trực tiếp từ 737 bars; Q13 có hai ngày cùng highest close 69,7: 10/04 và 20/05/2026, Golden chỉ ghi ngày đầu.
- Q31–Q39: đủ giá trị FPT 2026-Q2/Q1 được hỏi nhưng tại snapshot chưa có vector cho các observation cụ thể. Sáu locator gốc trong Golden lệch trường DB: Q32 bsa56, Q33 bsa90, Q35 isa22/isa23, Q36 cfa18, Q37 cfa19. Đơn vị/phạm vi nguồn chưa xác minh; Q38 có RATIO_TTM, không coi là riêng quý.
- Chưa có PDF BCTN/BCTC FPT 2024 được ingest cho Q21–Q29. Q40 không có hàng FPT 2026-Q4; hành vi từ chối Q30/Q40 vẫn cần chạy B1 thật mới chấm được.
- Index v2 đang BUILDING với 835 chunk ở snapshot; không tuyên bố đủ nguồn/vector chỉ từ tổng tiến độ.

### [2026-10-21] Chuyển nhúng corpus-v2 từ CPU sang GPU theo yêu cầu

- Xác nhận máy có NVIDIA GeForce RTX 2050 4 GB, driver 555.97; trước đó .venv dùng PyTorch 2.6.0+cpu nên CUDA không khả dụng.
- Tạo môi trường .venv-gpu riêng với torch 2.6.0+cu124 từ kho PyTorch chính thức, giữ nguyên .venv CPU; thêm .venv-gpu/ vào .gitignore. Tải gói CUDA khoảng 2,5 GB, không phát sinh phí API embedding.
- Thử BGE-M3 cùng revision trên GPU: 6 đoạn trong 1,219 giây, đỉnh VRAM 2.204 MiB, 1.024 chiều; so với 4 vector CPU đã lưu, cosine >0,99999999999. Không đổi model hoặc hạ precision.
- Thêm --device cho ingest_corpus_v2.py, device/batch_size trong checkpoint và runner run_corpus_v2_gpu.ps1. 5 test snapshot/index/versioning liên quan đạt. Dừng đúng runner CPU sau khi GPU probe đạt, tiếp tục index v2 hiện có bằng --device cuda --batch-size 2, không làm lại vector đã commit.
- Runner GPU chạy nền ẩn, log corpus-v2-ingest.gpu.log và .gpu.stderr.log, tiến độ chung corpus-v2-ingest-progress.json; tự audit khi xong. Không chạm corpus-v1 và chưa đánh dấu toàn bộ vector/benchmark hoàn thành.

### [2026-10-21 10:50 +07:00] Hoàn tất nhúng và ghi vector corpus-v2

- Worker GPU đã kết thúc exit_code=0. Supabase có đủ 15.058/15.058 vector trong index riêng 434ef5e0-6516-578d-8d18-721d21347e01.
- Audit cuối VECTORS_VERIFIED: đủ ID, document/hash/locator đúng snapshot, vector 1.024 chiều và norm hợp lệ, không bị supersede. 2.048 thành viên corpus-v1 còn đúng hash/số chiều; file manifest v1 không đổi.
- Kết quả: backend/.tmp/corpus-v2-vector-audit.json và corpus-v2-worker-exit.json. Không còn worker cần nhúng phần còn thiếu của lượt này; không chạy lại từ đầu.
- Hoàn thành bước embedding/ingest, chưa đăng ký corpus-v2 FROZEN, chưa xuất manifest với khóa chunk lưu DB và chưa chạy B1/citation; chưa tuyên bố benchmark-ready. Cập nhật kết quả cuối trong docs/embedding/corpus-v2-handoff.md.

### [2026-10-21] Soạn Golden40 v6 đề xuất theo bản v5 người dùng gửi

- Đọc file v5 trong Downloads (SHA-256 cd53c32cea638ceb93bfd1d8790ba1ae1e3734e5d276cfa2ecde054a37d04eb1), giữ nguyên file gốc và bộ Golden cũ trong repo. Không làm theo các tuyên bố “100%” của tài liệu như kết quả kiểm thử mới.
- Thêm build_golden40_v6.py, xuất vào outputs/golden40-v6/: Golden40_Cau_hoi_sau_sua.md (bản dễ đọc), Golden40_V6_De_xuat.md (đề và cách chấm/giới hạn), Golden40_V6_De_xuat.json (cấu trúc để duyệt).
- Giữ 40 ID, phân 27 câu tìm đoạn, 9 câu truy vấn/tính toán, 2 câu tra phiên giá, 2 câu từ chối. Q02 chỉ trích bài báo; câu giá cố định cửa sổ, cực trị xử lý đồng hạng; câu clean không tự gán VND/hợp nhất/riêng quý; Q38 rà TTM, Q39 có điều kiện về cơ sở so sánh.
- Giữ đủ 40 đáp án v5 dưới nhãn tham khảo chưa duyệt lại; không tự điền gold/đáp án được duyệt. Phân biệt source_chunk_id ứng viên với ID vector lưu DB, không dùng ID gold để lọc truy vấn. Đề xuất evidence-group Recall@5/@10, tách chấm phép tính và refusal.
- Nêu rõ thiếu lịch sử giá/PDF đúng phạm vi và khác bản nguồn ngay tại Q15 (v5 close 64,07, DB trước đó 64,13). Đây là DRAFT_NOT_BENCHMARK_READY, không tự cập nhật corpus/vector hoặc chạy B1. Đã kiểm tra đủ 40 câu duy nhất và giữ đủ 40 đáp án tham khảo.

### [2026-10-21] WBS24: đối chiếu retrieval/locator v2 thật, phát hiện nguồn thay đổi

- Theo yêu cầu đối chiếu, chạy check_wbs24_v2_locators.py: 18 câu v6 (Q01–Q10, Q31–Q38), BGE-M3 GPU thật, top-5 cosine không lọc trên index v2; transaction chỉ đọc, không sửa nguồn/vector/API.
- 90 lần kết quả: 31 locator dựng lại đúng hash, 59 SOURCE_CHANGED. Đây không phải điểm Recall hay điểm đúng đáp án; chưa có gold đã duyệt và chưa chạy câu trả lời B1/citation đầy đủ.
- 8/59 lần lỗi được xác định chỉ do header đổi (CTCP FPT → Công ty Cổ phần FPT); 51 lần còn lại không chỉ khác header. Ví dụ section ngân hàng có tên chỉ tiêu tiếng Việt bị đổi thành mã. Không tự kết luận số liệu thay đổi hoặc mọi lỗi cùng nguyên nhân khi chưa so toàn bộ.
- API hiện chưa chọn index v2 trực tiếp và chưa xuất đủ trường citation/locator; PDF nhiều trang và hai version chưa kiểm tra. WBS24 chưa hoàn thành. Kết quả chi tiết: docs/embedding/WBS24-v2-locator-check-20261021.md và các JSON trong backend/.tmp/.

### [2026-10-21 11:37 +07:00] Kiểm tra lại lý do có ID nhưng bị chặn nội dung

- Thêm recheck_wbs24_sources.py, đọc lại các ID và nguồn bằng READ ONLY REPEATABLE READ. 90 lần kết quả tương ứng 82 ID vector duy nhất; đủ 82 bản ghi tồn tại, không có nguồn bị thiếu. Vẫn 31 PASS, 59 SOURCE_CHANGED.
- Mở rộng so toàn bộ section: cả 59 lượt lỗi giữ nguyên mã dòng/thứ tự/mã chỉ tiêu và chuỗi giá trị/đơn vị hiển thị; chỉ khác header và/hoặc nhãn. Đây không phải audit bất biến mọi chữ số raw vì formatter có làm tròn.
- Làm rõ: SQL cosine tìm ID từ embedding được; phần đọc nguồn vẫn hoạt động, nhưng bước reconstruction/hash chặn xuất text khác phiên bản. Không phải không có dữ liệu hoặc locator trỏ vào hàng đã mất. Chưa sửa production/DB/vector; báo cáo WBS24 đã cập nhật, bằng chứng backend/.tmp/wbs24-v2-recheck.json.

### [2026-10-21 11:47 +07:00] Làm riêng bước 1: so metadata toàn bộ corpus-v2

- Theo yêu cầu “làm 1”, thêm compare_corpus_v2_metadata.py và xuất outputs/corpus-v2-step1/Doi_chieu_metadata_corpus_v2.md cùng JSON. Chỉ SELECT trong READ ONLY REPEATABLE READ; không sửa DB, vector hoặc code ứng dụng.
- Đã so 675 tài liệu/15.058 chunk đóng băng, 1.963 section: 455 không đổi, 1.444 chỉ đổi header/nhãn, 43 chỉ đổi header, 5 chỉ dịch vị trí section, 16 có khác nội dung cần rà riêng. 423 tài liệu có ít nhất một khác biệt; có 21 section dịch vị trí vì nguồn đã bổ sung lịch sử.
- So đúng section theo nhãn tháng/kỳ, đồng thời ghi vị trí cũ/mới để không so nhầm tháng 2026 với 2018. Thống kê nhãn là 905 khác biệt phân theo công ty/mã, không phải 905 mã chỉ tiêu độc lập.
- Trích metadata đóng băng (header, nhãn theo row_key/code) vào JSON để chuẩn bị bước sau; chưa áp dụng runtime. Xác nhận manifest v2 giữ nguyên hash. Đối chiếu rendered text không thay cho kiểm toán mọi chữ số raw.

### [2026-10-21] Bước 2: lưu metadata bất biến cho báo cáo tài chính corpus-v2

- Thêm backend/scripts/store_corpus_v2_renderer_context.py: mặc định kiểm tra chỉ đọc; --apply lưu vào raw_payloads có sẵn, không thêm bảng/cột hoặc chunk_text. Payload chỉ chứa liên kết phiên bản, header và tên chỉ tiêu gốc theo ID dòng/mã.
- Đã kiểm tra 419 báo cáo/13.003 chunk dựng lại đúng ID, hash và locator trước khi ghi. Đã thêm 419 payload và đọc lại kiểm chứng SHA-256 trong một giao dịch; từ chối ghi đè metadata khác.
- Không sửa số liệu nguồn, vector, manifest hoặc locator đang lưu; chưa bật đọc metadata trong ứng dụng. Bước 3 mới nối vào reconstruction rồi chạy lại kiểm thử. Các trường hợp giá/hồ sơ có thay đổi nội dung vẫn cần xử lý riêng.
- Bằng chứng: outputs/corpus-v2-step2/archive-result.json và Ket_qua_buoc_2.md.

### [2026-10-21] Bước 3: nối metadata gốc vào đọc kết quả tài chính corpus-v2

- Thêm backend/src/documents/renderer_context.py: đọc raw_payloads theo index và nguồn, kiểm tra duy nhất một bản, SHA-256, UUID xác định, schema và liên kết phiên bản. Khôi phục header/tên chỉ tiêu; giá trị vẫn lấy từ nguồn hiện tại.
- repository.resolve_result_rows chỉ dùng metadata cho tài chính thuộc db-corpus-v2; cache tách theo index. get_chunks/vector_search SELECT thêm index_version_id. Giữ nguyên kiểm tra fingerprint, hash, offset và ID chunk; không sửa vector, nguồn, manifest hay locator DB.
- Kiểm thử guard và luồng repository: metadata khôi phục được tên cũ; đổi số liệu, sai checksum/index vẫn bị từ chối. Các kiểm thử search/upload/reconstruction liên quan đạt.
- Thử chạy lại 18 câu/90 locator bằng GPU nhưng kết nối Supabase thất bại ở DNS (socket.gaierror 11001 getaddrinfo failed), trước truy vấn. Chưa có số PASS mới; không nghiệm thu WBS24 hoặc tuyên bố toàn bộ corpus hoạt động. Kết quả trước sửa được sao lưu backend/.tmp/wbs24-v2-locator-before-step3.json.
- Phạm vi chỉ tài chính 13.003/15.058 chunk. Các thay đổi nguồn giá/hồ sơ, chọn index v2 trên API và full B1 citation vẫn là việc riêng chưa hoàn tất.

### [2026-10-22] Rà bộ chỉ tiêu đã duyệt và khả năng áp dụng vào Supabase

- Chỉ rà soát, không sửa DB. Local có 348 định danh: 215 linked, 19 linked_with_conditions, 35 not_retained, 79 no_match. Toàn bộ chưa xác minh đơn vị nguồn/chưa cho quy đổi.
- get_metric_link chưa được gọi trong pipeline/app. Importer lấy nhãn JSON clean, không dùng bộ reviewed; metric trùng ID dùng DO NOTHING. SOURCE_NATIVE/scale=1/currency=NULL và trạng thái UNVERIFIED vẫn được importer ghi. MAPPED không đồng nghĩa đã đối chiếu Excel.
- Thêm audit_reviewed_metric_database.py để SELECT đối chiếu. Lần thử Supabase ngày này lỗi DNS gaierror; không kết luận trạng thái DB hiện hành. Báo cáo: outputs/metric-audit-20261022/Ket_qua_ra_soat.md và audit.json.

### [2026-10-22] Bước 1 thiết kế bộ chỉ tiêu dùng chung nhiều sprint

- Đối chiếu ERD.md, schema migration, importer và mapping hiện có. Tạo docs/embedding/Thiet-ke-chi-tieu-dung-chung-20261022.md.
- Thiết kế dùng config_versions/system_configs cho danh mục, mapping provider/schema/ngành/section, unit rules và checksum; giữ metrics/observations IDs cũ, gắn tham chiếu cấu hình vào locator JSON cho dữ liệu mới. Không tạo bảng, không ghi DB hoặc sửa pipeline.
- Làm rõ 234/348 mới nối danh mục, chưa xác minh đơn vị; cần version-aware reader, report ID chứa mapping hash cho các lần nhập mới, không cộng các phiên bản. Tách nguồn/native khỏi số chuẩn tính lại để tránh cộng trùng/đổi hệ số hai lần.
- Bản thiết kế dựa schema repo; schema live vẫn chưa xác nhận do lỗi DNS lần audit. Có lộ trình triển khai/tiêu chí nghiệm thu và giới hạn retention; không thay corpus-v2.

### [2026-10-22] Tiếp phần dùng chung: kiểm tra đầu vào mapping trước khi xây bản cấu hình

- Thêm backend/src/financial/config_validation.py và CLI backend/scripts/validate_financial_configuration.py. Chỉ đọc file local; không ghi Supabase, không đổi JSON gốc hoặc importer.
- Rà 348 định danh nguồn/706 dòng tiêu chí: cấu trúc và target tham chiếu chính xác đạt, 234 nối danh mục, 114 chưa nối/không được giữ. 0 mục đủ đưa importer vì còn thiếu provider/schema/rule/definition revision, xác minh đơn vị/ngữ cảnh, quy tắc đơn vị, phạm vi/kỳ và bản cấu hình đóng băng.
- Validator đơn vị kiểm tra hệ số Decimal dạng chuỗi, hữu hạn/dương, chiều đơn vị, tiền tệ và cờ duyệt. Kiểm tra này không tự chứng nhận bằng chứng provider hoặc bật quy tắc.
- Báo cáo dễ đọc từng mục: outputs/financial-config-review-20261022/Ket_qua_kiem_tra.md; JSON có hash đầu vào: validation.json. Đây là kiểm tra đầu vào cũ; chưa phải validator đầy đủ cho hợp đồng rule mới hoặc kiểm tra điều kiện chồng lấn giữa các provider.

### [2026-10-22] Truy vết nhóm chỉ tiêu cơ bản trước khi duyệt quy tắc nguồn

- Thêm trace_pilot_financial_metrics.py, đối chiếu bằng Decimal các trường bsa53/TOTAL_ASSETS, bsa54/TOTAL_LIABILITIES, bsa78/OWNERS_EQUITY từ raw đến normalized và clean trên 10 công ty BANK/TECH.
- 1.257/1.257 giá trị khớp; 10/10 hash nguồn normalized được ghi trong file clean khớp file hiện có. Có hash 30 file và chi tiết từng giá trị trong outputs/financial-pilot-review-20261022/source_trace.json, báo cáo Ket_qua_truy_vet.md.
- Nhận diện provider local là VIETCAP_VCI; schema 1.0 là wrapper của dự án, không tự nhận là version provider. Raw balance data chỉ có years/quarters, chưa có metadata xác nhận unit/scale/currency. Không dùng chú thích mapping hoặc độ lớn số để duyệt đơn vị.
- Xuất 30 ứng viên theo công ty ở trạng thái DRAFT, approved=false, factor/unit/currency chưa xác nhận. Chưa ghi DB, chưa chuyển đơn vị hoặc kích hoạt importer; cần xác nhận provider unit và phạm vi/kỳ trước khi đóng băng rule. Các con số khớp local không chứng nhận báo cáo gốc hoặc độ chính xác trước lúc raw được lưu.

### [2026-10-22] Xác minh cụ thể đơn vị/phạm vi bằng báo cáo FPT và VCB 2024

- Đọc PDF local, render và xem trực quan FPT PDF 150–152 (trang in 148–150), VCB PDF 67 (trang in 130–131). Dùng pypdfium2 trong backend/.tmp/pdf-rendering để render, không thay dependencies ứng dụng. Web xác nhận bản chính thức VCB tiếng Anh; các link FPT 2024 tìm thấy nhưng mở web 404, nên dùng PDF local đã lưu làm bằng chứng chính.
- Sáu giá trị (3 chỉ tiêu x 2 công ty) ngày 31/12/2024 khớp báo cáo hợp nhất. 12 bản YEAR/Q4 khớp nhưng cùng một ngày chốt, không coi là 12 mẫu độc lập. FPT báo cáo bằng VND; VCB báo cáo triệu VND nhưng JSON đã bằng số báo cáo x 1.000.000. Hệ số từ JSON hiện tại sang VND là 1 trong các mẫu, không nhân triệu lại.
- FPT bsa78 khớp tổng mã 400, bsa79 khớp nhóm 410, lệch 2.750.000.000 VND do nguồn kinh phí/quỹ khác. Đọc lại reviewed criteria xác nhận định nghĩa common.equity/TECH đã bao quát đúng; đây là điều kiện cần giữ khi triển khai, không phải lỗi mapping mới.
- Thêm backend/scripts/verify_pilot_report_evidence.py, kiểm tra số trong PDF, số normalized/clean, phân rã vốn và hash file. Chạy đạt 12/12 bản, 6 giá trị/ngày độc lập. Kết luận và JSON: outputs/financial-evidence-20261022/Ket_luan_don_vi_va_pham_vi.md, verified_samples.json.
- Không ghi Supabase, sửa mapping, importer hoặc corpus. Đã xác minh mẫu cụ thể; chưa có hợp đồng endpoint chứng nhận mọi kỳ/ngành nên không bật rule toàn nguồn hoặc gán verified cho 348 mục.

### [2026-10-22] Hoàn thành rà 10 công ty/2 niên độ và lập quy tắc nguồn có bằng chứng

- Theo yêu cầu làm bước 1 và 2, rà 20 hồ sơ niên độ 2024–2025 của 5 BANK (VCB/BID/CTG/MBB/TCB), 5 TECH (FPT/CMG/ELC/ITD/ICT). Quét PDF chỉ tạo ứng viên; đọc/render bảng nguồn để chốt ngày, cột, đơn vị, phạm vi. 19 hồ sơ có 57 giá trị khớp báo cáo và raw/normalized/clean; 1 hồ sơ ITD FY2024 thiếu phụ lục BCTC gốc (local 46 trang kết thúc ở bìa chương tài chính). Không tuyên bố hồ sơ thiếu đã đạt.
- Phát hiện BID 2024 hiện khớp cột trình bày lại trong BCTN 2025; CMC FY2024/FY2025 khớp provider 2025-Q1/2026-Q1 (ngày 31/3); ITD FY2025 khớp 2026-Q1. ICT có báo cáo TỔNG HỢP, không được gán hợp nhất. Các snapshot kiểm tra đã là VND, factor JSON sang VND=1; không nhân lại triệu đồng của báo cáo ngân hàng.
- Thêm balance_sheet_evidence_cases_v1.json (20 hồ sơ đã rà) và build_balance_source_rules.py tạo balance_sheet_source_rules_review_v1.json: 30 rule theo công ty/trường, mã chuẩn/định nghĩa/điều kiện, hash PDF và raw/normalized/clean, danh sách mẫu được xác nhận. Chỉ REVIEWED_SNAPSHOTS_ONLY, production_enabled=false, file mới yêu cầu rà; không giả đã xác minh hợp đồng/schema endpoint.
- Thêm source_rule_review.py và tests: kiểm tra hash, rule trùng, tham chiếu mẫu, trộn kỳ/phạm vi, nhân hệ số lần hai, kích hoạt nhầm production. 44 kiểm thử liên quan đạt.
- Bàn giao outputs/financial-all10-review-20261022/Ket_qua_va_quy_tac.md, summary.json, ảnh trang và gói rule trong backend/src/financial/data. Chưa sửa importer, Supabase, dữ liệu cũ hoặc corpus-v2. Đã thử tra ITD official annual report page nhưng bảng tài liệu không có link trong lần đọc; còn cần BCTC hợp nhất kiểm toán đầy đủ chốt 31/03/2025 để hoàn tất bằng chứng gốc cho hồ sơ đó.

### [2026-10-22] Bổ sung hồ sơ cuối và chốt bước 1–2: đủ 20/20, 60/60

- Tiếp tục tìm hồ sơ ITD FY2024, tải bản issuer English đầy đủ 91 trang từ https://cmsv5.fiingroup.vn/medialib/FG/2025/2025-06/2025-06-25/ITD/20250624--ITD--Annual-Report-2024.pdf. Lưu riêng outputs/financial-all10-review-20261022/ITD-Annual-Report-2024-EN.pdf, giữ nguyên bản tiếng Việt 46 trang thiếu phụ lục.
- Render/xem trực quan PDF 51–52: số chốt 31/03/2025 tài sản 681884657089, nợ 272241766116, vốn 409642890973 VND. Đúng raw/normalized/clean provider 2025-Q1. Cập nhật case, rule, báo cáo và test. Trạng thái thiếu ghi ở mục history trước đã được giải quyết trong cùng lượt công việc này.
- Kết quả cuối: 20/20 hồ sơ xác minh có giới hạn theo snapshot, 60/60 giá trị đúng, 30 rule có bằng chứng. Manifest 7cb565b8aef4747dd6689a9b4a8a088d53ce4c3e7e951f3a59e00952d3c61960. Chưa bật production; cần gắn cấu hình phiên bản vào importer ở bước tiếp theo. Không sửa Supabase/corpus-v2.

### [2026-10-22] Bước 3: tích hợp quy tắc vào importer, kiểm tra offline trước khi ghi chung

- Thêm src/financial/import_plan.py: kiểm hash bộ review, chọn rule theo provider/ngành/section/trường/công ty/kỳ, ràng buộc đúng hash clean/normalized và số mẫu. Mẫu mới/file đổi không tự được verified. Bản chưa xác minh giữ SOURCE_NATIVE và lý do riêng, không xóa hoặc đoán đơn vị.
- import_clean_financials.py có --financial-rules và --plan-out. Chạy mặc định offline xuất plan.json, Ke_hoach_nhap.md và configuration-draft.json (đủ catalogue/source mapping/unit rules/manifest). 10 công ty, 72096 số: 60 verified snapshots, 72036 chưa xác minh. Bản kế hoạch JSON đầy đủ khoảng 27,7 MB là đầu ra rà soát, không cần stage/push cùng source code.
- Nhánh ghi có điều kiện dùng ID job/payload/report chứa cả hash mapping; observation locator lưu config/rule/evidence/ngày chốt/phạm vi; chỉ 60 số đủ bằng chứng có VND/scale1/currencyVND. Không đổi metric/name toàn cục. Đọc lại so cả số, locator, đơn vị/hệ số/tiền tệ để phát hiện xung đột dù INSERT DO NOTHING.
- Trước ghi bắt buộc config_version_id đúng đã frozen trong Supabase, cả bốn config JSON và manifest phải khớp, mode VERIFIED_SNAPSHOT_IMPORT và policy giữ số native rõ ràng. Chưa đăng ký/đóng băng cấu hình hoặc chạy --apply/--rollback trên Supabase. Giao dịch repeatable_read, không sửa corpus-v2.
- 55 kiểm thử liên quan đạt, gồm SQL-facing DB mô phỏng chạy apply_one: nhập lặp không tăng số dòng, phiên bản mới không ghi đè legacy, sai unit bị bắt, chưa có config/đơn vị cấu hình bị đổi thì chặn. Chưa phải kiểm thử ghi thật Supabase.
- Trước triển khai ghi chung còn phải cho reader chọn đúng config/report version để không cộng hai phiên bản, và đọc scope/date từ metadata đúng. Hiện financial_reports.scope để UNKNOWN cho report chứa lẫn số chưa xác minh; scope xác minh lưu ở từng observation, không gán cả report theo ba dòng.

### [2026-10-22] Reader tài chính chọn phiên bản rõ ràng

- Hiểu yêu cầu “render đi” theo mạch trao đổi là làm reader, đã thông báo trước khi sửa. Thêm src/financial/reader.py: chọn symbol/period/config/report; không tự latest hoặc trộn legacy với config, nhiều report thì yêu cầu ID, thiếu bản chọn trả rỗng không fallback.
- Đọc nguồn và kiểm frozen config bốn nhóm, hash mapping/định nghĩa/evidence/file và unit/scale/currency/số trước khi trả standard_value. Chưa xác minh vẫn có số nguồn, standard_value=None kèm lý do. Trả niên độ issuer/ngày chốt/provider period/scope riêng, phân biệt BID restated và ICT AGGREGATED.
- db_source.fetch_financial_documents loại observation có financial_mapping khỏi luồng tạo index legacy; không đổi locators/hash/nguồn lịch sử. Chưa tạo chunk/index mới hoặc nối frontend; consumer mới dùng hàm/CLI reader chuẩn hóa.
- Thêm read_financial_facts.py CLI READ ONLY REPEATABLE READ và test_financial_reader.py. 91 kiểm thử liên quan đạt, gồm đủ 20 hồ sơ/60 giá trị và hồi quy importer/chunker/metadata reconstruction.
- Thử live FPT 2024-YEAR thất bại do connection closed trong giao dịch (InterfaceError Transaction.__aexit__ underlying connection is closed). Không khẳng định nguyên nhân là DNS, chưa có kết quả live đạt. Không ghi Supabase; cấu hình/import mới/corpus-v2 giữ nguyên.
- Bàn giao outputs/financial-reader-step4/Reader_va_cach_kiem_tra.md. Việc còn lại trước triển khai là kiểm tra kết nối và chạy thử đọc/nhập rollback trên DB thật sau khi chuẩn bị cấu hình; hiện mới xác nhận offline.

### [2026-10-22] Chẩn đoán lại thông báo kết nối reader bị đóng

- Thêm diagnose_financial_connection.py: CONNECT/SELECT1/giao dịch readonly/query/reader được log riêng, không in DSN. Kết nối lần này thành công 0,94s; SELECT1 đạt; query tài chính FPT/2024-YEAR trả 900 dòng sau ~21,17s. Server statement_timeout=2min, idle_in_transaction_session_timeout=0.
- 900 dòng thuộc 5 report ID với số dòng 160/287/47/225/181. Chọn cụ thể 977450b0-824d-598d-80ee-99e5448de582 đọc thành công 160 facts legacy; đây chỉ là mẫu chẩn đoán, không chọn bản chuẩn thay nhóm.
- Không chọn report thì lỗi đúng là FinancialReadError AMBIGUOUS_REPORT_VERSION, kết nối vẫn mở. Không kết luận lần đóng kết nối trước cùng nguyên nhân vì không có log lỗi gốc thời điểm đó.
- Sửa CLI reader dùng command_timeout=30 và quản lý rollback không che lỗi body khi connection đã đóng/cleanup lỗi. 35 tests reader/CLI đạt, gồm 2 regression về giữ nguyên lỗi gốc.
- Không ghi Supabase. Evidence outputs/financial-reader-step4/connection-diagnostic.json; cập nhật Reader_va_cach_kiem_tra.md với kết quả live legacy đã đọc được khi chọn rõ report.

### [2026-10-22] Đối chiếu năm bản ghi FPT 2024 (chỉ đọc)

- Đính chính: một report clean 160 observations và bốn report theo phần cùng payload/job (287/47/225/181), không có bằng chứng là năm lần sửa báo cáo. Tổng 900 observations.
- 130 chỉ tiêu tiền chung bằng nhau theo Decimal; 30 chỉ số chung có 4 bằng nhau và 26 khớp dấu vết float-to-Decimal. Metadata đơn vị giữa hai đường nhập khác nhau.
- Nguyên nhân reader dừng: hai cách tổ chức report cùng tồn tại, chưa chọn nguồn nên AMBIGUOUS_REPORT_VERSION. Importer nguồn còn dùng tên phần báo cáo làm statement_scope. Không sửa importer hay dữ liệu trong lần đối chiếu này.
- config_versions đang rỗng; cấu hình chỉ tiêu mới chưa đăng ký/đóng băng. Corpus cố định khác với kết nối bị đóng. Lần đọc lại kết nối vẫn mở; chưa xác định nguyên nhân lỗi đóng kết nối lịch sử.
- Thêm compare_fpt_report_versions.py và outputs/financial-reader-step4/Doi_chieu_FPT_2024.md, fpt-report-comparison.json. Đối chiếu tách giá trị Decimal khỏi metadata đơn vị; không ghi Supabase.

### [2026-10-22] Sửa luồng chọn nguồn tài chính, importer và lập kế hoạch Supabase (4 bước)

- Theo yêu cầu người dùng: chỉ sửa code/local và kiểm tra SELECT; mọi thay đổi Supabase phải chờ người dùng đồng ý. Không chạy --apply/rollback/migration, không đăng ký cấu hình, không tạo lại corpus/index, không git add/commit/push.
- Reader bổ sung source-family clean/normalized và payload-id; normalized ghép các phần cùng payload/job, giữ ID gốc. Chặn trộn nhiều payload, nhiều report cùng phần, báo cáo restated, phạm vi không nhất quán và payload/job sai. Không tự chọn bản mới nhất; không có nguồn phù hợp thì không fallback.
- Importer normalized đọc JSON bằng Decimal, từ chối float/NaN/khóa trùng/chỉ tiêu trùng. Version normalized-financial-v2 tạo report/payload/job ID mới theo snapshot, statement_scope UNKNOWN, đơn vị SOURCE_NATIVE khi chưa xác minh. Không ghi đè report/observation/payload/tên metric cũ; thêm kiểm tra đọc lại chính xác. Luồng clean có quy tắc xác minh trước đây giữ nguyên.
- db_source loại normalized-financial-v2 khỏi bộ tạo index legacy; truy vấn đọc locator gốc giữ nguyên. Reader mới hiện là thư viện/CLI, chưa nối API/frontend.
- Kiểm tra offline 10 công ty BANK/TECH, 419 tổ hợp công ty/kỳ, 308739 giá trị normalized; 156 tests liên quan đạt. Dry-run không mở kết nối DB; CLI đọc dùng READ ONLY REPEATABLE READ và rollback, có regression tests.
- SELECT metadata Supabase: 2072 report, 380835 observations, 419 tổ hợp đều có clean + normalized; 1653 report dùng section làm statement_scope. Đây là inventory metadata toàn bộ nhóm, chưa đối chiếu từng giá trị live toàn DB.
- Kiểm tra reader live FPT 2024: clean 160 facts, normalized 740 facts; không gộp hai họ nguồn. Không sửa các đuôi float lịch sử hay tự chuẩn hóa số/đơn vị cũ.
- Bàn giao outputs/financial-source-fix-20261022/Ket_qua_va_ke_hoach.md, audit.json, supabase-review-plan.json, live-fpt-clean.json, live-fpt-normalized.json và verification.json. Kế hoạch Supabase là REVIEW_ONLY_NOT_APPROVED; phải rà tham chiếu corpus/citation trước khi cập nhật. Lỗi đóng kết nối lịch sử chưa xác định nguyên nhân.

### [2026-10-22] Chuẩn bị corpus-v2 làm bản chính — bước 1–3, chưa cập nhật Supabase

- Theo phạm vi người dùng duyệt: kiểm tra nguồn/vector, sửa code chọn corpus và xuất kế hoạch đăng ký; mọi truy cập DB READ ONLY REPEATABLE READ. Không đăng ký/kích hoạt corpus/index, không sửa .env thực tế hay dữ liệu nguồn, không git add/commit/push.
- Thêm corpus_scope.py: kiểm tra registry FROZEN/index ACTIVE/model/hash/index identity; hash số bằng Decimal; đọc giá theo corpus_prices có kiểm tra giá/scale/indicators. financial.reader lọc corpus_facts, kiểm tra value_hash và ý nghĩa metric ID, áp dụng cấu hình mặc định cho CLI/thư viện.
- API search nhận corpus_version_id, lọc corpus_documents và index tương ứng, trả chunk/document/corpus/index ID. Chunk/vocab detail DB dùng cùng corpus mặc định. Upload dùng index riêng. Cấu hình default_corpus_version_id/default_corpus_manifest_sha256 để rỗng; corpus chưa sẵn sàng báo 409, không fallback.
- prepare_corpus_v2_release.py không có chế độ apply, chỉ SELECT và xuất plan local. Chia lô metadata vector/financial/context sau một lỗi DNS và một truy vấn lớn timeout; kiểm tra live hoàn tất.
- V2: 675 docs, 15058/15058 vector khớp ID/hash/locator/dim/norm; 14955 chunk dựng lại đạt, 103 không khớp (giá VCB/MBB/FPT mỗi mã 34, hồ sơ FPT 1). Toàn bộ 13003 chunk tài chính đạt. Kế hoạch gồm 72096 observation và 737 price ID; value_hash là baseline số chính xác hiện tại, không chứng nhận số gốc lúc freeze. Activation_ready=false, blocker SOURCE_RECONSTRUCTION_FAILED.
- diagnose_corpus_v2_release_sources.py READ ONLY xác định: 21 section giá dịch vị trí (tháng đầu từ 0 sang 99), có thêm phiên và thay đổi giá/tổng kết; hồ sơ FPT đổi company_name. Không bỏ kiểm tra hash, không dùng text manifest làm fallback runtime, không làm tròn/sửa nguồn.
- Xác nhận local manifest v1 không đổi; 2048 vector v1 còn đúng hash/1024 chiều; 249 documents membership/hash còn nguyên. Chưa thử dựng lại toàn bộ nguồn v1.
- Tests: 203 hồi quy rộng đạt; sau tinh chỉnh cuối 73 tests tập trung đạt, không cộng hai số. Không gọi embedding/model/GPU. Chưa chạy B1 sinh câu trả lời và chấm semantic toàn Golden Set.
- Bàn giao outputs/corpus-v2-release-20261022/Ket_qua_buoc_1_2_3.md, preflight.json, source-differences.json, registration-plan.json (DRAFT_NOT_APPROVED), default-corpus.env.proposed, v1-preservation.json, verification.json. Corpus đề xuất 232fbd29-355f-5a77-ba28-a06b8d5ceb40, index 434ef5e0-6516-578d-8d18-721d21347e01. Chưa đủ điều kiện xin kích hoạt; phải xác minh/đọc được nguồn cũ hoặc tạo phiên bản mới rồi chạy lại preflight và xin duyệt DB.

### [2026-10-22 21:20 Asia/Bangkok] Tiếp tục ingest corpus-v4 theo yêu cầu

- Kiểm tra SELECT READ ONLY Supabase xác nhận index e3725b7d-1a39-5196-b000-3496dbab388f BUILDING, 5807 stored/active chunks; khớp progress local 5807/7158, còn 1351.
- Khởi chạy nền CPU batch-size 8 với manifest/snapshot v4 hiện có, --apply chỉ append phần thiếu; script có advisory lock chống worker trùng và kiểm tra ID/hash các chunk đã tồn tại.
- Tiến trình launcher 33420, Python worker quan sát được 31188. Snapshot preflight VALIDATED 7158; chưa có batch progress mới ở lần kiểm tra ngay sau khởi chạy. Không khẳng định đã ingest xong.
- Log và PID được lưu outputs/corpus-v4-clean-mapped-20261022/resume-process.json và resume-20261022-212018.stdout.log/.stderr.log.
- Chưa freeze/register/activate v4, chưa đổi default từ v3, chưa sửa financial configuration. Các việc này tiếp tục chờ người dùng duyệt.

### [2026-10-22] Kiểm tra SOURCE_CHANGED Q31 sau bàn giao v3/v4

- SELECT READ ONLY kiểm tra lại 5 chunk Q31 từ wbs24-v2-locator-results.json: cả 5 PASS qua repository hiện tại; 5 bản tương ứng trong index default v3 cũng PASS. Audit toàn bộ 15058 chunks active của v3 với configured snapshot: PASS 15058, FAIL 0.
- Cấu hình local chọn corpus-v3-workbook 06171160-c31a-5ff7-8bf0-66308ad72520, snapshot v3 local. Cơ chế mới đọc snapshot và kiểm tra locator/hash; không bỏ guard để trả 200. Không khẳng định tất cả v2 tương thích snapshot v3.
- Chưa chạy embedding retrieval lại/HTTP live vì backend 8000 không thấy listen; chưa kiểm tra máy thành viên GamingGear. Thành viên cần code + artifact snapshot + config cùng release + restart backend. Golden40 v6 còn ghim index v2.
- Thêm check_q31_source_fix.py và outputs/q31-source-fix-check-20261022/audit.json, Ket_luan.md. 38 tests đạt sau khi cô lập test legacy khỏi snapshot .env; không sửa production để né lỗi test.
- Phát hiện ingest v4 resume 21:20 dừng ở query tái sử dụng vector vì statement_timeout. Đổi query sang lô 32 content_hash chỉ cho phần thiếu; khởi chạy lại CPU lúc 21:30, log resume-20261022-213043.* và resume-process.json. Không activate/register/default-switch, không tuyên bố ingest hoàn tất.

### [2026-10-22] Chuẩn bị hoàn tất bàn giao corpus-v4, chưa kích hoạt

- Thêm check_corpus_v4.py và npm run check:v4 (chạy trong backend): kiểm tra liên kết release/snapshot/manifest, toàn bộ 7158 chunk, giữ 72096 clean row, không có warning đơn vị; --database chỉ SELECT vector/hash/locator/norm/documents; --runtime thêm registry ACTIVE/FROZEN và config/snapshot đúng release.
- Tạo registration-manifest.proposed.json theo build_manifest, proposed corpus ID 33d33730-0f0a-5274-a7f8-8d32a6be07e8, registered-manifest hash 73f2e87a1cf5cd50a8fec3ee825e8bad211070c9e994b37c45a61ee86c6723c1. Chưa đăng ký. Không nhầm ingest hash với registered manifest hash.
- Audit lần này: offline PASS, DB 5807 chunks hợp lệ, thiếu 1351; chưa đủ một số documents do ingest còn chạy. Công cụ sau đó phân biệt documents chưa ingest với hash thực sự sai.
- 32 tests handoff/snapshot/API/ingest đạt. Chuẩn bị smoke request Q31–Q39 và bsa90, trạng thái draft không coi là approved gold và chưa chạy HTTP nghiệm thu.
- Thêm docs/CORPUS_V4_MEMBER_TEST.md và package_corpus_v4.py: ZIP artifact 21004274 bytes, có checksum/manifest/snapshot/request test và hướng dẫn; không có .env/model/credential, code phải pull riêng. Runtime env chỉ là file đề xuất theo đường dẫn từng máy, không sửa .env thực tế.
- Ingest vẫn chạy bước REUSE_LOOKUP (quan sát 320/1351 hash cần xét), chưa có batch progress mới. Bật watcher wait worker 16684 rồi audit READ ONLY nếu progress đủ 7158 VECTORS_WRITTEN_PENDING_VERIFICATION; chỉ đóng gói lại khi audit đạt, không tự register/activate/default-switch.
- Chưa hoàn thành ingest, API thực tế trên máy clone mới hoặc thay default. Các thao tác Supabase đăng ký/kích hoạt và cấu hình tiếp tục chờ người dùng duyệt sau khi audit đạt.

### [2026-10-22] Nguồn dùng chung theo phiên bản cho corpus-v4 (chưa triển khai DB)

- Theo yêu cầu bỏ phụ thuộc ZIP từng máy: đối chiếu ERD/raw_payloads READ ONLY, xây shared_source.py + source_read_backend opt-in, reader theo index/locator đọc normalized source sections từ raw_payloads, kiểm tra checksum/UUID/root corpus binding/locator/span/content hash, cache trong query. Không fallback local/live khi shared source thiếu hoặc lỗi. Config thực tế vẫn local.
- prepare_shared_source_plan.py không có apply mode; tạo outputs/corpus-v4-shared-source-plan-20261022/source-plan.json và summary.json, 675 source documents + 1 release root = 676 INSERT đề xuất, 15585845 bytes canonical JSON. Schema thật đã SELECT kiểm tra, job_id nullable, 0 URI đã có/0 conflict. Không thêm bảng/cột hoặc chunk_text vào vector.
- Source sections được tạo từ snapshot v4, không giả gọi là original PDF/JSON; vẫn lưu nội dung chữ ở nguồn. Không xóa nguồn đang có corpus lịch sử tham chiếu theo TTL độc lập.
- 7158/7158 reconstruction local đúng hash/locator. 44 tests nguồn chung/snapshot/API/locator đạt; hai client fake DB độc lập không dùng local files; thiếu/sửa nguồn/hash/locator/registration/index/trùng URI đều chặn. Chưa triển khai payload nên chưa test shared-source API/DB thật hoặc máy clone mới.
- Thêm npm run check:sources, docs/CORPUS_V4_SHARED_SOURCES.md; đánh dấu CORPUS_V4_MEMBER_TEST.md hướng ZIP đã bị thay thế; cập nhật HANDOFF_CURRENT.md. Không đổi .env, corpus default hoặc policy citation/units.
- Phần cần duyệt: 676 nguồn mới, register/activate v4 và chuyển SOURCE_READ_BACKEND/default corpus. Không chạy bất kỳ bước ghi nguồn/registration/activation/config nào. Ingest vector đã được duyệt trước vẫn riêng, quan sát REUSE_LOOKUP 704/1351, chưa tuyên bố hoàn tất.

### [2026-10-22] Tận dụng nguồn đã có — thay kế hoạch 676 bản bằng 1 metadata root

- Theo người dùng chọn hướng hạn chế trùng: SELECT audit toàn 675 docs/7158 chunk. 419 BCTC clean dựng từ payload gốc + renderer metadata; 234 tin dựng từ payload gốc (9 bài cần metadata hiển thị cũ); 6 lịch sử giá và 3 chỉ số dựng từ raw bars gốc + indicators thiếu; 13 hồ sơ giữ bộ trường nhỏ của bản cũ.
- 662 tài liệu tái dùng 43 raw_payloads đang tồn tại. Kế hoạch mới reuse-root.proposed.json: 1 bản metadata raw_payloads, 2428715 canonical bytes. Không sao chép giá trị BCTC/nội dung bài/OHLCV. Nhãn/rule deduplicate dùng chung; observation IDs dựng theo công thức đã kiểm chứng.
- Reader shared_source/reused_source xử lý pin payload_id/storedhash/semantic hash, renderer metadata, date membership, full fingerprint và content hash; không phụ thuộc local ZIP và không lấy latest. Chưa bật SOURCE_READ_BACKEND hoặc đổi .env.
- verify_v4_reuse_plan.py: dữ liệu gốc thật SELECT READ ONLY, root/registry mô phỏng local, hai client mới mỗi client dựng chính xác 7158/7158. Chưa phải triển khai API/máy thật. 49 tests related đạt.
- Ngăn tái diễn ở code nhập tương lai: supabase_sink không ép stable overwrite; ingest_market_news_to_supabase dùng digest-version IDs, raw_payload DO NOTHING + readback, xung đột từ chối. Không chạy crawler hoặc ghi payload thật. Cần giữ nguồn được tham chiếu theo retention nhóm chốt; không xóa âm thầm khi vẫn hỗ trợ lịch sử.
- Kế hoạch cũ 676 bản đã đánh dấu SUPERSEDED_DO_NOT_APPLY local. Tài liệu mới docs/CORPUS_V4_REUSE_EXISTING_SOURCES.md; banner thay thế trong docs cũ và HANDOFF_CURRENT. Không ghi nguồn/corpus registry, không activate/default-switch, không git add/commit/push.
