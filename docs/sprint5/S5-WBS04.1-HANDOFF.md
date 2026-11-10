# Bàn giao review S5-WBS04.1 — 11/11/2026

Đã triển khai trả nhóm ý định gần nhất và điểm cosine, có output từ BGE-M3 thật.
Chưa có xác nhận review 04.1. Chất lượng top-1 còn thấp: **22/47 (46,81%)**;
nhãn đúng trong top-3: **41/47 (87,23%)**. Không đặt ngưỡng pass sau khi xem điểm,
không coi unit test qua là accuracy đạt và không đưa kết quả vào router/WebChat.

## File cần xem trước

- [Hợp đồng và cách chạy](S5-WBS04.1-intent-matching.md).
- [Toàn bộ 25 ca sai, metrics và giới hạn](S5-WBS04.1-baseline-results.md).
- `outputs/s5_wbs041_20261110/run01`: method đã chọn trước inference,
  snapshot test, kết quả từng câu và summary. Giữ nguyên run01 sau khi đo.
- `outputs/s5_wbs041_review_20261111`: test sau rà soát và kiểm chứng lại model thật.

Code chính: `intent_matching.py`; CLI câu hỏi đơn: `match_s5_intent.py`; CLI đánh
giá: `evaluate_s5_intent_matching.py`. Thư viện mẫu vẫn là artifact 03.3 đã review.
`component_intents` trong best_example mô tả câu mẫu, không khẳng định hệ thống đã
trích đúng thành phần ý định của query.

## Kiểm tra không cần model/DB

Giải nén đầy đủ gói và mở PowerShell tại thư mục chứa backend, docs và outputs.
Dùng Python 3.12 với NumPy 1.26.4, pytest 8.3.3, hoặc môi trường backend có sẵn.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r docs/sprint5/requirements-s5-library-check.txt
$env:PYTHONPATH=(Join-Path $PWD.Path 'backend')
.\.venv\Scripts\python.exe -m pytest backend/tests/test_s5_intent_matching.py backend/tests/test_s5_intent_evaluation.py backend/tests/test_s5_intent_library.py backend/tests/test_s5_intent_dataset.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe backend/scripts/build_s5_intent_library.py --verify-only
```

Kỳ vọng 54 passed và artifact READY 90 × 1024. Không cần Torch, model weights,
Gemini, database hoặc web server cho hai lệnh kiểm tra này sau khi cài dependency.

## Chạy bằng BGE-M3 thật

Cần môi trường backend đầy đủ và cache đúng full revision của artifact 03.3.
Không kèm weights hoặc .env trong gói. Dùng Python môi trường backend thay cho
môi trường chỉ cài NumPy/pytest phía trên. Thiết lập offline và CPU thread giống
hướng dẫn 04.1 nếu muốn tái tạo gần nhất lượt đo đã lưu.

```powershell
python backend/scripts/match_s5_intent.py --question "Tìm bài tin về việc bổ nhiệm TGĐ DGC trong tháng 09/2025."
python backend/scripts/evaluate_s5_intent_matching.py --output outputs/s5_wbs041_review_20261111/reviewer-run
python backend/scripts/audit_s5_intent_matching.py
```

Không dùng lại đường dẫn đã có. Đánh giá nhúng tạm câu test để làm query, không
thêm chúng vào thư viện 90 mẫu. Chín câu null không tính accuracy bảy lớp và chưa
có abstention/hỏi lại. Policy max-per-label giữ nguyên; chưa chỉnh theo ca sai.

## Nội dung đã sửa khi tự review

Kiểm chứng lại ngày 11/11 bằng model thật: cả 56 thứ hạng nhóm khớp run01;
tính cosine bằng biểu thức độc lập sai lệch tối đa `8,89e-16`. Ba câu kiểm tra
batch so với encode đơn lệch tối đa `1,16e-7`. Thư viện và run01 giữ nguyên checksum.
Chi tiết: `outputs/s5_wbs041_review_20261111/real-model-audit.json`.
Script audit dành riêng cho baseline run01 đã đóng băng; chạy lại sẽ ghi đè hai
file báo cáo audit trong thư mục review, không ghi đè run01.

- Chặn batch đầu vào không phải list/tuple để tránh nhầm key của dict hoặc thứ tự set.
- Gắn checksum manifest vào đúng artifact đã nạp và dừng nếu nguồn đổi khi đánh giá.
- Kiểm tra thứ tự query ↔ vector bằng test có vector khác nhau, không chỉ encoder
  giả trả cùng một vector cho mọi câu.
- Giữ nguyên dataset, vector thư viện, cosine/max policy và báo cáo run01.

Đề nghị reviewer tách kết luận chức năng/công thức/tính tái tạo với chất lượng
baseline. Các ca sai đã được báo đầy đủ; không sửa đáp án hoặc mẫu để tăng điểm
trên bộ test này. Chưa coi workflow ECC phía reviewer là đã hoàn tất.
