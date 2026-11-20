# Bàn giao task 1 và 2

Nhánh bàn giao: `task1Sprint4`. Database PostgreSQL VPS đã có dữ liệu; clone Git chỉ lấy code và tài liệu, không lấy database. Không chạy lại script chuyển corpus, publish hàng loạt hoặc backfill để kết nối vào VPS hiện có.

## Nội dung

- Task 1: extractor người–chức vụ, chuẩn hóa và contract 2.1.0, review candidates, crawler rules không AI, reader BCTN hỗ trợ release ID khác source ID, tests.
- Task 2: migration metadata/RLS, repository metadata và WBS03 intake, CLI trích xuất/lưu/đọc, test nguồn sai và retry, SQL tra cứu.
- Registry đi kèm trong `backend/resources/person_role/`; runtime không phụ thuộc file tải về trong outputs.
- Bằng chứng kỹ thuật nhỏ tại `docs/graph/acceptance/`; không thay thế nghiệm thu bằng đầu ra WBS03 riêng của thành viên.

## Thành viên clone và chạy

```powershell
git clone --branch task1Sprint4 https://github.com/minhquan9125/FinMind.git
cd FinMind
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
$env:PYTHONPATH = "$PWD\backend"
$env:PYTHONIOENCODING = "utf-8"
```

Tạo `backend/.env` trên máy thành viên, nhận tài khoản DB qua kênh riêng:

```dotenv
DATABASE_URL=postgresql://YOUR_DB_USER:YOUR_DB_PASSWORD@127.0.0.1:15433/finmind
```

Mật khẩu trong URL cần percent-encode nếu có ký tự đặc biệt. Đây là mật khẩu PostgreSQL, không phải mật khẩu SSH. Không commit file .env.

Mở PowerShell khác, kết nối bằng tài khoản SSH được cấp:

```powershell
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -L 127.0.0.1:15433:127.0.0.1:5433 YOUR_SSH_USER@160.250.181.10
```

Giữ cửa sổ tunnel mở. Nếu port đang có tunnel thì không mở trùng. Tài khoản DB cần kế thừa role writer để nạp ứng viên; không dùng tài khoản admin dùng chung. Migration đã áp dụng trên VPS, không cần thành viên tự chạy lại.

## Chạy tests không ghi database

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_person_role_extractor.py backend/tests/test_person_role_review.py backend/tests/test_crawled_person_role_rules.py backend/tests/test_release_document_identity.py -q
```

## Kiểm tra file đầu ra của thành viên

```powershell
.\.venv\Scripts\python.exe backend/scripts/run_wbs03_pipeline.py --input C:\path\wbs03-output.json --output outputs/member-check
```

File phải là envelope contract 2.1.0, có chunk BCTN thật thuộc corpus `b2550a0b-c423-5c50-9b15-6fb6af12e2c6`, và các relation PENDING. Không tự đổi ID/hash trong file để vượt kiểm tra.

Khi dry-run đạt và muốn lưu ứng viên:

```powershell
.\.venv\Scripts\python.exe backend/scripts/run_wbs03_pipeline.py --input C:\path\wbs03-output.json --apply --output outputs/member-save
```

Lưu graph_version_id từ result.json. Chạy lại phải cùng ID và không tăng số quan hệ. Dùng graph ID đó để tra graph_extractions/evidence; đừng dùng ID phiên nháp cũ.

Để gọi trong code WBS03: `WBS03Repository(connection).save(payload)`, chi tiết trong `WBS03_DATABASE_PIPELINE.md`. Nếu repository của thành viên ở nơi khác, họ phải tích hợp lời gọi này; clone không tự sửa code của họ.

## Dữ liệu và trạng thái

- Graph chính: `6f1504e8-3eef-59e7-9d20-8c5957cb4427`, 184 quan hệ source-bound của 10 công ty; không phải toàn bộ nhân sự đã trích xuất hết.
- Bản nháp test ELC `a4ef18eb-a422-53ad-a0f1-e69b0b84f779` đã xóa theo yêu cầu. Không cần clone hoặc khôi phục bản nháp này.
- Test live `test_wbs03_pipeline_vps.py --apply` tạo probe rồi rollback nhưng áp dụng migration; chỉ người quản trị chạy. Thành viên dùng CLI --input cho nghiệm thu.
- Chưa có UI duyệt, không tự APPROVED, không xuất Neo4j. Đã kiểm thử PostgreSQL VPS, chưa kiểm thử Supabase cloud.
- DB dump, vector cache, PDF/HTML nguồn, mật khẩu, .venv/.runtime và toàn bộ outputs lớn không đưa lên Git. Truy cập dữ liệu bằng tài khoản VPS được cấp.

SQL xem dữ liệu chính: `docs/graph/sql/`. Reports acceptance là lịch sử kiểm thử, không tự chạy lại các bước ghi database.
