# Thiết kế tài khoản và API xác thực

**Trạng thái:** Đề xuất chốt trước khi triển khai  
**Phạm vi:** Đăng ký, đăng nhập, quên và đặt lại mật khẩu, làm mới phiên, đăng xuất, xem hồ sơ hiện tại.

## 1. Hiện trạng

- Frontend có trang `/login` và `/register`. `AuthContext` và `apiAdapter` hiện dùng dữ liệu giả lập, lưu phiên giả vào `localStorage`.
- Bộ định tuyến khai báo `/forgot-password` và `/reset-password`, nhưng thư mục trang xác thực hiện chỉ có `LoginPage.jsx` và `RegisterPage.jsx`.
- Backend FastAPI chưa có bộ định tuyến xác thực. Các endpoint `/api/v1/auth/*` trong `API_SPECIFICATION.md` mới là thiết kế, chưa gọi được.
- Biểu mẫu frontend dùng `full_name`, `email`, `password`, trong khi tài liệu API đang dùng `username` khi đăng nhập. Thiết kế mới thống nhất dùng email.
- Migration tạo `public.users` (có `password_hash`), `public.sessions` (có `token_hash`, thời hạn và trạng thái thu hồi) cùng các bảng vai trò. Migration cũng ghi rõ rằng các ràng buộc, chỉ mục và chính sách RLS chưa được suy ra từ ERD.

## 2. Quyết định về nhà cung cấp xác thực

**Chọn Supabase Auth làm nhà cung cấp xác thực; FastAPI cung cấp lớp API trung gian `/api/v1/auth/*` cho frontend và các ứng dụng gọi API.** FinMind không tự kiểm tra mật khẩu hoặc tự phát hành JWT.

Lý do: dự án đã dùng Supabase Postgres; Supabase Auth có sẵn xác thực email/mật khẩu, xác minh email, khôi phục mật khẩu và phiên dùng access token/refresh token. Lớp API trung gian giữ hợp đồng API thống nhất cho Postman và backend, đồng thời không để frontend phụ thuộc trực tiếp vào chi tiết của nhà cung cấp. Tham khảo [tổng quan Supabase Auth](https://supabase.com/docs/guides/auth), [phiên đăng nhập](https://supabase.com/docs/guides/auth/sessions) và [xác thực bằng mật khẩu](https://supabase.com/docs/guides/auth/passwords).

Quy ước triển khai:

- Supabase Auth là nguồn dữ liệu duy nhất cho thông tin xác thực, xác minh email, khôi phục mật khẩu và phiên đăng nhập.
- `public.users` chỉ lưu hồ sơ ứng dụng và liên kết `user_id` với ID của người dùng trong Supabase Auth. Không lưu mật khẩu hoặc mã khôi phục. Cột `password_hash` hiện có không được dùng cho luồng xác thực mới; chỉ xóa bằng migration sau khi xác nhận không còn dữ liệu cần giữ.
- `public.sessions` không lưu access token, refresh token hoặc bản băm token. Supabase quản lý phiên xác thực. Nếu cần ghi nhận hoạt động, chỉ lưu siêu dữ liệu tối thiểu, không chứa bí mật.
- `public.user_roles` lưu vai trò của ứng dụng. Đăng ký công khai luôn nhận vai trò người dùng mặc định; không bao giờ nhận vai trò quản trị viên từ dữ liệu gửi lên.
- Frontend giữ access token trong bộ nhớ và gửi qua `Authorization: Bearer`. Refresh token chỉ dùng qua cookie `HttpOnly`, `SameSite=Lax`, `Secure` trên HTTPS; trên máy cục bộ có thể bỏ `Secure`. CORS phải bật gửi cookie và chỉ cho phép các nguồn cụ thể. Postman dùng cookie jar khi gọi làm mới phiên và đăng xuất.
- FastAPI xác minh chữ ký, nhà phát hành, đối tượng nhận và hạn dùng của JWT theo cấu hình Supabase; sau đó tra hồ sơ và vai trò ứng dụng. Không tin vai trò do client gửi.
- Bật xác minh email trước khi cho phép đăng nhập. Cấu hình URL chuyển hướng cho frontend và SMTP theo từng môi trường; dịch vụ gửi email mặc định để thử nghiệm của Supabase không phù hợp cho môi trường thật.

## 3. Luồng người dùng

### Đăng ký

1. Người dùng nhập họ tên, email, mật khẩu, xác nhận mật khẩu và đồng ý điều khoản tại `/register`.
2. Frontend kiểm tra định dạng và độ mạnh cơ bản; backend kiểm tra lại toàn bộ dữ liệu.
3. `POST /api/v1/auth/register` tạo tài khoản qua Supabase Auth và hồ sơ `public.users` với vai trò mặc định.
4. Nhà cung cấp gửi email xác minh. Giao diện yêu cầu người dùng kiểm tra hộp thư; chưa tự đăng nhập khi email chưa được xác minh.
5. Người dùng nhấn liên kết xác minh, quay lại frontend và hoàn tất bước xác nhận phiên.

### Đăng nhập

1. Người dùng nhập email và mật khẩu tại `/login`; `remember_me` chọn thời hạn phiên theo chính sách đã cấu hình, không làm frontend tự tạo token dài hạn.
2. `POST /api/v1/auth/login` xác thực qua nhà cung cấp. Nếu email chưa xác minh, trả lỗi có mã rõ ràng nhưng không tiết lộ email có tồn tại hay không.
3. API trả access token ngắn hạn trong nội dung phản hồi, đặt refresh token vào cookie HttpOnly, đồng thời trả hồ sơ và vai trò ứng dụng.
4. Frontend dùng access token trong bộ nhớ khi gọi API. Sau khi tải lại trang, frontend gọi endpoint làm mới phiên để khôi phục đăng nhập.

### Quên và đặt lại mật khẩu

1. Người dùng nhập email tại `/forgot-password`.
2. `POST /api/v1/auth/password/forgot` yêu cầu nhà cung cấp gửi liên kết khôi phục; luôn trả cùng một thông báo chung để tránh tiết lộ email có tài khoản hay không.
3. Liên kết mở `/reset-password`. Frontend nhận mã hoặc mã ủy quyền từ bước chuyển hướng rồi gửi một lần qua HTTPS đến endpoint xác nhận.
4. `POST /api/v1/auth/password/reset` đổi mật khẩu qua nhà cung cấp. Mã khôi phục chỉ dùng một lần; không ghi mã vào URL phía máy chủ, công cụ phân tích, log, báo cáo lỗi hoặc lịch sử ứng dụng. Sau khi đổi mật khẩu thành công, thu hồi các phiên hiện có theo chính sách nhà cung cấp và yêu cầu đăng nhập lại.

### Đăng xuất

1. Frontend gọi `POST /api/v1/auth/logout` với access token Bearer và cookie refresh.
2. Backend/nhà cung cấp thu hồi phiên hiện tại và xóa cookie bằng `Set-Cookie` hết hạn; frontend xóa access token trong bộ nhớ rồi chuyển về `/login`.
3. Nếu cần chức năng “đăng xuất khỏi mọi thiết bị”, bổ sung riêng sau phiên bản đầu; không gộp chức năng này với đăng xuất hiện tại.

## 4. Hợp đồng API đề xuất

Địa chỉ gốc khi chạy cục bộ: `http://localhost:8000`. Các endpoint dưới đây là hợp đồng đề xuất, hiện chưa được triển khai.

### `POST /api/v1/auth/register` — không cần đăng nhập

Yêu cầu:

```json
{
  "email": "analyst@example.com",
  "password": "MatKhauRiengBiet!2026",
  "full_name": "Thái Quốc Hưng",
  "accept_terms": true
}
```

Phản hồi `201 Created`:

```json
{
  "success": true,
  "data": {
    "user": {
      "user_id": "uuid",
      "email": "analyst@example.com",
      "full_name": "Thái Quốc Hưng",
      "roles": ["RESEARCHER"],
      "email_verified": false
    },
    "verification_required": true
  }
}
```

### `POST /api/v1/auth/login` — không cần đăng nhập

Yêu cầu: `{"email":"analyst@example.com","password":"...","remember_me":false}`

Phản hồi `200 OK`: `data` có `access_token`, `token_type: "Bearer"`, `expires_in` và hồ sơ người dùng an toàn để trả về. Phản hồi đặt cookie chứa refresh token; không trả refresh token trong JSON.

### `POST /api/v1/auth/refresh` — cần cookie refresh

Không cần nội dung yêu cầu. API luân phiên refresh token trong cookie và trả access token mới cùng hồ sơ người dùng. Nếu refresh token bị thiếu, hết hạn, dùng lại hoặc đã bị thu hồi, trả `401` và xóa cookie.

### `GET /api/v1/auth/me` — cần Bearer token

Trả hồ sơ hiện tại và vai trò do máy chủ xác định. Không trả siêu dữ liệu riêng của nhà cung cấp, bản băm thông tin xác thực hoặc token.

### `POST /api/v1/auth/password/forgot` — không cần đăng nhập

Yêu cầu: `{"email":"analyst@example.com"}`. Luôn trả `202 Accepted` cùng một thông báo chung, bất kể tài khoản có tồn tại hay không.

### `POST /api/v1/auth/password/reset` — không cần đăng nhập, cần mã khôi phục dùng một lần

Yêu cầu: `{"recovery_code":"...","new_password":"..."}`. Thành công trả `204 No Content`; mã không hợp lệ, hết hạn hoặc đã dùng trả lỗi `400` chung. Không ghi mã hoặc mật khẩu mới vào log.

### `POST /api/v1/auth/logout` — cần Bearer token và cookie refresh

Thu hồi phiên hiện tại, xóa cookie chứa refresh token và trả `204 No Content`. Gọi đăng xuất lặp lại vẫn an toàn.

Mọi lỗi tuân theo định dạng Problem Details hiện có, với mã ổn định như `VALIDATION_ERROR`, `INVALID_CREDENTIALS`, `EMAIL_NOT_VERIFIED`, `RECOVERY_INVALID` và `RATE_LIMITED`. Không tiết lộ email có tồn tại khi quên mật khẩu hoặc đăng nhập thất bại.

## 5. Quy tắc bảo mật và ghi log

- Cấm ghi mật khẩu, mật khẩu xác nhận, access token, refresh token, mã khôi phục, header `Authorization`/`Cookie`, hoặc phản hồi của nhà cung cấp có chứa thông tin bí mật vào log ứng dụng, log máy chủ trung gian, telemetry, tracing, analytics, thông báo lỗi hoặc dữ liệu kiểm thử.
- Tắt hoặc che nội dung yêu cầu trên các endpoint xác thực; che chuỗi truy vấn có mã chuyển hướng. Không ghi nguyên văn lỗi từ nhà cung cấp nếu lỗi có thể chứa dữ liệu nhạy cảm.
- Chỉ ghi sự kiện cần thiết: loại sự kiện, kết quả, trace ID, user ID nếu đã xác định và thời điểm. Chỉ ghi IP/user-agent khi có mục đích và thời hạn lưu rõ ràng.
- Dùng HTTPS ngoài môi trường cục bộ; giới hạn CORS; giới hạn tần suất đăng ký/đăng nhập/khôi phục/đặt lại mật khẩu; phản hồi quên mật khẩu không cho phép dò tài khoản; dùng cookie HttpOnly/SameSite và kiểm tra CSRF với endpoint xác thực bằng cookie.
- Không lưu token trong `localStorage`. Không đưa khóa bí mật hoặc khóa service-role vào frontend hay kho mã nguồn.
- Mật khẩu chỉ được gửi đến Supabase Auth qua TLS; FinMind không lưu mật khẩu dạng rõ hoặc bản băm mật khẩu.

## 6. Việc cần xử lý trong schema trước khi tạo migration

1. Liên kết `public.users.user_id` với `auth.users.id`; bổ sung ràng buộc bắt buộc/duy nhất cho email phù hợp với mô hình hồ sơ.
2. Bỏ `password_hash` khỏi luồng đọc/ghi xác thực; chỉ xóa cột sau khi xác nhận dữ liệu và triển khai migration an toàn.
3. Không ghi token vào `public.sessions.token_hash`; quyết định ngừng dùng bảng này hoặc chỉ giữ siêu dữ liệu kiểm toán không nhạy cảm. Supabase Auth là nơi quản lý phiên duy nhất.
4. Bổ sung thao tác tạo/cập nhật hồ sơ có thể chạy lặp an toàn và quy tắc đồng bộ email/họ tên.
5. Tạo vai trò mặc định; chỉ quản trị viên hoặc backend có quyền mới được cấp vai trò cao hơn, không nhận vai trò từ yêu cầu đăng ký.
6. Cấu hình xác minh email, danh sách URL chuyển hướng khôi phục được phép, SMTP và các nguồn CORS cho môi trường cục bộ/thử nghiệm/sản phẩm.

## 7. Thứ tự triển khai sau khi duyệt hợp đồng

1. Chốt cấu hình Supabase Auth (xác minh email, URL chuyển hướng, SMTP, thời hạn token/phiên) và migration hồ sơ/vai trò.
2. Tạo lớp API xác thực, dịch vụ nghiệp vụ, bộ kiểm tra JWT và cơ chế giới hạn tần suất/che log.
3. Bổ sung trang quên/đặt lại mật khẩu và thay mock trong `AuthContext`/`apiAdapter` bằng API thật.
4. Kiểm tra bằng Postman theo thứ tự: đăng ký → xác minh email → đăng nhập → xem hồ sơ → làm mới phiên → quên/đặt lại mật khẩu → đăng nhập bằng mật khẩu mới → đăng xuất.
