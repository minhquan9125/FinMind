# S5-WBS04.1 — Nhận diện câu hỏi lấy số liệu, 12/11/2026

Câu REVIEW-03 “Doanh thu AI và cloud của doanh nghiệp ABC là bao nhiêu?”
hiện được lớp quyết định trả **NUMERIC**. Classifier gốc vẫn
xếp ENTITY_RELATION 0,2669 trước NUMERIC 0,2541; không sửa/xếp lại các điểm đó.
Đây là guard mục tiêu ở ứng viên offline V5 (`intent-request-objectives-v3`),
không phải retrain hoặc chứng minh BGE đã hết nhạy tên doanh nghiệp.

## Cách làm

Yêu cầu lấy giá trị + chỉ tiêu tài chính (doanh thu, lợi nhuận, EPS, ROE, ROA,
tài sản, dòng tiền…) tạo bằng chứng NUMERIC. Không có điều kiện riêng theo ABC,
ticker, năm, tên người hoặc câu hoàn chỉnh. Giữ loại trừ câu đếm quan hệ/bài tin,
ngày/chức vụ, nguyên văn, giải thích/tóm tắt/đánh giá và kế hoạch chưa rõ mục tiêu.
BCTN hoặc bài tin chỉ là nguồn không tự làm câu hỏi con số đổi thành REPORT/NEWS.

Kế thừa parser V4. Các phần rõ NUMERIC và PERSON_ROLE/REPORT khác nhau có thể
đề xuất MIXED; không mặc định MIXED là BOTH. Nếu chưa nhận đủ mục tiêu, vẫn có
thể sai. `resolution.confidence=null`, raw ranking giữ nguyên và tham chiếu về
artifact V4 thay vì chép lại hàng trăm bảng điểm. Ngưỡng của Huyền không đổi.

## Hồi quy trên 293 câu đã xem

| Bộ | Có nhãn | V4 đúng | V5 đúng |
|---|---:|---:|---:|
| controls | 32 | 32 | 32 |
| development | 84 | 70 | 70 |
| known_diagnostic | 8 | 6 | 6 |
| previous_check | 28 | 24 | 24 |
| regression | 47 | 41 | 41 |
| previous_new_check | 42 | 39 | 39 |
| previous_final_check | 28 | 25 | 26 |
| review_probes | 15 | 14 | 15 |

Sửa thêm: FINAL-NUMERIC-2-DPM, REVIEW-03. Đang đúng thành sai:
không có. Điều kiện đã đóng băng:
**ĐẠT**.
293 hàng gồm 9 câu null không được tính accuracy; cả 15 probe review cũ nay
là phát triển/hồi quy. Không gọi việc đạt 15/15 trên chúng là test mù hoặc
accuracy toàn bộ hệ thống.

## 20 câu kiểm tra bổ sung sau đóng băng

Đúng **17/20 (85.00%)**. Dùng model BGE-M3,
revision và head C=1 cũ; vector hóa 26 văn bản câu hỏi/phần câu mới, không fit.
Tập do cùng tác giả soạn dựa trên tiêu chí guard và có cách hỏi tương tự unit
test; chưa phải đánh giá độc lập hay đại diện cho toàn bộ Web Chat.

| Mã còn sai | Câu | Kỳ vọng | Quyết định |
|---|---|---|---|
| NV-13 | Tìm bài tin cho biết doanh thu của VJC trong năm 2024. | NEWS | MIXED |
| NV-19 | Cho biết LNST VJC 2024 rồi tìm bài tin VJC mở đường bay mới. | MIXED | NEWS |
| NV-20 | Đọc tổng tài sản PNJ cuối năm 2024 và xác định ai là CEO của PNJ. | MIXED | PERSON_ROLE |

Giữ nguyên mọi lỗi sau phép đo, không đổi gold hoặc thêm ngoại lệ theo câu.
Các lỗi còn lại có thể thuộc parser/nhãn nền; cần đọc từng câu trước khi đề xuất
sửa tiếp. Chưa kết luận đã xử lý mọi câu nhiều ý hoặc mọi biến thể chỉ tiêu.

## Kiểm chứng và bàn giao

**144/144 unit test đạt** (119 cũ + 25 mới). Test mới có ca số liệu, ca âm và
kiểm raw score bất biến, confidence=null, NUMERIC+PERSON_ROLE không thành một ý.
Giữ kết quả test lỗi trước sửa và ba ca âm bổ sung, không xóa dấu vết các lượt đó.

Audit tái hiện 313 quyết định, tái tính probability
từ vector/coefficients, sai lệch tối đa 7.77e-16;
kiểm hash nguồn và tham chiếu raw ranking. Replay quy tắc là bằng chứng tái tạo,
không thay review gold/ngữ nghĩa độc lập. Audit V4 trước đó vẫn cần chạy kèm.

```powershell
$env:PYTHONPATH=(Join-Path $PWD.Path 'backend')
$env:PYTHONUTF8='1'
python backend/scripts/audit_s5_intent_numeric.py
python backend/scripts/audit_s5_intent_reviewfix.py
python backend/scripts/report_s5_intent_numeric.py
$tests=(Get-ChildItem backend/tests/test_s5_intent_*.py).FullName
python -m pytest $tests -q -p no:cacheprovider
```

Dùng môi trường backend hoặc `requirements-s5-objectives-check.txt` để audit
offline; không cần weights/DB/API cho audit. File mới:
`backend/src/retrieval_orchestration/intent_numeric_requests.py`. Kết quả từng
câu ở `outputs/s5_intent_numeric_20261112/run01/results.json`; method.json giữ
nguồn trước đo. Giữ V3/V4 cùng audit và báo cáo lịch sử không đổi.

Chưa tích hợp consumer 04.2/router/Web Chat, chưa calibration. Ranh giới kế
hoạch lợi nhuận vẫn DRAFT; nếu ABC chưa xác định được doanh nghiệp thì consumer
vẫn cần hỏi lại phạm vi, dù ý định là NUMERIC. Không dùng điểm ENTITY_RELATION
để gắn confidence cho nhãn NUMERIC mới.
