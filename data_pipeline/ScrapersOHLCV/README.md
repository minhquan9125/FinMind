# ScrapersOHLCV

**Mở biểu đồ:** double-click [Mo-bieu-do.cmd](Mo-bieu-do.cmd), giữ terminal mở.
Trình duyệt dùng **http://127.0.0.1:18765/**. Nhập mã rồi Enter; tự cập nhật mã
đang xem trong phiên, ngoài phiên lấy thủ công. Không sử dụng cổng8765.

```text
ScrapersOHLCV/
├── Mo-bieu-do.cmd       Mở app
├── README.md           Hướng dẫn nhanh và bản đồ thư mục
├── ohlcv/
│   ├── app/            CLI, server biểu đồ và snapshot
│   ├── core/           Nến, trạng thái, lịch giao dịch và pipeline
│   ├── history/        Lấy lịch sử giá từ public/vnstock
│   ├── realtime/       Bảng điện, websocket, phiên và hạn mức
│   ├── sdk/            Client và tiến trình vnstock
│   ├── storage/        Đường dẫn an toàn và lưu dữ liệu
│   ├── providers/      Adapter nguồn dữ liệu (DNSE)
│   ├── __main__.py     Lệnh python -m ohlcv
│   └── chart_server.py Tương thích lệnh mở server cũ
├── web/                Giao diện biểu đồ (chart.html)
├── data/
│   ├── stocks/<MÃ>/     OHLCV, chỉ số và receipt theo mã
│   └── runtime/         SQLite, export và dữ liệu chạy CLI
├── config/             Lịch giao dịch, cấu hình và nguồn kiểm chứng
├── requirements/       Dependency Python: base, dev, vnstock
├── tests/              Kiểm thử Python và JavaScript
├── fixtures/           Dữ liệu giả lập cho replay/test
├── docs/               Hướng dẫn chi tiết
└── .agent-state/        Checkpoint, worker, môi trường SDK và bằng chứng QA
```

- [Hướng dẫn đầy đủ](docs/guide.md): cài đặt, CLI, nguồn dữ liệu và giới hạn.
- [Dữ liệu lưu ở đâu](data/README.md).
- [Giao diện và cách sửa polling](web/README.md).
- [Nguồn lịch giao dịch 2026](config/calendar.live.sources.md).

Mã mới có dữ liệu hợp lệ tự tạo `data/stocks/<MÃ>/data.json`. Bản lưu chứa
nến ngày, SMA20/SMA50/RSI14 và provenance. `live.json` lưu receipt bảng điện.
Mở riêng [web/chart.html](web/chart.html) chỉ xem snapshot offline.

Tất cả lệnh terminal chạy tại thư mục **ScrapersOHLCV**:

```powershell
python -m ohlcv --help
python -B -m pytest tests -q -p no:cacheprovider
node --test tests/test_chart.cjs tests/test_live.cjs tests/test_chart_script.cjs
```

Nếu cần cài lại môi trường SDK trên máy mới, xem [hướng dẫn](docs/guide.md).
Các mục **VNINDEX, VN30, HNX và UPCOM** trên web chỉ lấy dữ liệu khi bấm xem.
HNX/UPCOM dùng mã nguồn HNXINDEX/UPCOMINDEX; chỉ số tính theo điểm, được lưu riêng
trong `data/stocks/<MÃ>/` và tự cập nhật mục đang xem trong phiên. Ngoài phiên
dùng nút cập nhật thủ công. Chuyển mục sẽ dừng polling cũ; các ô chỉ số không được
tải nền đồng loạt. Nguồn hiện cập nhật chỉ số bằng nến 1D trong phiên, chưa đo độ trễ.
Giữ `.agent-state/vnstock-venv` và `.agent-state/vnstock-home` tại chỗ để tránh
phải cài lại môi trường hoặc làm mất trạng thái SDK. Toàn bộ dữ liệu đã có được
giữ khi sắp xếp thư mục; package vẫn chạy bằng `python -m ohlcv`.
