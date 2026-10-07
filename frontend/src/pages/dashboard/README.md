# Dashboard mock

Chạy `npm run dev` trong `frontend/`, rồi mở `/dashboard`. Tìm doanh nghiệp hoặc bấm mã phổ biến sẽ mở thẳng `/companies/:ticker`. Danh mục `/companies` cũng dẫn tới trang chi tiết này; Dashboard không chọn mã để thay dữ liệu tại chỗ. Ở trang chi tiết, tab **Tài chính** đổi được kỳ `FY2025` và `Q2/2026`.

Kiểm tra trạng thái qua `/dashboard?fixture=empty`, `/dashboard?fixture=error` và `/dashboard?fixture=loading`. Trạng thái loading này được giữ lại để xem Skeleton. Trang `/companies` cũng hỗ trợ các tham số fixture tương tự.

`dashboard/mock.js` chứa dữ liệu minh họa cho watchlist, công bố và panel thị trường chưa có giá. `companies/detailMock.js` chứa facts minh họa cho 10 mã ở hai kỳ. Các số tài chính chỉ phục vụ thử giao diện, không phải số liệu thực. Các file `api.js` và `detailApi.js` hiện trả Promise từ mock; khi có FastAPI, thay phần thân hàm gọi dữ liệu, giữ nguyên JSX của page. Không đặt API key trong frontend.
