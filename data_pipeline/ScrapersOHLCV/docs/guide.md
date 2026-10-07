# ScrapersOHLCV

Pipeline OHLCV ngày độc lập cho FinMind, Python 3.11+. Code, SQLite, export và checkpoint đều nằm trong folder này. Chưa nối backend, frontend hoặc Supabase.

## Chạy thử offline

Mở terminal tại `data_pipeline/ScrapersOHLCV`. Python cần `tzdata` trên Windows; live cần thêm `websockets` 16.x. Các dependency đã dùng trong phiên phát triển có sẵn; không có service được cài đặt hoặc chạy ngầm.

```powershell
python -m ohlcv --help
python -m ohlcv --calendar fixtures/calendar.json validate-calendar
python -m ohlcv --calendar fixtures/calendar.json --db data/runtime/demo.sqlite3 --now 2026-10-06T03:00:10+00:00 --price-multiplier 1 --price-basis raw --volume-basis matched replay --input fixtures/stream.jsonl
python -m ohlcv --calendar fixtures/calendar.json --db data/runtime/demo.sqlite3 --now 2026-10-06T03:00:10+00:00 status
python -m ohlcv --calendar fixtures/calendar.json --db data/runtime/demo.sqlite3 export --include-open --output data/runtime/demo-ohlcv.json
```

Lần replay đầu trên database mới nhận 2 snapshot và từ chối 1 snapshot trùng. Kết quả có **một** dòng FPT ngày 2026-10-06, volume **1300**, revision 2, status `open`. Replay lại cùng database không tăng revision. Giá fixture dùng multiplier 1; đây là dữ liệu giả lập, không phải xác nhận đơn vị giá hoặc lịch giao dịch thật DNSE.

Các option chung (`--calendar`, `--db`, `--now`, `--price-multiplier`, …) đặt **trước** subcommand. Mọi đường dẫn tương đối tính từ folder này, hoặc từ `--root` nếu chọn một folder con trong phạm vi này. Đường dẫn thoát phạm vi, symlink và junction bị từ chối. Mã lỗi CLI: 0 thành công, 2 thất bại, 130 Ctrl+C. Replay malformed JSON hoặc lỗi lưu dữ liệu dừng với mã 2; các snapshot đã commit trước đó vẫn được giữ.

## Xem biểu đồ chứng khoán

### Nhập mã và lấy dữ liệu thật qua vnstock

**Double-click [Mo-bieu-do.cmd](../Mo-bieu-do.cmd)**. File mở trình duyệt tại **http://127.0.0.1:18765/** và giữ server Python trong cửa sổ terminal. Cổng 8765 dành cho app quản lý Codex của người dùng, không sử dụng cho biểu đồ. Giữ cửa sổ terminal mở khi dùng; Ctrl+C hoặc đóng cửa sổ để dừng. Nếu cổng 18765 đã có ứng dụng khác thì launcher báo lỗi, không dừng hay thay thế ứng dụng đó.

Nhập mã như **FPT, VCB, MBB, CTR, HPG**, rồi Enter hoặc bấm **Xem biểu đồ**. Server tra mã/sàn từ danh sách vnstock/KBS, lấy nến ngày của khoảng 180 ngày gần nhất và hiển thị biểu đồ thật. Mã mới có dữ liệu hợp lệ sẽ tự tạo thư mục mới:

```text
data/stocks/
  FPT/data.json
  VCB/data.json
  MBB/data.json
  CTR/data.json
```

Mỗi `data.json` chứa OHLCV, SMA20/SMA50/RSI14 (Wilder), nguồn, thời điểm lấy, tên công ty và revision. Chỉ số chưa đủ số phiên trả `null`. Đây là chỉ số tính từ giá đóng cửa, không phải báo cáo tài chính doanh nghiệp. Một file được thay thế nguyên tử, giữ nhất quán nến/chỉ số/provenance. Mã sai hoặc nguồn lỗi giữ dữ liệu trước đó và không tạo thư mục mã rỗng. Bản lưu và giá trong SDK không được gắn nhãn final/raw/adjusted khi chưa kiểm chứng. Giá dùng cách viết thập phân ngắn nhất của số SDK; không cam kết giữ độ chính xác JSON gốc trước khi SDK chuyển sang float.

**Tự cập nhật trong phiên** được bật sẵn khi double-click **Mo-bieu-do.cmd**. Chỉ lấy bảng điện của mã đang xem, mỗi 5 giây sau khi phản hồi xong; đổi mã sẽ hủy vòng cũ, ẩn tab sẽ tạm dừng, quay lại sẽ kiểm tra phiên rồi lấy giá mới. Cập nhật nến ngày/volume/chỉ số và lưu file, giữ vùng zoom đang xem. Bỏ chọn ô tự cập nhật để dừng. Không chạy service khi khởi động máy; cần mở launcher và giữ terminal.

Giờ Việt Nam: HOSE 09:00–11:30 và 13:00–14:45; HNX/UPCOM 09:00–11:30 và 13:00–15:00. Nghỉ trưa, cuối tuần, nghỉ lễ, ngoài phiên hoặc ngoài phạm vi lịch: **chỉ lấy thủ công** như trước. Trình duyệt kiểm tra phiên với server cục bộ mỗi 30 giây, không gọi vnstock ngoài phiên. Lịch 2026 được kiểm chứng tại [calendar.live.sources.md](../config/calendar.live.sources.md), whitelist trong `config/calendar.live.json`; đến năm mới phải cập nhật lịch chính thức và khởi động lại server. Thiếu/hỏng lịch sẽ tắt tự động.

**Cập nhật dữ liệu** thủ công lấy lịch sử khi cache đủ 60 giây; hai lượt lịch sử cách ít nhất 10 giây, danh sách mã cache 24 giờ. Cả thủ công và tự động dùng chung hạn mức server: 16 credit/60 giây và khoảng cách tối thiểu 5 giây; catalog/lịch sử dành 3 credit để dự phòng retry SDK, quote dành 1. Khi nhiều tab cùng mở hoặc nguồn lỗi, app chờ/backoff 15–60 giây. SDK giữ nguyên cơ chế Guest/quota của nó, chạy trong một child process tồn tại suốt phiên server để không mất trạng thái qua mỗi lần polling. Không cần API key. Agent setup/telemetry tắt; cache SDK nằm trong `.agent-state/vnstock-home`. Server chỉ bind `127.0.0.1`, kiểm tra Host/Origin/token trước khi lấy/lưu dữ liệu, không phục vụ thư mục tùy ý.

Giá quote đồng được chia 1000 để khớp đơn vị lịch sử vnstock/KBS đã kiểm chứng từ SDK. `TD` phải là ngày phiên hiện tại; không tạo nến hôm nay từ giá hôm qua. Volume lũy kế giảm hoặc biên giá lùi sẽ giữ bản cũ. Receipt bảng điện lưu riêng `data/stocks/<MÃ>/live.json`; các trường decimal bổ sung được giữ dạng text. Khi thiếu các phiên gần nhất, tự tải bù lịch sử trong phiên trước khi lấy quote. Dữ liệu vẫn là nến **1D chưa chốt**, không phải streaming tick hoặc nến phút; chưa đo độ trễ nguồn trong phiên.

Hiện đã lấy thật **123 nến FPT** qua vnstock/KBS và nhúng bản lưu vào HTML; kiểm tra trình duyệt cũng đã lấy thật **123 nến VCB**, tự tạo `data/stocks/VCB/data.json`. Các thư mục MBB/CTR được tạo qua luồng nhập mã trong phiên này. Mở riêng `chart.html` vẫn xem được bản lưu FPT offline; để lấy mã khác hãy mở `Mo-bieu-do.cmd`.

Môi trường riêng hiện đã có sẵn. Khi chuyển sang máy mới, cài tại folder này:

```powershell
python -m venv .agent-state/vnstock-venv
.agent-state/vnstock-venv/Scripts/python.exe -m pip install -r requirements/vnstock.txt
.agent-state/vnstock-venv/Scripts/python.exe -m ohlcv.app.server --open
# Nếu cần cổng khác:
.agent-state/vnstock-venv/Scripts/python.exe -m ohlcv.app.server --port 18766 --open
```

Mở trực tiếp **[chart.html](../web/chart.html)** bằng Chrome/Edge/Firefox (double-click file) để xem bản lưu offline, không cần server hoặc API key. Nhập mã để lấy dữ liệu mới cần launcher/server cục bộ ở mục trên. Trang có biểu đồ nến ngày, volume bên dưới, OHLCV khi rê chuột/chạm, zoom/kéo vùng xem, chọn mã và lọc ngày/nến đã chốt, giao diện sáng/tối và tải ảnh PNG.

**Double-click `chart.html` hiện mở ngay bản lưu dữ liệu thật FPT: 123 phiên từ 2026-04-09 đến 2026-10-06.** Nguồn và thời điểm thu thập được ghi trên trang. Dữ liệu được nhúng sẵn trong HTML, không cần server hoặc chọn file, không gọi mạng khi mở. Mỗi lần chạy collector công khai sẽ cập nhật bản lưu này; F5/mở lại HTML để thấy lần thu thập mới. Đây là bản lưu, không phải feed giá trực tiếp.

Để xem file khác, bấm **Mở JSON export** hoặc kéo thả JSON vào trang. Nút **Xem mẫu replay** mở mẫu giả lập một phiên để kiểm tra; F5 quay về bản lưu đã thu thập. Nếu chưa có lịch sử thật được nhúng thì trang mới dùng mẫu replay. Tooltip/bảng phân biệt nguồn và trạng thái dữ liệu.

```powershell
# Đặt calendar/database đúng với dữ liệu bạn đã thu thập.
python -m ohlcv --calendar fixtures/calendar.json --db data/runtime/demo.sqlite3 export --include-open --output data/runtime/demo-ohlcv.json
```

Giá giữ nguyên đơn vị/basis của nguồn; không tự nhân hệ số hoặc quy đổi. Các chuỗi khác sàn/nguồn/basis được tách riêng. Thân nến tô màu đặc: xanh tăng, đỏ giảm, xanh dương không đổi so với mở cửa. Trạng thái đã chốt/chưa chốt hiển thị trong tooltip và bảng; ngày `no_trade` không vẽ thành nến giả. Tooltip/bảng giữ nguyên chuỗi Decimal và volume bigint; trục/hình vẽ dùng số xấp xỉ rút gọn. Chấp nhận JSON export `version: 1`, `count` khớp `bars`, tối đa 10 MiB/20.000 dòng; giá vẽ hỗ trợ 1e-100 đến 1e100. File sai được báo lỗi và giữ dữ liệu trước đó. Bảng hiển thị tối đa 100 phiên cuối vùng xem.

Kiểm thử dữ liệu JavaScript bằng `node --test tests/test_chart.cjs` nếu máy có Node; người xem biểu đồ không cần Node. Kiểm tra Chrome thực tế qua file://, desktop/tablet/mobile, nhập file, zoom/pan/filter, tooltip chính xác và xuất PNG đã được thực hiện; bằng chứng ở `.agent-state/chart-browser-verification.json`.

## Calendar và universe

`config/universe.json` chứa mapping ticker → sàn, ví dụ `{"FPT":"HOSE"}`. Ticker phải viết hoa, ASCII chữ/số, tối đa 10 ký tự; sàn gồm HOSE/HNX/UPCOM.

Trước khi thu thập thật, tạo `config/calendar.json` từ nguồn đã kiểm chứng. `config/calendar.example.json` chỉ minh họa schema; **không phải lịch chính thức**. Không có lịch sản xuất mặc định được suy ra từ thứ trong tuần. `working_dates` là whitelist ngày giao dịch trong khoảng `coverage_start`–`coverage_end`. Ngoài khoảng này pipeline từ chối recovery và không chạy live. Ghi nguồn vào `source`; tự xác nhận coverage của phản hồi ngày làm việc từ nhà cung cấp, không mở rộng coverage bằng phỏng đoán.

`overrides` có dạng:

```json
{"2026-10-06":{"HOSE":[{"start":"09:00","end":"10:00","phase":"continuous"}],"HNX":[]}}
```

Override chỉ áp dụng trên ngày đã có trong whitelist. Danh sách rỗng là sàn đóng cửa. Session phải có giờ HH:MM, không chồng lấn/qua đêm; phase gồm `ato`, `continuous`, `lunch`, `atc`, `after_hours`, `halted`. Session toàn `halted` không cung cấp bằng chứng chốt nến. Default giờ phiên theo contract dự án; nếu lịch/sàn thay đổi, cập nhật overrides từ nguồn kiểm chứng.

## Thu thập thật qua DNSE

### Lịch sử công khai, không cần API key

Người dùng đã chọn lấy dữ liệu công khai miễn phí, không đăng nhập. Đã thực hiện **một GET** đến endpoint chart công khai DNSE, nhận **123 phiên FPT ngày 2026-04-09 đến 2026-10-06** (HTTP 200 lúc 2026-10-06 16:36:20 +07:00). SQLite: `data/runtime/public-candles.sqlite3`; JSON cho biểu đồ: `data/runtime/public-ohlcv.json`; receipt URL/thời gian/hash: `data/runtime/public-fetch.json`. Mở `chart.html` là thấy ngay bản lưu dữ liệu thật này. Collector tự đồng bộ export vào HTML để lần mở tiếp theo không phải chọn JSON thủ công.

```powershell
# Mỗi lần chạy: một request cho một mã, mặc định 180 ngày đến hôm nay.
python -m ohlcv.history.public --symbol FPT --exchange HOSE
# Hoặc chọn khoảng ngày cụ thể (không quá 366 ngày khoảng cách giữa hai mốc).
python -m ohlcv.history.public --symbol FPT --exchange HOSE --start 2026-04-09 --end 2026-10-06
```

Đây là đường thu thập độc lập từ `https://api.dnse.com.vn/chart-api/v2/ohlcs/stock`, không phải signed OpenAPI recovery. Không dùng key, giả headers đăng nhập, xử lý CAPTCHA hoặc thử vượt xác thực; không retry/poll tự động, gặp lỗi HTTP thì dừng. Không cần tự tạo lịch giao dịch: chỉ lưu ngày nguồn thực sự trả về, không suy ra ngày còn thiếu/holiday. Giữ nguyên đơn vị giá (`multiplier=1`), source `dnse_public`, price/volume basis `unknown`, status `pending_reconciliation`; receipt không chứng minh finality. Chưa gắn nhãn raw/adjusted/matched/total khi không có bằng chứng. Database riêng không trộn với demo hoặc signed provider. Thu thập lại dữ liệu giống nhau không tăng revision; sửa dữ liệu từ quan sát mới tăng revision. Chưa cài scheduler hay chạy collector nền.

### Signed OpenAPI / WebSocket (cần credentials)

Credentials chỉ đọc từ **process environment** `DNSE_API_KEY` và `DNSE_API_SECRET`. Code không tự đọc `.env`, không nhận secret từ argument và không in request headers/body. Dùng secret manager hoặc thiết lập environment riêng của terminal. Không lưu credentials vào fixture, config, README hoặc checkpoint.

Đơn vị giá và provenance phải được xác nhận với nguồn trước khi cấu hình `--price-multiplier`, `--price-basis raw|adjusted|unknown`, `--volume-basis matched|total|unknown`. Multiplier bắt buộc cho recover/replay/live. Basis mặc định `unknown`; code không tự nhận định dữ liệu raw chỉ vì đến từ DNSE. Dữ liệu basis/quality chưa rõ không được tự chốt.

```powershell
# Thay PRICE_MULTIPLIER bằng hệ số đã xác nhận; đặt basis đúng theo dữ liệu nguồn.
python -m ohlcv --price-multiplier PRICE_MULTIPLIER --price-basis raw --volume-basis matched recover --start 2026-10-05 --end 2026-10-06
python -m ohlcv --price-multiplier PRICE_MULTIPLIER --price-basis raw --volume-basis matched live --start 2026-10-05 --duration 28800 --max-reconnects 5
python -m ohlcv export --output data/runtime/closed-daily.json
```

Mỗi request recovery tối đa 366 ngày khoảng cách giữa hai mốc; các khoảng dài hơn cần chia thành từng lần. Không request ngày tương lai. Live dùng đồng hồ thực, timezone Việt Nam, giới hạn duration ≤86400 giây; không dùng `--now`. Live kiểm tra calendar, recovery ban đầu, HMAC auth và subscribe hai kênh daily; mỗi lần reconnect sẽ auth/subscribe/recover lại. Số reconnect có giới hạn, lỗi auth/protocol/persistence dừng ngay. Không subscribe tick hoặc intraday, không lưu raw stream. Live hoạt động tuần tự cùng thread SQLite; heartbeat WebSocket và JSON có timeout. Ctrl+C dừng tiến trình, các snapshot đã commit còn nguyên.

Duration là giới hạn mềm cho tác vụ đang chặn: một batch recovery REST có thể kéo dài qua deadline theo số ticker và timeout/retry HTTP. Không có scheduler/service tự cài; lệnh live chạy hữu hạn trong terminal và chờ phiên mở khi cần. Khi hết phiên, runner giữ tối đa 60 giây để nhận sự kiện cuối rồi recovery lại; việc đó không tự biến today's REST thành nến closed.

## Quy tắc dữ liệu

- SQLite có khóa `(symbol, trade_date)`, lưu OHLC dưới dạng Decimal text và timestamps có timezone; WAL và transaction `BEGIN IMMEDIATE` bảo vệ batch. Revision được tạo bởi state, không tin revision từ stream.
- Volume trong daily snapshot là cộng dồn của nguồn: snapshot mới **thay** volume, không cộng vào volume cũ. Opening cố định trong luồng ordinary; authoritative recovery có thể sửa opening/extrema/volume. Timestamp cũ, conflict cùng timestamp và provenance khác bị từ chối.
- Nến `no_trade` chỉ khi **đủ trường nguồn**, tất cả giá null/zero và volume zero. Dữ liệu thiếu không được bịa thành giá, volume hoặc ngày giao dịch. `missing_expected` báo ngày nguồn chưa trả về, không tạo dòng giả.
- `closed` cần lịch ngày đó đã kết thúc và bằng chứng finality: sự kiện `bc` daily có source timestamp không cũ hơn session end, hoặc dữ liệu ngày quá khứ qua signed REST đã đối soát. Today's REST luôn `open`/`pending_reconciliation`, kể cả sau giờ đóng cửa.
- Recovery có thể sửa nến historical đã chốt bằng revision mới, giữ provenance; nến closed không mở lại. Today's nonfinal REST không sửa nến đã closed. Export mặc định chỉ lấy closed; `--include-open` lấy cả provisional.
- Recovery commit từng symbol; nếu symbol sau lỗi, các symbol đã commit được giữ và in-memory book đồng bộ với SQLite. Mỗi stream update được commit trước khi publish in-memory state; restart khôi phục latest từ SQLite.
- `reconciled_at` ở nến provisional ghi mốc quan sát recovery, không có nghĩa nến đã closed. Sau khởi tạo/đối soát REST, ordinary stream phải có timestamp nguồn **mới hơn** mốc này; snapshot buffer trước recovery bị từ chối. Timestamp nguồn vẫn giữ nguyên hoặc null theo nguồn, không được lấy từ đồng hồ receipt. Recovery lại dữ liệu giống hệt không đổi revision/mốc quan sát. Để chốt nến vẫn cần các điều kiện finality bên trên.

Path confinement kiểm tra trước ghi; với stdlib cross-platform không cam kết chống tuyệt đối việc một tiến trình khác thay directory/link trong đúng khoảng giữa check và write. Chạy trong thư mục riêng có quyền truy cập kiểm soát.

## Kiểm tra và checkpoint

```powershell
python -m pytest tests -q -p no:cacheprovider
python .agent-state/verify.py
python .agent-state/audit_scope.py
python .agent-state/worker_budget.py
```

`verify.py` đo executable-line coverage bằng stdlib `trace`, không đo branch coverage; report `.agent-state/verification.json`. Fixture tạm của tests nằm trong `.agent-state/test-tmp`. Windows không có quyền symlink sẽ skip các trường hợp tương ứng. Checkpoint và quyết định review nằm trong `.agent-state`; proposal worker không tự động được áp dụng. `worker-budget.json` tính token OmniRoute riêng, ceiling **1.000.000**, gồm các attempt ghi nhận từ checkpoint trước và reserve cho attempt chưa báo usage; không tính token Codex.

Đã chạy thu thập lịch sử thật từ endpoint chart công khai như mô tả phía trên. Chưa chạy smoke test signed DNSE OpenAPI/WebSocket; đường này cần credentials hợp lệ, calendar đã kiểm chứng và xác nhận đơn vị/basis giá.

Nguồn giao thức đã đối chiếu ngày 2026-10-06: [DNSE OHLC REST](https://developers.dnse.com.vn/docs/dnse/get-ohlc-history/), [ngày làm việc](https://developers.dnse.com.vn/docs/dnse/get-market-working-dates/), [REST signing](https://github.com/dnse-tech/openapi-sdk/blob/main/python/dnse/api/common.py), [WebSocket auth](https://github.com/dnse-tech/openapi-sdk/blob/main/python/dnse/websocket/auth.py), [daily subscriptions](https://github.com/dnse-tech/openapi-sdk/blob/main/python/dnse/websocket/client.py). Header version pin `2026-07-23` theo SDK đọc trong phiên; cần kiểm tra tương thích khi provider thay đổi.
