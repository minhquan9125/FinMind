# S5-WBS09.2 / S5-WBS09.3 — Bàn giao phần hội thoại

Nhân, 17/11/2026. Nhánh `nhan-next-task-20261116`, tiếp nối 09.1 tại `98a2926d`.
**Hoàn thành triển khai, sẵn sàng review; chưa xác nhận nghiệm thu trình duyệt.**

## Người dùng làm được gì?

**09.2 — Xử lý liệt kê và giới thiệu tổng quan:** sau khi hỏi về công ty con hoặc
nhân sự của FPT, người dùng có thể nói “Liệt kê ra giúp tôi”, “Cho tôi xem danh
sách” hoặc “Liệt kê ra xem”. Hệ thống giữ công ty, năm và loại quan hệ đang hỏi,
gọi lại đúng nhánh truy xuất. Trong ngữ cảnh tin tức, lệnh chuyển về danh sách;
trong BCTN, lệnh giữ chủ đề báo cáo trước đó.

“Giới thiệu tổng quan công ty này” dùng đúng công ty đang nói và tìm hồ sơ doanh
nghiệp, bỏ bộ lọc chức vụ/chỉ tiêu/kỳ không phù hợp. Nếu người dùng ghi mã mới thì
mã mới được ưu tiên. Chưa có công ty hoặc có nhiều công ty thì hỏi lại. Lệnh liệt
kê chưa xác định được đối tượng cũng hỏi lại, không tự chọn nội dung.

**09.3 — Xử lý tổng hợp nãy giờ:** “Tổng hợp nãy giờ”, “Tóm tắt nội dung phiên hiện
tại” hoặc “Tổng kết những gì vừa trao đổi” trả bản trích chọn các ý đã có nguồn
trong phiên. Mỗi nhóm giữ tên công ty và kỳ; citation được đánh lại số nhưng giữ
nguyên locator, hash và đoạn nguồn. “Nguồn đâu?” sau đó mở lại nguồn của bản tổng hợp.

Phiên mới không lấy nội dung phiên cũ. `/new` và `/moi` là ranh giới làm mới.
Tiếp tục một phiên đã lưu giữ lịch sử được kế thừa, nhưng không sửa phiên gốc.

## Cách làm

- Nhận diện các lệnh nối tiếp rõ nghĩa ở `conversation_actions.py`, dùng chung
  cho service và planner. Câu có đối tượng mới như “Liệt kê công ty con VCB” vẫn
  được parser hiện có đọc đầy đủ; không đổi ngưỡng hay classifier intent.
- `conversation_summary.py` chỉ đọc document phiên mà store đã kiểm chủ sở hữu.
  Kiểm lại pack nguồn và liên kết citation/claim; dùng bộ kiểm chứng B1 hiện có.
  Không gọi retrieval, Gemini hoặc mô hình khác để tổng hợp.
- Các pack nguồn được lưu riêng trong trường mới `evidence_packs`. Mỗi pack giữ
  nguyên schema, corpus/index hoặc snapshot feed của nó. Không ghép các corpus
  thành một phiên bản nguồn giả. Trường `evidence_pack` của câu trả lời thông thường
  giữ contract cũ; bản tổng hợp dùng `evidence_pack: null` và `evidence_packs: [...]`.
- Frontend hiển thị các nguồn được dùng từ nhiều pack, đúng số citation. Chỉ thêm
  hỗ trợ nguồn đa lượt và nhãn “Tổng hợp hội thoại”; không triển khai bộ định dạng
  danh sách/bảng tổng quát thuộc 12.1.

## Giới hạn được thể hiện rõ

Đây là tổng hợp trích chọn, không tính thêm số liệu hoặc suy ra nhận định mới.
Chỉ dùng câu trả lời `LIVE` với nguồn schema 1.1/1.2; dữ liệu fixture, nguồn hỏng,
claim không đối chiếu được hoặc kết quả chưa có citation không được biến thành
khẳng định có nguồn. Các lần hỏi lại, lỗi hoặc thiếu bằng chứng được tính là phần
chưa tổng hợp; không chép nội dung câu hỏi của người dùng vào bản tổng hợp.

Giới hạn: tối đa 12 lượt có nguồn gần nhất, 2 ý/lượt, 1.500 ký tự/ý, 30 nguồn và
240.000 byte cho các pack nguồn. Nếu lược bớt do nguồn/giới hạn, phản hồi thông báo
số lượt/ý bị lược. Nếu không đưa được ý nào vì giới hạn thì báo riêng, không nói
sai rằng dữ liệu nguồn không tồn tại. Giới hạn 2 MiB/phiên của store vẫn áp dụng.

Các bản tổng hợp và lần hỏi lại nguồn không được tổng hợp tiếp như dữ kiện mới.
Hai nguồn khác nhau trùng evidence ID bị chặn khi ghép. Nguồn là snapshot đã lưu
ở lượt gốc; không tự tra cứu lại để xác nhận chúng còn là dữ liệu mới nhất.
Kiểm chứng B1 vẫn có giới hạn về ngữ nghĩa, không được gọi là xác minh độc lập B3.

## Kiểm chứng và cách chạy lại

Các test mới nằm tại:

- `backend/tests/test_s5_wbs092_followups.py`: service/planner và API nhiều lượt.
- `backend/tests/test_s5_wbs093_summary.py`: nguồn, khác mã/kỳ, `/new`, phiên mới,
  tiếp tục phiên, nguồn hỏng, lặp tổng hợp, trùng ID và giới hạn.
- `backend/tests/test_s5_wbs09_postgres.py`: SQL/RLS thật, lưu/mở lại/tiếp tục và cách ly.
- `frontend/src/pages/research/citationView.test.js`: nguồn đa lượt trong UI.

Lượt review rộng đã bắt được hai hồi quy “Liệt kê ra xem”; đã sửa và chạy lại
**1.098 test router/09.2, tất cả đạt**. Bộ nghiệm thu cuối **349 pass / 1 skip**,
gồm **42 ca mới** (16 ca 09.2, 25 ca 09.3 và 1 ca PostgreSQL thật). Frontend Chat
**30/30 test đạt** và `npm.cmd run build` thành công.

Full backend chạy lại sau sửa hồi quy: **3522 pass / 69 fail / 27 skip / 2 xfail**.
69 lỗi tương ứng nhóm đã có trước: 64 ca cần DB thử riêng ở cổng 15434 chưa chạy,
5 ca thiếu fixture WBS02. Không hạ tiêu chí hay thay test để che lỗi. Lượt full này
chạy trước bốn ca kiểm bổ sung cuối về fixture và nguồn nhiều schema; các ca đó và
toàn bộ suite Chat liên quan đã được kiểm lại trong bộ 349 pass nêu trên.
Thống kê và danh sách lỗi được trích từ JUnit tại
[verification.json](../../outputs/s5_wbs09_20261117/verification.json).

PostgreSQL thật kiểm bằng tài khoản giả lập trong giao dịch rollback; SQL/RLS và
store là code thật, engine câu trả lời dùng nguồn giả lập. Test xác nhận không còn
tài khoản/phiên thử sau rollback. Adapter dùng savepoint bên trong giao dịch ngoài,
không kiểm isolation level hoặc cạnh tranh giao dịch. Các test graph/retrieval dùng
stub nguồn có khai báo; không coi là kiểm Neo4j hoặc chất lượng dữ liệu thật.

Từ thư mục gốc:

```powershell
$env:PYTHONPATH='backend'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& backend/.venv/Scripts/python.exe -X utf8 -m pytest `
  backend/tests/test_s5_wbs092_followups.py `
  backend/tests/test_s5_wbs093_summary.py -q -p no:cacheprovider
```

Để kiểm PostgreSQL thật, cần tunnel và `backend/.env` đã cấu hình:

```powershell
$env:RUN_S5_WBS09_DB_SMOKE='1'
& backend/.venv/Scripts/python.exe -X utf8 -m pytest `
  backend/tests/test_s5_wbs09_postgres.py -q -p no:cacheprovider
```

Frontend: trong `frontend/`, chạy `node --test src/pages/research/citationView.test.js`
và `npm.cmd run build`. Danh sách suite hồi quy có trong verification để chạy lại.

## Kịch bản review trên Web Chat

1. Phiên mới: hỏi “Các công ty con của FPT năm 2025?” rồi “Liệt kê ra giúp tôi”.
   Trace phải giữ FPT/2025/HAS_SUBSIDIARY; rỗng/lỗi graph phải phản hồi đúng tình trạng.
2. Gửi “Giới thiệu tổng quan công ty này”. Phải dùng hồ sơ FPT, không giữ lọc công ty con.
3. Hỏi thêm một câu có nguồn về VCB năm khác, rồi “Tổng hợp nãy giờ”. Kiểm từng nhóm
   mã/kỳ, số citation và liên kết nguồn; lượt chưa có bằng chứng phải được nêu là thiếu.
4. Gửi “Nguồn đâu?”, tải lại phiên và tiếp tục phiên: nguồn còn mở được, phiên gốc
   không đổi. Bấm “Nghiên cứu mới” rồi “Tổng hợp nãy giờ”: không được thấy nội dung cũ.

Chưa điều khiển trình duyệt để nghiệm thu E2E. API được kiểm bằng ASGI TestClient;
không cần dùng tài khoản hoặc token người dùng để chạy các test tự động này.
