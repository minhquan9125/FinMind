Đường dẫn mặc định mới: dữ liệu ở `data/`, báo cáo ở `reports/`. Các lệnh bên dưới chạy từ thư mục gốc FinMind. Xem [README](../README.md) để chạy trực tiếp từ scrapers. Báo cáo đã lưu được giữ nguyên nội dung, nên có thể còn ghi đường dẫn trước khi sắp xếp.

# Tin chứng khoán CafeF và FireAnt

## Chạy toàn bộ luồng bằng một file

```powershell
python -B -X utf8 data_pipeline/scrapers/run_news_pipeline.py
```

Nhập mã khi được hỏi, ví dụ `FPT` hoặc `FPT HPG VCB`. Mặc định cào tin chung và tab tin của từng mã trên CafeF/FireAnt, hạn mức **10 bài hợp lệ mỗi nguồn/phạm vi**. Ví dụ nhập FPT có 4 nhóm, tối đa 40 lượt bài hợp lệ. Hạn mức mặc định bao gồm bài đã lưu; số bài thêm mới được báo riêng.

Luồng tự động: collector chuyển dữ liệu legacy nếu còn → khám phá/tải bài → gộp và lưu JSON theo ngày → cross-check và cập nhật marker → phân tích uncheck theo sự kiện → in báo cáo từng nhóm/thư mục. Không chạy test unittest hay collector giá/tài chính `legacy/direct_vn_collector.py` trong luồng này.

```powershell
# Bỏ bước nhập tương tác
python -B -X utf8 data_pipeline/scrapers/run_news_pipeline.py --symbols FPT HPG

# Chỉ theo mã; lấy thêm 10 URL chưa có trong file hôm nay
python -B -X utf8 data_pipeline/scrapers/run_news_pipeline.py --symbols VCB TPB --only-symbols --new-only

# Tùy chỉnh hạn mức
python -B -X utf8 data_pipeline/scrapers/run_news_pipeline.py --symbols FPT --limit 20
```

Báo cáo được thay thế mỗi lượt ở `scrapers/reports/pipeline/latest.md` và `latest.json`. Bằng chứng ứng viên sự kiện ở `events.md` và `events.json` cùng thư mục. Báo cáo gồm nhóm đủ hạn mức/không lỗi, lượt bài hợp lệ, lượt bài thêm mới, file được ghi/file mới tạo, tổng JSON và record theo mỗi thư mục, record cross-check thành công/check/uncheck, số URL uncheck đã phân tích, số cặp/bài ứng viên khác cách viết và số cặp cùng tiêu đề. File JSON ở đây là file lưu theo ngày, không phải một file cho mỗi bài.

Cross-check và phân tích sự kiện chỉ chạy trên phạm vi vừa yêu cầu; bảng thư mục thống kê cả dữ liệu cũ ở các mã khác. Một bài lưu ở nhiều ngày/mã có thể tính nhiều record. Phân tích sự kiện bỏ trùng URL và không tự biến ứng viên thành marker check. Marker check vẫn chỉ áp dụng khi giống văn bản >80%, không xác minh sự thật.

Hai bảng thu thập và thống kê thư mục tự căn độ rộng theo nội dung/Unicode: cột chữ căn trái, cột số căn phải. Dấu phân cột thẳng hàng trong terminal và khi đọc Markdown bằng font monospace.

## Vai trò các file

| File | Vai trò |
|---|---|
| `run_news_pipeline.py` | Nhập mã, chạy toàn bộ luồng tin tức và xuất báo cáo |
| `stock_news_collector.py` | Điều phối cào, trích nội dung, gộp URL, ghi JSON, tự cross-check |
| `news_sources.py` | RSS/API/tab tin theo mã, phân trang và lọc chủ đề |
| `news_storage.py` | Ngày UTC+7, đường dẫn lưu theo nguồn/phạm vi, hỗ trợ migration |
| `news_crosscheck.py` | Độ giống văn bản bằng Dice cụm ba từ, cập nhật marker/bằng chứng |
| `analyze_uncheck_events.py` | Ứng viên cùng sự kiện bằng TF-IDF/cosine và quy tắc, không đổi marker |
| `migrate_news_daily.py` | Lệnh chuyển riêng dữ liệu legacy và kiểm tra kết quả, không cào mạng |
| `legacy/direct_vn_collector.py` | Luồng giá OHLCV và tài chính riêng, không được wrapper tin tức gọi |
| `test_stock_news_collector.py` | 11 test collector, lưu theo ngày và migration |
| `test_news_crosscheck.py` | 4 test độ giống văn bản, phạm vi, ngưỡng và new-only |
| `test_uncheck_events.py` | 6 test ứng viên sự kiện, thời gian và loại trùng |
| `test_run_news_pipeline.py` | 5 test luồng tổng và báo cáo khi có lỗi |

## Các file Markdown được cập nhật khi nào?

| File | Cơ chế cập nhật |
|---|---|
| `reports/pipeline/latest.md` | Tự tạo lại khi chạy wrapper: báo cáo lượt chạy mới nhất |
| `reports/pipeline/events.md` | Tự tạo lại khi chạy wrapper: bằng chứng ứng viên trong phạm vi vừa chạy |
| `reports/uncheck/report.md` | Tự tạo lại khi chạy analyzer riêng: mặc định toàn bộ dữ liệu |
| `README.md` | Sửa thủ công khi cách sử dụng/chức năng thay đổi |
| `AGENTS.md` | Sửa thủ công khi hướng dẫn làm việc cho Codex thay đổi |
| `CODEX_CONTEXT.md` | Sửa thủ công để ghi yêu cầu, quyết định và trạng thái công việc |

Báo cáo đi kèm bản JSON và ghi đè mỗi lượt, chưa lưu lịch sử từng lượt. Chạy wrapper không cập nhật `reports/uncheck/report.md`. Script không tự git add/commit/push; file đã được Git theo dõi cần add/commit khi muốn lưu phiên bản mới. Giữ cả bốn file test trong repository để kiểm tra thay đổi. Các thư mục báo cáo có thể tạo lại nên việc commit báo cáo là tùy chọn.

## Trạng thái khi có lỗi

Thiếu bài hoặc lỗi vẫn lưu dữ liệu lấy thành công, tiếp tục phân tích dữ liệu hiện có và xuất báo cáo với mã thoát 1. Không lấy thống kê `last_run` cũ để báo thành công cho lượt mới. Phân tích lỗi sẽ thay báo cáo sự kiện cũ bằng thông báo lỗi, tránh hiển thị kết quả cũ như mới. Tổng bộ test offline hiện có 26 test, gồm 5 test tích hợp cho luồng này.

## Sử dụng collector riêng

Chạy từ thư mục gốc dự án, Python 3.10+, `requests` và `scrapling`. Collector tin tức dùng HTTP và Scrapling Selector, không cần Chromium.

```powershell
python -m pip install "requests>=2.32,<3" "scrapling>=0.4,<1"

# Tin chung: 10 bài hợp lệ mỗi nguồn
python -m data_pipeline.scrapers.news.stock_news_collector --source all --limit 10

# Tin chung + tab tin của từng mã
python -m data_pipeline.scrapers.news.stock_news_collector --source all --symbols FPT HPG VCB --limit 10

# Thêm 10 bài chưa có trong file hôm nay, mỗi nguồn/phạm vi
python -B -m data_pipeline.scrapers.news.stock_news_collector --source all --symbols VCB TPB --limit 10 --new-only

# Chỉ tin theo mã (cũng nhận --symbols FPT,HPG hoặc --symbol FPT --symbol HPG)
python -m data_pipeline.scrapers.news.stock_news_collector --source all --symbols FPT HPG --only-symbols --limit 10

# Lọc lại tin ngoài chủ đề đã có trong file cũ
python -m data_pipeline.scrapers.news.stock_news_collector --source all --limit 10 --prune-irrelevant

# Tìm sâu hơn nếu thiếu tin
python -m data_pipeline.scrapers.news.stock_news_collector --source all --symbols FPT --limit 50 --max-pages 10
```

`--limit` tính bài hợp lệ mỗi **nguồn/phạm vi**, bao gồm bài đã lưu. `all --symbols FPT HPG --limit 10` có sáu nhóm, tối đa 60 lượt bài; số bài duy nhất có thể thấp hơn vì bài thuộc nhiều nhóm. Chạy lại lấy cùng các bài mới nhất, không chuyển sang bài cũ chỉ để thêm đủ số bài mới. Bài lỗi không chiếm hạn mức.

`--new-only` bỏ URL đã có trong file của ngày hiện tại; `--limit` lúc này đếm bài thêm mới. Bài chưa có trong file hôm nay có thể đã xuất hiện trong ngày cũ. Nếu nguồn không có đủ bài trong giới hạn khám phá, giữ các bài đã lấy được và trả mã lỗi 1.

## Kiểm tra chéo CafeF và FireAnt

Sau mỗi lượt cào, `crosscheck_news()` trong `news_crosscheck.py` tự đối chiếu hai nguồn của các phạm vi vừa chạy, bao gồm dữ liệu đã lưu ở các ngày khác nhau. Tin chung chỉ so với tin chung; VCB chỉ so với VCB, không so với TPB hay mã khác. Có thể chạy lại toàn bộ dữ liệu mà không cào mạng:

```powershell
python -B -m data_pipeline.scrapers.news.news_crosscheck
```

Điểm từ 0 đến 1 dùng Dice trên cụm ba từ liên tiếp, có tính số lần xuất hiện: **85% nội dung + 15% tiêu đề**. Chuẩn hóa Unicode, chữ hoa/thường và dấu câu; giữ dấu tiếng Việt và các giá trị số. Bài thiếu nội dung hoặc dưới 5 từ nhận điểm 0. So sánh với mọi bài của nguồn còn lại trong cùng phạm vi và chọn bài có điểm cao nhất.

- `marker: "check"` khi điểm **lớn hơn 0.8**; đúng 0.8 vẫn là `"uncheck"`.
- `marker: "uncheck"` nếu chưa có bài tương đồng trên ngưỡng, kể cả khi thiếu nguồn đối chiếu.
- `cross_check` lưu `method`, `threshold`, `score`, `matched_source`, `matched_url`, `matched_file`, `checked_at`. Điểm lưu đầy đủ, không làm tròn trước khi xét ngưỡng.

Marker phản ánh mức giống nội dung, không xác nhận sự thật. Hai website có thể đăng lại cùng một nguồn; thay đổi một con số trong bài dài vẫn có thể có điểm cao. Cách này cũng có thể bỏ sót bài diễn đạt khác nhưng cùng sự kiện. Việc đối chiếu không xóa/gộp các bài giữa hai nguồn.

`--url <URL>` (lặp nhiều lần) lấy bài cụ thể, ưu tiên hơn `--source`/`--symbols` và bỏ qua lọc chủ đề. Chỉ nhận URL bài CafeF/FireAnt.

## Phân tích uncheck theo sự kiện

`analyze_uncheck_events.py` đọc dữ liệu đã lưu, không gọi mạng và không sửa JSON nguồn/marker. Chạy từ gốc dự án:

```powershell
python -B -X utf8 -m data_pipeline.scrapers.news.analyze_uncheck_events

# Chỉ phân tích một số phạm vi; cửa sổ ngày xuất bản mặc định là 3 ngày
python -B -X utf8 -m data_pipeline.scrapers.news.analyze_uncheck_events --scopes market FPT TPB --window-days 3
```

Kết quả ở `scrapers/reports/uncheck/report.md` (đọc từng cặp) và `report.json` (xử lý bằng code). Chạy lại thay thế báo cáo. `--root` và `--output` chỉ nhận đường dẫn trong scrapers; root là thư mục chứa hai cây dữ liệu. `--threshold` mặc định 0.52 là điểm quy tắc, không phải xác suất hay ngưỡng marker 0.8.

So CafeF với FireAnt trong cùng phạm vi qua các ngày; mỗi cặp phải có ít nhất một bản lưu `uncheck`. Cùng URL qua nhiều ngày chỉ đếm là một bài trong phạm vi, dùng nội dung của ngày cào mới nhất. Tổng toàn cục bỏ trùng URL/cặp giữa các mã; số record tính tất cả bản lưu uncheck.

- `possible_rewritten_event`: tiêu đề khác nhưng có thực thể chung, loại sự kiện chung, ngày xuất bản gần nhau và độ giống TF-IDF đủ cao. Nếu tiêu đề rất khác, cần nội dung cosine >=0.4 và ít nhất hai số liệu chung. Điểm dùng 55% tiêu đề + 35% nội dung + 10% loại sự kiện; nhánh nội dung có số liệu dùng 75% nội dung + 25% thực thể/sự kiện. Số liệu chung chỉ là manh mối, chưa xác nhận chúng nói về cùng đại lượng.
- `same_title_low_body_overlap`: tiêu đề giống nhưng độ giống văn bản không vượt 0.8; thường gặp ở công bố có tên PDF/phụ lục khác nhau. Không tính nhóm này vào số bài khác cách viết.

Báo cáo lưu URL, file gốc, đoạn trích, thực thể/loại sự kiện, từ khóa, số liệu chung, khoảng cách ngày xuất bản và điểm giống văn bản hiện tại. Ngày CafeF thiếu offset được hiểu theo UTC+7. Cặp tiêu đề khác thiếu ngày không được chọn; cặp cùng tiêu đề thiếu ngày được gắn cờ. Nghị quyết có số văn bản khác nhau bị loại.

TF-IDF tạo vector trọng số từ vựng; cosine đo độ giống giữa hai vector. Đây là hai bước bổ sung nhau, không phải hai lượt xác minh độc lập. Nhánh tiêu đề/nội dung cần cosine tiêu đề >=0.25, nội dung >=0.20 và điểm tổng >=0.52. Nhánh số liệu cần nội dung >=0.40, ít nhất hai số liệu chung, cùng thực thể/loại sự kiện và điểm tổng >=0.52; nếu áp dụng, chọn điểm cao hơn giữa hai công thức. Cặp có độ giống văn bản >0.8 được loại khỏi báo cáo ứng viên này.

Đây là **ứng viên cần đọc lại**, không phải số sự kiện đã xác nhận hay xác minh tin đúng/sai. Quy tắc thực thể/loại sự kiện còn hữu hạn, không dùng mô hình semantic/LLM, nên có thể bỏ sót hoặc ghép nhầm bài cùng chủ đề. Không có ứng viên không đồng nghĩa với tin độc quyền/sai. Không tải hay đọc PDF. `test_uncheck_events.py` có 6 test offline cho phân tích; tổng bộ test hiện có 26 test.

## Nguồn và nội dung

- CafeF tin chung: RSS chứng khoán và fallback trang chuyên mục. Theo mã: `/du-lieu/Ajax/PageNew/News.ashx`, tham số `Symbol`, `NewsType=0`, `PageIndex`, `PageSize`. Nhận cả bài báo và công bố doanh nghiệp.
- FireAnt: API website dùng, `/posts?type=1&offset=...&limit=...`, thêm `symbol=FPT` cho tab mã. Không lấy bài cộng đồng `type=0`. Nội dung từ `/posts/<id>`. Credential anonymous công khai đọc từ bundle website hiện hành, chỉ giữ trong RAM; không dùng tài khoản người dùng hoặc lưu token.
- Tin chung lọc bằng tag nguồn hoặc tín hiệu chứng khoán/vĩ mô trong tiêu đề/mô tả. Tin theo mã giữ liên kết của tab mã, kể cả ticker không có trong tiêu đề. Bộ lọc quy tắc có thể bỏ sót tin liên quan gián tiếp.
- Mỗi bài phải có nội dung thực. Công bố CafeF lấy `og:title`, `#newscontent` để tránh nhầm tên công ty ở `h1`. Lưu link PDF ở `attachments`, không tải/trích toàn bộ PDF.
- HTTP retry cho lỗi tạm thời; phân trang tối đa `--max-pages` (mặc định 5, mỗi trang API 50 ứng viên). Website/API thay đổi có thể cần cập nhật parser.

## JSON theo ngày, tách phạm vi và nguồn

Mọi dữ liệu nằm trong `scrapers`, không phụ thuộc thư mục chạy:

```text
scrapers/data/
├── tin_tuc_chung/
│   ├── cafef/01-10-2026.json
│   └── fireant/01-10-2026.json
└── tin_tuc_theo_ma/
    ├── FPT/
    │   ├── cafef/01-10-2026.json
    │   └── fireant/01-10-2026.json
    └── HPG/
        ├── cafef/01-10-2026.json
        └── fireant/01-10-2026.json
```

Ngày là **ngày chạy lượt cào theo giờ Việt Nam (UTC+7)**, chốt khi bắt đầu chạy, không phải ngày xuất bản bài. Tên file dùng `DD-MM-YYYY.json` vì Windows không cho dấu `/` trong tên file. Các lượt chạy cùng ngày gộp vào cùng file, không trùng URL. Sang ngày mới tạo file mới, giữ file ngày cũ; cùng bài có thể xuất hiện ở nhiều ngày. Mã mới tự tạo thư mục khi chạy `--symbols` với mã đó. Bài được tab của nhiều mã trả về được lưu vào từng thư mục mã tương ứng; không suy ra thư mục mã từ tag hoặc tiêu đề của tin chung.

`--source all` cào cả hai nguồn; chọn một nguồn chỉ cào/gộp bài của nguồn đó. Bước cross-check sau cào vẫn có thể ghi lại marker/bằng chứng trong JSON của cả hai nguồn thuộc phạm vi vừa chạy. `--only-symbols` chỉ cập nhật tin theo mã. `--url` lưu vào tin chung của nguồn tương ứng với phạm vi `direct`.

Lần chạy mặc định tự chuyển `stock_news.json`, `cafef_news.json`, `fireant_news.json` và `news_trial.json` cũ sang cấu trúc mới. Ngày lấy từ `crawled_at`, đổi sang UTC+7. Phân thư mục theo `scopes` và `matched_symbols`; bài không có phạm vi được giữ trong tin chung. Kiểm tra lại toàn bộ dữ liệu đã ghi trước khi xóa các file cũ. File sai định dạng, thiếu thời gian cào hoặc bị khóa thì dừng, giữ file cũ. Migration bị gián đoạn có thể chạy lại và gộp theo URL.

Chỉ chuyển dữ liệu, không cào mạng:

```powershell
python -B -m data_pipeline.scrapers.news.migrate_news_daily
```

`--output` hiện nhận **thư mục** bên trong `scrapers`, không nhận tên JSON. Ví dụ `--output data_pipeline/scrapers/demo` tạo cùng cấu trúc trên trong `demo`. Dùng output tùy chỉnh không tự chuyển dữ liệu cũ.

Gộp theo URL chuẩn hóa, bỏ tracking; giữ bài cũ và hợp nhất `symbols`, `matched_symbols`, `scopes`. Không xóa bài cũ khi nguồn lỗi. `--prune-irrelevant` chủ động lọc bài cũ bằng cùng quy tắc, giữ bài theo mã và phạm vi `direct`. File sai định dạng được giữ nguyên và báo lỗi.

Ghi qua `.json.tmp` rồi thay thế nguyên tử; `.json.lock` chặn hai tiến trình ghi cùng lúc. Hai file phụ được dọn khi chạy bình thường. Nếu tiến trình bị kill, chỉ xóa khóa sau khi xác nhận nó đã dừng.

Schema `1.2` giữ các trường bài cũ: `id`, `source`, `url`, `title`, `description`, `content`, `published_at`, `crawled_at`. Bổ sung:

- `symbols`: tag mã từ nguồn và mã của tab truy vấn.
- `matched_symbols`: các mã đã lấy từ tab theo mã.
- `scopes`: `market`, mã cổ phiếu hoặc `direct`.
- FireAnt: `provider_id`, `category`. CafeF: `attachments` (URL PDF).
- `source` ở cấp file: `cafef` hoặc `fireant`; mỗi file chỉ chứa bài của nguồn đó.
- `crawl_date`: ngày của file dạng `DD-MM-YYYY`; `timezone`: `Asia/Ho_Chi_Minh`.
- `last_run`: thời gian UTC và `results` theo nhóm của riêng nguồn đó với `source`, `scope`, `accepted`, `limit`, `errors`.

`published_at` có thể null nếu nguồn không cung cấp; ngày tab CafeF đổi milliseconds sang UTC. Mã thoát 0 khi mọi nhóm đủ hạn mức và không lỗi; mã 1 khi có lỗi/thiếu hạn mức. Bài thành công vẫn được lưu trong lượt thất bại một phần. Không có bài dùng được thì file cũ và `last_run` giữ nguyên.

## Kiểm thử và ngữ cảnh

### Đánh giá trên bài báo thật (khác với unittest)

Đọc `accuracy_benchmark/results.md` và `results.json` để xem kết quả đã lưu, gồm nhãn, lý do và số đếm đúng/sai/bỏ sót từng cặp. Theo yêu cầu người dùng, đã xóa hai script đánh giá, fixture, file SHA256 và bản sao corpus; chỉ giữ hai file kết quả nguyên vẹn. Đây là báo cáo lưu trữ, không tự cập nhật và không còn lệnh chạy lại benchmark. Các tham chiếu fixture/corpus trong báo cáo mô tả đầu vào của lần đánh giá trước khi dọn.

Đây là **đánh giá chẩn đoán có chủ đích**, chưa phải benchmark độc lập: nhãn do một trợ lý đọc bài gán, một số cặp đã được thấy khi phát triển, mẫu không ngẫu nhiên/held-out. Không dùng marker hiện tại làm nhãn đúng/sai. Nhãn tái sử dụng câu chữ bỏ qua phần giao diện/tên tập tin PDF; nhãn cùng sự kiện xét sự kiện chính, hai công bố khác nhau vẫn là hai sự kiện. Cross-check chấm với nhãn câu chữ; analyzer chấm nhãn sự kiện trên các cặp đủ điều kiện uncheck; luồng OR kết hợp chỉ là đánh giá nghiên cứu, không đổi marker production. Các tỷ lệ chỉ áp dụng cho các cặp này, không xác minh sự thật trong bài báo.

Kết quả bộ v1: cross-check đúng 18/26 (3 ghép đúng, 15 loại đúng, 0 ghép nhầm, 8 bỏ sót theo nhãn câu chữ); analyzer đúng 22/23 (9 ghép đúng, 13 loại đúng, 0 ghép nhầm, 1 bỏ sót theo nhãn sự kiện); kết hợp đúng 25/26. Analyzer bỏ sót cặp CTR nghị quyết tín dụng BIDV/nghị quyết 84 ngày 17/09/2026. Đã chạy hai lần với dự đoán giống nhau và đối chiếu số đếm/mẫu số. Không thay đổi thuật toán sau khi thấy kết quả. 26 cặp benchmark không phải 26 test unittest bên dưới.

```powershell
python -B -m unittest discover -s data_pipeline/scrapers/tests -t data_pipeline/scrapers -p "test_*.py"
```

26 test offline trong bốn module kiểm tra phân trang, lọc, RSS hỏng, nội dung công bố, chạy lặp cùng ngày, sang ngày mới, mã mới, file hỏng, khóa ghi, UTC+7, migration nhiều phạm vi, đối chiếu hai nguồn, cách ly mã, ngưỡng đúng 80%, đặt lại marker, lấy bài mới, phân tích sự kiện và báo cáo luồng tổng khi thành công/lỗi. Lượt xác nhận gần nhất: 26 test pass; sau chỉnh thống kê thư mục, 5 test tích hợp pass; căn bảng đã kiểm tra vị trí dấu phân cột trên báo cáo sẵn có. Test offline không xác nhận website/API đang hoạt động. `news_trial.json` cũ đã chuyển sang thư mục tin chung theo nguồn/ngày.

`AGENTS.md` và `CODEX_CONTEXT.md` trong thư mục này là ghi chú Codex dùng cục bộ, đã được `.gitignore` loại khỏi Git. Chúng không được đưa lên repository và không phải lịch sử chat nhập vào Codex app. Archify dùng để tạo sơ đồ, không có chức năng lưu cuộc chat vào app.
