# Thiết kế tài khoản và API xác thực

**Trạng thái:** Mô tả theo code hiện tại. Đã triển khai đăng ký, đăng nhập, đăng nhập Google, quên và đặt lại mật khẩu; quản lý phiên đầy đủ còn cần bổ sung.

**Quyết định:** FinMind **tự triển khai xác thực trong FastAPI**. Supabase được dùng làm nơi lưu PostgreSQL, **không dùng Supabase Auth**. Tài liệu này thay cho phương án Supabase Auth từng được đề xuất.

## 1. Thành phần và dữ liệu

| Thành phần | Vai trò hiện tại |
| --- | --- |
| React: `LoginPage`, `RegisterPage`, `ForgotPasswordPage`, `ResetPasswordPage` | Nhận thông tin người dùng, hiển thị kết quả và gọi API qua `authApi.js`. |
| FastAPI: `backend/src/api/routers/auth.py` | Kiểm tra yêu cầu, xử lý đăng ký/đăng nhập/đặt lại mật khẩu và trả token. |
| `backend/src/auth/schemas.py` | Kiểm tra email, độ mạnh và xác nhận mật khẩu bằng Pydantic. |
| `backend/src/auth/service.py` | Băm/xác minh mật khẩu bằng Argon2, tạo và đọc JWT. |
| Supabase PostgreSQL | `public.users` lưu hồ sơ và `password_hash`; `public.user_roles` lưu vai trò; `public.sessions` lưu **bản băm** refresh token và trạng thái phiên. |
| SMTP | Gửi liên kết đặt hoặc đặt lại mật khẩu; không gửi mật khẩu qua email. |

Email là định danh đăng nhập. Đăng ký công khai được gán vai trò `RESEARCHER`; client không thể tự cấp vai trò cao hơn. Mật khẩu gốc không được lưu vào database.

## 2. Luồng đã triển khai

### Đăng ký bằng email và mật khẩu

1. Người dùng nhập họ tên, email, mật khẩu, xác nhận mật khẩu và chấp nhận điều khoản ở `/register`.
2. Frontend gọi `POST /api/v1/auth/register`. Backend kiểm tra dữ liệu, yêu cầu mật khẩu từ 8 ký tự, có chữ hoa, chữ thường, số và ký tự đặc biệt.
3. Backend băm mật khẩu bằng Argon2 rồi tạo `public.users` và vai trò `RESEARCHER` trong một giao dịch. Email đã có trả `409`.
4. API trả `201` với hồ sơ và vai trò, không trả mật khẩu. Frontend gọi đăng nhập ngay sau khi đăng ký thành công.

**Hiện chưa có bước xác minh email khi đăng ký.** Tài khoản mới được tạo ở trạng thái hoạt động.

### Đăng nhập bằng email và mật khẩu

1. Frontend gửi `email` và `password` tới `POST /api/v1/auth/login`.
2. Backend tìm tài khoản, so mật khẩu với bản băm Argon2, kiểm tra trạng thái hoạt động. Email không tồn tại và mật khẩu sai đều trả thông báo chung. Bộ giới hạn trong bộ nhớ khóa tạm sau 5 lần thử sai trong 15 phút.
3. Thành công: backend đọc vai trò từ database, tạo access JWT có hạn 15 phút; tạo refresh token ngẫu nhiên, lưu bản băm của nó vào `public.sessions` với thời hạn cấu hình mặc định 7 ngày.
4. API trả access token, refresh token, thời hạn và hồ sơ trong JSON. `AuthContext` lưu hồ sơ và access token vào `localStorage` để duy trì giao diện khi tải lại trang.

Tùy chọn “Ghi nhớ đăng nhập” hiện kéo dài thời gian phiên **trên frontend** lên 7 ngày; nó **không** làm access JWT 15 phút có hiệu lực 7 ngày.

### Đăng nhập Google

1. Google trả ID token cho frontend; frontend gửi token tới `POST /api/v1/auth/google`.
2. Backend dùng `google-auth` xác minh ID token, cho phép lệch đồng hồ tối đa 5 giây. Thư viện kiểm tra audience khi biến `GOOGLE_CLIENT_ID` được cấu hình; code hiện cho phép biến này rỗng.
3. Backend tìm tài khoản theo email; nếu chưa có thì tạo `public.users` với `password_hash = NULL` và vai trò mặc định. Nếu email đã có, dùng tài khoản đó, không tạo tài khoản thứ hai.
4. Sau đó backend cấp token và phiên FinMind như đăng nhập bằng mật khẩu. Tài khoản chỉ có Google có thể đặt mật khẩu lần đầu qua luồng email bên dưới.

### Quên hoặc đặt lại mật khẩu

1. Người dùng nhập email ở `/forgot-password`; frontend gọi `POST /api/v1/auth/password/forgot`.
2. Với tài khoản tồn tại và đang hoạt động, backend tạo reset JWT ký bằng khóa của FinMind, chứa ID người dùng, thời hạn **15 phút** và dấu phiên bản của trạng thái mật khẩu hiện tại. Cách này hỗ trợ cả tài khoản có mật khẩu và tài khoản Google đang có `password_hash = NULL`.
3. Tác vụ nền gửi liên kết `/reset-password#token=...` qua SMTP. API luôn trả `202` với cùng thông báo cho mọi email để tránh dò tài khoản. **Phản hồi 202 chỉ là tiếp nhận yêu cầu, không xác nhận thư đã tới hộp thư.**
4. Trang reset lấy mã từ liên kết, nhận mật khẩu mới và xác nhận, rồi gọi `POST /api/v1/auth/password/reset`.
5. Backend kiểm tra chữ ký, thời hạn, trạng thái tài khoản và dấu phiên bản mật khẩu. Mật khẩu mới được băm bằng Argon2. Câu lệnh cập nhật chỉ thành công nếu mật khẩu hiện tại vẫn khớp, kể cả trường hợp `NULL`; các hàng phiên còn hoạt động của người dùng được đánh dấu thu hồi trong cùng giao dịch.
6. Thành công trả `204` và frontend chuyển về đăng nhập. Vì bản băm mật khẩu đã đổi, mã reset cũ không dùng lại được.

## 3. Hợp đồng API hiện có

Địa chỉ gốc khi chạy cục bộ: `http://127.0.0.1:8000`. Frontend Vite chuyển tiếp đường `/api` sang backend.

| Endpoint | Dữ liệu chính | Kết quả |
| --- | --- | --- |
| `POST /api/v1/auth/register` | `full_name`, `email`, `password`, `confirm_password`, `accept_terms` | `201`, `data` chứa ID, email, họ tên, vai trò, thời điểm tạo; email trùng `409`. |
| `POST /api/v1/auth/login` | `email`, `password` | `200`, `data` chứa `access_token`, `refresh_token`, `token_type`, `expires_in`, `user`; sai thông tin `401`, bị khóa tạm `429`. |
| `POST /api/v1/auth/google` | `credential` là Google ID token | `200` cùng dạng dữ liệu đăng nhập; token không hợp lệ `401`. |
| `POST /api/v1/auth/password/forgot` | `email` | `202` và thông báo chung. |
| `POST /api/v1/auth/password/reset` | `recovery_code`, `new_password`, `confirm_password` | `204`; mã sai, hết hạn hoặc đã dùng `400`; dữ liệu không hợp lệ `422`. |

## 4. Cấu hình và bảo mật

- Backend lấy `DATABASE_URL`, `JWT_SECRET_KEY`, `GOOGLE_CLIENT_ID`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` và `FRONTEND_URL` từ cấu hình môi trường. Frontend dùng `VITE_GOOGLE_CLIENT_ID`. Không đưa khóa bí mật vào frontend hoặc commit file `.env`.
- Mật khẩu được băm trước khi lưu. JWT có chữ ký và thời hạn; JWT **không mã hóa** nội dung bên trong, nên không đặt mật khẩu hay bí mật vào payload.
- Email quên mật khẩu chỉ chứa liên kết; không gửi mật khẩu cũ hoặc mật khẩu mới.
- Ngoài môi trường cục bộ, cần HTTPS, giới hạn origin và cấu hình `FRONTEND_URL` đúng địa chỉ người dùng mở được. Giá trị mặc định `localhost` chỉ phù hợp khi mở email trên chính máy chạy frontend.

## 5. Giới hạn và việc tiếp theo

Các mục sau **chưa được triển khai đầy đủ**; không trình bày như tính năng đã hoàn tất:

1. API `refresh`, `logout` và `me` chưa có trong router auth. Frontend logout hiện xóa `localStorage`, chưa gọi backend để thu hồi phiên. Refresh token đã được cấp và lưu bản băm, nhưng chưa có API sử dụng nó.
2. Frontend lưu access token trong `localStorage`. Trạng thái “ghi nhớ đăng nhập” có thể còn hiển thị sau khi JWT 15 phút đã hết hạn. Cần chốt lại mô hình phiên, nơi lưu token và cơ chế làm mới.
3. Chưa có xác minh email lúc đăng ký. Bộ giới hạn thử sai khi đăng nhập nằm trong bộ nhớ của từng tiến trình. API quên mật khẩu chưa có giới hạn tần suất riêng.
4. Gửi thư chạy bằng `BackgroundTasks`; lỗi SMTP cần được theo dõi ở backend vì phản hồi `202` không phản ánh việc phát thư. Cấu hình `SMTP_FROM` và `FRONTEND_URL` cần thống nhất cho từng môi trường.
5. Hàm đọc access JWT đã có, nhưng chưa có đầy đủ endpoint/hàng rào xác thực theo JWT cho vòng đời tài khoản. Cần rà soát yêu cầu phân quyền từng API.
6. Khóa JWT phải được cấp qua môi trường triển khai, không dựa vào giá trị mặc định trong code. Cần có kiểm tra bắt buộc cấu hình cho môi trường thật.
7. Cần bắt buộc `GOOGLE_CLIENT_ID` và kiểm tra claim `email_verified` trước khi dùng email Google để liên kết hoặc tạo tài khoản.

## 6. Kiểm tra đã thực hiện

- Bộ test `backend/tests/test_auth.py`: 14 trường hợp đạt, gồm đăng ký, đăng nhập, giới hạn thử sai, quên/đặt lại mật khẩu cho tài khoản thường và tài khoản Google chưa có mật khẩu, từ chối mã sai và mã đã dùng.
- `npm run build` ở frontend hoàn tất.
- Đăng nhập SMTP thành công; một email đặt mật khẩu thật gửi đến tài khoản do người dùng cung cấp đã được người dùng xác nhận nhận được. Chưa xác nhận toàn bộ thao tác nhấn liên kết và đổi mật khẩu trên tài khoản thật.

**Lưu ý:** Tài liệu cũ từng chọn Supabase Auth, cookie refresh, xác minh email và các API `refresh/logout/me`. Đó là **phương án đề xuất trước đây**, không phải trạng thái của code hiện tại.
