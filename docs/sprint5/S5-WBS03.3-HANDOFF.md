# Bàn giao review S5-WBS03.3

Gói review gồm code tạo/đọc/kiểm tra thư viện, test, bộ dữ liệu đã được duyệt,
artifact thật 90 × 1024 và báo cáo kiểm tra. Không kèm model weights, cấu hình
`.env`, database hoặc cache. Nội dung chưa được reviewer nghiệm thu 03.3.

## Kiểm tra mà không nạp model

Giải nén đầy đủ ZIP và mở PowerShell ở thư mục chứa `backend`, `docs`, `outputs`.
Môi trường đã kiểm tra: Python 3.12.10, NumPy 1.26.4, pytest 8.3.3.

Nếu chưa có môi trường phù hợp, có thể tạo riêng:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r docs/sprint5/requirements-s5-library-check.txt
```

Sau đó chạy:

```powershell
.\.venv\Scripts\python.exe backend/scripts/build_s5_intent_library.py --verify-only
$env:PYTHONPATH=(Join-Path $PWD.Path 'backend')
.\.venv\Scripts\python.exe -m pytest backend/tests/test_s5_intent_library.py backend/tests/test_s5_intent_dataset.py -q -p no:cacheprovider
```

Có thể thay đường dẫn Python bằng môi trường của máy đang có NumPy và pytest.
Kỳ vọng: READY, shape [90, 1024], và `28 passed`. Không cần Torch/Transformers,
DB, Neo4j hoặc mạng cho lượt đọc artifact và chạy test này (sau khi đã có dependency).
Các test dùng encoder giả để thử lỗi, không tạo vector giả thay artifact thật.

## Bằng chứng model thật và tái tạo

- `outputs/s5_wbs033_20261110/intent-library-v1/manifest.json` ghi model BAAI/bge-m3,
  full revision, phiên bản môi trường, thứ tự ID và checksum.
- `outputs/s5_wbs033_20261110/verification.json` ghi kết quả đọc toàn bộ vector và
  tạo lại ba câu bằng model thật: sai lệch tối đa khoảng 7.8e-8, dung sai 1e-5.
- `outputs/s5_wbs033_20261110/pre-review-tests.xml` ghi 28 test dữ liệu/artifact.

Muốn tạo lại bằng BGE-M3 thật, dùng môi trường backend đủ dependency và model
cache đúng revision. Làm theo [hướng dẫn 03.3](S5-WBS03.3-vector-library.md), dùng
thư mục output mới. Artifact có thể kiểm tra độc lập; việc tái tạo model phụ thuộc
model cache và môi trường, không tự phát sinh khi chỉ giải nén ZIP.

Không đưa test.jsonl vào thư viện vector. Chưa có điểm accuracy, chưa thực hiện
04.1 và chưa nối WebChat/router. Review này xác nhận tạo/lưu/đọc lại vector và
metadata; không coi kết quả test dữ liệu là nghiệm thu chất lượng phân loại.
