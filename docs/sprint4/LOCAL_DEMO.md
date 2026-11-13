# Demo dữ liệu News OCR trong tập dữ liệu chung

## Khởi động

### Máy mới sau khi merge

Từ thư mục gốc repository:

```powershell
git switch backup-demo
git pull --ff-only origin backup-demo
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

Chuẩn bị Python 3.12, Node.js LTS >=20, npm và Git. Nếu không có `py`, dùng
`python -m venv .venv` sau khi kiểm tra `python --version` đúng phiên bản.
Không sao chép `.venv` từ máy khác; môi trường này chứa đường dẫn Python của máy tạo.

Nhận cấu hình thật qua kênh riêng của nhóm, rồi sửa `backend/.env`:

| Mục | Thành viên cần có |
| --- | --- |
| `DATABASE_URL` | PostgreSQL của nhóm có schema, corpus/chunk/vector và quyền runtime/auth/chat |
| `ADMIN_INGEST_DATABASE_URL` | Kết nối writer cho chức năng tạo chunk, vector và nạp DB của admin |
| `JWT_SECRET_KEY` | Secret theo môi trường backend; thay placeholder, không đưa lên Git |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Neo4j của nhóm có phiên graph READY; PostgreSQL không thay thế Neo4j |
| `RESEARCH_CORPUS_VERSION_ID` | ID corpus thực sự tồn tại trong đúng DB đang kết nối |
| `GEMINI_API_KEY` | Key hợp lệ nếu cần sinh/tóm tắt câu trả lời bằng Gemini |

File mẫu dùng `127.0.0.1:15433` và `127.0.0.1:17687` làm ví dụ tunnel local.
Mỗi thành viên phải mở tunnel trên chính máy mình hoặc dùng địa chỉ DB được nhóm
cấp; clone Git không tạo tunnel. Không gửi `.env` lên Git hay qua chat công khai.
`run_demo_backend.py` vẫn chạy khi không có `.env.operator` nếu writer đã đặt trong
`backend/.env`; không cần lấy file `.env.operator` riêng của máy người khác.

Nếu dùng DB chung, xác nhận corpus mẫu với leader vì phiên phục vụ có thể đã đổi.
Git chỉ cung cấp ID mẫu, không tự tạo dữ liệu cho ID đó. Dùng DB mới phải triển
khai schema/migration và nạp corpus/index/vector trước; chỉ tạo DB rỗng chưa đủ.
Xem [lịch sử Chat và migration](../../backend/src/retrieval_orchestration/notes/POSTGRES_HISTORY.md).
Không chạy reset/migration nhập dữ liệu thử lên DB chung chỉ để mở web.
Queue local có thể trống trên máy mới; chat vẫn đọc bài đã nạp từ corpus DB.
Muốn chia sẻ cả lịch sử thu thập/duyệt, sao lưu/chuyển thư mục
`outputs/admin-ingestion` riêng giữa các máy và giữ cùng corpus; thư mục này
không nằm trong Git. Đây vẫn là control plane cho một máy, chưa phải hàng đợi đa máy.

### SDK giá trên máy mới

`backend/requirements.txt` chưa cài `vnstock`. Để có lịch sử và giá mới, cài
SDK riêng; backend tự nhận đường dẫn dưới đây, tránh trộn dependency SDK và RAG:

```powershell
py -3.12 -m venv data_pipeline/ScrapersOHLCV/.agent-state/vnstock-venv
.\data_pipeline\ScrapersOHLCV\.agent-state\vnstock-venv\Scripts\python.exe -m pip install -r data_pipeline/ScrapersOHLCV/requirements/vnstock.txt
```

Nếu đã cài SDK trong `.venv` chính thì không bắt buộc tạo môi trường thứ hai.
Nếu SDK yêu cầu tài khoản/hạn mức, dùng cơ chế chính thức của SDK và cấu hình của
nhóm. Có SDK chưa đồng nghĩa nguồn luôn trả dữ liệu. Không có SDK thì chỉ các bản
giá đã lưu dùng được; dễ gặp lỗi tải giá mới dù đăng nhập và Chat vẫn mở được.

### OCR và frontend

Cài [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html) và
[Poppler](https://poppler.freedesktop.org/), đặt trên PATH hoặc cấu hình
`TESSERACT_CMD` / `PDFTOPPM_CMD` trong `.env`. Bộ ngôn ngữ tiếng Việt/Anh:

```powershell
.\.venv\Scripts\python.exe backend/scripts/setup_news_ocr.py
```

File ngôn ngữ tải từ kho chính thức, ghim revision; không commit binary/model.
Nếu dùng thư mục riêng, đặt `TESSDATA_PREFIX`. Áp dụng
`docker/postgres/init/090_raw_payload_source_uri_index.sql` vào DB đã có schema
(chỉ tạo index đọc nguồn; không xóa dữ liệu). Docker DB mới chạy init tự động.

```powershell
cd frontend
npm ci
```

Gemini: điền key và chỉ bật `B1_GEMINI_FREE_TIER_CONFIRMED=true` khi tài khoản
đã xác nhận đúng chính sách free tier của dự án. OCR/chunk không dùng Gemini.
Tài khoản admin cần quyền ADMINISTRATOR được cấp từ DB; không có tài khoản
hay mật khẩu dùng chung được ghi trong mã nguồn.

### Chạy ứng dụng

Giữ tunnel PostgreSQL cổng 15433 hoạt động. Từ thư mục backend:

```powershell
..\.venv\Scripts\python.exe scripts/run_demo_backend.py
```

Trong terminal khác, từ thư mục frontend:

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Kiểm tra `http://127.0.0.1:8000/api/health`: research_warmup và router_warmup
cần ở trạng thái ready trước khi đo thời gian. Lần khởi động đầu dựng cache
có thể lâu hơn các lần đã có cache. Không đóng backend/tunnel khi demo.
Máy mới có thể phải tải model `BAAI/bge-m3` theo revision ghim từ Hugging Face;
cần mạng và dung lượng cho Torch/model/cache. Những file này không đi cùng Git.
Cache corpus FROZEN dùng được tối đa 7 ngày; mỗi lần tìm vẫn kiểm fingerprint
membership/mô hình và hash nguồn trả về. Đổi corpus tự dùng cache khác.

### Checklist bàn giao cho thành viên

```powershell
.\Chay-FinMind.cmd --check
.\.venv\Scripts\python.exe -m pip check
```

Launcher `--check` chỉ kiểm tra dependency cơ bản và có file cấu hình; chưa xác
minh nội dung secret, DB/tunnel, corpus, Neo4j, SDK giá, OCR hoặc quota Gemini.
Thông báo `[OK]` của launcher chưa phải xác nhận toàn bộ chức năng sẵn sàng.

Sau khi mở hai server, kiểm tra từng luồng:

1. Đăng nhập bằng tài khoản của thành viên. Tài khoản mới mặc định RESEARCHER;
   leader cấp ADMINISTRATOR từ DB nếu cần admin, không sửa role ở frontend.
2. `/api/health` phản hồi và hai warmup ở trạng thái `ready`.
3. Mở công ty, đợi lịch sử giá tải và kiểm tra ngày dữ liệu; thiếu SDK/quota có
   thể làm giá lỗi dù DB vẫn hoạt động.
4. Mở Đồ thị, có phiên READY và xem được quan hệ/bằng chứng. Kiểm tra tunnel
   Neo4j riêng nếu danh sách phiên lỗi.
5. Hỏi một câu có nguồn trong corpus chung rồi mở citation. Key/đơn giá/hạn mức
   của nhà cung cấp không được xác minh chỉ bằng health check.
6. Nếu làm admin: thử OCR một tệp và kiểm tra đủ Tesseract, Poppler, `vie+eng`,
   rồi nạp một bài đã duyệt bằng writer DSN. Lịch cào tự động dùng tiến trình
   scheduler riêng (`backend/scripts/run_admin_scheduler.py`); mở web không
   tự khởi động lịch đó.

Nếu dùng Google login, cần client ID khớp frontend/backend và origin đã được
Google cho phép. Xem hướng dẫn Google trong README gốc; đăng nhập email/mật khẩu
không yêu cầu Google OAuth. Không dùng dữ liệu/phiên bản ở file minh họa để
khẳng định DB đã được nạp đầy đủ.

## Dữ liệu và câu hỏi kiểm tra

Bài ICT giải trình chênh lệch LNST Q2/2026 đã được OCR, duyệt và lưu 5 chunk
cùng vector vào public.text_chunks. Phiên thử ban đầu có 44.935 chunk, gồm dữ liệu
tài chính, BCTN, giá, hồ sơ công ty, News cũ và News OCR mới.
Lượt thử nạp một nút sau đó thêm 4 chunk, nâng tổng lên 44.939. Số lượng tiếp tục
thay đổi theo các bài được duyệt và nạp. Hệ thống chuẩn bị cache từ manifest
đã kiểm tra trước khi báo hoàn tất, để chat không phải đọc lại toàn bộ nguồn.

Trong Chat, hỏi:

- Theo bài giải trình của ICT, LNST quý 2/2026 và quý 2/2025 là bao nhiêu,
  tăng bao nhiêu phần trăm?
- Theo bài giải trình ICT, nguyên nhân doanh thu và lợi nhuận gộp quý 2/2026
  tăng là gì?
- Theo bài giải trình ICT, vì sao chi phí tài chính tăng?
- Theo bài giải trình quý 2/2026 của ICT, có số liệu LNST quý 3/2026 không?

Đáp án bảng đã đối chiếu PDF: 32.507.122.941; 13.443.564.076; 141,80%.
Nguyên nhân doanh thu: dự án chuyển tiếp từ năm 2025 ghi nhận doanh thu Q2/2026.
Chi phí tài chính: liên quan biến động tỉ giá. Tài liệu không cung cấp Q3/2026.

## Duyệt dữ liệu mới

Cào (tự đọc PDF/OCR nếu nội dung chính nằm trong tệp/ảnh) → Chờ duyệt
với văn bản đã đọc → kiểm tra và duyệt → chọn bài, bấm
**Tạo chunk & lưu dữ liệu** một lần. Hệ thống tự chia chunk, tạo vector,
lưu vào DB chung và hoàn tất chuyển Chat sang phiên dữ liệu chung mở rộng.
Không có nút kích hoạt riêng trong luồng bình thường. Khi job **Đã nạp xong**
thì có thể hỏi trong Chat; không thay corpus chung bằng corpus chỉ có vài bài News.
Các snapshot cũ được giữ nguyên để trích dẫn còn tái dựng được. Vector cũ
được tái sử dụng khi tạo phiên chung; chỉ bài mới cần embedding mới.
Nếu lỗi, job báo FAILED và giữ dữ liệu phục vụ trước đó. **Chạy lại lần nạp**
tiếp tục bước cuối nếu chunk/vector đã lưu, không cần tạo lại vector đó.

OCR là bước trong `crawl_job`, dùng chung cho cào tay và scheduler. Nguồn thô
cần đọc tệp được giữ khỏi hàng đợi duyệt, tạo revision PENDING sau khi đọc xong;
lỗi đọc đưa vào Cần kiểm tra và không làm dừng các bài khác. Cào lặp không OCR
lại nguồn đã có revision; nguồn lỗi tự động có thể được thử lại khi cào gặp lại.
Nút Đọc PDF/OCR trong chi tiết là công cụ phục hồi, không phải bước bắt buộc sau
Đã duyệt. Bản OCR vẫn cần kiểm tra chữ/số trước duyệt, không tự nhận là chính xác.

## Cách đọc kết quả

Nếu Dashboard hiện `Authentication required`, F5 và đăng nhập lại một lần nếu
phiên cũ thiếu token. Frontend loại phiên chỉ có profile, gộp refresh đồng thời
(kể cả React StrictMode), dùng Web Locks để phối hợp các tab, đồng bộ đăng xuất
và không để phản hồi refresh cũ ghi đè lần đăng nhập mới. API thị trường thử refresh
một lần khi gặp 401; 403 giữ là lỗi quyền, không tự đăng xuất. Không bỏ kiểm tra
token/role ở backend để né lỗi. Phiên hết hạn hoặc bị thu hồi vẫn cần đăng nhập.

Dashboard đọc kho tin thị trường trước. Nếu kho này trống, backend chính dùng metadata
các bài FireAnt INDEXED của admin làm nguồn dự phòng; không trả bài chờ duyệt, bị giữ
hoặc từ chối, không trả lịch sử review/payload thô. Nguồn dự phòng dùng cùng queue
local với admin, chưa phải nguồn đồng bộ metadata giữa nhiều máy.

Trang `/admin/overview` lấy số bài và job từ SQLite trên máy đang chạy backend,
đồng thời đọc số tài liệu/chunk của phiên phục vụ từ PostgreSQL chung. Tự cập nhật
mỗi 30 giây. Nếu DB mất kết nối, trang vẫn trả số liệu hàng đợi và cảnh báo phần kho
dữ liệu; không suy ra rằng model đang hoạt động chỉ từ trạng thái DB.
Bố cục giữ các phần KPI truy vấn, ngân sách, truy vấn gần đây, cảnh báo, hoạt động
quản trị và dịch vụ cốt lõi. Truy vấn Chat LIVE, kết quả, thời gian và token Gemini
được ghi từ khi bật theo dõi vào `outputs/admin-ingestion/research-metrics.sqlite`.
Thống kê ngày theo giờ Việt Nam; dữ liệu còn sau khi khởi động lại, không cộng
các phiên fixture hoặc suy đoán token từ lịch sử trước khi bật. Phạm vi là backend
trên máy này, không phải toàn bộ lượt dùng chung API key ở các máy/dịch vụ khác.
Trace mới lưu câu hỏi người dùng (tối đa 4.000 ký tự), nguồn đã trích dẫn, mã nguyên
nhân, model và thời gian. Không lưu prompt nội bộ, văn bản nguồn, câu trả lời đầy đủ,
khóa API hay exception thô trong ledger. Trace cũ thiếu chi tiết sẽ để trống.
Lấy usageMetadata trước kiểm tra nội dung để giữ token đã dùng cả khi câu trả lời
bị chặn hoặc không hợp lệ. Lỗi không có usage ghi số lần **không xác định** riêng;
tổng hiển thị là phần đã biết. Token dự trù trong Budget không phải token thực tế.
Không gọi Gemini (làm rõ câu hỏi, giá trực tiếp...) có thể là 0 token thật.
Token đầu vào/đầu ra/tổng theo từng model; tổng có thể gồm suy luận ngoài đầu ra.
Không tự suy ra hóa đơn. Đơn giá và hạn mức tiền chưa cấu hình sẽ ghi rõ.
KPI “truy vấn thành công” là nhận được câu trả lời (kể cả trích nguyên văn dự phòng),
không khẳng định đã kiểm chứng toàn bộ tài chính. Request lỗi ngoài dự kiến/hủy
vẫn ghi ERROR nếu tiến trình còn hoạt động; tắt cưỡng bức có thể mất lượt đang chạy.
Khởi tạo Research và
Router lấy từ app.state của backend; giám sát Graph/Gate/Verifier/Telemetry chưa
được kết nối. Nhật ký quản trị gần đây dùng API audit thực tế.

Trang `/admin/audit` đọc lịch sử quyết định từ bảng reviews (gồm lịch sử trước khi
thêm trang) và các thao tác đã ghi trong bảng audit: cấu hình nguồn, thử nạp lại,
ngắt job. Có lọc nhóm và phân trang; đây chưa phải nhật ký toàn bộ hành động của
mọi module. Hai API đều yêu cầu vai trò ADMINISTRATOR từ máy chủ. Các mục
Cấu hình nguồn và Phiên bản kho dữ liệu riêng vẫn là giao diện minh họa; thao tác
nguồn thật nằm trong Thu thập & duyệt. `/admin/traces` có danh sách/chi tiết thật,
lọc ngày Việt Nam, công ty, trạng thái và phân trang. `/admin/configuration` lưu
ngân sách/đơn giá thật theo phiên bản, cảnh báo và hiển thị chi phí ước tính; các
ngưỡng Evidence Gate, Retrieval và Token khác chưa nối chỉnh sửa qua giao diện.
Xem thêm [ADMIN_OPERATIONS.md](ADMIN_OPERATIONS.md) về phục hồi job và ngân sách.

Gemini có thể trả HTTP 503 khi quá tải. Hệ thống không tự gọi lại vô hạn.
Khi có dòng nguồn phù hợp đã xác minh, kết quả sẽ ghi rõ trích nguyên văn,
có citation, thay cho bản diễn đạt của mô hình. Đây không phải một câu trả lời
do LLM diễn đạt thành công. Nếu nguồn không có đúng kỳ hoặc dòng phù hợp,
hệ thống từ chối thay vì lấy số liệu của kỳ/chỉ tiêu khác.

OCR có thể sai dấu/chữ: giữ bản gốc và kiểm tra số liệu trước khi duyệt.
Không coi các test trong một bài demo là cam kết mọi câu hỏi đều đúng.

Báo cáo máy đọc và thời gian từng câu: outputs/ocr-ai-demo/web-api-report.json.
Các báo cáo ai-report.json và diagnostic-report.json là kết quả trước sửa;
không dùng chúng làm kết luận cho phiên chung hiện tại.

### Biểu đồ chỉ số thị trường

Trang chi tiết công ty tự đọc cache rồi tải lịch sử khoảng sáu tháng khi mở,
kể cả với vai trò RESEARCHER. `GET /api/market-data/stocks/{symbol}/history`
yêu cầu quyền xem, dùng cache và hạn mức SDK chung; thao tác POST thủ công
vẫn yêu cầu DATA_ENGINEER/ADMINISTRATOR. Mã chưa có cache hiển thị đang tải,
lỗi tải hiển thị nút thử lại; không báo đã có biểu đồ khi nguồn chưa trả dữ liệu.

Dashboard tự mở VN-INDEX và đọc bản lưu của bốn chỉ số qua
`GET /api/market-data/indices/{symbol}/ohlcv?cached=true` (vẫn yêu cầu đăng nhập).
Đọc cache không gọi SDK và không tiêu hạn mức nguồn. Bản lưu được hiển thị ngay
với ngày dữ liệu; frontend cập nhật lần lượt ở nền, ưu tiên chỉ số đang chọn và
tự chờ theo `Retry-After` khi gặp 429 (tối đa bốn lần gọi). Nếu cập nhật lỗi, giữ
biểu đồ đã lưu và hiện cảnh báo. Chỉ số chưa có bản lưu phải chờ lần tải đầu.
Các lần tải thành công được lưu nguyên đơn vị điểm tại
`.agent-state/market-data/indices/index-{symbol}/history.json`, dùng lại sau khi
khởi động backend; không coi bản lưu hay thời điểm lấy dữ liệu là giá realtime.
