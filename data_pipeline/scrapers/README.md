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
