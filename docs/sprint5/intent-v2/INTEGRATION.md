# Bàn giao intent v2 trên backup-demo — 14/11/2026

Nhánh: `nhan-intent-v2-integration`.
Nền: `backup-demo` tại `4544ba04350246d723919d0e5fb51f9e30258539`.
Nguồn đã review: `nhan-sprint-501` tại `f415f448674022663c6e277ca8e1042d5d476d26`.

Đây là gói phân loại để Hưng tích hợp vào Chat. Code chạy Chat, router, contract
fallback, truy vấn dữ liệu và frontend của backup-demo được giữ nguyên. Nhánh
gốc của Nhân và các bản nháp đang sửa không bị thay đổi. Chưa merge vào backup-demo.

## Những gì được chuyển

- API `classify_intent`, luật r2, validator, 183 test v2 và các runner tái tạo.
- Schema 11 nhãn, 470 mẫu LIBRARY, 110 câu DEVELOPMENT, vector BGE-M3 và
  classifier đã review. Không fit lại hoặc sửa gold.
- Bốn phụ thuộc: `intent_library`, `intent_matching`, `intent_scoring`,
  `intent_experiment`. Module cuối là phụ thuộc import sẵn có của scorer;
  hàm chọn route thử nghiệm trong đó không được API v2 gọi để định tuyến.
- Bằng chứng cuối, cache vector tách biệt và gold hồi quy cũ cần cho audit.
  Không mang các lượt chạy trung gian, ZIP, model BGE gốc hay môi trường máy.

Hai file từng xung đột `documents/repository.py`, `vector_retrieval/backend.py`
giữ đúng phiên bản backup-demo. Toàn bộ thay đổi so với nền là file bổ sung,
không lấy lịch sử merge/code cũ của nhánh Nhân.

## Kiểm chứng trên nền mới

| Phép kiểm | Kết quả |
|---|---|
| Import API cùng các phụ thuộc | Đạt |
| Unit/contract v2, NumPy 1.26.4 | 183/183 |
| Unit/contract v2, NumPy 2.1.3 | 183/183 |
| Audit trên NumPy 2.1.3 | 470 mẫu + 110 development + 47 hồi quy đạt |
| Biến thể kiểm luật, tái dùng vector gốc | 2.165/2.165 |
| API BGE-M3 thật, NumPy 2.1.3 | 33/33 ca, đủ nhãn/thành phần/trạng thái kỳ vọng |
| Câu kiểm thêm từ review, BGE-M3 thật | 5/5 đúng nhãn và PROPOSED |
| Checksum đầu vào/source đã đóng băng | 25 kiểm tra đạt |

NumPy 2.1.3 được nạp từ thư mục kiểm thử riêng, dùng lại các dependency khác của
venv backend (Torch 2.6.0, sentence-transformers 3.1.1). Đây là kiểm tương thích
NumPy theo requirements `>=2.1`, chưa phải cài mới toàn bộ requirements.

Ba câu “tình hình tài chính MBB/FPT/VCB” đều ra ANALYSIS bằng
CLASSIFIER_PROPOSAL, status PROPOSED, vẫn ghi một request chưa có luật nhận diện.
Không thêm luật riêng theo mã. “phân tích FPT MBB VCB” giữ một ý ANALYSIS;
“so sánh doanh thu FPT và CMG” là NUMERIC. Tách mã và thao tác so sánh thuộc tầng slot.

Đây là kiểm chuyển nền và hồi quy, không phải bộ kín độc lập, không phải E2E
Chat hoặc nghiệm thu latency. Chưa suy ra độ chính xác trên câu mới. Cần nhóm
review và bộ kín trước khi chốt nghiệm thu chất lượng.

## Gọi API và chạy lại

Dùng Python của môi trường backend đã cài dependencies; từ thư mục repo:

```python
from src.documents.embeddings import get_embedding_service
from src.retrieval_orchestration.intent_v2_classifier import classify_intent

embedder = get_embedding_service()  # dùng lại singleton, warmup trước khi nhận chat
result = classify_intent("Chủ tịch HĐQT FPT là ai?", embedder=embedder)
```

Giữ nguyên policy `intent-request-objectives-v2-11-r2`, 11 nhãn và confidence=null.
Consumer kiểm status, unresolved_requests và cờ hạn chế; PROPOSED không đồng
nghĩa SEARCH, MIXED không mặc định BOTH. API không tự gọi tìm kiếm hoặc Chat.

```powershell
$env:PYTHONPATH = 'backend'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$tests = @(rg --files backend/tests -g 'test_s5_intent_v2_*.py')
backend/.venv/Scripts/python.exe -m pytest @tests -q -p no:cacheprovider
backend/.venv/Scripts/python.exe backend/scripts/check_s5_intent_v2_fixes.py --output backend/.tmp/recheck-audit
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
backend/.venv/Scripts/python.exe backend/scripts/run_s5_intent_v2_functional_probes.py --output backend/.tmp/recheck-real
backend/.venv/Scripts/python.exe backend/scripts/run_s5_intent_v2_functional_probes.py --corpus docs/sprint5/intent-v2/integration-probes.jsonl --output backend/.tmp/recheck-review
```

Các thư mục đầu ra phải chưa tồn tại. Lượt BGE thật cần model đúng revision đã
có trong cache; thời gian nạp lạnh tách khỏi thời gian suy luận. Phiên bản và
bằng chứng gọn của đợt chuyển nền nằm tại
`outputs/s5_intent_integration_20261114/verification.json`.
