# Chuẩn bị task người – chức vụ – doanh nghiệp: bước 1 và 2

Đã rà soát repo và tạo gói chuẩn bị tại `outputs/person-role-step1-2-20261028/`:

- `Buoc_1_contract.md`: contract nào đã có, phần không đúng phạm vi, checklist thiếu và đề xuất fields/rules chức vụ/trạng thái/thời gian/provenance. Chưa coi là WBS01 đã duyệt.
- `Buoc_2_bo_mau.md`: 21 ca từ 21 chunk nguồn thật, kỳ vọng review sơ bộ, gồm cả ca âm tính và ca mơ hồ.
- `real_source_samples.json`: text, ID, hash, locator, PDF page, evidence offsets và kỳ vọng sơ bộ cho thành viên triển khai.
- `source_candidates.json`: 724 chunk ứng viên tìm bằng từ khóa; không phải 724 quan hệ đúng.
- `validation.json`: kiểm tra tính toàn vẹn bộ mẫu, không phải kết quả chạy extractor.

Đã kiểm tra digest manifest corpus và SHA-256 text của từng chunk. Lần này lấy từ manifest đóng băng cục bộ vì PostgreSQL local không mở cổng; chưa replay nguồn trực tiếp trên database hoặc kiểm thử VPS. Không gọi LLM/API AI, không ghi database, không sửa pipeline/graph runtime.

Chưa thấy contract WBS01 và output NER WBS02 thực cho quan hệ nhân sự trong checkout này. Bộ mẫu giữ `wbs01_approved=false`, `wbs02_output=false`, `publish_allowed=false`; person/role canonical IDs chưa resolve để NULL, không tạo ID giả. Company IDs trong mẫu lấy từ bản danh mục công ty đã lưu, chưa phải chứng cứ WBS01 signoff.

Còn thiếu ca đề cử một người cụ thể chỉ là ứng viên và cặp nguồn mâu thuẫn đã xác minh cùng người/tổ chức/chức vụ/thời điểm. Mẫu quy trình đề cử là ca âm tính, không bù vào coverage dương tính. Các đoạn nhiều công ty ngoài 10 mã chỉ dùng để test không nối nhầm tổ chức, không đưa quan hệ đó lên graph production.

Để tái tạo gói mẫu (Python với dependencies dự án):

```powershell
python backend/scripts/prepare_person_role_source_samples.py --offline-manifest
python backend/scripts/build_person_role_preparation_pack.py
```

Bước tiếp theo sau chuẩn bị là nhận/đối chiếu WBS01 và NER WBS02 thật rồi triển khai bộ trích xuất, review, và nghiệm thu. Không đánh dấu toàn bộ task hoàn thành chỉ từ bộ mẫu này.
