# S5-WBS04.1 — Sửa mục tiêu bài tin và tách nhiều ý, 12/11/2026

Ba lỗi NV-13/NV-19/NV-20 đã được sửa ở lớp quyết định offline V6
(`intent-request-objectives-v4`). Không thay BGE-M3, classifier C=1,
training, nhãn chuẩn, raw ranking hoặc ngưỡng 0,65/0,08 của Huyền.

## Nguyên nhân và thay đổi

- NV-13: mục tiêu là tìm bài tin; thêm nhận diện thao tác trên bài tin
  ở đầu yêu cầu. Câu lấy số từ bài đã chỉ định không tự thành NEWS.
- NV-19: đã tách đúng nhưng điều kiện ghép xác suất không nhận hai ý.
  Nhận diện rõ NUMERIC và NEWS ở hai phần để đề xuất MIXED. Không nới
  điều kiện ghép xác suất chưa hiệu chỉnh cho mọi câu.
- NV-20: thiếu động từ Đọc ở bước tách nên luật CEO ghi đè MIXED đúng.
  Tách vế Đọc giá trị khi có hành động độc lập ở vế kế; danh sách chỉ
  tiêu/mảng AI và cloud/kỳ năm vẫn là một yêu cầu.

Không có luật theo mã câu hoặc tên doanh nghiệp. V6 nằm trong module
riêng để giữ source/checksum và cách tái tạo kết quả V3–V5.

## Hồi quy 313 hàng đã xem

| Bộ | Có nhãn | Trước sửa | Sau sửa |
|---|---:|---:|---:|
| controls | 32 | 32 | 32 |
| development | 84 | 70 | 70 |
| known_diagnostic | 8 | 6 | 6 |
| previous_check | 28 | 24 | 24 |
| regression | 47 | 41 | 41 |
| previous_new_check | 42 | 39 | 39 |
| previous_final_check | 28 | 26 | 28 |
| review_probes | 15 | 15 | 15 |
| additional_checks | 20 | 17 | 20 |

Sửa đúng thêm: previous_final_check/FINAL-MIXED-2-DPM, previous_final_check/FINAL-MIXED-2-VRE, additional_checks/NV-13, additional_checks/NV-19, additional_checks/NV-20. Đang đúng thành sai: **0**.
313 hàng gồm 9 câu không có nhãn gold, không tính chúng vào accuracy.
**20 câu bổ sung nay là hồi quy đã xem; không gọi kết quả này là test mù**
hoặc bằng chứng mọi câu mới đều đúng. Còn lỗi trên các tập cũ:

| Bộ | Mã còn sai |
|---|---|
| development | DEV-NUMERIC-2-TCB, DEV-REPORT_CONTENT-2-VCB, DEV-REPORT_CONTENT-2-MBB, DEV-NEWS-1-TCB, DEV-NEWS-1-FPT, DEV-TREND-3-VCB, DEV-TREND-3-TCB, DEV-TREND-3-FPT, DEV-MIXED-1-TCB, DEV-MIXED-2-VCB, DEV-MIXED-2-TCB, DEV-MIXED-2-MBB, DEV-MIXED-2-FPT, DEV-MIXED-3-MBB |
| known_diagnostic | KNOWN-07, KNOWN-08 |
| previous_check | LATER-REPORT_CONTENT-2-DGC, LATER-REPORT_CONTENT-2-PNJ, LATER-NEWS-2-DGC, LATER-MIXED-2-PNJ |
| regression | S5-T-021, S5-T-027, S5-T-037, S5-T-039, S5-T-041, S5-T-042 |
| previous_new_check | NEW-NEWS-3-DBC, NEW-ENTITY_RELATION-2-VHC, NEW-ENTITY_RELATION-2-DBC |

## Kiểm chứng

- Test trước sửa: 9 fail, 9 pass; sau sửa 18 ca mới qua.
- Toàn bộ **162/162 unit test ý định Sprint 5 đạt**; không phải suite toàn ứng dụng.
- Lượt green riêng có cảnh báo Windows ở bước lấy thông tin máy khi xuất
  JUnit. Lượt toàn bộ chạy ngoài sandbox kết thúc sạch, exit 0.
- Audit tái tạo 313 quyết định, tính lại softmax từ vector/head;
  sai lệch probability lớn nhất 7.77e-16.
- Giữ nguyên raw ranking qua tham chiếu; không refit. Chỉ vector hóa hai
  đoạn mới tách bằng BGE-M3 cùng revision, không đưa câu test vào training.
- Unit test kiểm ca âm, hai yêu cầu cùng NEWS, raw score bất biến và
  confidence=null. Replay luật không thay thế review nhãn độc lập.

## Chạy lại và review

Từ thư mục gốc, dùng Python trong backend/.venv. Runner cố ý từ chối
ghi đè run01; kiểm lại bản đã bàn giao bằng hai lệnh:

```powershell
$env:PYTHONUTF8='1'
$env:OPENBLAS_NUM_THREADS='4'
.\backend\.venv\Scripts\python.exe backend/scripts/audit_s5_intent_news.py
.\backend\.venv\Scripts\python.exe backend/scripts/report_s5_intent_news.py
```

Kết quả từng câu/vector/checksum: outputs/s5_intent_news_20261112/run01.
Test: backend/tests/test_s5_intent_news_requests.py và các test_s5_intent_*.py.
Runner: backend/scripts/run_s5_intent_news.py (thư mục đầu ra mới trong checkout
tái tạo riêng, model BGE-M3 cùng revision đã có trong cache).

Hưng review ranh giới tìm bài/lấy số từ bài, tách câu và bảo toàn kết quả cũ.
Huyền review hợp đồng đầu ra trước khi tích hợp. resolution là evidence,
confidence=null; điểm classifier vẫn chưa hiệu chỉnh. Không đưa qua ngưỡng
cosine và không gắn điểm nhãn cũ cho nhãn mới. MIXED không mặc định BOTH.
Chưa calibration, chưa nối consumer/router/Web Chat; ranh giới kế hoạch
lợi nhuận vẫn cần nhóm xác nhận. S5-WBS01.2 vẫn tạm dừng theo yêu cầu Nhân.
