# Admin — theo dõi báo cáo job WBS16

Nhánh triển khai bắt đầu từ `backup-demo` tại `477dbf67`. Điểm vào giao diện:
`/admin/jobs` và `/admin/jobs/:jobId`, mục **Job dữ liệu** trong sidebar admin.

## Phạm vi đã nối

- API `GET /api/v1/admin/jobs?offset=0&limit=20` và
  `GET /api/v1/admin/jobs/{job_id}?offset=0&limit=50` đọc báo cáo đã lưu của runner.
- Backend kiểm tài khoản còn hoạt động và quyền `ADMINISTRATOR` hiện tại từ DB
  qua dependency auth có sẵn. Thiếu đăng nhập trả 401, sai quyền trả 403. Không
  cấp thêm quyền cho tài khoản hay thay đổi schema DB.
- Frontend nhận đúng role `ADMINISTRATOR`, xét toàn bộ danh sách role khi đăng
  nhập thường/Google và khôi phục phiên. Kiểm tra frontend chỉ điều hướng; quyền
  API luôn do backend quyết định.
- Danh sách và chi tiết có phân trang, trạng thái tải/lỗi/trống, nút làm mới;
  hiển thị riêng fixture, chờ duyệt, lỗi, thiếu nguồn, chưa xử lý và kết quả đối
  chiếu export. Không tự thay lỗi API bằng dữ liệu mock.
- API chỉ xuất trường cần hiển thị; không trả đường dẫn máy chủ, body bài News,
  candidate payload hoặc raw exception. Báo cáo sai tổng/trạng thái trả 409 và
  hiện trong danh sách dưới dạng báo cáo lỗi. Chặn đường dẫn vượt kho báo cáo.

Đây là trình xem snapshot báo cáo. Chưa theo dõi tiến độ trực tiếp, khởi chạy,
resume từ web, duyệt dữ liệu hoặc ghi audit cho thao tác thay đổi. Các trang
admin cũ vẫn giữ phạm vi hiện có; riêng trang Job dùng API thật.

## Cấu hình kho báo cáo

Mặc định backend đọc `outputs/wbs16-jobs` từ gốc FinMind. Có thể cấu hình
`ADMIN_JOBS_DIRECTORY` thành đường dẫn tuyệt đối của kho báo cáo, rồi khởi động
lại backend. Backend phải được quyền đọc thư mục runner ghi; nếu chạy container,
cần mount cùng kho báo cáo vào container backend.

Mỗi lần chạy có một thư mục con riêng, tên gồm chữ/số, `_`, `-`, tối đa 100 ký
tự, ví dụ `news-20261105-01`. Runner ghi:

```text
outputs/wbs16-jobs/news-20261105-01/report.json
outputs/wbs16-jobs/news-20261105-01/checkpoint.json
outputs/wbs16-jobs/news-20261105-01/records/...
```

Ví dụ chuẩn bị fixture bằng file đầu vào có sẵn:

```powershell
.\.venv\Scripts\python.exe backend/scripts/run_news_manifest.py --mode fixture --manifest PATH/manifest.json --articles PATH/articles.json --output outputs/wbs16-jobs/news-fixture-01
```

Không tạo báo cáo mẫu trong kho mặc định của người dùng. Nếu chưa có báo cáo,
giao diện trả trạng thái trống. Job bị ngắt trước lần xuất `report.json` chưa
xuất hiện; resume runner để hoàn tất lần xuất báo cáo. Với input thật/full,
giữ gate receipt WBS09.5 như tài liệu runner.

## Demo local có nhãn Fixture

Tạo hoặc mở lại báo cáo minh họa bằng lệnh dưới đây từ gốc FinMind. Script không
kết nối DB, không cấp quyền và không tạo receipt WBS09.5:

```powershell
.\.venv\Scripts\python.exe backend/scripts/prepare_admin_demo.py
```

Mở `/admin/jobs/demo-fixture-wbs16` bằng tài khoản có quyền ADMINISTRATOR. Bộ demo
có 5 bài: 1 chờ duyệt, 1 cần kiểm tra, 1 chưa tìm thấy ứng viên, 1 lỗi thân bài
rỗng, 1 thiếu nguồn. Trạng thái “cần xử lý tiếp” là kết quả dự kiến của fixture.
Chạy lại giữ nguyên checkpoint và không nhân đôi. Đăng nhập vẫn dùng DB thật;
cần tunnel PostgreSQL nếu cấu hình DB trỏ cổng local 15433. Không dùng fixture
này để nghiệm thu nguồn News thật hay chất lượng extractor.

## Lệnh kiểm thử

```powershell
$env:PYTHONPATH='.;backend'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_admin_jobs.py backend/tests/test_news_batch_runner.py backend/tests/test_news_event_extractor.py -q
cd frontend
node --test src/shared/context/authRoles.test.js src/pages/admin/jobsApi.test.js
npm.cmd run build
```

Test auth dùng dependency kiểm quyền thật với repository DB giả lập; báo cáo
được tạo bởi runner thật trên fixture tạm. Chưa phải nghiệm thu tài khoản/DB
production hoặc kết quả News full-load.
