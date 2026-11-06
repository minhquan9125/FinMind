# Vận hành admin local demo

## Phục hồi khi backend/worker dừng

Mọi worker CRAWL, OCR, RECHECK, INDEX giữ khóa file theo job trong
`outputs/admin-ingestion/worker-locks`. Hệ điều hành giải phóng khóa khi tiến trình
chết. Backend kiểm tra mỗi 15 giây; job QUEUED/RUNNING quá 30 giây không có worker
giữ khóa được ghi FAILED/WORKER_STOPPED và thêm audit. Không dùng tuổi job làm
bằng chứng một worker còn giữ khóa đã chết. Job khác không còn bị chặn vô hạn.

Trong Thu thập & duyệt, bấm **Tiếp tục / chạy lại**. INDEX có manifest tiếp tục
kiểm tra/publish/cache, không embedding lại. INDEX ghi dở chưa có manifest tạo mã
job/index mới để không đụng index BUILDING có thể đã commit; giữ job cũ và liên kết
successor. Chunk/vector chưa được đóng manifest có thể phải tạo lại. OCR có
revision rồi không tạo bản trùng khi chạy tiếp. CRAWL dùng chống trùng hiện có.
Phiên Chat đang phục vụ và quyết định duyệt không đổi khi chỉ phát hiện worker mất.

Khóa chỉ bảo vệ worker chạy bản code mới. Khi nâng cấp, phải dừng worker/scheduler
bản cũ trước khi bật backend mới; bản cũ không giữ khóa. Chỉ dùng một thư mục queue
trên một máy, không dùng SQLite/file lock làm hàng đợi phân tán giữa các máy.
Backend tự gỡ trạng thái kẹt, **không tự khởi chạy lại job** trước khi admin bấm tiếp tục.

## Trace thật

GET `/api/v1/admin/ingestion/traces` hỗ trợ offset/limit, outcome, company và day.
Day lọc theo ngày Việt Nam. GET `/traces/{uuid}` đọc chi tiết, không lọc mảng giả lập.
Mọi endpoint yêu cầu ADMINISTRATOR được xác nhận từ server. Trace mới lưu câu hỏi
người dùng, mã nguyên nhân, nguồn trích dẫn, phiên corpus/cấu hình nếu có, thời gian
đã đo và usage của từng lần generate Gemini. Không lưu prompt nội bộ hoặc toàn bộ
câu trả lời. Các mục Graph/Gate/Verifier chưa có kết quả không được gán đạt hay 0 ms.
Không backfill câu hỏi/token/chi tiết mà lịch sử cũ chưa ghi.

## Ngân sách API

GET/PUT `/api/v1/admin/ingestion/budget` đọc/lưu cấu hình phiên bản và lịch sử.
PUT cần reason và expected_version; thay đổi đồng thời trả 409 thay vì ghi đè.
Cấu hình gồm mode (unconfigured/free/paid), kỳ day/month, limit_usd, warn_at và
đơn giá input/output theo tên model chính xác. Giao diện chỉ cảnh báo, chưa chặn AI.

USD ước tính = input * giá đầu vào / 1.000.000 + (total - input) * giá đầu ra /
1.000.000. Phần total ngoài input gồm đầu ra nhìn thấy và token suy luận. Không
tính chiết khấu cache, batch hoặc giá riêng theo hợp đồng. Giá do admin nhập,
không tự tra hay khẳng định bảng giá hiện hành của nhà cung cấp.

Chế độ free ước tính 0 theo lựa chọn admin, không kiểm tra tài khoản billing
Google. Chỉ tính Chat LIVE từ ledger trên máy này, không biết các dịch vụ khác
dùng chung API key. Giá mới áp dụng lại cho dữ liệu đã ghi trong kỳ, không sửa hóa
đơn hay token cũ. Thiếu usage và thiếu đơn giá hiển thị riêng, không coi là miễn phí;
thanh ngân sách khi thiếu dữ liệu chỉ là phần đã biết. Kỳ theo giờ Việt Nam và kết
thúc không bao gồm thời điểm đầu kỳ kế tiếp. Tổng quan tự cập nhật mỗi 30 giây.

Bản demo được khởi tạo free theo cấu hình Free Tier hiện có, ngân sách cảnh báo
10 USD/tháng, ngưỡng 80%; admin có thể sửa. Đây là giá trị cấu hình, không phải
chi phí mẫu hay bằng chứng có chi phí thực tế 10 USD.

Các cấu hình Evidence Gate, Retrieval và giới hạn Token nội bộ còn dùng file của
dự án; giao diện giữ nhóm tương ứng nhưng chưa cho sửa. Cấu hình nguồn/corpus
riêng vẫn minh họa. Hàng đợi, audit và ledger vẫn nằm tại máy chạy backend;
PostgreSQL lưu dữ liệu chung, các phiên corpus và vector.
