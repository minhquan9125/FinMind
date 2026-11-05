# Demo dữ liệu News OCR trong tập dữ liệu chung

## Khởi động

### Máy mới sau khi merge

Từ thư mục gốc repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

Sửa `backend/.env`: kết nối PostgreSQL đọc/ghi, JWT secret và corpus thực tế.
Không ghi đè `.env` nếu máy đã có cấu hình. Nếu dùng DB chung của nhóm ở lượt
demo đã kiểm tra, `.env.example` đã ghi corpus
`924c00e5-8bd9-5141-8f8d-30a49c107b70` (44.939 chunk tại lúc bàn giao).
Dùng DB khác thì phải đặt corpus FROZEN/ACTIVE thực sự của DB đó.
Queue local có thể trống trên máy mới; chat vẫn đọc bài đã nạp từ corpus DB.
Muốn chia sẻ cả lịch sử thu thập/duyệt, sao lưu/chuyển thư mục
`outputs/admin-ingestion` riêng giữa các máy và giữ cùng corpus; thư mục này
không nằm trong Git. Đây vẫn là control plane cho một máy, chưa phải hàng đợi đa máy.

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
Cache corpus FROZEN dùng được tối đa 7 ngày; mỗi lần tìm vẫn kiểm fingerprint
membership/mô hình và hash nguồn trả về. Đổi corpus tự dùng cache khác.

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

Cào → đọc PDF/OCR nếu thiếu chữ → kiểm tra và duyệt → chọn bài, bấm
**Tạo chunk & lưu dữ liệu** một lần. Hệ thống tự chia chunk, tạo vector,
lưu vào DB chung và hoàn tất chuyển Chat sang phiên dữ liệu chung mở rộng.
Không có nút kích hoạt riêng trong luồng bình thường. Khi job **Đã nạp xong**
thì có thể hỏi trong Chat; không thay corpus chung bằng corpus chỉ có vài bài News.
Các snapshot cũ được giữ nguyên để trích dẫn còn tái dựng được. Vector cũ
được tái sử dụng khi tạo phiên chung; chỉ bài mới cần embedding mới.
Nếu lỗi, job báo FAILED và giữ dữ liệu phục vụ trước đó. **Chạy lại lần nạp**
tiếp tục bước cuối nếu chunk/vector đã lưu, không cần tạo lại vector đó.

## Cách đọc kết quả

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
