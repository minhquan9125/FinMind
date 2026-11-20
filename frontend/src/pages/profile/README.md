# Hồ sơ mẫu

Mở `/profile` khi chạy `npm run dev` trong `frontend/`. Avatar chỉ xem trước trên máy; chấp nhận PNG/JPG tối đa 2 MB và không upload. Form mật khẩu chỉ kiểm tra ba ô và xác nhận khớp, sau đó xóa giá trị đã nhập; không gửi mật khẩu hoặc báo đã đổi thật.

Thử `/profile?fixture=empty`, `/profile?fixture=error`, `/profile?fixture=loading` để xem các trạng thái. `mock.js` chứa người dùng mẫu, `api.js` là chỗ thay bằng API tài khoản sau này. Nút Đăng xuất trong Sidebar hiện chỉ chuyển sang route `/login` vì frontend chưa có phiên đăng nhập thật để xóa.
