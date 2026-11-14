# Tách người – chức vụ – công ty bằng quy tắc, không dùng AI

Mã xử lý: `backend/src/person_role/rules_pipeline.py`. Lệnh chạy: `backend/scripts/extract_crawled_person_roles.py`. Chỉ dùng thư viện chuẩn Python; không gọi LLM, mô hình NER, embedding hoặc API mạng. Không ghi database tự động và không đổi các bản ghi SOURCE_VERIFIED trước đây.

## Đầu vào sau khi cào

Hỗ trợ file JSON, JSONL hoặc thư mục chứa các file `pages.jsonl`. JSON có thể là một record, danh sách record, object có `records` hoặc object tài liệu có `pages`. Với thư mục BCTN, đọc symbol và year từ source.json bên cạnh nếu có. Không dùng thư mục v2 đã biết lỗi làm đầu vào chuẩn.

Đầu vào trang văn bản:

```json
{"document_id":"ELC-2024-source","symbol":"ELC","source_kind":"annual_report","page":68,"reporting_year":2024,"source_url":"https://example.org/report.pdf","text":"Danh sách HĐQT\nÔng Ngô Ngọc Hà Thành viên HĐQT/Phó Tổng Giám đốc"}
```

`example.org` trong tài liệu chỉ minh họa định dạng, không phải nguồn thực tế. Dùng URL thật do crawler lấy được. `page` là trang PDF vật lý, không phải số trang in. Bài web không có trang thì để thiếu/null, không giả trang 1. Nếu có content_hash hoặc clean_text_sha256, script kiểm tra hash trước xử lý.

Đầu vào ưu tiên từ một hàng bảng đã tách được:

```json
{"document_id":"news-source-id","symbol":"TCB","source_kind":"news","person":"Phan Thị Hải Yến","position":"Phó Tổng Giám đốc","event":"bổ nhiệm từ 01/11/2026","organization_verified":true,"as_of":"2026-10-30","source_url":"https://example.org/disclosure"}
```

Chỉ đặt `organization_verified=true` khi crawler đã xác định đúng doanh nghiệp của hàng đó từ cấu trúc nguồn, không chỉ lấy ticker gắn cho cả bài. Tên person không chứa Ông/Bà hoặc chức vụ. Trường position có thể là chức vụ kiêm nhiệm nối bằng / hoặc kiêm. Trường event giữ nguyên chữ từ nguồn; không được tự tạo sự kiện. Cờ này không biến kết quả thành người duyệt phê duyệt.

## Chạy trên PowerShell

Tại `C:\NhanhFrontend\FinMind\backend`:

```powershell
..\.venv\Scripts\python.exe scripts/extract_crawled_person_roles.py --input tests/fixtures/crawled_person_roles.jsonl --source-kind annual_report --output-dir ../outputs/person-role-demo-moi
```

Chạy một BCTN:

```powershell
..\.venv\Scripts\python.exe scripts/extract_crawled_person_roles.py --input ../outputs/annual-clean-review-20261029-columns/ELC/2024/937811ef432d/pages.jsonl --source-kind annual_report --symbol ELC --reporting-year 2024 --source-url https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf --output-dir ../outputs/person-role-elc-lan-moi
```

Chạy cả thư mục đã có source.json với symbol/year bên cạnh từng pages.jsonl:

```powershell
..\.venv\Scripts\python.exe scripts/extract_crawled_person_roles.py --input ../outputs/annual-clean-review-20261029-columns --source-kind annual_report --as-of 2026-10-30 --output-dir ../outputs/person-role-toan-bo-lan-moi
```

Mỗi lần chọn thư mục đầu ra mới. Script từ chối ghi đè. `--as-of` là ngày tham chiếu minh bạch để phân loại sự kiện có hiệu lực tương lai, không suy ra từ năm báo cáo.

Tích hợp trực tiếp sau crawler:

```python
from src.person_role.rules_pipeline import extract_record

result = extract_record(crawled_record, symbol="ELC", source_kind="annual_report")
save_candidates(result["candidates"])
save_quarantine(result["quarantine"])
```

Hai hàm save_* ở ví dụ là nơi tích hợp của crawler, không phải API đã cài sẵn. Hàm extract_record không truy cập database hoặc filesystem.

## Quy tắc xử lý

1. Xác minh hash văn bản nếu đầu vào có hash; giữ nguyên văn bản để offsets không lệch.
2. Nhận diện tên có Ông/Bà và ranh giới từ, hoặc dùng tên trong cột person rõ ràng. Chặn tên có chức vụ bị nuốt vào cuối.
3. Ghép theo một hàng/câu với đúng một người. Từ điển hiện hỗ trợ 13 mẫu chức vụ, bao gồm HĐQT, Ban Kiểm soát, TGĐ/Phó TGĐ, Kế toán trưởng, CFO, Ủy ban kiểm toán và thành viên Ban Điều hành. Giữ position_raw và position_code riêng.
4. Chức vụ kiêm nhiệm được tách thành từng ứng viên khi liên kết liền bằng /, kiêm hoặc và. Nếu một sự kiện theo sau nhiều chức vụ và chưa rõ phạm vi, đưa vào quarantine.
5. Phân biệt bổ nhiệm, miễn nhiệm, từ nhiệm, xin từ nhiệm và đề cử. Phủ định, điều kiện và tiểu sử lịch sử chưa đủ timeline không trở thành khẳng định đang giữ chức.
6. Ngày quyết định không tự coi là ngày hiệu lực. Không tự điền năm thiếu. Ngày lịch không hợp lệ hoặc nhiều ngày hiệu lực mâu thuẫn bị chặn.
7. Với tin tức, ticker cả bài không đủ xác nhận người thuộc công ty. Cần hàng tổ chức được crawler kiểm tra hoặc alias cụ thể trong câu; câu có tên doanh nghiệp không rõ bị đưa vào quarantine.

## Đầu ra

- `candidates.jsonl`: ứng viên có ID xác định theo nội dung, tên, vị trí, công ty, sự kiện, ngày, hash và offsets chứng cứ.
- `quarantine.jsonl`: đoạn không được gán quan hệ và lý do cụ thể.
- `unmatched_records.jsonl`: các trang/record chưa có mẫu hỗ trợ, để không nhầm không có kết quả với đã rà đúng toàn bộ.
- `summary.json`: số record, ứng viên, đoạn bị chặn và thống kê lý do; xác nhận ai_calls/network_calls/database_writes đều 0.

Trạng thái `RULE_MATCHED`/`PENDING` khác với `SOURCE_VERIFIED`. Không tự nâng thành APPROVED hoặc ghi vào graph đang hoạt động. Một người có nhiều mention vẫn có nhiều bằng chứng; ID rule không phải canonical person xuyên công ty.

## Giới hạn và kiểm thử

Không dùng AI vẫn có thể tách bảng/tên bằng quy tắc, nhưng không thể đảm bảo đúng mọi OCR và bố cục lạ. Script không tự đọc ảnh/PDF, không tự chữa tên sai dấu, không giải mã font PDF và không đoán tên thiếu. PDF scan cần bước OCR trước; OCR sai thì phải đánh dấu/đối chiếu nguồn hoặc sửa crawler. Các cảnh báo layout_uncertain/blocked_reasons có thể chặn record trước khi trích xuất.

19 kiểm thử quy tắc đạt; fixture minh họa xuất 4 ứng viên và chặn 1 câu gán nhầm công ty. Lượt chạy cuối trên cả 20 BCTN (2.749 trang) xuất 730 ứng viên, 3.583 đoạn bị chặn, không gọi mạng/AI/database. Xem summary.json trong outputs/person-role-rules-all-20261030-final để biết chính xác phiên chạy. Đây là kiểm tra chạy pipeline, không phải precision/recall hoặc chứng nhận toàn bộ ứng viên đúng.

Kiểm thử:

```powershell
$env:PYTHONPATH = (Get-Location).Path
..\.venv\Scripts\python.exe -m unittest discover -s tests -p test_crawled_person_role_rules.py
```
