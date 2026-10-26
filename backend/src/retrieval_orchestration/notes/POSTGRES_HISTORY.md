# Lịch sử web chat trên Supabase

Từ24/10/2026, router `/api/research/chat` dùng `PostgresSessionStore`. Các thao tác tạo, danh sách, mở, gửi, tiếp tục và xóa đi qua database; không ghi JSON lịch sử mới hoặc fallback file khi DB lỗi. Frontend và snapshot API cũ giữ nguyên. Module `web_sessions.SessionStore` còn phục vụ kiểm thử/offline cũ; CLI fixture không tự kết nối Supabase.

## Dữ liệu và quyền

Schema riêng `research_chat`:

| Bảng | Dữ liệu |
|---|---|
| `conversations` | UUID phiên, `user_id`FK`public.users`, revision, thời gian, preview, số lượt, metadata/ngữ cảnh và processing lease |
| `messages` | Từng tin nhắn, vị trí, chủ sở hữu, payloadJSONB gồm câu gốc/đáp án/nguồn/manifest |
| `schema_migrations` | Phiên bản/checksum migration, chỉ admin |

JSONB là kiểu cột trong database, không phải file JSON trên máy backend. Giữ nguyên evidence/quote/locator, kết quả làm rõ, reference_date và câu gõ gốc. FK ghép `(conversation_id,user_id)` của tin nhắn bắt buộc khớp chủ cuộc hội thoại. `ON DELETE CASCADE` xóa tin của đúng phiên khi xóa phiên/tài khoản.

Backend lấy owner từ JWT đã kiểm tra qua `get_owner`, không nhận owner body/query. `ChatRepository.transaction` dùng `SET LOCAL ROLE finmind_chat_runtime` và `set_config('app.chat_user_id',owner,true)` trong mỗi transaction. Role `NOLOGIN`, `NOBYPASSRLS`, không phải chủ bảng, chỉ có quyền trên hai bảng chat. Cả hai bảng ENABLE/FORCE RLS, policy USING/WITHCHECK theo identity cục bộ. Sau transaction/pool release không giữ role/identity của người trước. `anon`, `authenticated`, `service_role` không được cấp quyền vào schema/bảng này; frontend chỉ gọi backend hiện có.

Mọi thao tác người dùng phải đi qua repository này. Kết nối admin có quyền bypass RLS chỉ dùng migration/vận hành; không dùng bare admin query cho API customer. `auth.uid()` không tự đại diện cho JWT riêng của FinMind. Các kiểm thử role/pool là phần bắt buộc của bàn giao khi đổi cơ chế DB.

## Đồng thời và lỗi

Send nhận revision như trước. Backend claim một lease hữu hạn bằng UPDATE có điều kiện owner/revision/lease trước khi gọi engine, rồi trả connection vào pool. Không giữ transaction/row lock qua lượt Gemini có thể chờ10phút. Request cùngrevision đang chạy bị409 trước generation. Lease theo tổng timeout engine cộng khoảng dọn; request đến muộn không save/release lease của request mới.

Sau generation, tăng revision, lưu hai messages và metadata trong cùng transaction. Bất kỳ lỗi SQL nào rollback cả revision/messages; lỗi engine không lưu nửa lượt và dọn lease. Process/network chết thì lease hết hạn. DB lỗi trả lỗi an toàn, không lưu local để tránh sinh hai nguồn lịch sử. Snapshot/read dùng transaction nhất quán; GET/resume không gọi lại retrieval/Gemini cho LIVE.

DELETE `/api/research/chat/sessions/{id}` trả204 cho chủ,404 với phiên không thuộc user; đang xử lý thì409. Frontend hiện không thêm nút xóa trong task này. Những route khác vẫn cùng request/response/auth/revision cũ.

## Triển khai và nhập lịch sử cũ

Chạy từ gốc repository bằng môi trường backend đã cấu hình DATABASE_URL đúng. Cùng Supabase hiện tại đã áp dụng migration và nhập **9phiên/188tin** ngày24/10/2026; không cần chạy lại khi chỉ restart ứng dụng.

Kiểm tra chỉ đọc:

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend/scripts/migrate_chat_history.py
```

Cho DB mới, áp dụng trước khi khởi động bản backend mới:

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend/scripts/migrate_chat_history.py --apply-schema --import-json
```

Migration additive `supabase/migrations/20261024000100_research_chat_history.sql` chỉ tạo schema/role/bảng/policy mới và quyền cho tài khoản DB chạy migration. Journal/checksum và advisory transaction lock chống sửa/race migration. Không sửa file migration đã áp dụng; thay đổi schema tiếp theo phải dùng migration mới. Nếu runtime DATABASE_URL dùng login khác migration, admin cần cấp membership role này cho đúng login đó; không mở role thànhLOGIN/BYPASSRLS hoặc exposeDBcredential ra frontend.

Importer đọc đúng `chat_history/web/<owner>/<session>.json`, kiểm tra UUID/path/symlink/owner/schema/size và tài khoản tồn tại. Giữ UUID/revision/messages/metadata. Rerun cùng dữ liệu không tạo bản trùng; phiên DB đã thay đổi được giữ lại và báokept_existing. Không ghi đè session khác chủ hoặc sửa/xóa nguồn. File JSON cũ vẫn là archive tĩnh, không được dùng bởi default web store.

Không để bản backend cũ tiếp tục ghi JSON trong lúc chuyển đổi. Nếu report có invalid/unknown_owner/kept_existing cần xem xét từng trường hợp bằng công cụ admin, không đổiowner hoặc forceoverwrite cho tiện. Source archives vẫn nguyên để xử lý thủ công khi cần.

## Phục hồi

Migration không xóa/đổi dữ liệu users, authsessions hoặc corpus. Trước thay đổi DB tiếp theo hãy sao lưu schema chat qua công cụ PostgreSQL/Supabase. Khi gặp sự cố ưu tiên khôi phục schema/role/grant/kết nối và triển khai sửa tiếp, giữ nguyên tables/archives; không DROP schema hay bật JSON fallback để chữa tạm. Bản JSON cũ không chứa chat phát sinh sau chuyển đổi, nên rollback code cũ sẽ không cung cấp lịch sử mới. Muốn rollback phải bảo toàn DBdata/sao lưu và có kế hoạch chuyển dữ liệu được duyệt; các lệnh DROP không tự chạy trong app hoặc CLI.

## Kiểm thử

`test_postgres_chat_store.py`: hai owner, revision/collision, enginefail cleanup, persist/reopen/resume. `test_chat_import.py`: import cùngowner/idempotence/nooverwrite/rawfile không đổi. `test_live_chat_factory.py`: production và webfixture đềuDB, khôngfilefallback.

Opt-inDBthật, tạo data tạm với marker riêng và dọn đúng UUID đã tạo, không gọi Gemini/SDK:

```powershell
$env:PYTHONPATH="backend;."
$env:RUN_CHAT_DB_SMOKE="1"
backend\.venv\Scripts\python.exe -X utf8 -m pytest -q -s backend/tests/test_postgres_chat_live.py
Remove-Item Env:RUN_CHAT_DB_SMOKE
```

Khi chạy pytest cần PYTHONPATH chứabackend như các testcommand trong checkpoint. Ca thật kiểm tra tokenA/B, RLSkhiSQLquênownerfilter, FKowner, roleẩn khỏiDataAPI, poolreset/missingidentity, khônggiữconnectionchờengine, CASlease/recovery/expiredlateworker, atomicrollback, DELETEcascade và khôngJSONwrites. Chưa browser/authE2E; frontendhelpers/APIcontracttest vẫn dùng giao diện hiện có.
