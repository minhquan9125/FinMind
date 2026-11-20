# S5-WBS01.2 — Theo dõi

Tiếp tục ngày 16/11/2026 theo yêu cầu Nhân, sau thời gian tạm dừng từ 12/11.
Trạng thái mới nhất: retest ngày 17/11/2026 trên bản sửa `c4857941` đạt refresh/retry qua HTTP và PostgreSQL thật; sẵn sàng review báo cáo, chưa nghiệm thu browser/React.
Đã đủ bằng chứng lập báo cáo tái hiện/chuyển review. Hội thoại đạt qua ảnh; lỗi token tái hiện tự động với HTTP/SQL auth thật. Chưa nghiệm thu E2E browser/React + DB lịch sử Chat.

- [x] Đối chiếu backlog: task của Nhân, hai ca, 2 giờ; không phụ thuộc 04.1 review.
- [x] Đọc Chat API/auth và chạy 16 test hiện có: đạt; chưa chứng minh Chat refresh.
- [x] Đồng bộ nền `backup-demo` tại `cd272640` trên nhánh `nhan-next-task-20261116`.
- [x] Chạy lại test hiện có: backend 22/22, frontend 16/16 đạt.
- [x] Chạy fixture qua API: đổi BID → VCB giữ chỉ tiêu/kỳ; phiên mới sạch.
- [x] API từ chối JWT hết hạn bằng 401; snapshot không đổi.
- [x] Tái hiện client Chat không refresh sau 401; hàm dùng chung refresh/retry thành công với HTTP mô phỏng.
- [x] Khởi động backend/frontend; kết nối DB; router và retrieval warmup đã ready.
- [x] Bổ sung cấu hình thiếu vào `.env` theo quyền Nhân; Google chấp nhận khóa và provider sinh JSON thành công.
- [x] Viết [báo cáo thực tế/kỳ vọng](../../docs/sprint5/S5-WBS01.2-reproduction.md).
- [x] Ghi bản chép Web Chat do Nhân cung cấp: BID → VCB đều trả “Chưa đủ bằng chứng”; gợi ý đổi sang VCB. Chưa xác nhận chỉ tiêu/kỳ.
- [x] Nhận hai ảnh ở lượt kiểm tra sau: scope VCB, LNST, năm 2025 đúng; câu BID/VCB đều có câu trả lời kèm mục trích dẫn. Ca kế thừa phạm vi đạt; chưa đối chiếu đoạn nguồn/số liệu.
- [x] Nhận ảnh gửi tiếp “Còn BID thì sao?” thành công sau hướng dẫn chờ; scope BID/LNST/2025 đúng. Chưa đo thời gian chờ/TTL hay quan sát refresh/401 nên chưa nghiệm thu token hết hạn.
- [x] Nhận ảnh sau hướng dẫn mở phiên mới: “Còn VCB thì sao?” chỉ có mã VCB, hỏi chọn chỉ tiêu, không kế thừa LNST/năm 2025.
- [x] Tự động dùng client thật + HTTP local + auth PostgreSQL thật: Chat 401 không refresh; đối chứng refresh/retry thành công, đúng một tin trong store tạm; refresh cũ bị 401.
- [x] Rollback toàn bộ dữ liệu auth tổng hợp; kiểm tra user thử không còn sau rollback. Không dùng token/lịch sử cá nhân, không đổi TTL server đang chạy.
- [ ] Nghiệm thu hai ca trên Web Chat hiện có khi backend/DB khả dụng.
- [x] Ghi nhận kiểm tra tách phiên trên giao diện thật: không kế thừa chỉ tiêu/kỳ.
- [ ] Nếu cần nghiệm thu tính năng tổng hợp: xác nhận yêu cầu và chạy trên UI; hiện mới có kết quả fixture hỏi làm rõ.
- [x] Khôi phục thời hạn access token của tiến trình backend về 15 phút bằng khởi động lại đúng backend test. Settings xác nhận 15 phút, health `ok`; router/retrieval đang nạp lại. Không sửa TTL trong `.env`.

Công cụ Chrome chưa kết nối; đã xác nhận scope/tách phiên qua ảnh và auth HTTP/SQL thật qua runner. Còn giới hạn kiểm chứng UI/timer/DB lịch sử Chat khi token hết hạn. Không yêu cầu Nhân canh 15 phút. Bằng chứng:
`outputs/s5_wbs012_20261116/`. Không đưa `.env`, bản sao `.env` hoặc log thô vào gói review.

## Retest ngày 17/11/2026

- [x] Fetch các nhánh; bản tích hợp đang kiểm là `backup-demo` tại `62cc3720`.
- [x] Backend auth/Chat/store: 25 test đạt; frontend authSession/chatApi: 19 test đạt.
- [x] Ca riêng với client Chat thật, fetch/storage cô lập: gửi 401, refresh 0 lần;
  đối chứng `authorizedFetch`: 401 → refresh 200 → gửi lại 200, đúng một lần ghi trong mock.
- [x] Nhận bản sửa trên `backup-demo`: `c4857941 fix(auth): refresh research chat token on expiry`.
- [x] Mở lại tunnel PostgreSQL; giữ lượt đầu ConnectionRefused làm bằng chứng lịch sử.
- [x] Chạy HTTP/auth SQL thật: Chat 401 không refresh; đối chứng xoay refresh được và token cũ bị 401.
- [x] Kiểm PostgresSessionStore/SQL/RLS thật: đối chứng giữ VCB/LNST/2025, lịch sử cũ không đổi, retry chỉ ghi một lần.
- [x] Đếm trực tiếp 3 phiên / 10 dòng tin / 5 tin người dùng; rollback và kiểm không còn user/phiên thử.
- [ ] Nghiệm thu browser/React trên đúng bản refresh mới; hiện mới kiểm module client + HTTP + SQL thật.

Kết luận tạm thời: còn tái hiện lỗi thiếu phục hồi sau 401 trên `62cc3720`, chưa
kết luận về bản mới của Quân nếu chưa nhận được nhánh/commit. Bằng chứng mới:
`outputs/s5_wbs012_20261117/`. Không sửa code xác thực, không đổi `.env` hoặc TTL.
Nhánh script/báo cáo retest: `nhan-s5-token-conversation-retest`. Lượt cuối dùng
`auth-and-chat-postgres-run03.json`; mode lịch sử file cũ cũng chạy lại đạt ở
`auth-db-http-run03.json`. Hai lượt đầu của mode PostgreSQL lỗi so sánh thứ tự khóa
JSON trong harness, không phải lỗi mất lịch sử sản phẩm; đã sửa và ghi rõ trong báo cáo.

## Retest bản sửa `c4857941`

- [x] Fast-forward `backup-demo` và nhánh retest lên `c4857941`, giữ toàn bộ bằng chứng cũ.
- [x] Frontend authSession/chatApi mới: 21/21 test đạt.
- [x] Client Chat thật: gửi 401 → refresh 200 → gửi lại 200; refresh cũ bị 401.
- [x] PostgreSQL thật: cùng phiên, giữ lịch sử và VCB/LNST/2025; mỗi ca thêm đúng một lượt.
- [x] SQL đếm 3 phiên / 12 dòng tin / 6 tin người dùng; rollback sạch user/phiên thử.
- [x] Lưu kết quả tại `auth-and-chat-postgres-recovery-run01.json`, không ghi đè các lượt FAIL trước.

Lỗi thiếu refresh của Chat **không còn tái hiện trên bản mới trong phạm vi HTTP/SQL đã kiểm**.
Các dòng FAIL `62cc3720` ở trên là lịch sử trước sửa. Còn giới hạn React/browser,
timer và tương tác nhiều tab; không tự ghi là E2E trình duyệt đã đạt.
