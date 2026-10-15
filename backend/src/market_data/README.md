# Đưa giá OHLCV và tin FireAnt lên trang doanh nghiệp

Trang `/companies/FPT` đọc lịch sử OHLCV và tin từ file đã lưu. Khi panel Tổng quan đang hiển thị, frontend đăng ký mã với API; backend gom các mã đang được xem vào **một request bảng giá KBS mỗi 5 giây trong phiên**. Giá mới được ghép vào nến ngày trong bộ nhớ. Tin FireAnt vẫn chỉ đọc file.

```text
ScrapersOHLCV/data/stocks/<MÃ>/data.json ─┐
                                           ├─ API giá/tin ─ CompanyDetailPage
scrapers/data/tin_tuc_theo_ma/<MÃ>/fireant/*.json ┘
vnstock Market.quote([các mã đang xem]) ── cache RAM ── API ── chart
```

## Chạy thử trên máy

Mở terminal ở **thư mục gốc FinMind**, dùng Python có FastAPI/Uvicorn:

```powershell
python -B -m uvicorn backend.src.market_data.app:app --host 127.0.0.1 --port 8001 --workers 1
```

Nếu máy khác chưa có môi trường, tạo bằng `python -m venv venv` rồi cài gói tối thiểu `.\venv\Scripts\python.exe -m pip install fastapi uvicorn httpx`. Dùng Python của môi trường đó thay cho `python` trong lệnh trên. Không cần cài mô hình embedding.

App nhỏ này **không cần PostgreSQL, Neo4j hay Supabase**. SDK chạy trong tiến trình con riêng và chỉ khởi động khi thật sự cần lấy giá. Kiểm tra tại `http://127.0.0.1:8001/docs` hoặc chạy:

```powershell
curl.exe "http://127.0.0.1:8001/api/market-data/stocks/FPT/ohlcv?limit=5"
curl.exe "http://127.0.0.1:8001/api/market-data/companies/FPT/news?limit=5"
```

Mở terminal thứ hai, chạy frontend:

```powershell
cd frontend
npm run dev
```

Vào `http://localhost:5173/companies/FPT` (đăng nhập bằng tài khoản mock nếu được chuyển tới `/login`). Trong phiên, giá tự cập nhật khi đang xem Tổng quan. Ngoài phiên, bấm **Làm mới giá/tin** để lấy bảng giá mới nhất thủ công và đọc lại tin đã lưu. API mặc định ở `http://127.0.0.1:8001`. Muốn đổi máy chủ, tạo `frontend/.env.local` với `VITE_MARKET_DATA_API_URL=http://127.0.0.1:8000`, rồi khởi động lại Vite. Đây chỉ là địa chỉ API; **không đặt Supabase key trong file frontend**.

API này chạy riêng ở cổng 8001 để không cần khởi động hoặc sửa backend Vector RAG. Sau này dùng chung cổng 8000 thì cần đăng ký router **và tích hợp vòng đời collector** vào app chính, bảo đảm chỉ một collector toàn hệ thống, rồi đổi `VITE_MARKET_DATA_API_URL`. Chỉ đăng ký router sẽ đọc được dữ liệu đã lưu nhưng chưa chạy tự cập nhật.

## API trả gì?

- `GET /api/market-data/stocks/{symbol}/ohlcv?limit=60` trả `symbol`, `interval`, `source`, `fetched_at`, `bars`. Mỗi bar có `date`, OHLC, `volume`, `status`, `quality`, `price_basis`, `volume_basis`, `source`. Các giá OHLC giữ nguyên **chuỗi từ file gốc**; frontend chỉ đổi sang số để vẽ.
- API giá trả `ETag` theo toàn bộ nội dung trả về: lịch sử, limit, giá và trạng thái tự cập nhật. Frontend gửi `If-None-Match`; nội dung chưa đổi thì API trả `304` không có body. `fetched_at` là thời điểm lấy dữ liệu nguồn, không phải thời điểm frontend gọi API. Có thêm `live.active`, `live.stale`, `live.last_success_at`, `live.poll_seconds`, `live.reason`.
- `GET /api/market-data/companies/{symbol}/news?limit=10` trả `symbol`, `source: fireant`, `articles`. Mỗi bài có tiêu đề, mô tả ngắn, ngày đăng, URL gốc, danh mục và `marker`. API chỉ đọc thư mục đúng mã, bỏ trùng ID và không gửi toàn bộ nội dung bài lên trang.
- `GET /api/market-data/news?limit=10` đọc tin FireAnt ở `tin_tuc_chung` cho trang Tổng quan. Đây là tin đã thu thập, không tự cào bài mới khi mở trang.
- `POST /api/market-data/stocks/{symbol}/history` tải khoảng 180 ngày lịch sử cổ phiếu qua `Market.equity(symbol).ohlcv`. Frontend gọi khi mở biểu đồ, trước khi đăng ký live; dùng chung SDK/khóa/hạn mức với giá. Cache 60 giây. Chuỗi giá SDK lịch sử giữ nguyên đơn vị, không chia thêm 1.000. Lưu atomic ở `.agent-state/market-data/stocks/symbol-MÃ/history.json`; GET OHLCV ghép lịch sử này và dữ liệu cũ, sau đó phủ giá trong ngày hợp lệ.
- `POST /api/market-data/companies/{symbol}/news/refresh` tự gọi một lần khi mở mã hoặc bấm Làm mới giá/tin. Lấy một trang tin công khai FireAnt, tối đa 10 tiêu đề/mô tả, không tải nội dung toàn bài. Cache 60 giây, tối đa 10 lượt lấy/phút dùng chung, không chạy theo vòng giá 5 giây. Lưu `.agent-state/market-data/stocks/symbol-MÃ/news.json`. Nguồn lỗi giữ tin đã lưu và trả `refresh.stale/error`, nghỉ 30 giây trước khi thử lại. Tin mới nhất có thể mang ngày cũ nếu nguồn không có bài mới cho mã đó. Frontend giữ tin cũ trong lúc lấy mới, hủy chờ/thử lại khi đổi mã. SDK và tin có hạn mức riêng; không cần API key người dùng.
- `GET /api/market-data/indices/{symbol}/ohlcv` tải lịch sử VNINDEX, VN30, HNXINDEX hoặc UPCOMINDEX khi bấm chỉ số. Giá chỉ số giữ đơn vị điểm, không chia 1.000. Cache RAM 60 giây, dùng chung SDK, khóa lấy dữ liệu và hạn mức với cổ phiếu; có thể trả 429 khi đang lấy giá khác. Bấm Thử lại sau khoảng chờ. Ngoài phiên vẫn có thể tải thủ công. Không ghi vào ScrapersOHLCV hoặc DB.
- GET giá không tự gọi nguồn; mã chưa có dữ liệu trả mảng rỗng. Trang doanh nghiệp gọi POST lịch sử khi mở để bổ sung các phiên trước rồi mới đăng ký live. Nếu tải lịch sử thất bại, vẫn giữ nến đã có và báo lỗi. Mã không hợp lệ trả 400; `limit` ngoài phạm vi trả 422; JSON lỗi/không đọc được trả 503.
- `PUT /api/market-data/live/viewers/{UUID}` với JSON `{"symbol":"FPT"}` đăng ký/gia hạn một mã cho một chart. `DELETE` cùng URL hủy đăng ký. Đổi mã thay đăng ký cũ; nhiều chart cùng mã được gộp. Đăng ký tự hết hạn sau 20 giây nếu mất kết nối/hủy không tới server. Tối đa 100 mã khác nhau và 1.000 đăng ký.
- `POST /api/market-data/stocks/{symbol}/refresh` lấy thủ công, dùng chung hạn mức với vòng tự động. Nếu có giá lấy thành công trong 60 giây gần nhất thì dùng cache; không gọi lại nguồn. Hết hạn mức trả 429 kèm `Retry-After`; nguồn lỗi trả 503 và giữ biểu đồ trước.
- `GET /api/market-data/live/status` xem số đăng ký, mã đang xem, số mã cache và khoảng chờ. Đăng ký không trực tiếp gọi nguồn, GET giá cũng không trực tiếp gọi nguồn.

File FPT đang có nến với `status: pending_reconciliation` hoặc `open` và `price_basis: unknown`. Trang hiển thị rõ đây là snapshot chưa xác nhận cơ sở/đơn vị giá, không ghi là realtime. `marker: check` của tin chỉ có nghĩa tìm được bài **tương đồng về văn bản** ở nguồn đối chiếu, không xác nhận tin đúng. `uncheck` nghĩa chưa đạt ngưỡng đối chiếu; không kết luận tin sai.

Chạy test API từ thư mục gốc:

```powershell
python -B -m unittest backend.tests.test_market_data_api backend.tests.test_market_data_live backend.tests.test_market_data_live_api backend.tests.test_market_data_validation backend.tests.test_market_data_sdk -v
node --test frontend/tests/pricePolling.test.js
```

## Sau này đổi sang Supabase

Frontend chỉ biết hợp đồng JSON của hai URL trên. Thay `FileMarketDataRepository` trong `repository.py` bằng lớp đọc Supabase có cùng hai hàm `get_ohlcv(symbol, limit)` và `get_news(symbol, limit)`, rồi đổi hàm `get_market_data_repository()` trong `backend/src/api/routers/market_data.py` để trả lớp mới. Giữ nguyên cấu trúc JSON trả về thì `CompanyDetailPage.jsx`, `PriceHistory.jsx` và `marketDataApi.js` không phải sửa. Đặt URL/key Supabase trong **môi trường backend**; dùng service role key chỉ phía server. Nên lưu nến với khóa `(symbol, trade_date, source, revision)` và bài báo với khóa `id` hoặc URL chuẩn hóa để cập nhật mà không tạo bản trùng.

`FINMIND_DATA_ROOT` là tùy chọn cho cách đọc file: trỏ tới thư mục chứa `data_pipeline/` khi chạy trong Docker hoặc máy khác. Mặc định là thư mục gốc repo hiện tại.

Panel giá trên trang doanh nghiệp vẽ nến OHLC ngày: xanh khi giá đóng cửa bằng hoặc cao hơn giá mở cửa, đỏ khi thấp hơn. Bóng nến thể hiện giá cao/thấp; cột bên dưới thể hiện khối lượng. Di chuột hoặc bấm một nến để xem số liệu phiên đó. Frontend lấy tối đa 250 phiên đã lưu để hiển thị; đây là biểu đồ xem dữ liệu, chưa có bộ công cụ phân tích như TradingView.

Frontend dùng Lightweight Charts để chọn 30/90/tất cả phiên, cuộn chuột phóng to, kéo ngang xem lịch sử và mở rộng biểu đồ. Nút **Về mới nhất** đưa về phiên cuối. Nếu người xem đang xem quá khứ, dữ liệu mới không tự kéo biểu đồ về cuối; nút này báo có dữ liệu mới. Khi tab Tổng quan và tab trình duyệt đang hiển thị, frontend kiểm tra API giá sau mỗi khoảng 5 giây từ lúc phản hồi trước; lỗi thì giữ chart cũ và thử lại thưa dần, tối đa 30 giây. Ẩn tab hoặc rời trang thì dừng. Tin FireAnt không tự tải theo vòng 5 giây; dùng nút **Làm mới giá/tin** để tải lại cả hai panel.

Không cần mở `Mo-bieu-do.cmd` khi dùng cập nhật giá trên frontend. Phần mới **không ghi hoặc sửa bất kỳ file nào trong `data_pipeline/ScrapersOHLCV`**. Lịch sử cũ và lịch giao dịch được đọc từ đó; lịch sử cổ phiếu và tin vừa tải lưu riêng dưới `.agent-state/market-data/stocks`. Overlay giá live vẫn chỉ nằm trong RAM, mất khi khởi động lại API. Chưa có bước lưu vào Supabase hoặc đối soát đóng phiên. Chỉ batch realtime mã cổ phiếu 3 chữ cái; bốn chỉ số dùng endpoint lịch sử riêng, tải thủ công khi bấm xem trên Tổng quan và cache RAM 60 giây.

## Phiên giao dịch, hạn mức và cấu hình

Backend đọc lịch có ngày giao dịch được xác nhận trong `ScrapersOHLCV/config/calendar.live.json`. Nghỉ trưa, cuối tuần, ngày nghỉ, lịch thiếu hoặc ngày ngoài phạm vi lịch đều dừng tự lấy giá. Hiện lịch bao phủ năm 2026; cần bổ sung lịch đã xác nhận trước khi dùng tự động sang năm khác. Kiểm tra lại phiên ngay trước request trong tiến trình SDK và trước khi nhận kết quả. Giá nguồn sai ngày, sai OHLC, sai đơn vị/kiểu, khối lượng lùi, biên độ thu hẹp hoặc khác cơ sở giá sẽ bị bỏ; giảm giá đóng cửa bình thường vẫn được nhận.

Một batch 10 mã mỗi 5 giây tương đương khoảng 12 request/phút, chưa tính lỗi/retry. Tự động và thủ công dùng chung ngân sách 16 lượt/phút, cách nhau ít nhất 5 giây; lỗi cũng tiêu lượt và tăng thời gian nghỉ tới 60 giây. SDK giữ nguyên cơ chế guest/auth/quota của nó trong một tiến trình con tồn tại lâu dài. Không nên đồng thời chạy nhiều công cụ lấy giá cùng nguồn/tài khoản vì ngân sách này chỉ quản lý collector mới. Nguồn có thể trễ; đây không phải feed tick-by-tick hoặc cam kết giá mới mỗi 5 giây.

Biến môi trường đặt trước khi khởi động API:

| Biến | Mặc định | Chức năng |
|---|---|---|
| `FINMIND_LIVE_POLL_SECONDS` | `5` | Khoảng cách tối thiểu giữa request nguồn, không nhận giá trị dưới 5 |
| `FINMIND_LIVE_ENABLED` | `1` | Đặt `0` để tắt collector và tải lịch sử SDK; API đọc file và lấy tin thủ công vẫn hoạt động |
| `FINMIND_VNSTOCK_PYTHON` | Python SDK đã có, nếu không có thì Python hiện chạy API | Đường dẫn Python có `vnstock==4.0.9` và `vnai==2.6.3` |
| `FINMIND_DATA_ROOT` | Gốc repo | Gốc chứa dữ liệu và runtime mới |

Ví dụ đổi khoảng lấy giá thành 10 giây trong PowerShell:

```powershell
$env:FINMIND_LIVE_POLL_SECONDS = "10"
python -B -m uvicorn backend.src.market_data.app:app --host 127.0.0.1 --port 8001 --workers 1
```

SDK ưu tiên Python hiện có trong `ScrapersOHLCV/.agent-state/vnstock-venv/Scripts/python.exe`, nhưng chạy module mới `backend.src.market_data.sdk_worker` với `-B`. HOME/cache SDK mới nằm trong `.agent-state/market-live/sdk-home`, khóa collector trong `.agent-state/market-live/collector.lock`. Môi trường SDK chưa có trên máy khác thì tạo môi trường riêng **ngoài ScrapersOHLCV**, cài phiên bản trên và trỏ `FINMIND_VNSTOCK_PYTHON` vào Python đó. Không cần API key guest.

Chỉ chạy API này với **một Uvicorn worker** trên cùng máy/root. Khóa file sẽ từ chối collector thứ hai để không nhân số request. Muốn triển khai nhiều máy cần tách collector dùng chung và kho cache chung trước.
