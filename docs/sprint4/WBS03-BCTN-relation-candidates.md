# WBS03 — Ứng viên quan hệ doanh nghiệp từ BCTN

Phạm vi: chỉ đọc chunk BCTN đã index, trích xuất ứng viên `PENDING` theo contract 2.1.0. Không OCR, chia chunk lại, gọi LLM, ghi PostgreSQL hay Neo4j. WBS06 quyết định `APPROVED` hoặc `REJECTED`.

## Luồng hiện có

1. `bctn_source.read_verified_bctn_chunks` lọc `ANNUAL_REPORT` theo `corpus_versions` → `corpus_documents` → `documents` → `text_chunks`, chỉ lấy chunk hiện hành của index trong corpus. Hàm dùng `resolve_shared_source` để dựng chữ từ snapshot trong `raw_payloads` và so `content_hash`. Caller phải mở transaction `READ ONLY`.
2. `db_adapter.document_envelope` đưa **toàn bộ chunk của một BCTN** sang một JSON contract 2.1.0. `document_version` là SHA256 của toàn snapshot nguồn đã pin, đúng quy tắc Hưng chốt ngày 29/10/2026; `source_view_sha256` của từng section được giữ trong `documents[0].source_sections`. UUID document/chunk, span, trang, nguồn và hash được giữ nguyên; không tạo bbox hay block ID giả.
3. `entities.normalize` trong runtime Hưng bàn giao tìm mention và chuẩn hóa alias theo `company.registry.json`. `relation_extractor.extract_candidates` tạo `OWNS_SHARES`, `HAS_SUBSIDIARY`, `HAS_ASSOCIATE`, `COOPERATES_WITH` ở trạng thái `PENDING`, giữ câu chứng minh, document ID và chunk ID. Quan hệ nêu rõ hai pháp nhân cần cả hai đã resolve; hợp tác được sắp hai đầu và gộp bằng chứng. Với mẫu “công ty con kiểm soát trực tiếp/gián tiếp Công ty X”, chủ thể có thể là doanh nghiệp phát hành BCTN **chỉ khi** `documents.company_id` khớp `companies`, symbol khớp locator/title và `company_name` khớp duy nhất một dòng registry verified. Đối tượng chưa có canonical ID vẫn được giữ như một ứng viên `unresolved` nếu tên pháp lý đủ cụ thể; WBS06 phải kiểm duyệt trước khi dùng. Ứng viên ngữ cảnh mang `attributes.inference_basis=document_issuer`. Các tên chung như “CÔNG TY CỔ PHẦN”, “Quỹ” và alias dùng như tính từ trong câu bị loại ở lớp extractor dù registry đánh dấu verified.
4. `contracts.validate_envelope` kiểm tra toàn bộ JSON đầu ra. Có thể dùng `backend/scripts/extract_bctn_relations.py` để chạy trên một envelope đã được kiểm chứng; chương trình không ghi đè file đã tồn tại.

## Chạy thử offline

Từ thư mục gốc FinMind, trong PowerShell. Lệnh đầu chỉ chạy test và mẫu CTG một chunk; lệnh cuối đọc DB trong transaction `READ ONLY` và tạo một file JSON cho mỗi BCTN trong thư mục `.tmp`:

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m unittest backend.tests.test_wbs03_relation_extractor backend.tests.test_wbs03_db_adapter -v
backend/.venv/Scripts/python.exe -X utf8 backend/scripts/extract_bctn_relations.py --input backend/tests/fixtures/wbs03_db_ctg_chunk.json --output backend/.tmp/wbs03-ctg-candidates.json
backend/.venv/Scripts/python.exe -X utf8 backend/scripts/extract_bctn_from_db.py --corpus-version-id a5338f75-5894-5b8a-bf94-0a6da7c26ced --output-dir backend/.tmp/wbs03-candidates
```

Mẫu CTG là **một chunk thật đã được Hưng kiểm chứng khi bàn giao**, nhưng là trang chữ ký không có phát biểu quan hệ; kết quả 0 ứng viên không đại diện cho cả BCTN. Unit test dùng câu tự tạo để kiểm hướng, tỷ lệ, thời gian, phủ định, dự kiến, tên không rõ và chống trùng. Có thể chạy lại rule trên envelope đã xác minh (không đọc DB) bằng `extract_bctn_relations.py --reextract --input ... --output ...`; input không bị sửa.

## Điều kiện còn phải chốt trước khi chạy toàn corpus

- Mẫu DB 2.1.0 Hưng gửi trước đây có `document_version` bằng hash của một section. Adapter hiện dùng hash snapshot chung theo xác nhận mới, nên mẫu cũ chỉ dùng để kiểm locator và text; không dùng để so nguyên JSON đầu ra.
- Kết nối VPS qua `127.0.0.1:15433/finmind` đã hoạt động ngày 29/10/2026. Đã đọc và xác minh 20 BCTN với 15.398 chunk hiện hành trong corpus frozen. JSON đầu ra chỉ là ứng viên để WBS06 review, không phải quan hệ đã được xác nhận. Chưa có nhãn gold để đo precision/recall. Hai BCTN CMG chưa resolve issuer vì tên `Tập đoàn Công nghệ CMC` trong `companies` chưa khớp duy nhất alias registry; không tự gán canonical ID.
- Tập BCTN index trong corpus v5 được dùng để thử theo thống nhất với Nhân; đây chưa phải danh sách chunk WBS01 được duyệt chính thức. Trước nghiệm thu, cần xác nhận phạm vi và kiểm tra bằng chứng ứng viên với người kiểm duyệt.

Mẫu contract/registry thuộc gói `BAN_GIAO_NHAN_WBS03_CONTRACT_2.1.0.zip` của Hưng. Các file runtime được giữ nguyên; phần adapter và extractor là code WBS03.

## Kết quả chạy thực tế ngày 29/10/2026

- Corpus `a5338f75-5894-5b8a-bf94-0a6da7c26ced` (`FROZEN`), index `bcc6251d-ba1b-51d9-8fd5-92eb893a9ff0`: 20 BCTN và 15.398 chunk hiện hành. Mọi chunk được dựng lại từ snapshot nguồn trong transaction chỉ đọc; 20 envelope hợp lệ, mọi `document_version` bằng `source_sha256` chung của snapshot.
- Bộ rule cuối tạo **1 ứng viên `PENDING`**: ELC BCTN 2024, `HAS_SUBSIDIARY` tới chuỗi “Công ty Cổ phần đầu tư Smortek (Lò công” ở chunk `331eb5e5-4661-5fae-a372-b0da0c9dc2fc`. ELC được resolve qua `documents.company_id` → `companies.company_name` → registry. Đối tượng **unresolved** và đoạn OCR có nhiễu; Huyền/WBS06 phải kiểm duyệt, không được publish như sự thật. JSON kiểm tra ở `backend/.tmp/wbs03-live-reviewed/` (không commit).
- Lượt rule trước có 2 ứng viên sai: “giữ vị thế tiên phong” và “sở hữu lợi thế cạnh tranh”, cùng một ca nhận chữ chung “Quỹ” như tên pháp nhân. Các ca này đã được chặn bằng rule và test; **không tính** vào kết quả cuối.
- Kết quả chỉ 1 ứng viên trên 15.398 chunk là dấu hiệu cần audit các ca bỏ sót, nhưng **chưa thể tính recall** hay nghiệm thu độ chính xác/độ bao phủ khi chưa có tập gold được duyệt. Vướng mắc cụ thể: OCR làm méo tên và cắt câu qua ranh giới chunk; một số tên công ty con chưa có canonical ID trong registry; 2 BCTN CMG chưa nối được issuer “Tập đoàn Công nghệ CMC” với registry. Không tự sửa registry, OCR hoặc contract của người khác trong WBS03.
