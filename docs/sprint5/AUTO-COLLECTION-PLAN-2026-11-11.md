# Plan cơ chế cào tự động giá và dòng tiền

Ngày lập: 11/11/2026. Cập nhật23:08: **đã triển khai mục2A/LIVE01/LIVE02 và nhập dữ liệu rổ30; phần hoàn thiện lịch/kiểm đủ/retry bên dưới vẫn là đề xuất chưa hoàn tất**. Bằng chứng/trạng thái VPS ở `CHECKPOINT-CLAUDE-2026-11-11.md`, mục mới nhất.

**Yêu cầu đã triển khai:** giữ cập nhật các mã đang có người xem **5 giây/lượt**, đồng thời thu nền rổ **30 mã mỗi 60 giây**. Hai nhóm dùng chung bộ điều phối/quota; không có hai timer tự gọi nguồn độc lập. DBflush chạy nền có lock chung, không chặn nhịp quote; budget local giữ qua restart. Chưa xác minh quota provider hoặc thử trọn phiên thật.

Mục tiêu: mở `Chay-FinMind.cmd` là hệ thống tự thu dữ liệu đúng lịch, biết còn thiếu gì, bù được phần lịch sử nguồn cung cấp, và không báo hoàn tất khi chưa đủ dữ liệu.

Phạm vi: rổ30 quan sát từ SSIAM VN30 ngày05/11/2026, cố định tại `backend/src/market_data/universe.py`; chưa có xác nhận quyết định HOSE/ngày hiệu lực hoặc tự rebalance. Mapping30mã và lịch sử24mã mới đã nhập, tổng69643giá/34company trên VPS.10mã gốc giữ nguyên dữ liệu và scope tài chính/news. Mã ngoài rổ đang được xem có thể tham gia nhóm live trong giới hạn batch hiện có. Giá cổ phiếu dùng ENTRADE theo cơ sở đang lưu; quote/khối ngoại và VNINDEX dùng SDK KBS hiện có. Không thêm nguồn/SDK/key/chỉ báo mới.

## 1. Cách vận hành được đề xuất

**Tiếp tục chạy collector trong backend hiện có, một tiến trình giữ SDK và collector lock.** `.cmd` mở tunnel → backend → frontend; backend tự lập lịch. Nhóm nền vẫn chạy dù không có người xem; nhóm nhanh chỉ chạy khi có chart đang xem trong phiên. Frontend đăng ký/giữ lease và đọc DB/cache, nhiều người xem cùng mã dùng chung một lượt cào.

Hai cách đã cân nhắc:

| Cách | Ưu điểm | Giới hạn | Lựa chọn |
|---|---|---|---|
| Collector chạy cùng backend qua `.cmd` | Tái dùng code, SDK, lịch và lock đang có; ít thay đổi | Máy ngủ/tắt hoặc backend tắt thì ngừng cào | Đề xuất cho giai đoạn hiện tại, đúng luồng trong checkpoint |
| Collector chạy thường trực trên VPS | Có thể thu khi máy cá nhân tắt | Cần triển khai tiến trình thường trực, quản lý vận hành và bảo đảm chỉ một collector | Giai đoạn sau nếu cần hoạt động liên tục |

Không chạy thêm Task Scheduler/cron song song với backend đang giữ cùng SDK lock. DB ở VPS không có nghĩa bộ cào cũng đang chạy trên VPS.

## 2. Hiện trạng trước triển khai (giữ làm căn cứ thiết kế)

Bảng dưới là baseline ban đầu. Mục2A đã tích hợp và kiểm thử; xem checkpoint mới nhất để biết trạng thái thực tế, không dùng tracked10 dưới đây làm cấu hình hiện tại.

| Nội dung | Hiện tại | Chỗ cần hoàn thiện |
|---|---|---|
| Trong phiên | `LiveCoordinator.tick`, mặc định 5 giây/batch, tracked 10 mã và mã đang xem | Giữ cơ chế dùng chung; phân biệt số lượt gọi ứng dụng với quota thật của nhà cung cấp |
| Lịch phiên | `SessionGate` đọc lịch explicit, nghỉ trưa/ngày nghỉ; dừng tự động từ 15:01 | Dùng cùng lịch cho refresh cuối ngày, retry và kỳ vọng ngày dữ liệu |
| Activity | Lưu bản quan sát bền vững theo mã/ngày; flush DB mỗi 60 giây | Kiểm đủ 10 mã sau đóng cửa và xác nhận đã flush trước khi báo phần activity hoàn tất |
| Refresh giá | Khi backend khởi động và 15:35; lỗi thử lại sau 30 phút | Không coi nguồn chưa có phiên mới là đã đủ dữ liệu; phân loại lỗi và chặn retry vô hạn |
| Giá ngày hiện tại | Script chỉ cho phép từ 15:30 trở đi | Đây chỉ là mốc cho phép nhận nến ngày, không phải bằng chứng nhà cung cấp đã chốt hay chất lượng đã validated |
| Khóa/SDK | Một collector lock và một SDK client có khóa tuần tự | Mọi nhánh tự động/thủ công phải đi qua cơ chế hạn mức phù hợp, không tạo SDK thứ hai |
| Trạng thái | Có `daily_refresh` và `activity_persistence` trên live status | Phân biệt chạy xong, còn chờ nguồn, đủ giá, đủ activity và bị chặn đối soát |
| Launcher | Code mở tunnel có sẵn; checkpoint ghi chưa thử toàn bộ từ trạng thái sạch | Kiểm tích hợp một lần sau khi người dùng đã đóng các tiến trình hiện có |

Hai đường gọi thêm cần đưa vào cơ chế chung: `pricePolling.js` hiện có thể gọi tải lịch sử trước khi đăng ký live; job cuối ngày/khởi động trong `app.py` truyền thẳng `sdk.history` cho refresh. Khóa SDK hiện tại chống gọi đồng thời, nhưng chưa đủ để chứng minh mọi đường đều được tính trong cùng ngân sách local.

## 2A. Cơ chế 5 giây cho chart và 60 giây cho rổ nền

Gọi `B` là tập 30 mã nền; `V` là tập mã có chart hiển thị và lease còn hạn, đã loại trùng giữa các user/tab. Chỉ chọn mã có sàn đang được phép thu theo calendar.

- Cứ 5 giây: thu một batch các mã trong `V`.
- Mỗi 60 giây: đưa `B` vào **chính batch 5 giây đó**, thành `B ∪ V`; mã trùng chỉ xuất hiện một lần.
- Nếu `V` rỗng: chỉ còn một batch nền mỗi 60 giây; các mốc 5 giây khác không gọi nguồn.
- Người mới mở chart được đọc lịch sử/cache ngay, tham gia mốc live hợp lệ kế tiếp; không tạo request riêng cho mỗi user hoặc mỗi lần đổi mã.
- Mã ngoài rổ khi hết người xem/lease thì rời nhóm nhanh. Rổ nền vẫn giữ lịch60giây. Giữ giới hạn union batch100 mã và viewer1000 hiện có; không âm thầm chia thành nhiều batch làm tăng lượt gọi.

Ví dụ các mốc dispatch lý tưởng trong một phút, khi luôn có người xem:

| Mốc | Batch gửi nguồn |
|---|---|
| 09:00:00 | 30 mã nền ∪ các mã đang xem |
| 09:00:05 | Các mã đang xem |
| 09:00:10 … 09:00:50 | Các mã đang xem, mỗi5giây |
| 09:00:55 | Các mã đang xem |
| 09:01:00 | 30 mã nền ∪ các mã đang xem của phút mới |

Trong cửa sổ nửa kín `[09:00:00,09:01:00)` có tối đa **12 batch quote ở tầng ứng dụng**, không phải12batch live+1batch nền. Rổ nền không thêm một request riêng tại mốc trùng. Tăng số mã trong batch vẫn có thể tăng chi phí quota/HTTP nội bộ của SDK; con số12 không phải bằng chứng nguồn tính12request.

### Đồng hồ và xử lý chậm

1. Giữ một vòng điều phối và một request nguồn đang chạy tại một thời điểm. Dùng đồng hồ monotonic cho khoảng5/60giây, đồng hồ Việt Nam cho lịch phiên/15:35; không ghép hai `setInterval` tự gọi SDK.
2. Lưu deadline riêng nhóm nhanh/nhóm nền và lần dispatch trước; khi cùng đến hạn thì hợp batch. Không gửi trước khoảng cách tối thiểu5giây và thời điểm quota/cooldown cho phép. Callback chạy sát ranh giới giây/phút không được tạo hai request liên tiếp.
3. Nếu request trước chưa xong, không mở request thứ hai. Bỏ các lượt đã lỡ, không dồn nhiều lượt ngay sau khi hồi phục/thức máy. Giữ nhu cầu nền đến khi có lượt được dispatch, rồi lên lịch60giây tiếp theo; phần mã thiếu được ghi rõ, không báo đủ cả rổ.
4. Đổi mã/thêm user không reset đồng hồ, cửa sổ quota hay backoff. Lease20giây hiện có tiếp tục được gia hạn từ chart; tab ẩn/đóng thì bỏ đăng ký, không tiếp tục tốn nhóm nhanh cho tab đó.
5. Chart giữ nhịp đọc cache5giây/ETag như cũ. Đo riêng tuổi snapshot, thời gian nguồn phản hồi và thời điểm UI nhận dữ liệu để phát hiện lệch pha giữa backend/frontend. Một timer5giây không bảo đảm dữ liệu nguồn hoặc màn hình luôn trễ tối đa5giây.

### Ngân sách request dùng chung

- Một bộ kiểm soát cho mọi lời gọi KBS/SDK: quote live, quote nền, refresh thủ công, stock/index history và capture cuối ngày. Failed request vẫn chiếm lượt; không reset khi đổi mã hoặc khởi động lại để né quota.
- Refresh thủ công của mã đang xem dùng cache hoặc nhập vào lượt quote sắp tới; không chèn thêm một request độc lập giữa hai mốc5giây. History đã đủ trong DB thì mở chart không tự tải lại history từ SDK.
- Khi nhóm live đang hoạt động, công việc history không thiết yếu được phục vụ từ DB/cache hoặc hoãn. Không để một lượt history90giây đứng trước quote5giây. History phục vụ catch-up/khởi động cũng phải đi qua admission chung; tách giai đoạn SDK khởi động nguội khỏi trạng thái đang cập nhật ổn định.
- ENTRADE cuối ngày là nguồn khác, có nhịp tuần tự riêng; không gán lượt ENTRADE bằng lượt quota KBS. Flush DB60giây không phải request provider và không phát sinh cào lại.
- Ưu tiên quote đang xem khi tranh ngân sách; công việc nền còn thiếu phải hiện bị trễ, không giả thành đủ. Nếu quota không đủ cho nhóm nhanh thì giữ cache, báo chậm/thời gian chờ và tôn trọng hạn mức, không tiếp tục ép gửi5giây/lượt.
- **Điều kiện khả thi:** xác nhận nguồn/SDK/tài khoản hiện dùng hỗ trợ cả chi phí của12batch/phút khi luôn có người xem, kích thước batch, hạn mức giờ/ngày/tháng và các việc phụ. Bộ chặn16lượt/phút trong code chỉ là local. Chưa biết quota thực thì không được cam kết “xếp giờ là không bao giờ hết request”. Không thay key/SDK/tài khoản để né giới hạn.

Tóm lại: 5giây/60giây là mục tiêu ở trạng thái khỏe; lỗi mạng, nguồn trễ, cold start hoặc giới hạn thật phải được hiển thị. Chưa có SLA bảo đảm nhận giá mới đúng từng5giây.

Nguồn đọc: `backend/src/market_data/{app,live,session,sdk,sdk_worker}.py`, `backend/scripts/refresh_market_prices.py`, `scripts/bootstrap-finmind.ps1` và checkpoint20:55. Sau baseline này đã triển khai2A, chạy test/review, nhập VPS và restart backend; receipts trong `outputs/sprint5/dual-cadence-20261111/`.

## 3. Lịch thu đề xuất — toàn bộ giờ Việt Nam (UTC+7)

| Khi nào | Việc thực hiện | Dữ liệu/đích lưu |
|---|---|---|
| Mỗi lần backend khởi động hoặc máy thức dậy | Đọc lịch và ngày cuối đã có trong DB; xác định các phiên đã kết thúc còn thiếu. Xử lý backlog trước, bù lịch sử giá trong khả năng nguồn | `price_bars`, `price_indicators`, `market_index_bars`; backlog activity đã thu trước đó |
| 09:00–11:30 ngày giao dịch | Theo phase của từng sàn: nhóm đang xem5giây, rổ nền30mã60giây; gộp batch ở mốc trùng theo mục2A | Quote/OHLCV tạm, GTGD, ngoại mua/bán; cache chung, bản quan sát ngày cho rổ tracked |
| 11:30–13:00 | Nghỉ cào quote tự động; vẫn phục vụ dữ liệu đã có và xử lý backlog | Không gọi provider cho vòng live tự động |
| 13:00–15:01 ngày giao dịch | Tiếp tục hai nhịp5/60giây dùng chung điều phối; giữ khoảng lấy snapshot cuối phiên đã có trong `SessionGate` | Giống buổi sáng; dừng live tự động lúc15:01 |
| Mỗi 60 giây khi backend chạy | Flush các bản activity đang chờ sang DB, không cần có lượt cào mới | `daily_market_activity`; lỗi DB giữ bản local để nhập lại |
| 15:35 ngày giao dịch | Một job cuối ngày: chụp quote/khối ngoại rổ30mã, flush; lấy lịch sử giá ENTRADE + VNINDEX KBS, đối soát và thêm các phiên còn thiếu | Activity sau đóng cửa, giá ngày và indicators; raw/receipt/report |
| 16:05, 16:35, 17:05 nếu job cuối ngày chưa đủ vì lỗi tạm/nguồn chậm | Tối đa 3 lần thử lại, cách 30 phút. Chỉ xử lý phần chưa hoàn tất | Không tạo bản trùng; báo còn thiếu sau lần cuối |
| Ngoài phiên/cuối tuần/ngày nghỉ | Không polling live, không chạy job cuối ngày cho ngày nghỉ. Lần khởi động vẫn kiểm backlog và lịch sử thiếu của các ngày giao dịch trước | Không tạo nến cho ngày nghỉ |

09:00/11:30/13:00 là các mốc trong lịch dự án hiện tại; calendar và override của từng sàn có quyền ưu tiên. 15:01 là mốc dừng thu của ứng dụng, không phải tuyên bố giờ đóng cửa chính thức của mọi sàn. Lịch phiên đặc biệt được xử lý theo calendar; vẫn giữ mốc refresh bảo thủ 15:35, không cần nhận nến sớm hơn.

Nếu mở backend lúc 20:00, chạy job bù/đối soát ngay, không đợi đến 15:35 hôm sau. Nếu mở trong phiên, chỉ bù giá đến phiên đã kết thúc trước đó; quote hôm nay vẫn là quan sát trong phiên. Lần chạy khởi động không thay thế job cuối ngày của cùng ngày.

Khởi động sau 17:05 vẫn được phép chạy một lượt bù; nếu lỗi tạm thì tối đa 3 lần tiếp theo cách 30 phút. Khởi động lại không được tạo vòng retry dồn dập: tính khoảng chờ từ report lần gần nhất của cùng ngày mục tiêu. Hết lượt vẫn giữ trạng thái thiếu và thử lại ở chu kỳ ngày giao dịch kế tiếp; lỗi cơ sở giá/dữ liệu phải chờ xử lý, không tự ghi đè.

**Giới hạn khi tắt ứng dụng:** giá ngày có thể bù từ lịch sử nếu nguồn trả đủ và còn đoạn chồng lấp để đối soát. Các snapshot khối ngoại/GTGD chưa từng thu không tự tái tạo được; không hứa bù chúng bằng endpoint quote hiện tại. Sleep/tắt máy bỏ lỡ 15:35 phải được phát hiện khi vòng scheduler hoạt động lại.

## 4. Điều kiện xác định hoàn tất

Mỗi job có một `target_date`: ngày giao dịch gần nhất đã đủ điều kiện nhận nến ngày. Sử dụng lịch explicit và mốc 15:30; trước mốc này target là ngày giao dịch trước. Lịch không có/ngoài coverage thì báo cần cập nhật lịch, không đoán thứ Hai–thứ Sáu.

Lịch hiện có chỉ bao phủ đến **31/12/2026**. Đưa coverage/source vào report; cần lịch năm mới trước khi chạy sang 2027. Không tự suy ra ngày nghỉ hoặc đánh dấu “đã đủ” khi lịch hết hạn.

**Phần giá hoàn tất khi:**

- Cả30mã đã cấu hình và VNINDEX đủ các ngày cần có từ ngày cuối đã lưu đến target, theo calendar và sàn của mã; không chỉ so `max(trade_date)`.
- Các phiên chồng lấp khớp nguồn, cơ sở giá/đơn vị không thay đổi, OHLCV hợp lệ.
- Giá mới và indicators được commit cùng transaction; đọc lại DB xác nhận ngày/số dòng.
- Lặp lại cùng dữ liệu không thêm dòng và không sửa phiên cũ.

Ngày giao dịch theo calendar mà nguồn không có bar: báo `waiting_for_source` hoặc cần kiểm tra mã bị ngừng giao dịch; không tự sinh giá/volume=0. Thiếu một phần batch thì giữ job chưa hoàn tất; không ghi một phần batch giá để che việc chưa đủ.

**Phần activity hoàn tất việc thu khi:**

- Có bản quan sát đúng ngày mục tiêu cho đủ30mã cần chụp, timestamp hợp lệ và sau đóng cửa đối với lượt cuối ngày.
- Các trường có sẵn được chuẩn hóa, lưu raw/hash/provenance, flush DB đã xác nhận; không chỉ dựa vào số quote được SDK trả về.
- Bản thiếu trường có đánh dấu thiếu; không biến NULL thành 0. Chỉ số tích lũy cùng ngày được cập nhật theo quy tắc store hiện có, không cộng các snapshot.

Thu và lưu đủ **không đồng nghĩa đã đối soát chất lượng**: activity vẫn `pending_reconciliation` nếu chưa có bằng chứng và basis phù hợp. Tiền khối ngoại mua/bán không có thì giữ NULL; cửa sổ dòng tiền 5/20 phiên chưa đủ điều kiện vẫn NULL.

Vì quote chỉ trả snapshot hiện tại, job bù giá cho một ngày cũ không được gán quote hôm nay cho ngày đó. Theo dõi hoàn tất giá và activity riêng; phần giá có thể đủ trong khi lịch sử activity còn thiếu.

## 5. Lỗi, quota và ghi DB

| Tình huống | Cách xử lý đề xuất |
|---|---|
| Timeout/mất mạng/nguồn chưa có bar mục tiêu | Giữ dữ liệu gần nhất, ghi rõ phần thiếu; retry 30 phút, tối đa 3 lần sau lượt đầu |
| Rate limit/429 | Tôn trọng thời gian chờ SDK/Retry-After nếu có; không đổi key/tài khoản hay tạo SDK mới. Không thử sớm hơn cả lịch retry lẫn hạn chờ của nguồn |
| Lỗi live trong phiên | Giữ backoff hiện có 5→10→20→40→60 giây; cập nhật tình trạng stale, không dùng vòng cuối ngày để né backoff |
| Sai OHLCV, lệch phiên cũ, đổi source/basis | Dừng ghi batch giá, lưu report `blocked`, cần xem xét; không tự sửa dữ liệu cũ và không retry đối soát vô hạn |
| DB/tunnel mất sau khi đã lấy quote | Giữ backlog local. Flush mỗi 60 giây khi DB trở lại; không cần cào lại để có cùng bản quan sát |
| Hai backend/CLI cùng lấy dữ liệu | Lock từ chối tiến trình thứ hai; không tự tắt tiến trình của người dùng |
| Tunnel SSH không lên | Một lần thử theo launcher hiện có rồi dừng và báo lỗi; không áp retry dữ liệu 30 phút vào xác thực SSH |
| Nguồn chỉ trả một phần rổ30mã | Ghi rõ mã thiếu; chưa báo phần activity hoàn tất, không để một quote thành công đại diện cho cả batch |
| Tắt máy lâu, lịch sử không đủ overlap | Báo cần backfill riêng; không nối hai đoạn giá thiếu chứng cứ nguồn/basis |

Lịch hợp nhất ở mục2A cần tối đa12quote batch/phút khi luôn có người xem; không có người xem chỉ cần1quote batch/phút. Đây là nhu cầu tầng ứng dụng, chưa phải số HTTP hoặc đơn vị quota nhà cung cấp. Hạn mức SDK/tài khoản/nguồn thật là điều kiện để đáp ứng nhịp5giây; không được lấy trần16local làm bảo đảm. Các lời gọi phụ cũng phải được tính và hoãn nếu không đủ ngân sách.

## 6. Trạng thái người vận hành cần xem

Tái dùng `GET /api/market-data/live/status`, `daily_refresh`, `activity_persistence` và report trong `outputs/market-refresh/`.

- Giữ các trường cũ để không làm hỏng caller.
- Bổ sung trạng thái job (`running`, `complete`, `waiting_for_source`, `blocked`, `failed`, `disabled`), ngày mục tiêu, mã/ngày thiếu, lỗi cuối và đường dẫn report.
- `last_ok=true` chỉ khi công việc của job thực sự đủ; report tách kết quả giá và activity. Ghi giờ bắt đầu/kết thúc rõ nghĩa, không dùng một timestamp cho cả hai.
- Trong report có lịch/coverage, ngày cuối từng mã/index, số phiên dự kiến/đã ghi, raw hash và kết quả hậu kiểm. Không chứa DSN/password/token.
- Hiện riêng số mã đang xem/rổ nền, lần thành công và deadline5/60giây, batch đang chạy, số lượt trong cửa sổ trượt, thời gian nguồn phản hồi, độ trễ và lý do chờ quota. Giữ `poll_seconds=5` cho chart; không đổi thành60 vì thêm nhóm nền.
- Backend tắt hoặc `FINMIND_LIVE_ENABLED=0` thì collector/scheduler này không chạy; không hiển thị là đang tự cào.

## 7. WBS triển khai sau khi chốt plan

Không chạy lại các batch DB ngày11/11 đã commit. **LIVE01/LIVE02 đã xong**; AUTO00 đã có rổ quan sát/mapping/bootstrap nhưng chưa xác nhận quota thật/quyết định HOSE; AUTO03 đã có capture30/flush/error gate và DBflush nền. Các AC lịch/kiểm đủ/retry/report/full-session còn lại chưa được tuyên bố hoàn tất. Bảng giữ tiêu chí mục tiêu để làm tiếp.

| ID | Công việc và phạm vi file | Phụ thuộc | Tiêu chí đạt |
|---|---|---|---|
| AUTO00 | Xác nhận danh mục30mã/ngày hiệu lực, mapping, bootstrap lịch sử các mã mới và quota SDK/nguồn thực. Rà các caller của `PROJECT_SYMBOLS` trong importer/refresh trước khi sửa danh mục | Không | Có30mã đúng danh mục, mapping và lịch sử neo cùng nguồn/basis; báo rõ quota thực hoặc chưa biết; chưa có quota thì không claim nhịp5giây bền vững |
| LIVE01 | Hai nhịp hợp nhất và request admission: `backend/src/market_data/live.py`, test `backend/tests/test_market_data_live.py`, `backend/tests/test_market_activity_collector.py`; đọc `sdk.py` và callers trong `app.py` | AUTO00 |30mã60giây/nhóm xem5giây;12batch/phút; không user thì1batch/phút; union không trùng; một request đang chạy; min spacing/sliding-window/backoff/lease đúng |
| LIVE02 | Mở chart không tự tốn history đã có, giữ read5giây: `frontend/src/pages/companies/pricePolling.js`, `backend/src/api/routers/market_data.py`, tests frontend hiện có và `backend/tests/test_market_data_live_api.py` | LIVE01 | Đọc lịch sử DB ngay; không gọi SDK thừa khi mở chart; đổi mã/nhiều user không reset quota; tabẩn/đóng hết lease; ETag hoạt động |
| AUTO01 | Thống nhất ngày mục tiêu/lịch retry: `backend/src/market_data/session.py`, `backend/src/market_data/app.py`, test `backend/tests/test_market_activity_collector.py` | LIVE02 | Đúng timezone, nghỉ trưa/ngày nghỉ/coverage/override; startup trong phiên không bỏ job15:35; thức máy sau15:35 phát hiện job trễ |
| AUTO02 | Kiểm đủ giá trước commit: `backend/scripts/refresh_market_prices.py`, test `backend/tests/test_market_price_refresh.py`; đọc gate `reconcile_market_prices.py` | AUTO01 | Phát hiện nguồn chậm/thiếu ngày; không ghi phần batch; mismatch cũ blocked; atomic/idempotent và indicators đúng |
| AUTO03 | Kiểm đủ activity và backlog: `backend/src/market_data/live.py`, `backend/src/market_data/app.py`, test `backend/tests/test_market_activity_collector.py`; tái dùng store/repository | AUTO01 | Thiếu1/30 không báo đủ; capture và flush phân biệt; DB mất rồi hồi phục không nhân đôi; pending không thành validated |
| AUTO04 | Hoàn thiện lịch và trạng thái job/retry: `backend/src/market_data/app.py`, `backend/src/api/routers/market_data.py`, test `backend/tests/test_market_activity_collector.py` | AUTO02, AUTO03 | Tối đa3 retry sau lượt đầu; quota/backoff/lock dùng chung; restart không spam; status/report phản ánh thiếu và không lộ secret |
| AUTO05 | Kiểm tích hợp launcher và một ngày vận hành, cập nhật checkpoint; đọc `scripts/bootstrap-finmind.ps1`, `Chay-FinMind.cmd`, test launcher hiện có | AUTO04 | Một lần mở tunnel từ trạng thái sạch; startup bù; trong phiên live/flush; cuối ngày giá+index/activity; đọc lại DB và UI khớp |

Các bước chạm cùng `app.py`, `live.py` hay router phải thực hiện tuần tự trên bản đã tích hợp của bước trước, không cho các worker sửa đồng thời cùng file. Khi triển khai dùng ECC manager theo AGENTS, mỗi job có context/edit/test allowlist và budget cố định riêng workflow; không reset hay tái sử dụng allowance review đã hết của workflow giá trước.

Các tình huống bắt buộc dùng fake clock/provider ở unit test: trước/sau15:30, đúng15:35, UTC↔VN, ngày nghỉ, lịch hết hạn, hôm nay đã đủ, thiếu1mã, nguồn trả chậm dù HTTP200, lỗi429, mismatch phiên cũ, backend ngủ qua lịch, restart trong khoảng retry, DB mất/khôi phục. Test lịch không cần chờ đến ngày mai hay cào provider nhiều lần.

Riêng LIVE01/LIVE02: đếm12batch trong mỗi cửa sổ60giây, không chỉ phút lịch;0/1/30mã đang xem;100user cùngmã; mốc59.999→60; callback trễ; request kéo dài>5giây; lỗi/429 ngay trước mốc nền; người xem đổi mã hoặc tabẩn; mã ngoài VN30; phản hồi chỉ có29/30; history/thủ công chen vào; khởi động lại khi đang cooldown; không nổ dồn sau sleep. Đo fresh timestamp UI để phân biệt polling5giây với nguồn thật5giây.

Lệnh kiểm tối thiểu dự kiến (từ gốc repo, dùng môi trường backend hiện có):

```powershell
backend\.venv\Scripts\python.exe -B -m pytest backend/tests/test_market_data_live.py backend/tests/test_market_data_live_api.py backend/tests/test_market_data_sdk.py backend/tests/test_market_activity_collector.py backend/tests/test_market_price_refresh.py backend/tests/test_market_price_reconciliation.py backend/tests/test_price_analysis_api.py backend/src/b1_answering/tests/test_launcher.py -q
```

Các test cần PostgreSQL chạy trên owned cluster15434, không dùng VPS làm DB thử phá dữ liệu. Lượt thật đầu tiên với phiên giá mới phải hậu kiểm số phiên/indicators/VNINDEX, giữ nguyên hash các phiên cũ và xem report; không chỉ nhìn HTTP200/`last_ok`.

## 8. Quyết định đã có và đề xuất mới cần phân biệt

Đã triển khai: chạy cùng backend, viewers5giây/nền30mã60giây hợp batch, admission/lock/history/manual chung, budget giữ qua restart; history DB tránh gọi SDK thừa, DBflush nền60giây. Dừng15:01, giá từ15:30, refresh15:35 và retry30phút kế thừa code hiện có; source/basis/pending rules giữ nguyên.

Phần còn đề xuất: kiểm đủ theo calendar trước khi báo xong, thống nhất job cuối ngày theo ngày nghỉ, giới hạn3retry, lưu căn cứ retry qua restart bằng report sẵn có, phân loại blocked/waiting và trạng thái riêng giá/activity đầy đủ. Không coi các mục này đã hoàn tất chỉ vì cơ chế5/60 đã chạy.

Chưa bổ sung nguồn lịch sử khối ngoại; chưa xác minh quota/free tier hiện hành; chưa thử launcher từ trạng thái sạch hoặc phiên thực12/11. Backend8000 đã restart theo user cho phép; tunnel/frontend giữ nguyên.
