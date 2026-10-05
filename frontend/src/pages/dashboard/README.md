# Dashboard mock

Chạy `npm run dev` trong `frontend/`, rồi mở `/dashboard`. Chọn một trong 10 mã bằng ô tìm kiếm hoặc các nút mã phổ biến. Đổi **Kỳ dữ liệu** giữa `FY2025` và `Q2/2026` để xem bộ facts và công bố mẫu tương ứng. Có thể mở trực tiếp `/dashboard?company=FPT&period=Q2%2F2026`.

Kiểm tra trạng thái qua `/dashboard?fixture=empty`, `/dashboard?fixture=error` và `/dashboard?fixture=loading`. Trạng thái loading này được giữ lại để xem Skeleton. Trang `/companies` cũng hỗ trợ các tham số fixture tương tự.

`mock.js` chứa dữ liệu giả lập cho 10 mã ở hai kỳ, tin mẫu, watchlist và panel thị trường chưa có giá. Các số tài chính chỉ phục vụ thử giao diện, không phải số liệu thực. `api.js` hiện trả Promise từ mock; khi có FastAPI, thay phần thân `getDashboard()` bằng lời gọi API và giữ nguyên JSX của page. Không đặt API key trong frontend.
