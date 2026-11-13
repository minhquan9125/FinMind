# Bàn giao hiện tại S5-WBS04.1 — review vòng 2, 12/11/2026

Phụ trách: Hồ Phạm Đăng Nhân. Nhánh: `nhan-sprint-501`.
Đây là bản chờ review, chưa xác nhận hoàn thành tích hợp router/Web Chat.

## Phạm vi Nhân đã chốt lại

Theo yêu cầu của Nhân: chỉ bàn giao phần thư viện mẫu, vector hóa và đối chiếu
ý định thuộc S5-WBS03.1–03.3, S5-WBS04.1. Vòng sửa này tập trung vào
`intent_semantic_requests.py`, kiểm thử ngữ nghĩa và kết quả đối chiếu BGE-M3.
Consumer, ngưỡng, fallback và tích hợp router thuộc phần Huyền, loại khỏi phạm vi
nghiệm thu của Nhân. Các bản thử consumer/patch đã tạo trước đó chỉ là dấu vết
thử nghiệm, không phải yêu cầu Huyền áp dụng và không dùng để chốt Done cho Nhân.

## Gửi Hưng review

Đọc [báo cáo kiểm chứng vòng 2](S5-WBS04.1-news-mixed-results.md).
Nhờ kiểm tra:

1. Phân biệt đọc/độc, lương/lượng ở cả NUMERIC và giải thích diễn biến TREND.
2. Các cách hỏi CEO, người đứng đầu, tin gì mới và ghép NUMERIC + giải thích.
3. Tách nhãn đề xuất, bằng chứng quy tắc và điểm xếp hạng; ghi rõ ca chưa chắc chắn.
4. Tái tạo đối chiếu và bảo toàn các ca cũ của phần Nhân.

## Đã kiểm chứng

- 313 hàng hồi quy giữ nhãn V6, không đúng→sai; bộ 20 cũ vẫn 20/20.
- 32 probe bổ sung: 27/27 có gold đúng, 5/5 không ép nhãn đạt. Năm câu chưa có
  gold không tính là phân loại đúng; các tập cũ vẫn còn lỗi. Không phải test mù.
- Chạy lại riêng phần Nhân: **192/192 test đạt**, không lỗi hoặc skip, gồm 30 test
  mới cho ranh giới ngữ nghĩa. XML ở `outputs/s5_intent_review2_20261112/nhan-review-only.xml`.
  Audit tái tạo 345 quyết định đạt. Kết quả trước review ở
  `outputs/s5_intent_review2_20261112/nhan-pre-review-check.json`.
- Chưa hoàn tất mã hóa lại 56 query baseline trong phiên này: lần đầu vướng proxy,
  lần offline nạp model quá lâu nên đã dừng. Không tính là PASS; audit 345 quyết định
  dùng vector đã lưu. Bằng chứng BGE-M3 thật trước đây được giữ nguyên.
- Giữ BGE-M3/revision, classifier C=1, training, gold và raw ranking.
  Lớp quyết định trả evidence riêng với `confidence=null`.

Lưu ý: classifier vẫn đề xuất NUMERIC cho câu “Lợi nhuận FPT có độc lập…”.
Quy tắc không ép nhãn nữa; phần Nhân ghi nhận đây là ca chưa phân loại đúng.
Chưa được xem câu đó đã phân loại đúng hoặc đã sửa bất biến có dấu/không dấu.

Kết quả cuối: `outputs/s5_intent_review2_20261112/run03/`.
Module cần review cho task Nhân: `intent_semantic_requests.py`.
`IntentMatcher`/CLI vẫn trả cosine baseline. V7 là thử nghiệm offline, chưa thay
baseline hoặc chạy trong Web Chat. Điểm classifier chưa hiệu chỉnh không phải cosine.
Baseline có top-1 22/47; V7 đúng 41/47 trên bộ test gốc đã xem, còn 6 câu sai.
Không suy chất lượng chung từ riêng 27/27 probe bổ sung theo review.

Từ thư mục gốc, kiểm lại artifact đã lưu bằng:

```powershell
$env:PYTHONUTF8='1'
$env:OPENBLAS_NUM_THREADS='4'
.\backend\.venv\Scripts\python.exe backend/scripts/audit_s5_intent_review2.py
```

Chạy riêng 192 test thuộc phần Nhân:

```powershell
$env:PYTHONPATH='backend'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$tests = @(Get-ChildItem backend/tests/test_s5_intent_*.py | Where-Object { $_.Name -notin @('test_s5_intent_consumer_contract.py','test_s5_intent_handoff.py') } | ForEach-Object { $_.FullName })
.\backend\.venv\Scripts\python.exe -m pytest @tests -q -p no:cacheprovider
```

## Còn chờ nhóm

- Hưng review logic và cách tái tạo; chưa tự ghi là đã được duyệt.
- Giá hôm nay giữ NUMERIC theo schema, luồng hiện có phân giải QUOTE/PRICE.
  Khi tích hợp cần giữ luồng giá trước consumer tổng quát; mới kiểm offline, chưa lấy giá thật.
- Chưa calibration hoặc tích hợp 04.2/router/Web Chat. Không áp ngưỡng cosine
  0,65/0,08 lên xác suất chưa hiệu chỉnh; không gắn điểm nhãn cũ cho nhãn mới.
  MIXED không mặc định là BOTH. Task 01.2 vẫn tạm dừng theo yêu cầu Nhân.

Tra cứu task 03.1–03.3 tại [README](README.md), các mốc ở [history](history.md).
Các kết quả và hướng dẫn cũ nằm trong `archive/`; bản bàn giao dài trước dọn ở
[đây](archive/S5-WBS04.1-HANDOFF-before-cleanup.md).
