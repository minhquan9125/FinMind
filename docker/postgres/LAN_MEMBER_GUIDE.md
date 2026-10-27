# Kết nối database phát triển chung trong LAN

Đã thiết lập trên máy chủ hiện tại:

| Trường | Giá trị |
| --- | --- |
| Host | `192.168.101.46` |
| Port | `5433` |
| Database | `finmind` |
| Username | `finmind_team` |
| Password / DATABASE_URL | Trong file riêng `finmind_team.env.local`, nhận từ người quản lý |

File credential là tài khoản phát triển, không phải quản trị. Không đẩy credential lên Git. Tài khoản này dành cho backend/công cụ import của các thành viên tin cậy trong nhóm, không đưa vào frontend/browser. Có thể chạy script cấp tài khoản với `--user ten_thanh_vien` để tách thêm tài khoản sau.

## Thành viên thực hiện

1. Kết nối cùng LAN với máy chủ. Kiểm tra IPv4 máy mình: subnet hiện cho phép là `192.168.101.0/24`.
2. Trong PowerShell:

```powershell
Test-NetConnection 192.168.101.46 -Port 5433
```

`TcpTestSucceeded: True` nghĩa là cổng truy cập được. Bước này phải thử trên máy thành viên: kiểm tra từ máy chủ chưa chứng minh router/switch cho phép thiết bị khác truy cập.

3. Điền Host/Port/Database/User/Password trên công cụ SQL hoặc đặt DATABASE_URL trong backend/.env theo file credential được cấp. Máy thành viên không dùng localhost để trỏ tới máy chủ.
4. Restart backend sau khi đổi .env. Giữ `RESEARCH_WARMUP_ENABLED=false` trong lúc DB chưa có corpus.

Thành viên không cần chạy thêm PostgreSQL Docker riêng khi dùng database chung này. Backend/frontend vẫn chạy trên máy mỗi người. Việc INSERT/UPDATE/DELETE commit vào DB này ảnh hưởng cả nhóm.

## Quyền và phạm vi

- Được SELECT/INSERT/UPDATE/DELETE các bảng public để phát triển và nạp dữ liệu.
- Không superuser, không tạo database/role/schema, không TRUNCATE hoặc làm chủ các bảng.
- RLS public được bổ sung policy riêng cho nhóm `finmind_developer` trên Docker này; không sửa RLS trên Supabase.
- Lịch sử chat vẫn dùng `finmind_chat_runtime` và app.chat_user_id, giữ chính sách theo chủ sở hữu. Không cấp quyền xem toàn bộ lịch sử chat trực tiếp cho tài khoản nhóm.
- Schema changes, tạo/xóa index và migration chạy bằng tài khoản quản lý. Không tự sửa bộ corpus đã frozen; thử thay đổi ở DB thử nghiệm hoặc release mới.

## Máy chủ

Máy chủ/Docker phải luôn bật khi nhóm phát triển. Khởi chạy lại bằng `Start-Database.ps1`: script tự thêm LAN overlay nếu `.env` có POSTGRES_LAN_IP. Tránh chạy compose base riêng khi muốn giữ cổng LAN.

Firewall rule `FinMind-Postgres-LAN-5433` chỉ cho `192.168.101.0/24` đến IP `192.168.101.46`, TCP 5433, qua Ethernet. Không đổi network profile của Windows và không cấu hình port forwarding router. Bind chỉ localhost + IP LAN này, không dùng 0.0.0.0.

IP có thể đổi do DHCP. Nếu đổi IP/mạng, cập nhật POSTGRES_LAN_IP và rule bằng `Enable-LanFirewall.ps1` với tham số đúng (PowerShell Administrator), chạy lại Compose rồi cấp URL mới. Có thể đặt DHCP reservation ở router để giữ IP ổn định.

## Dữ liệu

Hiện mới có cấu trúc bảng, chưa có seed/tài liệu/vector/corpus. Tạo tài khoản kết nối không đồng nghĩa đã nạp bộ dữ liệu Supabase. Nhóm nạp dữ liệu chung riêng sau; không cần sao chép toàn bộ dữ liệu về từng máy. Không chia sẻ file `.env` quản trị trong thư mục này cho thành viên.
