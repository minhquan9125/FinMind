# Tự lấy và xác minh metadata BCTC — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Một job tự động chạy theo lịch, làm 4 việc:
- thu danh mục BCTC (Vietstock) và số mới (Vietcap);
- xác minh phạm vi, kiểm toán, đơn vị, kỳ, năm tài chính, cơ sở so sánh cho từng báo cáo;
- ghi kết quả vào DB kèm link PDF và số trang, chỉ ghi thêm;
- cho bộ tính BCTC và đoạn vector đọc kết quả đó từ DB.

**Architecture:** Hai lớp.
- **Lớp thuần, không I/O:**
  - `vietstock_statements.py` đọc danh mục;
  - `statement_pdf.py` tìm số và chữ trong PDF;
  - `verification.py` ra kết luận.
- **Lớp DB:**
  - `verification_store.py` ghi;
  - `health_db.py` đọc cho bộ tính;
  - `db_source.py`/`db_chunking.py` đọc cho vector.
- Job `refresh_financial_statements.py` nối hai lớp, chạy tay hoặc qua scheduler sẵn có ở `app.py`.

**Tech Stack:** Python 3.13, asyncpg, requests, pypdf (đã cài), unittest/pytest.

**Spec:** `docs/superpowers/specs/2026-11-12-bctc-auto-metadata-design.md`. Đọc mục "Quyết định của Claude" và "Kết quả kiểm schema thật".

## Global Constraints

- **Tiền điều kiện (Task 0):** các file BCTC của Codex chưa commit (`backend/src/financial/{health,health_store,peers}.py`, `data_pipeline/financial_data/financial_capture.py`, các test `test_financial_*`). Làm trong cây thư mục chính `midterm_demo`, giống lần làm giá. Chỉ tạo file mới hoặc sửa các file liệt kê trong từng task. Không đụng file khác của Codex. Không đụng `backend/src/graph/graph_store.py`.
- **Không commit/push khi user chưa bảo.** Bước "Checkpoint" thay cho commit: thêm 1–3 dòng vào `docs/sprint5/CHECKPOINT-BCTC-CAPTURE-2026-11-12.md`.
- **Chỉ ghi thêm.** Không UPDATE/DELETE `observations`, `financial_reports`, `documents`, `financial_report_verifications`. Ngoại lệ duy nhất là `sources` ở Task 10. Không chạy `import_clean_financials.py --apply`.
- **DB thật** là VPS `127.0.0.1:15433/finmind`. Chỉ Task 10 được ghi, sau khi user nói "chạy thật". Test dùng DB test `127.0.0.1:15434`, user `finmind_test` (khởi bằng `pg_ctl` ở `.agent-state/price-flow-postgres/data`).
- **Số học:** dùng Decimal. So với PDF phải lấy giá trị trong `raw_payloads.payload` (parse bằng `parse_float=Decimal`), **không** lấy `observations.value`: 9.886 tỷ số và 6 EPS ở đó bị nhiễu float.
- **Vietstock:**
  - chỉ gọi `finance.vietstock.vn` và tải từ host đuôi vietstock (`ALLOWED_HOST_SUFFIXES` có sẵn);
  - mỗi request cách nhau ≥ 1 giây;
  - không vượt đăng nhập hay CAPTCHA;
  - User-Agent giữ nguyên kiểu "FinMind … collector/1.0".
- **Phạm vi mặc định:**
  - 10 mã: `VCB, BID, CTG, MBB, TCB, FPT, CMG, ELC, ITD, ICT`;
  - kỳ năm 2024–2025, kỳ quý 2025-Q1 đến quý mới nhất nguồn có.
- **Ngưỡng tổng 4 quý so với năm:** 3%, chỉ tính trên chỉ tiêu dòng tiền trong kỳ: `NET_REVENUE` (ngân hàng `TOTAL_OPERATING_INCOME`) và `PROFIT_AFTER_TAX`. Không dùng `TOTAL_ASSETS`, vì đây là số cuối kỳ, không cộng được.
- **Chỉ tiêu dùng để tìm trong PDF:** `NET_REVENUE` (`isa3`) hoặc `TOTAL_OPERATING_INCOME` (`isb38`) với ngân hàng; `PROFIT_AFTER_TAX` (`isa20`); `TOTAL_ASSETS` (`bsa53`); thêm `OWNERS_EQUITY` (`bsa78`) với ngân hàng.
- **Lịch chạy:**
  - 18:00 giờ VN hằng ngày trong mùa nộp: 15/01–15/02, 15/04–15/05, 15/07–20/08, 15/10–15/11;
  - ngoài mùa: thứ Hai 18:00.
- **Trên web** chỉ hiện tên tài liệu làm chữ của hyperlink, không in URL, không ghi tên Vietstock/Vietcap. Đợt này không làm UI.
- **Ghi vector** (`text_chunks`) cần cờ `--confirmed-with-nhan` có sẵn. Job tự động **không** ghi vector.
- **Lệnh test:** `backend\.venv\Scripts\python.exe -m pytest <file> -q -p no:cacheprovider`, chạy ở gốc repo.

## Review Focus

1. **Chạy lại cùng ngày, không có gì mới.** Kỳ vọng: không thêm dòng `documents`, `financial_reports` hay `financial_report_verifications` nào. Bản xác minh giống hệt bản hiện hành thì bỏ qua. Test ở Task 5.
2. **PDF scan không có lớp chữ, hoặc PDF hỏng.** Kỳ vọng: kết quả `PARTIAL` với lý do `NO_TEXT_LAYER` hoặc `PDF_UNREADABLE`, job chạy tiếp mã khác. Test ở Task 3.
3. **Số trong PDF ghi theo triệu đồng đã làm tròn** (ví dụ `23.259.126` cho `23.259.126.277.266`), hoặc số âm ghi trong ngoặc `(212.582)`. Kỳ vọng: vẫn tìm thấy. Test ở Task 3.
4. **Tên file lạ:** "BCTC Riêng lẻ" của ngân hàng, tên tiếng Anh, thiếu chữ "Hợp nhất/Công ty mẹ", hoặc một kỳ có 0 hay hơn 2 file. Kỳ vọng: phạm vi `UNKNOWN`, không đoán; kỳ có nhiều file cùng phạm vi thì lấy `LastUpdate` mới nhất. Test ở Task 2.
5. **Mạng hỏng hoặc token hết hạn giữa chừng.** Kỳ vọng: mã đó ghi lỗi vào báo cáo; các mã đã xong vẫn giữ (mỗi mã một transaction); exit 1 để scheduler thử lại sau 30 phút. Test ở Task 7.

---

### Task 1: Bảng `financial_report_verifications`

**Files:**
- Create: `supabase/migrations/20261112000000_financial_report_verifications.sql`
- Modify: `docker/postgres/init/010_schema.sql` (thêm đúng khối của migration ở cuối file)
- Test: `backend/tests/test_financial_verification_schema.py`

**Interfaces:**
- Produces: bảng `public.financial_report_verifications`, gồm:
  - các cột theo spec;
  - thêm `comparison_basis varchar(20)`, `fiscal_label_convention varchar(20)`;
  - `fiscal_year_end varchar(5)` dạng `MM-DD`;
  - FK tới `financial_reports(report_id)`, `documents(document_id)`, `ingestion_jobs(job_id)`, và tự trỏ qua `supersedes_id`;
  - index `(report_id, verified_at DESC)`;
  - trigger `financial_report_verifications_append_only` chặn UPDATE và DELETE bằng `RAISE EXCEPTION 'append-only'`.

- [ ] **Step 1:** Viết test `test_migration_creates_append_only_table`, chạy trên DB test 15434 trong database tạm.
  - Tạo tối thiểu các bảng `financial_reports(report_id uuid pk)`, `documents(document_id uuid pk)`, `ingestion_jobs(job_id uuid pk)`, rồi chạy file migration.
  - Assert INSERT một dòng đạt.
  - Assert `UPDATE … SET status='X'` ném `asyncpg.RaiseError` có chữ `append-only`; DELETE cũng vậy.
  - Assert `status` ngoài `('VERIFIED','PARTIAL','MISMATCH')` bị CHECK chặn.
- [ ] **Step 2:** Chạy test. Kỳ vọng FAIL: file migration chưa có.
- [ ] **Step 3:** Viết migration. Dùng `CREATE TABLE IF NOT EXISTS` để chạy lại an toàn. Các CHECK cho `statement_scope`, `audit_status`, `period_basis`, `status`, `comparison_basis` lấy đúng giá trị liệt kê trong spec.
- [ ] **Step 4:** Chạy test. Kỳ vọng PASS.
- [ ] **Step 5:** Checkpoint.

### Task 2: Danh mục BCTC Vietstock

**Files:**
- Modify: `data_pipeline/annual_reports/vietstock_download_annual.py`. Tách `annual_report_type()` thành `document_type(match_vi: str, match_en: str) -> int`. `annual_report_type()` gọi lại hàm này với `"thường niên"`/`"annual report"`. Thêm tham số `document_type_id: int | None = None` cho `report_years` và `reports_for`. Hành vi cũ giữ nguyên.
- Create: `data_pipeline/financial_data/vietstock_statements.py`
- Create: `backend/tests/fixtures/vietstock_fpt_2025_statements.json` (dữ liệu dạng `getrptfile` như kết quả probe ngày 12/11: 2 file mỗi kỳ, `Title`/`FullName`/`Url`/`LastUpdate`/`FileInfoID`)
- Test: `backend/tests/test_vietstock_statements.py`

**Interfaces:**
- Produces:
  - `TERM_PERIOD = {1: 'YEAR', 2: 'Q1', 3: 'Q2', 4: 'Q3', 5: 'Q4'}`. Các term 9 (6T) và 12 (9T) bị bỏ qua.
  - `parse_title(title: str) -> dict(scope: str, audit_status: str)`.
  - `catalog_entries(rows: list[dict], *, symbol: str, year: int, term_id: int) -> list[dict]`. Mỗi phần tử có các khóa: `symbol, period_code ('2025-YEAR'|'2025-Q3'), scope, audit_status, title, url, external_id, last_update (datetime UTC)`.
  - `fetch_catalog(client, symbol: str, years: list[int]) -> list[dict]`.
  - `period_code` cùng dạng với `reporting_periods.period_code` (`YYYY-YEAR`, `YYYY-Qn`).

- [ ] **Step 1:** Viết test.
  - `test_parse_title`: `"BCTC Hợp nhất Kiểm toán năm 2025"` thành `('CONSOLIDATED','AUDITED')`; `"BCTC Công ty mẹ quý 1 năm 2025"` thành `('SEPARATE','NOT_STATED')`; `"BCTC Riêng lẻ Soát xét 6 tháng"` thành `('SEPARATE','REVIEWED')`; `"Financial statements Q3"` thành `('UNKNOWN','NOT_STATED')`.
  - `test_catalog_entries_from_fixture`: FPT 2025 term 4 cho ra 2 phần tử `2025-Q3`, một `CONSOLIDATED`, một `SEPARATE`; url bắt đầu bằng `https://static2.vietstock.vn/`; `last_update` parse từ `/Date(1761275715630)/`.
  - `test_duplicate_scope_keeps_latest`: hai file cùng phạm vi thì giữ `LastUpdate` lớn hơn.
  - `test_rejects_non_vietstock_url`: url ngoài vietstock thì phần tử bị loại, dùng `allowed_file_url` có sẵn.
  - `test_annual_report_type_unchanged`: client giả trả danh sách type, `annual_report_type()` vẫn ra 2.
- [ ] **Step 2:** Chạy test. Kỳ vọng FAIL.
- [ ] **Step 3:** Viết code. `parse_title` so khớp sau khi bỏ dấu và lower-case.
- [ ] **Step 4:** Chạy test `test_vietstock_statements.py` và `data_pipeline/annual_reports/tests`. Kỳ vọng PASS.
- [ ] **Step 5:** Checkpoint.

### Task 3: Đọc bằng chứng từ PDF

**Files:**
- Create: `backend/src/financial/statement_pdf.py`
- Test: `backend/tests/test_statement_pdf.py`

**Interfaces:**
- Produces:
  - `read_pages(data: bytes) -> list[str]`. Đọc bằng `pypdf.PdfReader`. Ném `NoTextLayer` khi tổng chữ dưới 200 ký tự, ném `PdfUnreadable` khi pypdf lỗi.
  - `find_value(pages: list[str], value: Decimal) -> list[dict(page: int, unit: 'VND'|'MILLION_VND', snippet: str)]`. Số trang bắt đầu từ 1. `snippet` dài tối đa 160 ký tự quanh số.
  - `page_unit(text: str) -> 'VND'|'MILLION_VND'|None`.
  - `fiscal_year_end(pages: list[str]) -> tuple[str, int] | None`, trả `('03-31', 2026)`.
  - `prior_column_value(pages: list[str], value: Decimal) -> bool`. Trả True khi giá trị kỳ trước xuất hiện.

- [ ] **Step 1:** Viết test trên chuỗi chữ giả lập trang PDF.
  - `test_find_value_vnd`: trang có `"23.259.126.277.266"` thì tìm ra `unit='VND'`, `page=1`.
  - `test_find_value_million_rounded`: `Decimal('23259126777266')` khớp `"23.259.127"` (làm tròn half-up) và cũng khớp `"23.259.126"` (cắt bỏ). Cả hai cho `unit='MILLION_VND'`.
  - `test_find_value_negative_parentheses`: `Decimal('-212582739626')` khớp `"(212.582.739.626)"` và `"(212.583)"`.
  - `test_find_value_no_false_hit`: `"123.259.126.277.2660"` không khớp, vì có ranh giới số.
  - `test_page_unit`: `"Đơn vị tính: VND"` ra `VND`; `"Đơn vị: triệu đồng"` ra `MILLION_VND`; `"Đơn vị tính: Đồng Việt Nam"` ra `VND`.
  - `test_fiscal_year_end`: `"cho năm tài chính kết thúc ngày 31 tháng 3 năm 2026"` và `"kết thúc ngày 31/03/2026"` đều ra `('03-31', 2026)`.
  - `test_no_text_layer_raises`: `read_pages` với PDF 1 trang trắng (tạo bằng `pypdf.PdfWriter().add_blank_page`) ném `NoTextLayer`.
  - `test_garbage_raises`: `read_pages(b'not a pdf')` ném `PdfUnreadable`.
- [ ] **Step 2:** Chạy test. Kỳ vọng FAIL.
- [ ] **Step 3:** Viết code. Số trong PDF tìm bằng regex các cụm chữ số có dấu chấm phân cách nghìn, chuẩn hóa về Decimal rồi so. Không so chuỗi thô.
- [ ] **Step 4:** Chạy test. Kỳ vọng PASS.
- [ ] **Step 5:** Checkpoint.

### Task 4: Kết luận xác minh, logic thuần

**Files:**
- Create: `backend/src/financial/verification.py`
- Test: `backend/tests/test_financial_verification.py`

**Interfaces:**
- Consumes: kết quả của `find_value`, `page_unit`, `fiscal_year_end`, `prior_column_value` (Task 3); `scope`, `audit_status` (Task 2).
- Produces:
  - `quarter_basis(year: dict[str, Decimal], quarters: dict[int, dict[str, Decimal]]) -> 'STANDALONE_QUARTER'|'UNKNOWN'`. Đủ 4 quý, và mọi chỉ tiêu có trong `year` lệch ≤ 3% (so với giá trị tuyệt đối của số năm), thì là quý riêng.
  - `fiscal_label_convention(year_report: int, end_month_day: str|None, end_year: int|None) -> 'CALENDAR'|'END_YEAR'|'START_YEAR'|'UNKNOWN'`.
  - `decide(report: dict, evidence: dict) -> dict`. Trả về đủ cột của bảng (trừ id, job, thời điểm), và `checks`, `evidence`, `status`, `reason_codes: list[str]`.
    - `report` có: `period_code, section, industry, values {metric_code: Decimal}, prior_values {metric_code: Decimal}|None, quarter_basis`.
    - `evidence` có: `document {scope, audit_status, title, url, document_id}`, `pages` (list[str] hoặc lỗi), `fiscal_end`.
  - `same_conclusion(a: dict, b: dict) -> bool`. So các cột kết luận, bỏ qua `verified_at`, `verification_id`, `job_id`, `supersedes_id`.

- [ ] **Step 1:** Viết test.
  - `test_quarter_basis_fpt_like`: dữ liệu giống FPT 2024 (lệch 0%) ra `STANDALONE_QUARTER`.
  - `test_quarter_basis_ytd_like`: quý là lũy kế (tổng ≈ 2,5× năm) ra `UNKNOWN`.
  - `test_quarter_basis_missing_quarter_unknown`.
  - `test_fiscal_label_convention`: `(2025, '12-31', 2025)` ra `CALENDAR`; `(2025, '03-31', 2025)` ra `END_YEAR`; `(2025, '03-31', 2026)` ra `START_YEAR`; `(2025, None, None)` ra `UNKNOWN`.
  - `test_decide_verified`: đủ 3 giá trị tìm thấy trên trang `MILLION_VND`, `page_unit` khớp, PDF `CONSOLIDATED`. Ra `status='VERIFIED'`, `unit='VND'`, `unit_status='VERIFIED'`, và `evidence` có 3 trang.
  - `test_decide_not_found_is_partial_not_mismatch`: giá trị không có trong PDF thì ra `PARTIAL`, có reason `VALUE_NOT_FOUND`.
  - `test_decide_mismatch_only_when_label_found_with_other_number`: tìm thấy nhãn "Lợi nhuận sau thuế" và một số khác trên cùng dòng thì ra `MISMATCH`.
  - `test_decide_bank_uses_profit_assets_equity`: ngân hàng không có `TOTAL_OPERATING_INCOME` trong PDF nhưng có 3 chỉ tiêu kia, ra `VERIFIED`.
  - `test_decide_no_text_layer_partial`: ra `PARTIAL` với reason `NO_TEXT_LAYER`.
  - `test_comparison_basis`: `prior_column_value` True ra `AS_REPORTED`; nhãn có mà số khác ra `RESTATED`; không có PDF ra `UNKNOWN`.
  - `test_same_conclusion_ignores_ids_and_time`.
- [ ] **Step 2:** Chạy test. Kỳ vọng FAIL.
- [ ] **Step 3:** Viết code. Hàm thuần, không I/O.
- [ ] **Step 4:** Chạy test. Kỳ vọng PASS.
- [ ] **Step 5:** Checkpoint.

### Task 5: Ghi DB chỉ thêm

**Files:**
- Create: `backend/src/financial/verification_store.py`
- Test: `backend/tests/test_financial_verification_store.py` (DB test 15434; schema dựng từ `010_schema.sql` cộng migration Task 1; nếu `010_schema.sql` cần extension `vector` mà DB test không có thì bỏ qua `text_chunks`)

**Interfaces:**
- Produces, tất cả `async`, nhận `conn` đang trong transaction:
  - `ensure_source(conn, name: str, *, source_type: str, base_url: str) -> UUID`. Chỉ INSERT khi chưa có, không đổi `approval_status`.
  - `start_job(conn, source_id) -> UUID` và `finish_job(conn, job_id, *, ok: int, quarantined: int, status: str)`.
  - `store_payload(conn, job_id, *, source_uri: str, payload_text: str) -> UUID`. `sha256` tính trên bytes UTF-8 của `payload_text`. Trùng `source_uri` và `sha256` thì trả id cũ.
  - `ensure_document(conn, entry: dict, *, company_id, period_id, job_id, sha256: str, page_count: int, file_size: int) -> UUID`. `doc_type='FINANCIAL_STATEMENT'`, `file_type='PDF'`. Trùng `sha256` thì trả id cũ (`ON CONFLICT (sha256) DO NOTHING` rồi SELECT).
  - `current_verification(conn, report_id) -> dict | None`.
  - `append_verification(conn, report_id, job_id, conclusion: dict) -> UUID | None`. Trả None, không ghi, khi `same_conclusion` với bản hiện hành. Ngược lại INSERT với `supersedes_id` là bản hiện hành.
  - `append_reports(conn, records: list[dict], *, job_id, payload_id) -> dict(new_reports: int, new_versions: int, unchanged: int)`. `records` là output đã chuẩn hóa của `financial_capture`. Quy tắc:
    - kỳ chưa có trong `reporting_periods` thì thêm, theo cùng dạng `period_code` và ngày dương lịch như các dòng hiện có;
    - chưa có (company, period, section) thì thêm `report_version=1`;
    - có, và mọi giá trị trùng bản mới nhất thì `unchanged`;
    - khác thì thêm `report_version` + 1 với `restated_from_id`.
    - Observations mới dùng `metric_id` theo `metrics.code`, `locator_json` cùng 4 khóa cũ (`dataset_version, ratio_type, source_field, source_section`).
  - `quarantine(conn, job_id, *, payload_id, reason_code: str, reasons: dict)`.

- [ ] **Step 1:** Viết test.
  - `test_append_verification_idempotent`: gọi 2 lần cùng kết luận thì chỉ 1 dòng.
  - `test_append_verification_supersedes`: kết luận khác thì có dòng 2, `supersedes_id` bằng id dòng 1, dòng 1 không đổi.
  - `test_ensure_document_same_sha_reuses_row`.
  - `test_append_reports_new_period_and_restatement`: kỳ mới thì `new_reports=1`; giá trị đổi thì `new_versions=1` với `restated_from_id` đúng; chạy lại thì `unchanged`. Đếm `observations` cũ không đổi.
  - `test_ensure_source_does_not_change_approval`.
- [ ] **Step 2:** Chạy test. Kỳ vọng FAIL.
- [ ] **Step 3:** Viết code.
- [ ] **Step 4:** Chạy test. Kỳ vọng PASS.
- [ ] **Step 5:** Checkpoint.

### Task 6: Bộ tính đọc từ DB và hàm link trích dẫn

**Files:**
- Create: `backend/src/financial/health_db.py`
- Modify: `backend/scripts/report_financial_health.py`. Thêm `--from-db`: đọc qua `fetch_health_records` với kết nối chỉ đọc (`default_transaction_read_only`). Cách cũ đọc file giữ nguyên.
- Test: `backend/tests/test_financial_health_db.py`

**Interfaces:**
- Consumes: bảng Task 1; `canonical_rows` (`health_store.py`, không sửa).
- Produces:
  - `fetch_health_records(conn, symbols: list[str]) -> list[dict]`.
    - Mỗi dòng có đủ khóa mà `canonical_rows` đọc: `symbol, industry_type, section, code, period_code, value, unit, scale, currency, locator_json, published_at, observation_id, payload_id, source_name, source_uri, sha256, approval_status, report_id, report_version, restated_from_id`.
    - `value` lấy từ payload thô khi tìm được, không lấy từ float.
    - `locator_json` = locator cũ gộp với bản xác minh hiện hành: `unit_status, period_basis, statement_scope, comparison_basis, fiscal_year_end, fiscal_label_convention, period_start, period_end`.
    - Ánh xạ kỳ: `ANNUAL` thành `YEAR`, `STANDALONE_QUARTER` thành `QUARTER`. Chỉ tiêu `BALANCE_SHEET` luôn là `INSTANT`.
    - Trường có phép kiểm riêng chưa đạt thì không gộp, để bộ tính tự loại.
    - Chỉ lấy `report_version` mới nhất của mỗi (company, period, section).
  - `citation_for(conn, observation_id: UUID) -> dict(title: str, url: str, page: int|None) | None`. Đi theo observation, report, bản xác minh hiện hành, rồi `documents`. `page` lấy từ `evidence` của đúng chỉ tiêu nếu có.

- [ ] **Step 1:** Viết test trên DB test.
  - `test_records_merge_current_verification`: cho ra `unit_status='VERIFIED'`, `period_basis='QUARTER'`, `statement_scope='CONSOLIDATED'`.
  - `test_balance_sheet_is_instant`.
  - `test_unverified_report_keeps_unknown`: `canonical_rows` cho `unit='UNKNOWN'`.
  - `test_value_from_payload_not_float`: payload `0.4194328993`, observation có nhiễu float; record ra `Decimal('0.4194328993')`.
  - `test_latest_version_only`.
  - `test_citation_for`: trả title, url, page đúng; report chưa xác minh thì trả None.
  - `test_report_from_db_cli_readonly`: `main(['--from-db', ...])` với DB test ra `analyses` cho mã có dữ liệu.
- [ ] **Step 2:** Chạy test. Kỳ vọng FAIL.
- [ ] **Step 3:** Viết code.
- [ ] **Step 4:** Chạy test, cộng `test_financial_health*.py` cũ. Kỳ vọng PASS hết.
- [ ] **Step 5:** Checkpoint.

### Task 7: Job `refresh_financial_statements.py`

**Files:**
- Create: `backend/scripts/refresh_financial_statements.py`
- Test: `backend/tests/test_financial_statements_refresh.py`

**Interfaces:**
- Consumes: Task 2–6; `capture_financial` (`financial_capture.py`, không sửa; alias ICT→CTIN có sẵn).
- Produces:
  - `SYMBOLS` (10 mã), `ANNUAL_YEARS = (2024, 2025)`, `QUARTER_FROM = '2025-Q1'`.
  - `async run(apply: bool, *, now: datetime, symbols=SYMBOLS, fetch_vietcap=None, vietstock=None, download=None, connect=None, on_report=None) -> int`.
    - Trả 0 khi mọi mã xong, 1 khi có mã lỗi.
    - `fetch_vietcap`, `vietstock`, `download`, `connect` là các điểm thay thế cho test.
    - Mặc định `apply=False`: không ghi DB, chỉ ghi báo cáo.
  - Báo cáo `outputs/financial-refresh/<YYYYmmdd-HHMMSS-ffffff>/report.json` có các khóa: `started_at, apply, symbols {SYM: {status, new_reports, new_versions, verifications_added, verified, partial, mismatch, error}}, documents_added`.
  - PDF lưu cache ở `data/references/vietstock/financial_statements/files/<SYM>/<period_code>/<external_id>.pdf`. Cache có sẵn thì kiểm `sha256` với `documents`; lệch thì tải lại.
  - CLI: `--apply`, `--symbols`. Mặc định chạy thử.
- Thứ tự cho mỗi mã, trong 1 transaction:
  1. Vietcap: `store_payload`, rồi `append_reports`.
  2. Vietstock: `fetch_catalog`.
  3. Mỗi kỳ trong phạm vi: tải PDF hợp nhất trước, rồi `ensure_document`.
  4. Gọi `decide`. Số không khớp file hợp nhất thì thử file riêng.
  5. `append_verification`. Kết quả `MISMATCH` thì gọi thêm `quarantine`.

- [ ] **Step 1:** Viết test với Vietcap, Vietstock, tải file giả và DB test.
  - `test_dry_run_writes_nothing`: đếm dòng các bảng không đổi; `report.json` có đủ 10 mã.
  - `test_apply_then_rerun_adds_nothing`: lần 2 có `verifications_added=0`, `documents_added=0`, `new_reports=0`.
  - `test_network_error_isolated_per_symbol`: `vietstock` ném lỗi với BID thì BID có `status='failed'`, FPT vẫn có dòng ghi, `run` trả 1.
  - `test_unscanned_pdf_partial`: PDF trắng thì có dòng xác minh `PARTIAL` với reason `NO_TEXT_LAYER`.
  - `test_cache_sha_mismatch_redownloads`.
- [ ] **Step 2:** Chạy test. Kỳ vọng FAIL.
- [ ] **Step 3:** Viết code.
- [ ] **Step 4:** Chạy test. Kỳ vọng PASS.
- [ ] **Step 5:** Checkpoint.

### Task 8: Đoạn vector có link (renderer `db-financial-v5`)

**Files:**
- Modify: `backend/src/documents/db_chunking.py`:
  - thêm `FINANCIAL_VERIFIED_RENDERER_VERSION = "db-financial-v5"` vào `FINANCIAL_RENDERER_VERSIONS`;
  - header theo bản xác minh;
  - thêm các khóa `verification_id`, `url`, `source_title`, `source_page` vào danh sách khóa `doc.meta` được chép sang `locator`.
- Modify: `backend/src/documents/db_source.py`:
  - thêm `FINANCIAL_VERIFIED_SQL`: `FINANCIAL_SQL` cộng `LEFT JOIN LATERAL` lấy bản xác minh hiện hành và `documents`;
  - `fetch_locator_document` với v5 chọn **đúng** `verification_id` ghi trong locator, không lấy bản mới nhất, để dựng lại đoạn cũ vẫn khớp hash.
- Modify: `backend/scripts/chunk_from_supabase.py`: thêm `--financial-renderer` (mặc định giữ như hiện nay). Cờ `--apply --confirmed-with-nhan` giữ nguyên.
- Test: `backend/tests/test_db_chunking_verified.py`

**Interfaces:**
- Header v5 khi `status='VERIFIED'`:
  `"{company} ({symbol}) | {section_vi} | {period_text} | Phạm vi: {Hợp nhất|Riêng} (đã xác minh) | Đơn vị: VND (đã xác minh) | Nguồn: {title}"`.
- Header khi chưa xác minh: giữ đúng câu của v3, có `"đơn vị nguồn chưa xác minh"`.

- [ ] **Step 1:** Viết test thuần trên các dòng giả.
  - `test_v5_header_verified`.
  - `test_v5_unverified_matches_v3_wording`.
  - `test_v5_locator_has_link`: `locator` có `url`, `source_title`, `verification_id`.
  - `test_v3_output_unchanged`: snapshot `chunk_id` của v3 trước và sau sửa giống nhau.
  - `test_locator_document_pins_verification`: với DB test, thêm bản xác minh mới thì dựng lại đoạn cũ vẫn ra đúng `content_hash` cũ.
- [ ] **Step 2:** Chạy test. Kỳ vọng FAIL.
- [ ] **Step 3:** Viết code.
- [ ] **Step 4:** Chạy test, cộng các test chunking cũ (`test_db_chunking*.py`, `test_clean_financial_chunk_edge_cases.py`). Kỳ vọng PASS hết.
- [ ] **Step 5:** Checkpoint.

### Task 9: Lịch chạy trong backend

**Files:**
- Modify: `backend/src/market_data/app.py`:
  - `FINANCIAL_REFRESH_AT = dt_time(18, 0)`;
  - `FILING_SEASONS = ((1,15,2,15),(4,15,5,15),(7,15,8,20),(10,15,11,15))`;
  - hàm `next_financial_refresh(now) -> datetime`;
  - một nhánh mới trong vòng `collect()` giống `daily_refresh`: gọi `refresh_financial_statements.run(True, now=now)`; lỗi thì thử lại sau `REFRESH_RETRY`; trạng thái ở `app.state.financial_refresh` (`last_run_at, last_ok, next_run_at`).
- Modify: `backend/src/api/routers/market_data.py`: `/live/status` thêm `financial_refresh`.
- Test: `backend/tests/test_financial_refresh_schedule.py`

- [ ] **Step 1:** Viết test cho `next_financial_refresh`.
  - 12/11/2026 17:00 (trong mùa) ra 12/11 18:00.
  - 12/11 18:30 ra 13/11 18:00.
  - 16/11/2026 (ngoài mùa, thứ Hai) 10:00 ra 16/11 18:00.
  - 17/11 (thứ Ba) ra thứ Hai 23/11 18:00.
  - 14/01 19:00 ra 15/01 18:00, ngày đầu mùa.
  - `test_status_includes_financial_refresh`.
- [ ] **Step 2:** Chạy test. Kỳ vọng FAIL.
- [ ] **Step 3:** Viết code. Job BCTC không chạy cùng lúc refresh giá: chờ `refresh_task` xong mới chạy.
- [ ] **Step 4:** Chạy test, cộng `test_market_dual_runtime.py`, `test_price_analysis_api.py`. Kỳ vọng PASS.
- [ ] **Step 5:** Checkpoint.

### Task 10: Chạy thật trên VPS (chỉ sau khi user nói "chạy thật")

- [ ] **Step 1:** Áp migration Task 1 lên VPS trong 1 transaction. Kiểm bảng và trigger có trên VPS.
- [ ] **Step 2:** Cập nhật `sources`.
  - VIETCAP_VCI: `approval_status='APPROVED'`, `approved_at=now()`, `scope_note` ghi "User cho phép dùng ngày 12/11/2026 cho BCTC".
  - Thêm nguồn "Vietstock BCTC" (`source_type='FINANCIAL_DOCUMENT'`, `APPROVED`), cùng ghi chú.
  - Không đổi ENTRADE, vnstock_kbs.
- [ ] **Step 3:** Chạy `refresh_financial_statements.py` không `--apply`. Đọc `report.json`: đủ 10 mã, và số kỳ cần xác minh khoảng 9 kỳ mỗi mã.
- [ ] **Step 4:** Chạy `--apply`. Đếm:
  - `observations` cũ vẫn là 308.546 dòng;
  - số dòng mới trong `financial_reports` (kỳ 2026-Q3);
  - số `VERIFIED`, `PARTIAL`, `MISMATCH`.
  Chạy lại `--apply` lần 2 thì không thêm dòng nào.
- [ ] **Step 5:** Chạy `report_financial_health.py --from-db`. Ghi số chỉ tiêu không còn `insufficient_data`.
- [ ] **Step 6:** Đoạn vector: `chunk_from_supabase.py --source financial --financial-renderer db-financial-v5 --out <file>` để xem trước, không ghi DB. Chỉ chạy `--apply --confirmed-with-nhan` khi Nhân đồng ý.
- [ ] **Step 7:** Checkpoint kèm các con số. Báo user.
