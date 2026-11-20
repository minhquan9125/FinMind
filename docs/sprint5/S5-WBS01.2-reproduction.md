# S5-WBS01.2 — Tái hiện lỗi hội thoại và hết hạn token

**Cập nhật mới nhất 17/11/2026: retest bản sửa `c4857941` đạt ở mức client + HTTP +
auth/Chat PostgreSQL thật.** Chat nhận 401, refresh một lần rồi gửi lại thành công;
giữ lịch sử/ngữ cảnh và không ghi trùng. Frontend 21/21 test và build đạt.
Xem [verification-recovery.json](../../outputs/s5_wbs012_20261117/verification-recovery.json)
và mục “Kết quả mới nhất — bản sửa `c4857941`” ở cuối tài liệu để chạy lại.
Chưa nghiệm thu React/browser. Các kết quả FAIL bên dưới là lịch sử trước sửa.

## Lịch sử kiểm tra trước sửa

Ngày kiểm tra: 16/11/2026. Người phụ trách: Nhân. Nền mã nguồn: `cd2726409aeb2b74b27ee1b777edb1fde3a78d33`, nhánh `nhan-next-task-20261116`.

Đã có bằng chứng tái hiện qua API/fixture, HTTP mô phỏng và lượt tự động dùng HTTP local + endpoint auth/SQL PostgreSQL thật. Ca kế thừa phạm vi BID → VCB và ca tách phiên đã đạt trên ảnh Web Chat do Nhân gửi. Đủ lập báo cáo tái hiện và chuyển review; chưa xác nhận phục hồi token trên toàn bộ UI hoặc lỗi đã được sửa. Không sửa source sản phẩm trong lượt kiểm thử này.

## 1. Hội thoại kế thừa phạm vi

| Bước | Kỳ vọng | Thực tế trong fixture qua API |
| --- | --- | --- |
| Hỏi “Lợi nhuận sau thuế của BID năm 2025 là bao nhiêu?” | Ghi nhận BID, LNST, năm 2025 | HTTP 200, scope đúng; `NO_DATA` do fixture không có bằng chứng tài chính |
| Hỏi tiếp “Còn VCB thì sao?” | Đổi sang VCB, giữ LNST và năm 2025 | HTTP 200; VCB, `PROFIT_AFTER_TAX`, `2025-12-31` |
| Tạo phiên mới | Không mang scope/lịch sử phiên trước | Phiên rỗng, không có VCB trong context |
| Hỏi “Tổng hợp những gì nãy giờ” trong phiên cũ | Đối chiếu khả năng tổng hợp với yêu cầu sản phẩm | Trả `ASK_CLARIFICATION / UNRECOGNIZED_INTENT`; cần review yêu cầu và xác nhận trên Web Chat |

Kết quả chỉ chứng minh xử lý scope trong fixture, chưa chứng minh câu trả lời số liệu/citation với corpus thật. Việc tạo phiên sạch chưa chứng minh phản hồi cho một câu hỏi thiếu ngữ cảnh trong phiên mới.

Bằng chứng: [api-fixture-run01.json](../../outputs/s5_wbs012_20261116/api-fixture-run01.json).

### Kết quả Web Chat do Nhân gửi

Nhân đã gửi bản chép hai lượt BID → VCB từ giao diện thật. Cả hai hiện “Chưa đủ bằng chứng”, kèm thông báo không tìm thấy nguồn khớp mã/kỳ/chỉ tiêu. Sau lượt hai, gợi ý là “Tin tức mới về VCB” và “Giá VCB hiện tại”. Có bằng chứng giao diện đã phản hồi và chuyển gợi ý sang VCB; chưa có dòng scope để xác nhận giữ LNST/năm 2025.

Không suy từ thông báo này rằng corpus chắc chắn thiếu dữ liệu: chưa loại trừ giới hạn tìm kiếm/lọc nguồn. Cũng chưa quan sát request HTTP, gọi Gemini trong Chat hay refresh token. Đang chờ Nhân chép dòng phạm vi, thử qua thời hạn token và thử phiên mới.

Bằng chứng do người dùng cung cấp, không phải quan sát browser trực tiếp: [manual-webchat-run01.json](../../outputs/s5_wbs012_20261116/manual-webchat-run01.json).

Ở lượt kiểm tra tiếp theo, Nhân gửi hai ảnh Web Chat. Ảnh hiển thị câu BID có câu trả lời kèm mục trích dẫn BCTC BID năm 2025; câu “Còn VCB thì sao?” có câu trả lời về LNST VCB năm 2025 kèm mục trích dẫn BCTC VCB. Dòng phạm vi ghi rõ `Công ty: VCB | Kỳ: 2025 | Chỉ tiêu: lợi nhuận sau thuế | Nguồn: BCTC`, khớp các chip bên dưới.

Kết luận: **đạt ca kế thừa phạm vi trên UI** — đổi mã, giữ chỉ tiêu và năm. Chưa mở đoạn nguồn nên chưa xác minh độ chính xác của số liệu hoặc citation. Thời gian chờ, refresh và phiên mới không thể xác định từ hai ảnh. Bằng chứng ảnh ở lượt sau khác kết quả NO_DATA ở bản chép trước; chưa đủ thông tin để kết luận nguyên nhân thay đổi. Không ghi đè bằng chứng cũ.

Ghi nhận ảnh: [manual-webchat-run02.json](../../outputs/s5_wbs012_20261116/manual-webchat-run02.json). Ảnh gốc nằm trong hội thoại người dùng; file JSON ghi lại nội dung quan sát được, không phải bản sao ảnh.

### Tách phiên trên Web Chat

Sau hướng dẫn bấm “Nghiên cứu mới” rồi chỉ hỏi “Còn VCB thì sao?”, Nhân gửi ảnh có phạm vi `Công ty: VCB`, chỉ một chip `Mã: VCB`, không có chỉ tiêu hoặc kỳ. Hệ thống trả “Cần làm rõ”, hỏi chọn chỉ tiêu với bốn lựa chọn Tổng tài sản / Doanh thu thuần / Lợi nhuận sau thuế / Tổng nợ phải trả.

Kết luận: **đạt ca không kế thừa LNST/năm 2025 từ phiên trước trên UI**. Đây là bằng chứng theo kịch bản người dùng chạy, chưa kiểm tra ID phiên/DB hay mọi trường hợp cách ly phiên. [manual-webchat-run04.json](../../outputs/s5_wbs012_20261116/manual-webchat-run04.json) ghi lại nội dung ảnh.

## 2. Access token hết hạn, refresh còn hợp lệ

Kỳ vọng kiểm thử phía client: khi nhận 401 do access hết hạn, dùng refresh hợp lệ để xin access mới, thử gửi lại tối đa một lần và không ghi trùng tin nhắn.

| Phạm vi | Thực tế | Kết luận |
| --- | --- | --- |
| API thật với JWT tổng hợp đã hết hạn, store cô lập | HTTP 401; snapshot trước/sau giống nhau | API từ chối đúng, không ghi dữ liệu khi xác thực thất bại |
| `chatApi.sendMessage`, fetch/storage mô phỏng | Gửi 1 lần → 401, gọi refresh 0 lần, ghi thành công 0 lần trong mock | Tái hiện thiếu phục hồi sau 401 ở client Chat |
| Đối chứng `authorizedFetch`, cùng mô phỏng | 401 → refresh 200 → gửi lại 200; 1 lần ghi thành công trong mock | Hàm dùng chung có đường phục hồi; chưa chứng minh với refresh/DB thật |

`frontend/src/pages/research/chatApi.js` gọi `fetch` trực tiếp. Đường xử lý refresh/retry nằm trong `frontend/src/shared/api/authorization.js`. Chuyển bằng chứng cho người phụ trách refresh token theo backlog 06.1/06.2 (Quân); task Nhân chỉ tái hiện/báo cáo.

`AuthContext.jsx` tự refresh trước thời hạn khoảng 30 giây và khi khôi phục phiên. Vì vậy chờ qua 1 phút trên tab đang hoạt động có thể vẫn gửi bình thường; kết quả đó không phủ nhận lỗi xử lý 401 ở client Chat. Chưa đo việc giữ bản nháp hoặc ghi trùng trên giao diện/DB thật.

Bằng chứng: [client-transport-run01.json](../../outputs/s5_wbs012_20261116/client-transport-run01.json), API fixture ở trên.

### Lượt gửi tiếp trên Web Chat

Sau hướng dẫn giữ nguyên trang 2 phút rồi hỏi “Còn BID thì sao?”, Nhân gửi ảnh cho thấy câu hỏi đã được trả lời, scope là BID / LNST / năm 2025, kèm mục trích dẫn BCTC BID. Không có màn hình yêu cầu đăng nhập trong ảnh.

Ghi nhận **gửi tiếp thành công trên UI**. Thời gian chờ thực tế, TTL của tiến trình tại lượt thử, request refresh/401 và lịch sử ngoài vùng ảnh chưa được quan sát; chưa kết luận refresh sau access hết hạn đã đạt, không mất bản nháp hay không ghi trùng trên DB. Cơ chế tự gia hạn trước hạn vẫn có thể giải thích việc gửi bình thường.

Bằng chứng: [manual-webchat-run03.json](../../outputs/s5_wbs012_20261116/manual-webchat-run03.json). Không đối chiếu số liệu với đoạn nguồn trong lượt này.

### Tự động kiểm thử token với HTTP và PostgreSQL thật

Không yêu cầu Nhân chờ hết 15 phút. Runner tạo app thử trên cổng loopback ngẫu nhiên, dùng router auth và Chat hiện có, secret ký JWT ngẫu nhiên riêng, tài khoản tổng hợp trong một giao dịch PostgreSQL rồi rollback. Access được cấp với `exp` đã qua bằng hàm tạo token hiện có; không đổi đồng hồ máy, không tắt kiểm tra JWT, không thay settings của backend đang phục vụ. Refresh token được lưu/xoay bằng repository và SQL thật.

Client dùng module JavaScript hiện có, fetch gửi HTTP thật đến app thử; localStorage là đối tượng bộ nhớ cô lập. Lịch sử Chat dùng `SessionStore` file tạm, không phải `PostgresSessionStore` của Web Chat. Không gọi Gemini hoặc model.

| Ca | Trace đo được | Trạng thái lưu sau khi gửi |
| --- | --- | --- |
| Client Chat hiện tại, access đã hết hạn, refresh còn hợp lệ | Gửi → 401; refresh 0 lần | Revision tăng 0, có 0 tin người dùng; hash refresh ban đầu vẫn tồn tại trong DB |
| Đối chứng `authorizedFetch`, metadata còn hạn nhưng server từ chối access | Gửi 401 → refresh 200 → gửi lại 200 | Revision tăng 1, đúng 1 tin người dùng; DB đã xoay refresh |
| Đối chứng `authorizedFetch`, metadata biết access đã hết hạn | Refresh 200 → gửi 200 | Revision tăng 1, đúng 1 tin người dùng; DB đã xoay refresh |

Ở hai ca đối chứng, dùng lại refresh cũ bị 401; access mới được endpoint Chat chấp nhận. Giao dịch rollback thành công, truy vấn theo ID thử xác nhận không còn user thử. Assertion runner đạt nghĩa là **tái hiện lỗi và đối chứng thành công**, không có nghĩa client Chat đạt yêu cầu phục hồi.

Kết luận cập nhật: lỗi thiếu refresh sau 401 ở `chatApi.js` đã tái hiện với auth HTTP/SQL thật, không còn chỉ dựa vào fetch mock. Đường refresh dùng chung hoạt động ở mức tích hợp. Chưa chạy React/browser, timer của `AuthContext`, DB lịch sử Chat thật, hoặc bảo toàn bản nháp trên UI; không dùng kết quả này để chốt E2E toàn bộ Web Chat.

Bằng chứng: [auth-db-http-run01.json](../../outputs/s5_wbs012_20261116/auth-db-http-run01.json). Mã runner: `backend/scripts/reproduce_s5_wbs012_auth_db.py` và `frontend/scripts/reproduce-s5-wbs012-http.mjs`.

## Môi trường và kiểm tra bổ trợ

- Backend `http://localhost:8000`, frontend `http://localhost:5173`; tunnel PostgreSQL/Neo4j đã kết nối ở thời điểm kiểm tra.
- Health: router và research retrieval đều `ready`; retrieval warmup mất 535,2 giây. Đây là thời gian nạp cache/model, không phải độ trễ mỗi câu hỏi.
- Backend 22/22 test và frontend 16/16 test đạt. Các test hiện có không thay thế nghiệm thu hai ca trên UI.
- Google trả HTTP 200 cho kiểm tra danh sách model. Một lần gọi sinh nội dung qua provider với model `gemini-3.5-flash-lite` trả đúng JSON mong đợi, dùng tổng 22 token. Chỉ chứng minh kết nối/provider, chưa chứng minh toàn luồng Chat.
- Smoke lần đầu yêu cầu chữ `OK`, không đúng hợp đồng JSON của provider, nên nhận `INVALID_GEMINI_JSON`. Đây là sai sót trong câu kiểm tra; đã chạy lại đúng định dạng và giữ nguyên cả hai bằng chứng.
- Tiến trình backend test trước đó có `ACCESS_TOKEN_MINUTES=1`; TTL trong `.env` không đổi. Sau loạt ảnh kiểm tra đã dừng đúng tiến trình test và khởi động lại backend với 15 phút; settings được kiểm tra trước khi khởi động. Health trả `ok`, router/retrieval đang `warming` sau lần khởi động lại. `.env` và bản sao chứa bí mật không nằm trong gói review.

Tổng hợp: [verification.json](../../outputs/s5_wbs012_20261116/verification.json). Kiểm tra Google: [gemini-key-check.json](../../outputs/s5_wbs012_20261116/gemini-key-check.json), [gemini-generation-smoke-run02.json](../../outputs/s5_wbs012_20261116/gemini-generation-smoke-run02.json).

## Chạy lại bằng chứng cô lập

Từ thư mục gốc dự án, dùng tên đầu ra mới để giữ bằng chứng cũ:

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend/scripts/reproduce_s5_wbs012.py --out outputs/s5_wbs012_20261116/api-fixture-run02.json
node frontend/scripts/reproduce-s5-wbs012.mjs
backend\.venv\Scripts\python.exe -X utf8 backend/scripts/reproduce_s5_wbs012_auth_db.py --out outputs/s5_wbs012_20261116/auth-db-http-run02.json
```

Runner đầu dùng endpoint và kiểm tra JWT thật với store file cô lập; runner thứ hai dùng module client thật với fetch/storage mô phỏng. Không dùng token hoặc lịch sử cá nhân. Assertion ở runner client xác nhận lỗi đã tái hiện, không phải xác nhận lỗi đã sửa.

Runner thứ ba cần tunnel PostgreSQL và Node; gọi HTTP local thật, dùng SQL auth thật trong giao dịch rollback, vẫn dùng lịch sử Chat file tạm. Không cần đăng nhập trình duyệt hay đợi 15 phút.

## Phần cần xác nhận trên Web Chat

1. Đã đạt qua ảnh Nhân gửi: BID → VCB giữ đúng LNST/năm 2025. Không yêu cầu chạy lại ca này nếu môi trường không đổi.
2. Đã nhận ảnh gửi tiếp BID thành công sau hướng dẫn chờ và tự động tái hiện lỗi 401 bằng HTTP/SQL auth thật. Chưa đo timer/refresh của React trên browser hoặc mất/trùng tin trên UI/DB lịch sử thật. Không yêu cầu Nhân canh 15 phút để lặp lại phép thử này.
3. Đã đạt qua ảnh: phiên mới hỏi “Còn VCB thì sao?” chỉ giữ mã VCB và hỏi chọn chỉ tiêu, không lấy LNST/năm 2025 từ phiên trước.
4. Nếu kiểm tra thêm câu tổng hợp, ghi rõ phạm vi hỗ trợ và kết quả thực tế, không sửa logic ngoài task Nhân.

Công cụ browser host hiện không khả dụng. Đã nhận bản chép và ảnh xác nhận scope, tách phiên, gửi tiếp thành công trên giao diện; lỗi client đã tái hiện tự động với HTTP/SQL auth thật. Đủ để review báo cáo tái hiện và chuyển lỗi cho người phụ trách refresh; giới hạn còn lại là nghiệm thu browser/React + DB lịch sử Chat. Chưa coi là lỗi đã sửa hoặc E2E đã đạt.

## Retest sau khi Quân báo hoàn thành — 17/11/2026

Đã fetch các nhánh từ origin. Bản đang kiểm là `backup-demo`, commit `62cc3720`.
Chưa có nhánh/commit riêng của phần refresh mới được người dùng xác nhận.

Backend auth/Chat/store **25/25 test đạt**, frontend authSession/chatApi **19/19 đạt**.
Các bộ này không thay thế ca hết hạn của chính client Chat. Chạy lại ca chuyên biệt
bằng `frontend/scripts/reproduce-s5-wbs012.mjs` cho kết quả:

| Client | HTTP mô phỏng qua module thật | Refresh | Lần ghi thành công trong mock |
| --- | --- | ---: | ---: |
| `chatApi.sendMessage` | 401 rồi dừng | 0 | 0 |
| Đối chứng `authorizedFetch` | 401 → refresh 200 → gửi lại 200 | 1 | 1 |

**FAIL yêu cầu phục hồi sau 401 trên bản `62cc3720`.** Assertion runner đạt chỉ có
nghĩa tái hiện đúng triệu chứng đã biết, không phải tính năng đã đạt. Mã Chat hiện
vẫn gọi `fetch` trực tiếp; hàm xác thực dùng chung có đường refresh/retry. Không
suy từ đây rằng toàn bộ phần Quân chưa làm: cần xác nhận đúng phiên bản và đường
tích hợp trước khi kết luận bản sửa mới.

Bằng chứng: [client-transport-run01.json](../../outputs/s5_wbs012_20261117/client-transport-run01.json).
Runner auth HTTP/PostgreSQL thật đã được gọi lại nhưng dừng ở `ConnectionRefusedError`
trước khi kết nối được DB hoặc tạo tài khoản tổng hợp. Kết quả đó là **BLOCKED**, không
phải bằng chứng auth/refresh sai; chờ mở lại tunnel để chạy lượt mới. Xem
[auth-db-http-run01.json](../../outputs/s5_wbs012_20261117/auth-db-http-run01.json).

Chưa kiểm browser/React/timer hoặc DB lịch sử Chat trên bản mới. Không dùng token
cá nhân, không thay TTL/`.env`, không sửa code của Quân trong lượt retest này.

### Tunnel mở lại — kết quả HTTP và PostgreSQL thật

Lượt [auth-db-http-run02.json](../../outputs/s5_wbs012_20261117/auth-db-http-run02.json)
đã tái hiện đúng lỗi qua HTTP local và SQL auth thật, không còn bị chặn kết nối.
Sau đó mở rộng harness sang `PostgresSessionStore` để kiểm cả lịch sử Chat thật.
Nhánh chứa script/báo cáo: `nhan-s5-token-conversation-retest`, nền sản phẩm vẫn là
`backup-demo` tại `62cc3720`; không sửa mã nguồn sản phẩm.

Lượt cuối: [auth-and-chat-postgres-run03.json](../../outputs/s5_wbs012_20261117/auth-and-chat-postgres-run03.json).
Mỗi ca tạo phiên rồi gửi “LNST BID năm 2025”; sau đó dùng access đã hết hạn gửi
“Còn VCB thì sao?”. Auth router, client JavaScript, SQL/RLS và store đều là code thật.
`LiveResearchService` phân tích scope thật, corpus trả rỗng có chủ ý; không đo chất
lượng số liệu/citation, không gọi BGE/Gemini. Không chạy React/browser.

| Ca | Trace HTTP thực tế | Trạng thái lịch sử Chat trong PostgreSQL |
| --- | --- | --- |
| Client Chat hiện tại | Gửi 401; refresh 0 lần | Giữ phiên và lịch sử BID, revision không tăng; câu mới chưa được ghi |
| Đối chứng dùng hàm chung, nhận 401 rồi refresh | Gửi 401 → refresh 200 → gửi lại 200 | Cùng phiên, lịch sử cũ không đổi; thêm đúng 1 lượt; scope VCB/LNST/2025 |
| Đối chứng metadata biết access hết hạn | Refresh 200 → gửi 200 | Cùng phiên, lịch sử cũ không đổi; thêm đúng 1 lượt; scope VCB/LNST/2025 |

Hai ca đối chứng đều xoay refresh thật trong DB; thử refresh cũ bị 401, access mới
được endpoint Chat chấp nhận. Kiểm SQL độc lập đếm đúng **3 phiên, 10 dòng tin,
5 tin người dùng** — mỗi câu có một tin user và một phản hồi. Không thấy ghi trùng.
Toàn bộ giao dịch rollback; kiểm lại không còn tài khoản hoặc phiên Chat tổng hợp.
Adapter test dùng savepoint và reset role giữa các request tuần tự, không xác nhận
isolation/concurrency hoặc hành vi nhiều tab của trình duyệt.

Hai lượt PostgreSQL đầu vướng assertion của harness: so sánh lịch sử bằng chuỗi
JSON khiến thứ tự khóa do JSONB sắp lại bị coi là thay đổi. Đã chuyển sang so sánh
nội dung cấu trúc; lượt 03 đạt, dữ liệu mọi lượt đều rollback sạch. Không dùng hai
lượt lỗi harness để kết luận mất lịch sử. Mode lịch sử file trước đây cũng được
kiểm lại đạt tại [auth-db-http-run03.json](../../outputs/s5_wbs012_20261117/auth-db-http-run03.json).

**Kết luận:** phần tái hiện đã có kết quả thực tế/kỳ vọng và bằng chứng HTTP/SQL.
Yêu cầu tự phục hồi sau 401 của Chat trên `62cc3720` vẫn **FAIL**. Đối chứng đạt
không có nghĩa client Chat đã dùng đường refresh đó. Còn cần nhánh/commit mới của
Quân để retest đúng bản sửa, và nghiệm thu React/browser nếu cần chốt toàn luồng.

Chạy lại từ thư mục gốc, dùng tên output mới để không ghi đè bằng chứng:

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend/scripts/reproduce_s5_wbs012_auth_db.py `
  --chat-store postgres --out outputs/s5_wbs012_20261117/auth-and-chat-postgres-run04.json
```

Không phải mở backend/frontend chính hoặc chờ 15 phút. Runner mở app HTTP loopback
tạm, dùng secret ngẫu nhiên riêng để cấp JWT đã hết hạn; token không được ghi vào
file kết quả hoặc stdout. Cần tunnel PostgreSQL; `.env` và TTL chính không thay đổi.

## Kết quả mới nhất — bản sửa `c4857941`

Đã fetch và fast-forward từ `origin/backup-demo`. Commit mới
`c4857941 fix(auth): refresh research chat token on expiry` nối `chatApi` với
`authorizedFetch` và chuẩn hóa lỗi refresh thành thông báo đăng nhập lại. Đây là
mã sửa từ nhóm, không phải sửa xác thực trong task của Nhân. Bản `backup-demo`
trên máy và nhánh `nhan-s5-token-conversation-retest` đều đã cập nhật.

**Ca HTTP/PostgreSQL thật đạt.** Bằng chứng:
[auth-and-chat-postgres-recovery-run01.json](../../outputs/s5_wbs012_20261117/auth-and-chat-postgres-recovery-run01.json).
Kết quả FAIL của `62cc3720` được giữ làm lịch sử, không phải trạng thái bản hiện tại.

| Ca trên `c4857941` | Trace đo được | Kết quả lưu Chat |
| --- | --- | --- |
| Client Chat thật, access hết hạn nhưng metadata chưa biết | Gửi 401 → refresh 200 → gửi lại 200 | Đúng 1 lượt mới; cùng phiên; giữ lịch sử và VCB/LNST/2025 |
| Đối chứng dùng hàm chung sau 401 | Gửi 401 → refresh 200 → gửi lại 200 | Đúng 1 lượt mới; cùng phiên; giữ lịch sử và VCB/LNST/2025 |
| Đối chứng metadata đã hết hạn | Refresh 200 → gửi 200 | Đúng 1 lượt mới; cùng phiên; giữ lịch sử và VCB/LNST/2025 |

Mỗi ca gọi refresh đúng một lần; refresh cũ bị 401 và access mới được chấp nhận.
SQL đếm đúng **3 phiên, 12 dòng tin, 6 tin người dùng**, tương ứng mỗi phiên có
hai lượt BID → VCB. Không có ghi trùng. Tài khoản và phiên thử không còn sau rollback.
Frontend authSession/chatApi **21/21 test đạt**, gồm ca refresh đồng thời và refresh
hết hạn yêu cầu đăng nhập lại. Bộ backend 25 ca đã chạy trước đó không có thay đổi
mã backend giữa hai phiên bản; không coi test frontend mô phỏng là kiểm HTTP/DB thật.

Harness thêm lựa chọn `--expect recovery` để kiểm tiêu chí sau sửa. Mode mặc định
`--expect reproduction` vẫn giữ kỳ vọng tái hiện lỗi cũ để dùng với bản trước sửa;
chạy mode đó trên bản đã sửa có thể báo không còn tái hiện, không phải lỗi sản phẩm.

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend/scripts/reproduce_s5_wbs012_auth_db.py `
  --chat-store postgres --expect recovery `
  --out outputs/s5_wbs012_20261117/auth-and-chat-postgres-recovery-run02.json
```

**Kết luận hiện tại:** lỗi refresh sau 401 đã qua retest ở mức module client +
HTTP + auth/Chat PostgreSQL thật. Task tái hiện có đủ kết quả trước/sau để gửi review.
Chưa kiểm React/browser, timer tự động, bản nháp UI hoặc nhiều tab; không gọi đây là
nghiệm thu E2E trình duyệt hay xác minh chất lượng câu trả lời tài chính.
