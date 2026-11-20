# Bàn giao Codex — đợt sửa sau review cuối kế hoạch BCTC metadata (13/11/2026)

> **13/11 09:40 — Codex dừng vì hết token, mới có test đỏ trong `.agent-state/bctc-fixwave-20261113` (BW-FLAG, BW-PDF), chưa sửa file nào trong cây chính. Claude tiếp quản toàn bộ đợt sửa này. Codex KHÔNG tiếp tục trên các file dưới đây trừ khi user giao lại.**

Review cuối của toàn bộ thay đổi (model opus) kết luận **chưa sẵn sàng chạy thật**. File này gom mọi lỗi phải sửa thành một đợt.

Tài liệu gốc:
- spec `docs/superpowers/specs/2026-11-12-bctc-auto-metadata-design.md`;
- plan `docs/superpowers/plans/2026-11-12-bctc-auto-metadata.md`;
- ledger `.superpowers/sdd/2026-11-12-bctc-auto-metadata/progress.md`.

## Ranh giới

- Làm trong cây thư mục chính, nhánh `midterm_demo`. **Không commit, push, stash hay đổi nhánh.**
- Được sửa đúng các file ghi trong từng mục, cùng file test tương ứng. Claude không đụng các file này cho tới khi Codex báo xong.
- **Không đụng** các file của gói price-trend minors đang làm (`trend.py`, `market_research.py`, `activity_store.py`).
- Không kết nối DB thật `127.0.0.1:15433`. DB test `127.0.0.1:15434`. Không gọi mạng. Không khởi động backend.
- TDD cho từng mục: test đỏ trước, sửa sau. Output sạch. Giữ kiểu xuống dòng của từng file.
- User đã chốt: **VERIFIED cần khớp đủ 3 chỉ tiêu.** Không nới điều kiện này.
- Xong thì ghi vào cuối `docs/sprint5/CHECKPOINT-BCTC-CAPTURE-2026-11-12.md` "Codex: fix wave xong", kèm lệnh test và kết quả.

## Phải sửa (Critical / Important)

### 1. [Critical] Áp migration xong là lịch tự chạy `--apply` ngay
`backend/src/market_data/app.py:139-147`. Điều kiện duy nhất để chạy là bảng xác minh đã tồn tại. Nhưng bước chạy thử của Task 10 cần bảng này có trước, vì `current_verification` đọc nó. Vì vậy ngay sau khi áp migration, backend sẽ tự chạy `run(True)` lúc 18:00. Hôm nay 13/11 vẫn trong mùa nộp BCTC (đến 15/11).

Sửa:
- Thêm cờ bật/tắt qua biến môi trường `FINMIND_BCTC_REFRESH`, **mặc định tắt**.
- Khi tắt: không chạy job, `app.state.financial_refresh.reason = 'DISABLED'`, hẹn kiểm lại ở khung lịch kế tiếp, không thử lại sau 30 phút.
- Chỉ chạy khi `FINMIND_BCTC_REFRESH=1` **và** bảng đã tồn tại.
- Sửa luôn comment lỗi thời ở `app.py:146` ("move to a thread if seen"; phần B đã đưa việc nặng ra thread).
- Test: tắt thì không chạy; bật mà thiếu bảng thì `MIGRATION_MISSING`; bật và có bảng thì chạy.
- File: `backend/src/market_data/app.py`, `backend/tests/test_financial_refresh_schedule.py`.

### 2. [Important] Migration thiếu GRANT
Nếu migration được áp bằng một user khác `finmind_team`, chủ bảng sẽ khác, và backend (kết nối bằng `finmind_team`) không INSERT được. Các bảng tài chính hiện có trên VPS cấp quyền `DELETE,INSERT,SELECT,UPDATE` cho `finmind_developer` và `SELECT` cho `finmind_graph_reader`.

Sửa:
- Thêm vào migration và khối tương ứng ở cuối `docker/postgres/init/010_schema.sql`, bọc trong `DO $$ … $$` để bỏ qua role không tồn tại:
  - `GRANT SELECT, INSERT ON public.financial_report_verifications TO finmind_developer`;
  - `GRANT SELECT ON public.financial_report_verifications TO finmind_graph_reader`.
- Không cấp UPDATE, DELETE, TRUNCATE.
- Test: migration chạy trên DB test không có các role này; nếu tạo role trong DB tạm thì kiểm quyền bằng `has_table_privilege`.
- File: `supabase/migrations/20261112000000_financial_report_verifications.sql`, `docker/postgres/init/010_schema.sql`, `backend/tests/test_financial_verification_schema.py`.
- (Claude sẽ ghi vào runbook Task 10: áp migration bằng user `finmind_team`.)

### 3. [Important] `raw_payloads` phình ra mỗi lần chạy dù không có gì mới
Phản hồi Vietcap chứa `"serverDateTime"` thay đổi theo từng lần gọi, nên sha256 lần nào cũng khác. `store_payload` thêm 4 dòng cho mỗi mã mỗi lần chạy, khoảng 11,5 MB mỗi lượt 10 mã. Các dòng này mồ côi, không gắn với báo cáo nào, và làm hỏng bước kiểm "chạy lại không thêm dòng" của Task 10.

Sửa: chỉ gọi `store_payload` cho một section khi `append_reports` thực sự ghi báo cáo mới hoặc phiên bản mới cho section đó. Bản ghi `payload_id` của dòng mới phải trỏ đúng payload đó.

Test:
- `fetch_vietcap` giả trả bytes khác nhau mỗi lần (giống `serverDateTime`) nhưng cùng số liệu;
- chạy lại thì `raw_payloads` không tăng;
- số liệu đổi thì payload được lưu và gắn đúng.

File: `backend/scripts/refresh_financial_statements.py`, `backend/src/financial/verification_store.py` (nếu cần), cùng test của chúng.

### 4. [Important] OCR chạy lại toàn bộ ở mỗi lần chạy, rất tốn máy
`_load` gọi `read_pages` cho mọi PDF trong mọi lượt chạy. Mỗi file OCR 15 trang, tối đa 30. 7/10 mã là bản scan, nên mỗi lượt có thể mất vài giờ, lặp lại hằng ngày trong mùa. Refresh giá lại phải chờ job BCTC xong (phần A).

Sửa:
- Cache kết quả `read_pages` cạnh file PDF, đặt tên theo sha256, ví dụ `<sha256>.pages.json` trong cùng thư mục cache.
- Có cache với đúng sha thì dùng lại. Ngoại lệ `NoTextLayer`/`PdfUnreadable` cũng cache dưới dạng ghi nhận lỗi để không OCR lại.
- Thêm `OMP_THREAD_LIMIT=1` vào env của subprocess tesseract trong `statement_pdf._ocr_page`.

Test:
- lần 2 không gọi `read_pages`;
- sha đổi thì OCR lại;
- `_ocr_page` truyền `OMP_THREAD_LIMIT`.

File: `backend/scripts/refresh_financial_statements.py`, `backend/src/financial/statement_pdf.py`, cùng test.

### 5. [Important] Lỗi OCR làm hỏng cả mã ở mọi lần chạy
`statement_pdf._ocr_page`/`read_pages` để lọt các lỗi `subprocess.CalledProcessError`, `subprocess.TimeoutExpired`, `OSError` (trang hỏng, thiếu dữ liệu tiếng Việt `vie`). Trong khi đó `_load` chỉ bắt `NoTextLayer` và `PdfUnreadable`. Một PDF lỗi vì vậy làm hỏng cả mã, ngày nào cũng hỏng như nhau.

Sửa: trong `read_pages`, bắt các lỗi này và ném `PdfUnreadable`. Test với `_ocr_page` giả ném từng loại lỗi.

File: `backend/src/financial/statement_pdf.py`, `backend/tests/test_statement_pdf.py`.

### 6. [Important] Phía đọc (`health_db` ↔ `health.py`) chưa khớp
Mục này không chặn bước chạy thử, nhưng chặn mục tiêu 4 của spec. Review đã xác nhận bằng cách gọi `analyze_company` trên các dòng có đúng dạng output của `health_db`.

- (a) `currency` vẫn NULL, vì importer cũ và job capture đều ghi NULL, trong khi `health._issues` đòi `currency=='VND'`. Mọi chỉ tiêu tiền vì vậy vẫn `insufficient_data`.
  - Sửa: gán `currency='VND'` cùng chỗ ghi đè `unit` cho dòng đã xác minh đơn vị (`health_db.py:85-89`).
  - Fixture test hiện chèn sẵn `'VND'`, nên che mất lỗi này. Sửa fixture để lấy NULL như dữ liệu thật.
- (b) Dòng bảng cân đối có basis `INSTANT` nhưng `period_start` lại là ngày đầu kỳ. `_window_ok` đòi start == end với INSTANT, nên tỷ số nợ trên tài sản không tính được.
  - Sửa: trong `_merge`, với BALANCE_SHEET thì `period_start = period_end`.
- (c) `RESTATED` vẫn được truyền xuống, mà `health.py` chỉ kiểm hai dòng có cùng giá trị, nên cặp RESTATED/RESTATED vẫn bị so. Spec không cho phép.
  - Sửa: không gộp `comparison_basis` khi giá trị là `RESTATED`.
- Test cho cả 3, dùng `analyze_company` thật: sau khi sửa, chỉ tiêu tiền và tỷ số nợ trên tài sản phải tính được trên dữ liệu đã xác minh.
- File: `backend/src/financial/health_db.py`, `backend/tests/test_financial_health_db.py`.

## Nên sửa trong cùng đợt (Minor đã chọn)

7. **Phạm vi lấy từ tên file mà không có bằng chứng.** `verification.py:194`: khi không tìm thấy chỉ tiêu bắt buộc nào thì ghi `statement_scope='UNKNOWN'`. `citation_for` (`health_db.py`) chỉ trả link khi có `page`.
8. **CMG:** lý do `FISCAL_QUARTER_CALENDAR_ASSUMED` phải chặn VERIFIED (thêm vào nhóm lý do chặn trong `verification.py`).
9. **Chỉ tiêu tùy chọn của ngân hàng.** Nếu chỉ `TOTAL_OPERATING_INCOME` lệch (chỉ tiêu không bắt buộc với BANK), kết quả là PARTIAL với lý do `OPTIONAL_VALUE_MISMATCH`, không phải MISMATCH. MISMATCH chỉ dành cho chỉ tiêu bắt buộc.
10. **`choose()`** (`refresh_financial_statements.py`): khi không có file nào VERIFIED, giữ kết luận có nhiều chỉ tiêu tìm thấy nhất, thay vì luôn lấy file đầu.
11. **Ký tự NUL:** bỏ `\x00` khỏi snippet (`statement_pdf._snippet` hoặc nơi tạo `evidence`), vì jsonb từ chối NUL.
12. **ZIP quá dung lượng:** `ValueError` từ `extract_zip_pdfs` được ghi thành `DOWNLOAD_NOT_PDF` cho file đó, không làm hỏng cả mã.
13. **Chỉ tiêu Vietcap lạ:** không làm hỏng cả mã. Bỏ qua trường đó, ghi vào `report.json` (`unknown_metrics`) và quarantine với `reason_code='UNKNOWN_METRIC'` khi `--apply`.
14. **Chạy thử phải chỉ đọc ở mức kết nối:** khi `apply=False`, kết nối với `server_settings={'default_transaction_read_only': 'on'}`.
15. **Header vector v5 nói quá:** `db_chunking.py` vẫn giữ hậu tố "(đơn vị chưa xác minh)" cho từng dòng có unit `SOURCE_NATIVE`/trống/`VND_PER_SHARE` (ví dụ EPS), kể cả khi báo cáo đã xác minh. Chỉ dòng tiền VND mới bỏ hậu tố. Không đổi văn bản của v1–v4.

## Lệnh test (chạy toàn bộ ở cuối)

`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_financial_verification_schema.py backend/tests/test_vietstock_statements.py backend/tests/test_statement_pdf.py backend/tests/test_financial_verification.py backend/tests/test_financial_verification_store.py backend/tests/test_financial_health_db.py backend/tests/test_financial_health.py backend/tests/test_financial_health_store.py backend/tests/test_financial_peers.py backend/tests/test_financial_statements_refresh.py backend/tests/test_db_chunking_verified.py backend/tests/test_db_chunking.py backend/tests/test_db_chunking_sources.py backend/tests/test_chunk_reconstruction.py backend/tests/test_clean_financial_chunk_edge_cases.py backend/tests/test_chunking.py backend/tests/test_financial_refresh_schedule.py backend/tests/test_market_dual_runtime.py backend/tests/test_price_analysis_api.py backend/tests/test_market_activity_collector.py data_pipeline/annual_reports/tests -q -p no:cacheprovider`

Mốc trước đợt sửa: 306 passed, 1 skipped (chưa tính 22 test PDF/verification Claude thêm sau đó).

## Để sau (không làm trong đợt này)

Các mục review đánh giá có thể để sau, đã ghi trong ledger:
- dọn thư mục `outputs/financial-refresh` (làm trước khi để lịch chạy cả mùa);
- mỗi lượt sinh 2 dòng `ingestion_jobs`/mã;
- không bắt kịp khung lịch bị lỡ;
- `next_run_at` cũ trong lúc đang chạy;
- `--apply` chạy tay trùng lúc với lịch có thể vấp WinError 32 (không hỏng dữ liệu).
