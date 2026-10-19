# History thay đổi code

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
