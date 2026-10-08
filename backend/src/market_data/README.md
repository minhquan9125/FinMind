# Đưa giá OHLCV và tin FireAnt lên trang doanh nghiệp

Trang `/companies/FPT` hiện có hai panel đọc **file JSON đã lưu**. Crawler vẫn chạy riêng; mở trang hoặc tải lại trang không kích hoạt việc cào dữ liệu.

```text
ScrapersOHLCV/data/stocks/<MÃ>/data.json ─┐
                                           ├─ API chỉ đọc ─ CompanyDetailPage
scrapers/data/tin_tuc_theo_ma/<MÃ>/fireant/*.json ┘
```

## Chạy thử trên máy

Mở terminal ở **thư mục gốc FinMind**. Máy hiện tại có `venv/` chứa FastAPI/Uvicorn, nên chạy:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.src.market_data.app:app --host 127.0.0.1 --port 8001
```

Nếu máy khác chưa có `venv/`, tạo môi trường bằng `python -m venv venv` rồi cài gói tối thiểu `.\venv\Scripts\python.exe -m pip install fastapi uvicorn httpx`. Không cần cài cả mô hình embedding để chạy app nhỏ này.

App nhỏ này chỉ đọc file, **không cần PostgreSQL, Neo4j hay Supabase**. Kiểm tra tại `http://127.0.0.1:8001/docs` hoặc chạy:

```powershell
curl.exe "http://127.0.0.1:8001/api/market-data/stocks/FPT/ohlcv?limit=5"
curl.exe "http://127.0.0.1:8001/api/market-data/companies/FPT/news?limit=5"
```

Mở terminal thứ hai, chạy frontend:

```powershell
cd frontend
npm run dev
```

Vào `http://localhost:5173/companies/FPT` (đăng nhập bằng tài khoản mock nếu được chuyển tới `/login`). Bấm **Làm mới giá/tin** sau khi crawler ghi snapshot mới. API mặc định ở `http://127.0.0.1:8001`. Muốn đổi máy chủ, tạo `frontend/.env.local` với `VITE_MARKET_DATA_API_URL=http://127.0.0.1:8000`, rồi khởi động lại Vite. Đây chỉ là địa chỉ API; **không đặt Supabase key trong file frontend**.

API này chạy riêng ở cổng 8001 để không cần khởi động hoặc sửa backend Vector RAG. Sau này nếu muốn dùng chung cổng 8000, nhóm backend chỉ cần đăng ký `market_data.router` vào `backend/src/main.py` và trỏ `VITE_MARKET_DATA_API_URL` tới cổng đó.

## API trả gì?

- `GET /api/market-data/stocks/{symbol}/ohlcv?limit=60` trả `symbol`, `interval`, `source`, `fetched_at`, `bars`. Mỗi bar có `date`, OHLC, `volume`, `status`, `quality`, `price_basis`, `volume_basis`, `source`. Các giá OHLC giữ nguyên **chuỗi từ file gốc**; frontend chỉ đổi sang số để vẽ.
- API giá trả `ETag` theo phiên bản file. Frontend gửi `If-None-Match` ở lần kiểm tra tiếp theo; file chưa đổi thì API trả `304` không có body. `fetched_at` là thời điểm lấy dữ liệu mới nhất trong provenance của scraper (nếu có), không phải thời điểm frontend gọi API.
- `GET /api/market-data/companies/{symbol}/news?limit=10` trả `symbol`, `source: fireant`, `articles`. Mỗi bài có tiêu đề, mô tả ngắn, ngày đăng, URL gốc, danh mục và `marker`. API chỉ đọc thư mục đúng mã, bỏ trùng ID và không gửi toàn bộ nội dung bài lên trang.
- Mã chưa có file trả mảng rỗng. Mã không hợp lệ trả 400; giới hạn `limit` ngoài phạm vi trả 422; JSON lỗi/không đọc được trả 503. Không có API ghi dữ liệu hoặc gọi crawler.

File FPT đang có nến với `status: pending_reconciliation` hoặc `open` và `price_basis: unknown`. Trang hiển thị rõ đây là snapshot chưa xác nhận cơ sở/đơn vị giá, không ghi là realtime. `marker: check` của tin chỉ có nghĩa tìm được bài **tương đồng về văn bản** ở nguồn đối chiếu, không xác nhận tin đúng. `uncheck` nghĩa chưa đạt ngưỡng đối chiếu; không kết luận tin sai.

Chạy test API từ thư mục gốc:

```powershell
.\venv\Scripts\python.exe -m unittest backend.tests.test_market_data_api -v
```

## Sau này đổi sang Supabase

Frontend chỉ biết hợp đồng JSON của hai URL trên. Thay `FileMarketDataRepository` trong `repository.py` bằng lớp đọc Supabase có cùng hai hàm `get_ohlcv(symbol, limit)` và `get_news(symbol, limit)`, rồi đổi hàm `get_market_data_repository()` trong `backend/src/api/routers/market_data.py` để trả lớp mới. Giữ nguyên cấu trúc JSON trả về thì `CompanyDetailPage.jsx`, `PriceHistory.jsx` và `marketDataApi.js` không phải sửa. Đặt URL/key Supabase trong **môi trường backend**; dùng service role key chỉ phía server. Nên lưu nến với khóa `(symbol, trade_date, source, revision)` và bài báo với khóa `id` hoặc URL chuẩn hóa để cập nhật mà không tạo bản trùng.

`FINMIND_DATA_ROOT` là tùy chọn cho cách đọc file: trỏ tới thư mục chứa `data_pipeline/` khi chạy trong Docker hoặc máy khác. Mặc định là thư mục gốc repo hiện tại.

Panel giá trên trang doanh nghiệp vẽ nến OHLC ngày: xanh khi giá đóng cửa bằng hoặc cao hơn giá mở cửa, đỏ khi thấp hơn. Bóng nến thể hiện giá cao/thấp; cột bên dưới thể hiện khối lượng. Di chuột hoặc bấm một nến để xem số liệu phiên đó. Frontend lấy tối đa 250 phiên đã lưu để hiển thị; đây là biểu đồ xem dữ liệu, chưa có bộ công cụ phân tích như TradingView.

Frontend dùng Lightweight Charts để chọn 30/90/tất cả phiên, cuộn chuột phóng to, kéo ngang xem lịch sử và mở rộng biểu đồ. Nút **Về mới nhất** đưa về phiên cuối. Nếu người xem đang xem quá khứ, dữ liệu mới không tự kéo biểu đồ về cuối; nút này báo có dữ liệu mới. Khi tab Tổng quan và tab trình duyệt đang hiển thị, frontend kiểm tra API giá sau mỗi khoảng 5 giây từ lúc phản hồi trước; lỗi thì giữ chart cũ và thử lại thưa dần, tối đa 30 giây. Ẩn tab hoặc rời trang thì dừng. Tin FireAnt không tự tải theo vòng 5 giây; dùng nút **Làm mới giá/tin** để tải lại cả hai panel.

Việc kiểm tra API **không tự chạy scraper**. Muốn snapshot thay đổi trong phiên, cần mở `data_pipeline/ScrapersOHLCV/Mo-bieu-do.cmd` và giữ chart scraper đang xem đúng mã. Scraper chỉ cập nhật mã đang xem, chịu giờ giao dịch và giới hạn nguồn; vì thế 5 giây là khoảng kiểm tra, không phải cam kết độ trễ giá hay feed từng giao dịch.
