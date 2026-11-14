# PostgreSQL Docker — chỉ có cấu trúc, chưa có dữ liệu

Đã xuất từ catalog Supabase ngày 27/10/2026: **53 bảng public + 3 bảng research_chat**, 168 constraints, 7 index ngoài constraint và 2 policy RLS. Có primary/foreign/check/unique constraints, kiểu cột, defaults và quyền riêng của role lịch sử chat. Không chứa bản ghi, tài khoản, role ứng dụng dạng dữ liệu seed, corpus, vector hay nội dung nguồn.

Snapshot dùng schema thực tế, không chạy lại baseline cũ còn cột chunk_text. Không copy các schema nền tảng Supabase auth/storage/vault/realtime hay credentials/owner/grants đặc thù Supabase. Bộ này phục vụ backend PostgreSQL của FinMind, không dựng lại toàn bộ nền tảng Supabase.

## Chạy từ thư mục gốc FinMind

```powershell
powershell -ExecutionPolicy Bypass -File docker/postgres/Start-Database.ps1
```

Hoặc khi Docker đã có trong PATH:

```powershell
docker compose --env-file docker/postgres/.env -f docker-compose.postgres.yml up -d --wait
docker compose --env-file docker/postgres/.env -f docker-compose.postgres.yml exec -T postgres psql -U finmind -d finmind -v ON_ERROR_STOP=1 -f /opt/finmind-verify-empty.sql
```

Container: `finmind-postgres-postgres-1`. PostgreSQL 17 + pgvector 0.8.2. Host `127.0.0.1`, port `5433`, database/user `finmind`. Mật khẩu local được tạo ngẫu nhiên trong `.env` tại thư mục này; file bị Git ignore. Volume riêng `finmind-postgres_finmind_pgdata` giữ dữ liệu qua lần khởi động lại. Compose Neo4j hiện có không bị thay đổi.

`init/010_schema.sql` chỉ tự chạy khi khởi tạo volume rỗng lần đầu. Không chạy lại file CREATE TABLE vào database đã có cấu trúc. Không dùng `down -v` để khởi động lại: cờ đó xóa volume dữ liệu.

## Kết nối backend sau này

`backend.env.local` cạnh README đã chuẩn bị DATABASE_URL cho backend chạy trên Windows và tắt warmup khi DB còn trống. Chưa đổi backend/.env hiện tại sang DB này. Khi sẵn sàng, chuyển các giá trị tương ứng vào cấu hình backend rồi restart. Nếu backend cũng nằm trong cùng Docker network, dùng host `postgres`, port `5432` thay cho localhost:5433.

Khi chưa nạp seed/nguồn/corpus, chức năng đăng nhập, chat và truy vấn chưa có dữ liệu để phục vụ. UUID V5 hiện có trên Supabase không tự tồn tại trong Docker. Nạp corpus phải bao gồm nguồn ghim, documents, index/chunks/vector và membership/manifest; không chỉ copy embedding. Giữ hash và locator nhất quán. Nạp role/permission/config seed cần thiết riêng; bộ schema này không tự seed vì yêu cầu database trống.

## HNSW tùy chọn

HNSW chỉ tăng tốc tìm kiếm; không tự tạo vector hay nạp dữ liệu. Đã tách khỏi init để database mới không dựng index nặng trước khi nạp. Sau khi nạp và muốn bật:

```powershell
docker compose --env-file docker/postgres/.env -f docker-compose.postgres.yml exec -T postgres psql -U finmind -d finmind -v ON_ERROR_STOP=1 -f /opt/finmind-optional/enable_hnsw.sql
```

## Kiểm tra

`verify-empty.sql` kiểm tra đủ 56 bảng, không có dòng dữ liệu, pgvector có mặt và cosine distance hoạt động. Chỉ dùng kiểm tra trống trước khi nạp dữ liệu. `schema_inventory.json` là metadata không có dữ liệu nghiệp vụ. Kết quả đối chiếu local lưu trong `outputs/docker-schema-20261027/verification.json`.

Không có thao tác xóa/sửa Supabase trong quá trình chuẩn bị Docker này.
