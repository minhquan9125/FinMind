# Bàn giao Codex — 3 phần việc của kế hoạch BCTC metadata (13/11/2026)

Kế hoạch: `docs/superpowers/plans/2026-11-12-bctc-auto-metadata.md`. Spec đã duyệt: `docs/superpowers/specs/2026-11-12-bctc-auto-metadata-design.md`. Ledger: `.superpowers/sdd/2026-11-12-bctc-auto-metadata/progress.md`. Ledger ghi mọi quyết định; mục "Ruling" là ràng buộc.

## Ranh giới chung (cả 3 phần)

- Làm trong cây thư mục chính, nhánh `midterm_demo`. **Không commit, push, stash hay đổi nhánh.**
- Mỗi phần **chỉ** sửa các file ghi trong phần đó. Claude không đụng các file này cho tới khi Codex báo xong.
- Không kết nối DB thật (`127.0.0.1:15433`). Test dùng DB test `127.0.0.1:15434`, user `finmind_test`, qua helper `backend/tests/financial_db_fixture.py`. Nếu DB test chưa chạy:
  `& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" -D "D:\Win\Capstone 1\FinMind\.agent-state\price-flow-postgres\data" -l "D:\Win\Capstone 1\FinMind\.agent-state\price-flow-postgres\server.log" -o "-p 15434" start -w`
- Không gọi mạng trong test. Không khởi động hay restart backend.
- TDD: test đỏ trước, rồi mới sửa. Lệnh test chạy ở gốc repo: `backend\.venv\Scripts\python.exe -m pytest <files> -q -p no:cacheprovider`. Output phải sạch, không có warning.
- Giữ nguyên kiểu xuống dòng của từng file (một số file CRLF, một số LF; kiểm bằng `file`).
- Xong mỗi phần thì thêm 1–2 dòng vào cuối `docs/sprint5/CHECKPOINT-BCTC-CAPTURE-2026-11-12.md`, ghi rõ "Codex: Phần X xong", lệnh test và kết quả.

---

## Phần A — Lịch chạy: không chạy chồng với refresh giá, và test giới hạn thử lại

**File được sửa (chỉ các file này):** `backend/src/market_data/app.py`, `backend/tests/test_financial_refresh_schedule.py`.

**Hiện trạng:** Task 9 đã thêm job BCTC vào vòng `collect()`:
- `FINANCIAL_REFRESH_AT`, `FILING_SEASONS`, `next_financial_refresh`;
- trạng thái lưu ở `app.state.financial_refresh`;
- kiểm `to_regclass` và trả `MIGRATION_MISSING` khi bảng chưa có;
- thử lại tối đa 2 lần, mỗi lần cách 30 phút.

Review chỉ ra hai việc còn thiếu.

**Việc cần làm:**
1. [Important] Hiện chỉ một chiều được chặn: job BCTC chờ refresh giá xong mới chạy, nhưng điều kiện bắt đầu refresh giá (`if mapped and refresh_task is None and now>=refresh_at`) không kiểm `fin_task`. Một lượt refresh giá có thể chạy chồng lên lượt BCTC đang dài.
   - Thêm điều kiện để refresh giá chờ tới khi `fin_task` xong.
   - Test runtime (cùng kiểu test hiện có trong `test_financial_refresh_schedule.py`, đồng hồ giả): khi lượt BCTC đang chạy mà tới giờ refresh giá, refresh giá chỉ bắt đầu sau khi BCTC xong.
2. [Minor] Thêm test giới hạn thử lại:
   - lỗi lần 1 thì hẹn thử lại sau +30 phút;
   - lỗi lần 2 thì lại +30 phút;
   - lỗi lần 3 thì chuyển sang khung lịch chính kế tiếp và đặt lại bộ đếm.

**Lệnh test:** `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_financial_refresh_schedule.py backend/tests/test_market_dual_runtime.py backend/tests/test_price_analysis_api.py backend/tests/test_market_activity_collector.py -q -p no:cacheprovider`. Mốc hiện tại: 39 passed, 1 skipped.

---

## Phần B — Job BCTC không được làm đứng event loop của backend

**File được sửa (chỉ các file này):** `backend/scripts/refresh_financial_statements.py`, `backend/tests/test_financial_statements_refresh.py`.

**Hiện trạng:** scheduler `await refresh_financial_statements.run(...)` ngay trong event loop của backend. Review chỉ ra các thao tác sau chạy thẳng trên loop: đọc file, tính sha256, `statement_pdf.read_pages` (pypdf), đếm trang, `decide`, `report_inputs`. Với khoảng 180 PDF, API và vòng giá 5 giây sẽ bị đứng từng lúc.

**Lượt sửa trước bị ngắt giữa chừng** do agent hết lượt gọi API. Trong file đã có phần sửa **chưa được test**:
- hai hàm `_cached(path)` và `_load(path)` chạy qua `asyncio.to_thread`;
- `decide` và `report_inputs` cũng đã chuyển qua `asyncio.to_thread`;
- file vẫn parse được.

**Việc cần làm:**
1. Đọc phần sửa dở, hoàn thiện nó. Đảm bảo **không còn** thao tác blocking nào trên loop: đọc/ghi/xóa file, sha, pypdf, `decide`. Hành vi phải giữ nguyên; các test refresh hiện có phải pass mà không sửa assertion.
3. [Bổ sung 13/11, thấy khi chạy PDF thật] Với CTG, Vietstock trả về **file ZIP chứa PDF** (byte đầu `PK\x03\x04`), nên hiện bị loại thành `DOWNLOAD_NOT_PDF`. Sửa trong `fetch_pdf`:
   - nếu file tải về là ZIP thì lấy PDF bên trong, dùng `extract_zip_pdfs` có sẵn trong `data_pipeline/annual_reports/vietstock_download_annual.py` (đã chống path traversal);
   - ZIP có đúng 1 PDF thì dùng PDF đó làm file cache;
   - ZIP có nhiều PDF hoặc không có PDF nào thì giữ lý do `DOWNLOAD_NOT_PDF`.
   - Test với một ZIP nhỏ tạo trong test.
2. Thêm test chứng minh loop vẫn phản hồi. Ví dụ: inject `read_pages` chậm (ngủ đồng bộ 0,5 giây) và assert một task asyncio chạy song song vẫn tick được trong lúc `run()` chạy.

**Lệnh test:** `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_financial_statements_refresh.py backend/tests/test_financial_verification_store.py backend/tests/test_financial_verification.py backend/tests/test_statement_pdf.py backend/tests/test_vietstock_statements.py backend/tests/test_financial_health_db.py -q -p no:cacheprovider`. Mốc trước lượt sửa dở: 89 passed.

---

## Phần C — Làm chắc phần ghi DB và migration

**File được sửa (chỉ các file này):**
- `backend/src/financial/verification_store.py`
- `backend/tests/test_financial_verification_store.py`
- `supabase/migrations/20261112000000_financial_report_verifications.sql`
- `docker/postgres/init/010_schema.sql` (chỉ khối của bảng mới ở cuối file)
- `backend/tests/test_financial_verification_schema.py`

**Việc cần làm:**
1. [Minor → nên sửa trước khi chạy thật] `verification_store._period_id` chèn dòng vào `reporting_periods` trước khi lấy advisory lock. Hai lượt ghi chạy song song lần đầu gặp cùng một kỳ mới sẽ vấp `UNIQUE(period_code)` và hỏng transaction.
   - Sửa bằng `INSERT … ON CONFLICT (period_code) DO NOTHING` rồi `SELECT`.
   - Test hai connection cùng thêm một kỳ mới: kết thúc với đúng 1 dòng, không lỗi.
2. [Minor] Bảng `financial_report_verifications` chặn UPDATE và DELETE nhưng chưa chặn TRUNCATE.
   - Thêm trigger `BEFORE TRUNCATE … FOR EACH STATEMENT`, `RAISE EXCEPTION 'append-only'`.
   - Migration phải chạy lại an toàn: `DROP TRIGGER IF EXISTS` rồi `CREATE`.
   - Chép đúng khối đó vào cuối `010_schema.sql`.
   - Test: TRUNCATE ném lỗi có chữ `append-only`; migration chạy 2 lần vẫn đạt.
3. [Cập nhật 13/11 — Claude đã kiểm VPS, chỉ đọc] Trên VPS:
   - PostgreSQL 17.10.
   - Backend kết nối bằng user `finmind_team`, chủ các bảng `financial_reports`, `observations`, `documents`.
   - Các bảng này cấp quyền `DELETE,INSERT,SELECT,UPDATE` cho `finmind_developer` và `SELECT` cho `finmind_graph_reader`.

   Việc cần làm: thêm vào migration (và khối tương ứng trong `010_schema.sql`)
   ```sql
   GRANT SELECT, INSERT ON public.financial_report_verifications TO finmind_developer;
   GRANT SELECT ON public.financial_report_verifications TO finmind_graph_reader;
   ```
   - Không cấp UPDATE, DELETE, TRUNCATE.
   - Bọc trong `DO $$ … $$` để bỏ qua role không tồn tại, vì DB test không có các role này.
   - Test: migration chạy được trên DB test không có role.

   (Ghi chú cũ, giữ để tham khảo:) Kiểm trong `010_schema.sql` xem các bảng khác có GRANT cho role `finmind_*_runtime` không. Nếu có, thêm GRANT `SELECT, INSERT` (không UPDATE/DELETE) cho bảng mới theo đúng mẫu đó, kèm test nếu fixture có role. Nếu không có mẫu thì chỉ ghi lại vào checkpoint.

**Lệnh test:** `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_financial_verification_store.py backend/tests/test_financial_verification_schema.py backend/tests/test_financial_statements_refresh.py backend/tests/test_financial_health_db.py -q -p no:cacheprovider`.

---

## Claude làm gì trong lúc này (không đụng file của A, B, C)

- Kiểm `statement_pdf.py` và `verification.py` trên vài PDF BCTC thật tải từ danh mục Vietstock, chỉ ghi vào cache và `outputs/`, không ghi DB. Nếu phải chỉnh thì chỉ sửa hai file đó và test của chúng.
- Khi Codex báo xong A, B, C: review toàn bộ nhánh, rồi chờ user nói "chạy thật" để làm Task 10 (áp migration lên VPS, đổi trạng thái duyệt nguồn, chạy thử rồi mới `--apply`).
