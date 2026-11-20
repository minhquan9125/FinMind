# Hợp đồng tích hợp hội thoại lên giao diện

> Bản này mô tả giai đoạn FIXTURE trước 23/10/2026. Đường web mặc định hiện đã nâng cấp theo [LIVE_CHAT_CONTRACT.md](LIVE_CHAT_CONTRACT.md); HTTP/auth/revision cũ tiếp tục tương thích, GET/resume LIVE không replay retrieval/generation.

Phạm vi: dùng lại ChatSession và render_response hiện tại; vẫn FIXTURE, không kết nối vector, LLM, dữ liệu thật hay sửa bộ intent/evidence. Trang /research dùng hội thoại thật qua API; bảng so sánh cũ giữ ở /research?mode=compare và ghi nhãn dữ liệu mẫu.

## Dịch vụ JSON

Module `backend/src/retrieval_orchestration/web_sessions.py` xuất `SessionStore(root: Path)`, `ChatError(status: int, message: str)` và các async methods `create(owner)`, `list(owner)`, `get(owner, session_id)`, `send(owner, session_id, text, revision)`, `resume(owner, session_id)`. Owner và session_id đều UUID chuẩn. Mỗi method trả dict JSON, list trả list descriptor. Không dùng FastAPI trong service.

Snapshot `{session_id, revision, messages, context, execution_mode: "FIXTURE"}`. Messages gồm role/content/timestamp; assistant có result nguyên envelope. List descriptor `{session_id, preview, saved_at, turns}`. Context là context_summary() tiếng Việt. Create revision=0; send tăng revision đúng một lần và thêm 2 messages. Lưu đủ schema_version 1.0, started_at, saved_at, per-user-turn reference_date để dùng load_history/restore_session. Phải gán lại ChatSession.session_id thành ID snapshot sau replay vì restore_session tạo UUID mới. Resume tạo UUID mới, metadata parent_session_id, giữ transcript và không ghi đè nguồn. Giới hạn 2 MiB/2000 messages, text 1..4000 ký tự sau trim. Lỗi input 422, không tìm thấy/cross-owner 404, revision conflict hoặc file lock bận 409, I/O 503 thông báo an toàn. Lỗi phải giữ snapshot gốc nguyên vẹn. Read/replay thật, không tin assistant.result. Update dùng exclusive file lock xuyên process (O_EXCL, không tự xóa lock của process khác) và atomic replace; không ghi đè khi đang lỗi/timeout. Cấm symlink/junction/traversal, cả root và owner dir. Chỉ temp files của test, không đọc lịch sử người dùng.

Web JSON mới lưu riêng `backend/src/retrieval_orchestration/chat_history/web/<owner UUID>/<session UUID>.json`; không liệt kê/mở các file CLI cũ (chưa xác định chủ sở hữu). File .gitignore tại chat_history/web bỏ qua nội dung runtime. Không log token/text. Không cache global session objects; reload từ disk giúp restart giữ ngữ cảnh. `context` trả về từ reconstructed session; document GET không tự sửa file.

## HTTP

Router `backend/src/api/routers/research_chat.py`, prefix `/api/research/chat`:
- POST /sessions -> snapshot (201)
- GET /sessions -> `{items: descriptors}`
- GET /sessions/{session_id} -> snapshot
- POST /sessions/{session_id}/messages body `{text, revision}` -> snapshot
- POST /sessions/{session_id}/resume -> snapshot (201)

Tất cả endpoints cần Bearer JWT: dùng sẵn `src.auth.service.read_access_token(token, get_settings())` trả UUID; token sai/hết hạn/thiếu ->401 và WWW-Authenticate: Bearer. Không lấy owner từ body/query. Dependency `get_owner`, `get_store` để override tests. get_store default cached SessionStore root như trên, không đọc .env trong worker tests. Router dùng `src.retrieval_orchestration.web_sessions`. Service imports relative `.retrieval_flow...`. Pydantic strict revision nonnegative, text strip nonempty max4000, extra forbid. Translate ChatError; lỗi unexpected thành503 an toàn, không lộ traceback/path. Dùng typed response schema cho snapshot/list, result dict giữ envelope. No DB/network required for standalone FastAPI router tests. Coordinator gắn router vào src/main.py sau review.

## React

`frontend/src/pages/research/chatApi.js`: named exports `createSession()`, `listSessions()`, `getSession(id)`, `sendMessage(id,text,revision)`, `resumeSession(id)`. Fetch cùng origin API trên (Vite đã proxy /api tới8000). Header Bearer đọc đúng localStorage `finmind_auth_session` trường `token`; không lưu thêm token. Reject thiếu token thông báo đăng nhập. HTTP/JSON/network lỗi ra Error dễ đọc (error.status); không dùng mock fallback. ID encodeURIComponent. Không tự retry POST.

`ResearchChat.jsx`: component mặc định với Sidebar userMenu, useAuth user/logout, useNavigate/useSearchParams từ ../../app/router.jsx. Dùng giao diện Tailwind hiện tại xanh/trắng, responsive; title Trợ lý nghiên cứu; link Bảng so sánh -> /research?mode=compare. Badge Dữ liệu mẫu, mô tả chưa có số liệu thật. Không tự gửi câu hỏi hoặc áp mã/kỳ FPT mặc định. URL question chỉ prefill input, user chủ động gửi. Conversation list tất cả user/assistant, whitespace-pre-wrap, plaintext React (không HTML), nhãn tiếng Việt cho status của result; context summary riêng; JSON chỉ trong details optional. Hiện loading, lỗi role=alert, disable gửi/mở/new khi request bận, ref guard chống double submit cùng tick. Input label hiện rõ, submit Enter qua form. Không mất input khi lỗi; không append user giả khi thất bại. New chat/create, danh sách history load từ backend, mở phiên để xem GET và nút tiếp tục tạo child resume (hoặc nút Mở và tiếp tục gọi resume luôn, hiển thị tất cả transcript). sessionStorage chỉ lưu active ID key theo user.id; mount/đổi user restore bằng GET, clear state và bỏ stale response của user cũ, unmount tránh setState. Không leak previous user transcript. Không hiện message assistant báo thành công khi request fail. Nếu401 hiển thị link đăng nhập. Có nút tải lại lịch sử khi list fail. Không xóa old snapshots. Tự cuộn giữ composer nhìn thấy; actions keyboard focus. Không thêm dependency. Không sửa legacy ResearchPage.jsx (coordinator gắn wrapper sau review). Node --test kiểm tra API thật với fetch fake boundary, không import JSX trực tiếp vào Node.

## Tiêu chí tích hợp cuối

Chạy backend và frontend như README hiện tại, đăng nhập, vào /research, hỏi lợi nhuận năm nay -> bổ sung BID, sau thuế -> kỳ/ngữ cảnh được giữ; sửa VCB; tải lại trang; mở lịch sử tiếp tục; user khác không đọc được phiên; backend lỗi hiển thị lỗi, không số liệu giả. CLI 109 regression tests phải còn pass. Mọi kiểm thử ghi temp trong vùng kiểm thử riêng, không động 3 file CLI của người dùng. Không tự git add/commit/push.
