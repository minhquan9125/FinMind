# Checkpoint — Watchlist, danh mục & BCTC doanh nghiệp (17/11/2026)

Nhánh `feature/bctc-health-chat`, đã fast-forward lên `origin/backup-demo` (`1fca08df`). **Chưa commit** mọi thay đổi dưới đây.

## Đã làm

### 1. Rà bảng DB (DB VPS qua tunnel `127.0.0.1:15433`)
- 70 bảng. 25 bảng theo ERD có 0 dòng và không có code dùng (`audit_logs`, `system_configs`, `config_versions`, `golden_*`, `evaluation_*`, `queries`, `query_companies`, `answers`, `claims`, `claim_verifications`, `citations`, `retrieval_results`, `usage_events`, `gate_decisions`, `gate_decision_evidence`, `reason_codes`, `calc_inputs`, `metric_aliases`, `permissions`, `role_permissions`).
- Audit, traces, evaluation, limits và budget của admin lưu ở SQLite/file trong `admin_ingestion_directory`, không dùng các bảng trên.
- VPS **thiếu** `public.admin_serving_corpus`: `docker/postgres/init/095_admin_serving_corpus.sql` chưa chạy. Khi đổi corpus đang phục vụ, lựa chọn không được lưu xuống DB, mất sau khi restart. Lỗi bị nuốt nên UI không báo gì.
- `annual_reports` (20 dòng) và `annual_report_pages` (2749 dòng) có trên VPS nhưng không có migration trong repo và không có câu SQL nào trong code.

### 2. Watchlist theo tài khoản
- API `GET /api/watchlist`, `PUT|DELETE /api/watchlist/{symbol}` ([watchlist.py](../../backend/src/api/routers/watchlist.py)). Mọi truy vấn lọc theo user đăng nhập. Vai trò: `READ_ROLES`.
- Trang `/watchlist`, khung watchlist trên dashboard và nút "Theo dõi" ở trang công ty đều đọc/ghi API. Bỏ `localStorage` và `pages/watchlist/mock.js`.

### 3. Xoá bảng `feedback`
- Migration [20261117000000_watchlists_drop_feedback.sql](../../supabase/migrations/20261117000000_watchlists_drop_feedback.sql) **đã chạy trên VPS**:
  - Xoá `feedback`.
  - Đặt `watchlists.pinned_at` mặc định `now()`.
  - Cấp quyền cho `finmind_app_runtime` nếu DB có role đó.
- Đã bỏ `feedback` khỏi `docker/postgres/init/010_schema.sql`.
- Xoá code chết của phần đánh giá câu trả lời trong `ResearchPage.jsx` và `research/mock.js`. Nút này chưa từng hiện trên UI.

### 4. Danh mục & BCTC doanh nghiệp (thay mock)
- [company_facts.py](../../backend/src/financial/company_facts.py) và router `GET /api/companies`, `GET /api/companies/{symbol}` ([companies.py](../../backend/src/api/routers/companies.py)).
- Mỗi kỳ lấy version báo cáo mới nhất, gồm các chỉ tiêu:
  - Tổng tài sản, nợ, vốn chủ.
  - Doanh thu: `NET_REVENUE`; ngân hàng dùng `TOTAL_OPERATING_INCOME`.
  - LNST, ROE, ROA.
  - Tăng trưởng doanh thu so với cùng kỳ: chỉ tính khi hai kỳ cùng đơn vị.
- Trạng thái đối chiếu lấy từ `financial_report_verifications`; ROE/ROA không tính vào trạng thái vì chưa đối chiếu PDF. API trả kèm link PDF BCTC gốc.
- FE dùng chung [financials.js](../../frontend/src/pages/companies/financials.js):
  - `/companies`: 34 công ty thật.
  - `/companies/:ticker`: tab Tài chính chọn kỳ thật; tab Báo cáo có link PDF. Bỏ `detailMock.js`.
  - `/research`, tab so sánh: số liệu thật kèm link "BCTC gốc". Bỏ drawer nguồn giả.
  - Ô tìm kiếm trên dashboard.
- Link cũ dạng `period=FY2025` / `Q2/2026` vẫn chạy (`toPeriodCode`).
- Sidebar trang `/companies` lấy profile thật, đăng xuất gọi `logout()`.

## Kiểm tra
- Test mới:
  - Backend: `test_watchlist_api.py` và `test_company_facts.py`, 9/9 pass.
  - FE: `watchlist/api.test.js`, `companies/financials.test.js`. FE liên quan 42/42 pass. `vite build` OK.
- Smoke test trên VPS:
  - Follow rồi unfollow FPT đúng. `watchlists` còn 0 dòng.
  - `/api/companies` trả 34 công ty. FPT có 43 kỳ và 9 PDF. ACB có 0 kỳ. Mã lạ trả 404.
- Toàn bộ backend: chạy trong `backend/` được 3507 pass.
  - 16 fail và 36 lỗi collect đều có sẵn từ trước, không do thay đổi này.
  - Lỗi collect `No module named 'backend'` là do chạy từ `backend/`. Chạy từ thư mục gốc thì collect được, nhưng 64 test fail vì cụm Postgres test `127.0.0.1:15434` chưa bật (108 lần `ConnectionRefusedError`).
  - Các lỗi còn lại: thiếu `openpyxl` (`test_s5_router_acceptance`) và thiếu file `backend/resources/person_role/wbs02-r2/examples/*.json` (`test_wbs02_person_identity_integration`).
- **Chưa kiểm:**
  - Chưa mở trình duyệt chạy thử giao diện.
  - Chưa chạy được `test_financial_verification_schema` (cần cụm 15434). Test này nạp `010_schema.sql` vừa bị sửa.

## Cần quyết / việc còn lại
1. **Đơn vị kỳ 2026-Q3.** Bản nhập mới để tiền ở `SOURCE_NATIVE` thay vì `VND`. Hiện UI hiện số đầy đủ kèm "(đơn vị theo nguồn)". Kỳ mới nhất của mọi mã vì vậy hiện số rất dài, và không tính được tăng trưởng 2026-Q3 so với 2025-Q3. Cần sửa bộ nhập để ghi `VND`, hoặc quyết định coi `SOURCE_NATIVE` của VIETCAP_VCI là VND.
2. 24/34 công ty chưa có BCTC trong DB, trang tài chính của các mã này trống. Tab so sánh chỉ liệt kê mã đã có BCTC.
3. Vẫn còn mock:
   - `/profile`: chưa có API profile/đổi mật khẩu.
   - Dashboard: "Nghiên cứu gần đây" và thông báo báo cáo.
   - Lịch sử của tab so sánh vẫn lưu trong `localStorage`.
4. Sidebar `/watchlist` vẫn hiện tên cứng "Nguyễn Văn A", và nút đăng xuất ở đó không gọi `logout()`.
5. Chạy `095_admin_serving_corpus.sql` trên VPS. Quyết định xoá hay giữ 25 bảng không dùng.
