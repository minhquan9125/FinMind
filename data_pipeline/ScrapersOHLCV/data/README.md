# Dữ liệu sinh ra khi chạy

```text
data/
├── stocks/
│   └── FPT/
│       ├── data.json    Nến 1D + SMA20/SMA50/RSI14 + provenance/revision
│       └── live.json    Receipt bảng điện gần nhất, nếu đã lấy trong phiên
└── runtime/             Database SQLite, export JSON, kết quả replay/collector
```

Mỗi mã có folder riêng. Không phải mã nào cũng đã có `live.json`; nó chỉ được
tạo khi nhận quote hợp lệ trong phiên. Dữ liệu giả lập nằm ở `fixtures/`, không
trộn vào các folder mã thật. Các folder dữ liệu được ignore trong Git.

Các file đã di chuyển được kiểm tra SHA256 trước/sau; OHLCV và chỉ số giữ nguyên.
Chỉ metadata `provenance.storage` đổi sang đường dẫn `data/stocks/...`.
Database được chuyển cùng thư mục runtime; không xóa/rebuild dữ liệu.

`recovered/` giữ snapshot và dữ liệu FPT mà server cũ ghi thêm trong lúc di chuyển.
Đã đưa bản mới hợp lệ vào `stocks/FPT/data.json`, giữ nguyên bản trước và receipt
để đối chiếu. Đây là backup của lần chuyển folder, không được dùng làm nguồn live.
