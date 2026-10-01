# Tin chứng khoán CafeF và FireAnt

Chạy từ thư mục gốc dự án, Python 3.10+, `requests` và `scrapling`. Collector tin tức dùng HTTP và Scrapling Selector, không cần Chromium.

```powershell
python -m pip install "requests>=2.32,<3" "scrapling>=0.4,<1"

# Tin chung: 10 bài hợp lệ mỗi nguồn
python data_pipeline/src/scrapers/stock_news_collector.py --source all --limit 10

# Tin chung + tab tin của từng mã
python data_pipeline/src/scrapers/stock_news_collector.py --source all --symbols FPT HPG VCB --limit 10

# Chỉ tin theo mã (cũng nhận --symbols FPT,HPG hoặc --symbol FPT --symbol HPG)
python data_pipeline/src/scrapers/stock_news_collector.py --source all --symbols FPT HPG --only-symbols --limit 10

# Lọc lại tin ngoài chủ đề đã có trong file cũ
python data_pipeline/src/scrapers/stock_news_collector.py --source all --limit 10 --prune-irrelevant

# Tìm sâu hơn nếu thiếu tin
python data_pipeline/src/scrapers/stock_news_collector.py --source all --symbols FPT --limit 50 --max-pages 10
```

`--limit` tính bài hợp lệ mỗi **nguồn/phạm vi**, bao gồm bài đã lưu. `all --symbols FPT HPG --limit 10` có sáu nhóm, tối đa 60 lượt bài; số bài duy nhất có thể thấp hơn vì bài thuộc nhiều nhóm. Chạy lại lấy cùng các bài mới nhất, không chuyển sang bài cũ chỉ để thêm đủ số bài mới. Bài lỗi không chiếm hạn mức.

`--url <URL>` (lặp nhiều lần) lấy bài cụ thể, ưu tiên hơn `--source`/`--symbols` và bỏ qua lọc chủ đề. Chỉ nhận URL bài CafeF/FireAnt.

## Nguồn và nội dung

- CafeF tin chung: RSS chứng khoán và fallback trang chuyên mục. Theo mã: `/du-lieu/Ajax/PageNew/News.ashx`, tham số `Symbol`, `NewsType=0`, `PageIndex`, `PageSize`. Nhận cả bài báo và công bố doanh nghiệp.
- FireAnt: API website dùng, `/posts?type=1&offset=...&limit=...`, thêm `symbol=FPT` cho tab mã. Không lấy bài cộng đồng `type=0`. Nội dung từ `/posts/<id>`. Credential anonymous công khai đọc từ bundle website hiện hành, chỉ giữ trong RAM; không dùng tài khoản người dùng hoặc lưu token.
- Tin chung lọc bằng tag nguồn hoặc tín hiệu chứng khoán/vĩ mô trong tiêu đề/mô tả. Tin theo mã giữ liên kết của tab mã, kể cả ticker không có trong tiêu đề. Bộ lọc quy tắc có thể bỏ sót tin liên quan gián tiếp.
- Mỗi bài phải có nội dung thực. Công bố CafeF lấy `og:title`, `#newscontent` để tránh nhầm tên công ty ở `h1`. Lưu link PDF ở `attachments`, không tải/trích toàn bộ PDF.
- HTTP retry cho lỗi tạm thời; phân trang tối đa `--max-pages` (mặc định 5, mỗi trang API 50 ứng viên). Website/API thay đổi có thể cần cập nhật parser.

## Hai JSON cố định, tách theo nguồn

CafeF lưu vào `cafef_news.json`, FireAnt lưu vào `fireant_news.json`, cạnh script và không phụ thuộc thư mục chạy. Tin chung và tin theo mã của cùng một nguồn gộp vào file của nguồn đó. Không tạo JSON theo ngày/giờ. `--source all` cập nhật cả hai file; chạy một nguồn giữ nguyên file nguồn còn lại.

Nếu có `stock_news.json` cũ, lần chạy mặc định sẽ tự chuyển bài sang hai file mới, gộp với dữ liệu đã có và kiểm tra đủ URL trước khi xóa file chung. File sai định dạng hoặc bị khóa thì dừng migration và giữ file chung. Không chuyển `news_trial.json` vì đó là dữ liệu thử lịch sử.

`--output` chỉ nhận đường dẫn `.json` trong `scrapers`: khi chạy một nguồn, dùng chính tên đó; khi chạy cả hai, thêm hậu tố nguồn. Ví dụ `--source all --output data_pipeline/src/scrapers/my_news.json` ghi `my_news_cafef.json` và `my_news_fireant.json`. Không được dùng tên file mặc định của nguồn khác hoặc tên cũ `stock_news.json`. Dùng output tùy chỉnh thì không tự chuyển dữ liệu legacy.

Gộp theo URL chuẩn hóa, bỏ tracking; giữ bài cũ và hợp nhất `symbols`, `matched_symbols`, `scopes`. Không xóa bài cũ khi nguồn lỗi. `--prune-irrelevant` chủ động lọc bài cũ bằng cùng quy tắc, giữ bài theo mã và phạm vi `direct`. File sai định dạng được giữ nguyên và báo lỗi.

Ghi qua `.json.tmp` rồi thay thế nguyên tử; `.json.lock` chặn hai tiến trình ghi cùng lúc. Hai file phụ được dọn khi chạy bình thường. Nếu tiến trình bị kill, chỉ xóa khóa sau khi xác nhận nó đã dừng.

Schema `1.1` giữ các trường cũ: `id`, `source`, `url`, `title`, `description`, `content`, `published_at`, `crawled_at`. Bổ sung:

- `symbols`: tag mã từ nguồn và mã của tab truy vấn.
- `matched_symbols`: các mã đã lấy từ tab theo mã.
- `scopes`: `market`, mã cổ phiếu hoặc `direct`.
- FireAnt: `provider_id`, `category`. CafeF: `attachments` (URL PDF).
- `source` ở cấp file: `cafef` hoặc `fireant`; mỗi file chỉ chứa bài của nguồn đó.
- `last_run`: thời gian UTC và `results` theo nhóm của riêng nguồn đó với `source`, `scope`, `accepted`, `limit`, `errors`.

`published_at` có thể null nếu nguồn không cung cấp; ngày tab CafeF đổi milliseconds sang UTC. Mã thoát 0 khi mọi nhóm đủ hạn mức và không lỗi; mã 1 khi có lỗi/thiếu hạn mức. Bài thành công vẫn được lưu trong lượt thất bại một phần. Không có bài dùng được thì file cũ và `last_run` giữ nguyên.

## Kiểm thử và ngữ cảnh

```powershell
python -B -m unittest discover -s data_pipeline/src/scrapers -p test_stock_news_collector.py
```

Test offline kiểm tra phân trang, lọc, RSS hỏng, nội dung công bố, merge, chạy lặp, file hỏng, khóa ghi và chuyển dữ liệu/tách nguồn. `news_trial.json` là dữ liệu thử cũ, không phải file được tạo mỗi lượt.

`AGENTS.md` và `CODEX_CONTEXT.md` trong thư mục này là ghi chú Codex dùng cục bộ, đã được `.gitignore` loại khỏi Git. Chúng không được đưa lên repository và không phải lịch sử chat nhập vào Codex app. Archify dùng để tạo sơ đồ, không có chức năng lưu cuộc chat vào app.
