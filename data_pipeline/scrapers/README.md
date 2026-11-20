# Scrapers tin chứng khoán

Thu thập tin CafeF/FireAnt, đối chiếu nội dung và xuất báo cáo theo mã chứng khoán.

```text
scrapers/
├── run_news_pipeline.py   # Lệnh chạy toàn bộ luồng
├── requirements.txt      # Thư viện Python
├── news/                 # Mã nguồn tin tức
├── data/
│   ├── tin_tuc_chung/     # Theo nguồn và ngày
│   └── tin_tuc_theo_ma/   # Theo mã, nguồn và ngày
├── reports/
│   ├── pipeline/         # latest.md/json và events.md/json
│   └── uncheck/          # Báo cáo phân tích uncheck
├── tests/                # Test offline
├── docs/guide.md         # Hướng dẫn chi tiết
├── legacy/               # Collector giá/tài chính cũ, chạy riêng
└── .agent-state/         # Checkpoint, review và bằng chứng kiểm tra
```

Chạy trong thư mục `data_pipeline/scrapers`:

```powershell
python -B -X utf8 run_news_pipeline.py
python -B -X utf8 run_news_pipeline.py --symbols FPT HPG
python -B -X utf8 run_news_pipeline.py --symbols VCB --only-symbols --new-only
```

Từ thư mục gốc FinMind, chỉ cào FireAnt cho 10 mã và lưu vào thư mục riêng (đổi ngày trong tên thư mục cho lượt làm lại mới):

```powershell
python -B -X utf8 data_pipeline/scrapers/run_news_pipeline.py --source fireant --symbols VCB BID CTG MBB TCB FPT CMG ELC ITD ICT --only-symbols --limit 10 --output data_pipeline/scrapers/data_fireant_10_20261027
```

`--source fireant` không cào CafeF; `--only-symbols` bỏ tin thị trường chung. Thư mục riêng tránh trộn JSON cũ. Khi thay toàn bộ `news_articles`, chạy script nạp từ gốc repo với cùng thư mục:

Crawler lấy URL tệp đính kèm từ trường `files[].fileContentUrl` của API chi tiết FireAnt và lưu vào `attachments`; bài không có tệp nhận `[]`. Nếu chỉ cập nhật attachment cho tập JSON đã có, dùng lệnh nạp bên dưới nhưng **bỏ `--replace-news`** để upsert bài hiện có mà không xóa bảng.

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\ingest_market_news_to_supabase.py --only news --news-source fireant --news-dir data_pipeline/scrapers/data_fireant_10_20261027 --symbol VCB BID CTG MBB TCB FPT CMG ELC ITD ICT --replace-news
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\ingest_market_news_to_supabase.py --only news --news-source fireant --news-dir data_pipeline/scrapers/data_fireant_10_20261027 --symbol VCB BID CTG MBB TCB FPT CMG ELC ITD ICT --replace-news --apply
```

Lệnh đầu chỉ đếm dữ liệu, không kết nối DB. Lệnh `--apply` xóa và nạp lại riêng bảng `news_articles` trong một transaction; chỉ chạy sau khi đã kiểm tra JSON mới. Chunk và corpus cũ không được xóa bởi script này, nhóm phụ trách lập chỉ mục sẽ xử lý sau.

Lệnh cũ từ thư mục gốc FinMind vẫn hoạt động:

```powershell
python -B -X utf8 data_pipeline/scrapers/run_news_pipeline.py --symbols FPT
```

Các công cụ riêng chạy bằng module, từ thư mục scrapers:

```powershell
python -B -X utf8 -m news.stock_news_collector --help
python -B -X utf8 -m news.news_crosscheck --help
python -B -X utf8 -m news.analyze_uncheck_events --help
```

Kiểm tra offline từ thư mục scrapers:

```powershell
python -B -X utf8 -m unittest discover -s tests -t . -p 'test_*.py'
```

Cài thư viện khi thiết lập môi trường mới: `python -m pip install -r requirements.txt`.

Đường dẫn mặc định đã trỏ vào `data/` và `reports/`. Đường dẫn tùy chọn vẫn phải nằm trong scrapers. Báo cáo cũ giữ nguyên nội dung, nên có thể còn ghi đường dẫn trước khi sắp xếp. `legacy/direct_vn_collector.py` giữ cách tính đường dẫn cũ và không được luồng tin tức gọi.

Xem [hướng dẫn chi tiết](docs/guide.md).
