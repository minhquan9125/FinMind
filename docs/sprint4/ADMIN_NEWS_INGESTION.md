# Admin News: thu thập, duyệt, chunk, vector và phiên dữ liệu mới

Điểm vào: `/admin/ingestion`, mục **Thu thập & duyệt**. Đây là dữ liệu nguồn
thật, tách khỏi các báo cáo Fixture ở trang Job dữ liệu.

## Cập nhật phạm vi và duyệt tự động

Policy mới **source-quality-v2** thay điều kiện độ dài v1 bên dưới: tiêu đề ít
nhất 6 ký tự; tin ngắn có phần chữ ít nhất 80 ký tự và 10 từ được xét bình
thường. Thông báo ngắn dẫn sang PDF được ghi `ATTACHMENT_TEXT_REQUIRED`; ảnh
có quá ít phần chữ được ghi `OCR_REQUIRED`. URL/ID nguồn và ngày đăng vẫn phải
đạt. Không tự duyệt phần giới thiệu như thể đã đọc tài liệu đính kèm.

Nút kiểm tra lại áp dụng các bài QUARANTINED mà quyết định mới nhất do
auto-review tạo, gồm cả v1/v2. Job đọc PDF/OCR nếu thiếu chữ; bản trích xuất
vào PENDING để kiểm tra thủ công. Bài lỗi giữ nguyên và có lý do riêng.
Không ghi đè quyết định thủ công; bài đã duyệt không tự bị xét lại.

**OCR:** News tái sử dụng hàm trong `data_pipeline/annual_reports/OCR_annuals.py`:
pypdf cho lớp chữ, Tesseract vie+eng cho PDF scan/ảnh. Nguồn gốc được giữ nguyên;
revision chứa chữ, trang và hash tệp. Bài chỉ có ảnh hoặc giới thiệu PDF bị chặn
duyệt/tạo chunk cho đến khi trích xuất xong. Chỉ việc OCR thành công chưa thay
thế bước kiểm tra nội dung, đặc biệt số liệu tài chính.

- “Xem nguồn” mở popup lớn với trạng thái tải/lỗi, nội dung, metadata, payload
  và lịch sử duyệt; không chỉ hiện banner rồi đặt nội dung ở dưới bảng.
- Cấu hình hỗ trợ tối đa 500 bài/lượt, 1–20 trang/mã, tối đa 30 mã ba ký tự
  viết hoa và tùy chọn tin thị trường chung. Local đang đặt 100 bài, 5 trang,
  10 mã VCB/BID/CTG/MBB/TCB/FPT/CMG/ELC/ITD/ICT và tin thị trường. Reader duyệt
  luân phiên các mã, chống trùng ID nhà cung cấp. Không cam kết lấy toàn bộ lịch sử.
- “Tự động duyệt bài mới đạt kiểm tra nguồn” mặc định tắt; khi bật và lưu, chỉ
  bài mới của lượt crawl sau được áp dụng. Nút “Duyệt tự động bài đang chờ” áp
  dụng tối đa 500 bài PENDING hiện có. Không ghi đè bài đã có quyết định người
  duyệt hoặc bài INDEXED.
- Policy `source-quality-v1` kiểm FireAnt HTTPS/đường dẫn/ID bài đối chiếu raw,
  title ít nhất 12 ký tự, body ít nhất 300 ký tự, ngày ISO có timezone và không
  ở tương lai quá một ngày. Đạt -> APPROVED; không đạt -> QUARANTINED kèm mã
  lý do. Đây là kiểm chất lượng nguồn, không xác minh sự thật của nội dung hay
  duyệt quan hệ Graph. Actor tự động và phiên policy được lưu trong reviews.
- Không tự embedding hoặc kích hoạt index sau duyệt tự động. Hai bước này vẫn
  có nút riêng. Bảng bài có lọc trạng thái, phân trang 50 bài và tổng số thật.
- Kho news_articles cũ và queue admin mới là hai phạm vi khác nhau. Queue không
  tự nhập lại mọi dữ liệu cũ đã index hoặc đánh dấu chúng đã được duyệt.

## Luồng sử dụng

Giao diện có các mục **Chờ duyệt / Đã duyệt / Đã xử lý**, cùng mục Cần kiểm tra
và Đã từ chối. Duyệt bài không tự tạo chunk. Trong Đã duyệt, mở nguồn kiểm tra
lại, chọn từng bài hoặc chọn tất cả xuyên trang rồi bỏ tick các bài chưa muốn
xử lý. Lựa chọn giữ nguyên khi đổi trang/làm mới nếu bài vẫn còn APPROVED.
Mỗi lượt tối đa 500 bài; nếu nhiều hơn, nút ghi rõ chọn 500 bài đầu để xử lý
theo đợt. Nút chính là **Tạo chunk & lưu dữ liệu**.

Job hiển thị bước chia chunk, số bài đã tạo vector/tổng bài, bước lưu DB và lỗi.
Vector được lưu tạm từng bài rồi ghi transaction sau khi toàn bộ embedding đạt,
tránh giữ mọi vector của một lượt lớn trong RAM. Tệp tạm được dọn khi kết thúc.

Trong Đã xử lý, **Xem bài & chunk** mở lại nguồn và lịch sử; nút xem chunk đọc
DB và dựng lại văn bản từ nguồn/hash đã ghim. Hiển thị nội dung chunk, ID,
vị trí, hash, phiên index/corpus và trạng thái kích hoạt; phân trang 30 chunk.
Không trả mảng vector lên giao diện. Endpoint đọc mới:
`GET /articles/selection` và `GET /articles/{id}/chunks?offset=0&limit=30`.

1. **Cào ngay**: reader FireAnt hiện có lấy số bài theo cấu hình (local 100/lượt).
   Không gọi CLI crawler cũ vì CLI đó có nhánh tự đẩy dữ liệu vào DB. Bản gốc
   API, nội dung đọc được, URL, ngày đăng, metadata được lưu vào SQLite local.
2. Bài mới vào **PENDING**; thiếu title/body/URL vào **QUARANTINED**. Khóa chống
   trùng bao gồm nguồn, URL, tiêu đề, body, ngày và symbols, không gồm lượt xem
   hoặc giờ fetch. Nội dung thay đổi tạo snapshot mới, phải duyệt lại.
3. Admin mở nguồn, xem payload, ghi lý do và quyết định. Actor lấy từ principal
   đã xác thực. Quyết định lưu bền; không chỉnh sửa payload hay ghi đè quyết định
   đã chốt. Đây là duyệt **bài nguồn**, không phải duyệt quan hệ Graph WBS06.
4. Chọn bài **APPROVED**, bấm **Tạo chunk & lưu dữ liệu**. Dùng lại `news_documents`,
   `chunk_document`, `embed_all`, `write_chunks` và BGE-M3 hiện có. Chỉ ghi khi
   mọi chunk có vector hợp lệ. Một index UUID mới có trạng thái **BUILDING**.
5. Bản nguồn bất biến được ghi `raw_payloads` với hash; document và chunk trỏ
   bản này bằng locator `admin_news_snapshot`. Reader kiểm raw hash, dựng lại
   bằng chunker hiện có và kiểm hash chunk. Không cập nhật bài/source của corpus
   cũ hoặc ghi đè vector cũ.
6. Tự động hoàn tất trong cùng job: đọc lại toàn bộ chunk từ nguồn, kiểm dimension,
   hash, manifest; đăng ký corpus FROZEN mới và chuyển index đó thành ACTIVE
   trong cùng transaction. Nếu khác bản vừa build thì từ chối kích hoạt.
   Người dùng không bấm thêm nút. Job giữ RUNNING đến khi con trỏ dữ liệu chung
   và trạng thái bài được cập nhật cùng nhau, rồi mới báo **Đã nạp xong**.
   Nếu lỗi, bấm **Chạy lại lần nạp**; khi đã lưu chunk/vector, chỉ chạy lại phần cuối.
7. **Tìm thử phiên mới**: dùng HybridRetriever Vector/BM25/RRF và đúng corpus
   vừa xuất bản, cache lexical theo job. Kết quả giữ chunk/hash/URL nguồn.

Theo phạm vi demo mới, index được tạo bằng cách mở rộng corpus chung hiện có:
copy vector cũ trên DB server và thêm vector News mới, giữ source binding cũ.
Facts và prices của corpus gốc cũng được mang sang. Snapshot FROZEN cũ giữ
nguyên. Sau khi kích hoạt, con trỏ serving_corpus được cập nhật; chat dùng
corpus chung mới ở câu hỏi kế tiếp mà không cần thay `.env` hoặc restart.
Chưa xuất quan hệ Graph từ chức năng này. Xem `LOCAL_DEMO.md` để chạy demo.

## Cấu hình và vận hành local

- `ADMIN_INGESTION_DIRECTORY`: mặc định `outputs/admin-ingestion`; gồm
  `control.sqlite`, manifest và cache lexical. Sao lưu cả thư mục. Dữ liệu
  duyệt/queue tồn tại sau restart. Đây là control plane cho demo một máy.
- `ADMIN_INGEST_DATABASE_URL`: kết nối ghi riêng. Không thay `DATABASE_URL`
  runtime bằng tài khoản operator. Nếu thiếu, API lập chỉ mục trả 503.
  Dùng credential qua môi trường tiến trình, không commit hoặc đưa lên frontend.
- Reader runtime cần quyền SELECT trên raw_payloads, documents, text_chunks,
  corpus/index mới để đọc lại bằng chứng. Nếu thiếu quyền, giữ lỗi và sửa
  cấu hình quyền; không bỏ kiểm hash/nguồn.
- Backend và scheduler phải dùng cùng thư mục SQLite. Một lượt crawl/index
  chạy tại một thời điểm. Nút ngắt giải phóng job treo; worker dừng ở ranh giới
  bước tiếp theo. Thao tác DB đã commit có thể còn là draft, không tự ACTIVE.
- Mất tiến trình giữa chừng không tự khôi phục coroutine. Ngắt job bị treo rồi
  chạy lại; crawl chống trùng và bài chưa index thành công vẫn được chọn lại.

## Lịch hằng ngày

Mặc định **tắt**, 07:00 giờ Việt Nam, tối đa 20 bài. Admin bật/lưu lịch và chạy
scheduler độc lập từ thư mục backend:

```powershell
..\.venv\Scripts\python.exe scripts/run_admin_scheduler.py
```

Worker kiểm tra mỗi 30 giây, lưu khóa ngày Việt Nam để không chạy hai lần cho
cùng ngày kể cả có hai scheduler hoặc restart. Nếu mở máy sau giờ chạy, thực
hiện một lượt bù trong ngày đó. Không chạy bù tất cả ngày máy tắt. Một lượt
thất bại vẫn được ghi nhận; admin có thể chạy thủ công lại. Lịch không tự duyệt,
không tự embedding và không tự kích hoạt. Crawler giới hạn trang gần nhất;
không cam kết thu đủ mọi tin của ngày hay backfill lịch sử.

## API

Tất cả endpoint dưới `/api/v1/admin/ingestion` yêu cầu ADMINISTRATOR thật:

- GET/PUT `/source`: cấu hình lịch, nguồn và giới hạn.
- POST `/crawl`: job thu thập nền.
- GET `/jobs`, GET `/articles`, GET `/articles/{id}`: trạng thái và bản nguồn.
- POST `/articles/{id}/review`: decision và note bắt buộc.
- POST `/index`: danh sách article_ids đã duyệt, tối đa 500.
- POST `/jobs/{id}/retry`: chạy lại một lần nạp lỗi/cũ; bước xuất bản tự động.
- POST `/jobs/{id}/activate`: kiểm tra và xuất bản index/corpus mới.
- POST `/jobs/{id}/search`: tìm thử bằng chứng trên phiên ACTIVE đó.
- POST `/jobs/{id}/interrupt`: ngắt/giải phóng job bị treo.

Job dùng FastAPI BackgroundTasks trong demo local. Chưa phải hàng đợi phân tán
cho nhiều máy. Các thao tác nguồn/job có actor và lịch sử cục bộ; chưa nối bảng
audit chung vào trang Audit mock cũ. Không tạo quyền thu thập từ nhà cung cấp;
phải dùng nguồn và phạm vi nhóm đã chốt.

## Kiểm tra

### Đọc PDF / OCR News

Trong Xem nguồn, nút **Đọc PDF / OCR ảnh** chạy job `OCR` cho một bài
PENDING/QUARANTINED. Adapter `admin_news_ocr.py` tái sử dụng hàm đọc lớp chữ,
render trang và Tesseract từ `data_pipeline/annual_reports/OCR_annuals.py`.
Không gọi mô hình/cloud OCR mới. PDF có chữ dùng pypdf; PDF scan/ảnh dùng
Tesseract `vie+eng`, cần executable và dữ liệu tiếng Việt/Anh trên máy.
Có thể đặt `TESSERACT_CMD` và `PDFTOPPM_CMD` bằng đường dẫn executable.

Mỗi tệp tối đa 25 MB, 100 trang PDF, 10 tệp/bài. Chỉ tải HTTPS từ miền
FireAnt (kiểm tra lại từng redirect); miền ảnh khác báo lỗi để bổ sung sau.
Nguồn tải về được giữ dưới `ocr/<job-id>/` trong thư mục hàng đợi.
Kết quả lưu hash tệp, URL, phương pháp và chữ theo từng trang trong payload.
Khi toàn bộ tệp đọc thành công, tạo revision PENDING; bản gốc giữ nguyên payload,
chuyển SUPERSEDED (Đã thay bằng bản PDF/OCR) kèm lịch sử và nút mở revision thay thế;
không tính vào Đã từ chối. Lỗi giữ nguyên bài cũ.
Revision OCR phải được người quản trị kiểm tra/duyệt thủ công trước khi tạo chunk;
auto-review không tự thông qua. Chưa có giao diện sửa chữ OCR theo từng trang.

- POST `/articles/{id}/ocr`: tạo job đọc PDF/OCR.
- Trong lịch sử job, **Xem bản đã đọc để duyệt** mở revision kết quả.
- Engine chưa cài sẽ báo `TESSERACT_NOT_AVAILABLE`; PDF có lớp chữ vẫn đọc được.

Nút **Kiểm tra lại & đọc PDF / OCR** gọi POST `/auto-review/recheck` (202),
tạo job RECHECK chạy nền cho tối đa 500 bài QUARANTINED có quyết định gần nhất
do auto-review. Không giới hạn ở quy tắc v1. Bài thiếu nội dung PDF/ảnh được
đọc bằng adapter OCR trên; revision vào PENDING để kiểm tra thủ công. Bài không
cần OCR được xét lại bằng quy tắc nguồn hiện tại. Quyết định giữ của người duyệt
không bị tự xét lại. Lỗi riêng từng bài được lưu trong job, giữ nguồn cũ và tiếp
tục các bài còn lại. UI hiển thị số bài hoàn tất, lỗi và mở được từng revision.

Các bản nguồn từng bị gắn REJECTED do thay bằng revision được sửa thành
SUPERSEDED khi mở Queue, chỉ khi liên kết revision và lịch sử thay thế khớp.
Quyết định từ chối của người duyệt giữ nguyên. Trigger tương thích worker cũ
phân loại các revision đang chạy sang SUPERSEDED mà không cần ngắt job OCR.

```powershell
$env:PYTHONPATH='.;backend'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_admin_ingestion.py backend/tests/test_admin_news_index.py -q
```

Tests dùng fixture/fake DB cho review, dedup, lịch, writer và activation gate.
Lượt lấy thử local đã lưu hai bài FireAnt thật ở PENDING; không tự phê duyệt
hai bài đó. Chưa coi test giả lập là bằng chứng embedding/publish nguồn thật.
