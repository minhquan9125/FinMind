# Bàn giao S5-WBS03.2 — draft3

Phụ trách: Hồ Phạm Đăng Nhân. Nội dung draft3 đã được Hưng xác nhận đạt review,
theo phản hồi Nhân chuyển lại. Nhân đã xác nhận bảng nhãn 03.1 được nhóm duyệt.
Bộ 03.2 sẵn sàng chuyển sang 03.3; tên người xác nhận sẽ do Nhân bổ sung.

## Nội dung gói bàn giao

- `docs/sprint5/intent-dataset-v1/library.jsonl`: 90 câu mẫu từ 30 câu gốc, chỉ bộ này dùng để tạo thư viện vector sau khi chốt.
- `docs/sprint5/intent-dataset-v1/test.jsonl`: 56 câu kiểm thử; không đưa vào thư viện embedding.
- `docs/sprint5/intent-dataset-v1/manifest.json`: checksum, phiên bản và trạng thái review/xác nhận.
- `docs/sprint5/intent-labels.v1.json`: định nghĩa nhãn được pin checksum.
- `docs/sprint5/S5-WBS03.1-intent-labels.md`: giải thích bảng nhãn.
- `docs/sprint5/S5-WBS03.2-samples-and-tests.md`: toàn bộ mẫu/test để đọc và review.
- `backend/scripts/validate_s5_intent_dataset.py`: validator offline, chỉ dùng thư viện chuẩn Python.
- `backend/tests/test_s5_intent_dataset.py`: 14 bài kiểm tra, cần pytest.
- `.gitattributes`: cố định LF cho các file dữ liệu có checksum.

Cũng có thể lấy validator/test từ [commit bd747663](https://github.com/minhquan9125/FinMind/commit/bd747663)
sau khi commit được push. Gói ZIP có sẵn hai file, không cần chờ remote để chạy lại.

## Chạy lại trên máy nhận

Giải nén toàn bộ ZIP, giữ nguyên cấu trúc thư mục. Mở PowerShell tại thư mục gốc
của gói, nơi có `backend` và `docs`. Không cần backend đang chạy, DB, Neo4j, Gemini,
Torch hay model embedding. Môi trường đã dùng kiểm tra: Python 3.12.10, pytest 8.3.3.

Nếu đã có Python 3.12 và pytest, chạy trực tiếp:

```powershell
python backend/scripts/validate_s5_intent_dataset.py
python -m pytest backend/tests/test_s5_intent_dataset.py -q -p no:cacheprovider
```

Nếu cần môi trường riêng trên Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install pytest==8.3.3
.\.venv\Scripts\python.exe backend/scripts/validate_s5_intent_dataset.py
.\.venv\Scripts\python.exe -m pytest backend/tests/test_s5_intent_dataset.py -q -p no:cacheprovider
```

Kỳ vọng: validator trả `valid: true`, số câu 90/56; pytest trả `14 passed`.
Đây là kiểm tra dữ liệu và công cụ kiểm tra, không phải 14 ca chứng minh mô hình
phân loại đúng. Không thay file dữ liệu hoặc xuống dòng trước khi kiểm checksum.

## Điều kiện chuyển 03.3

Review nội dung 03.2: đạt. Xác nhận bảng nhãn 03.1 của nhóm: Nhân xác nhận đã duyệt.
Nhân bổ sung tên người xác nhận vào hồ sơ; không tự gán Hưng là người duyệt bảng nhãn.
Nếu chỉ cập nhật metadata review trong JSON nhãn, cần cập nhật pin checksum tương
ứng ở manifest; nếu thay quy tắc nhãn, phải rà lại những câu chịu ảnh hưởng.

03.3 dùng `library.jsonl` để tạo vector và lưu model/revision/version thư viện.
Chưa tạo vector hoặc thay router trong gói bàn giao này.
