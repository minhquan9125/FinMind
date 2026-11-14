# Sprint 3: ma trận bảo vệ API theo vai trò

Áp dụng cho router FastAPI hiện có. Tất cả endpoint được bảo vệ nhận `Authorization: Bearer <access JWT>`; thiếu hoặc sai token trả `401`, tài khoản không hoạt động trả `401`, sai vai trò trả `403`. Backend đọc vai trò hiện tại từ `public.user_roles` và `public.roles` mỗi lần gọi. Vai trò trong JWT chỉ là thông tin hiển thị, không quyết định quyền. Nếu database không đọc được, yêu cầu không được cho qua.

Vai trò: `RESEARCHER` (R), `FINANCIAL_ANALYST` (F), `DATA_ENGINEER` (D), `EVALUATOR` (E), `ADMINISTRATOR` (A). Một tài khoản có thể có nhiều vai trò; chỉ cần một vai trò được phép.

| Nhóm | API đã triển khai | Vai trò được phép | Trạng thái |
| --- | --- | --- | --- |
| Tài khoản | `POST /api/v1/auth/register`, `/login`, `/google`, `/password/forgot`, `/password/reset` | Công khai; reset cần mã đặt lại hợp lệ | Có |
| Phiên | `POST /api/v1/auth/refresh`, `/logout` | Sở hữu refresh token hợp lệ; logout thu hồi token tương ứng | Có |
| Nguồn dữ liệu, tài liệu | `POST /api/documents`, `/json`, `/import-symbol/{symbol}` | D, A | Có |
| Corpus: đọc nội dung đã nạp | `GET /api/documents/{document_id}/chunks`, `/vocab` | R, F, D, E, A | Có |
| Truy vấn vector | `POST /api/search` | R, F, E, A | Có |
| Dữ liệu thị trường: đọc | `GET /api/market-data/stocks/{symbol}/ohlcv`, `/indices/{symbol}/ohlcv`, `/news`, `/companies/{symbol}/news`, `/live/status` | R, F, D, E, A | Có |
| Dữ liệu thị trường: theo dõi | `PUT`, `DELETE /api/market-data/live/viewers/{viewer_id}` | R, F, D, E, A | Có |
| Nguồn dữ liệu: cập nhật | `POST /api/market-data/stocks/{symbol}/refresh`, `/stocks/{symbol}/history`, `/companies/{symbol}/news/refresh` | D, A | Có |

`GET /` và `GET /api/health` vẫn công khai để kiểm tra trạng thái. Các API tài khoản dùng mật khẩu, Google credential, mã đặt lại hoặc refresh token riêng nên không yêu cầu access JWT.

## API trong đặc tả nhưng chưa có router

Các đường dẫn dưới đây nằm trong `API_SPECIFICATION.md`, **chưa được triển khai** trong `backend/src/main.py`; vì thế chưa thể xác nhận đã có bảo vệ hoặc test HTTP cho chúng. Khi tạo router, phải gắn dependency vai trò tương ứng và thêm test gọi trực tiếp bằng tài khoản sai vai trò trước khi nghiệm thu.

| Nhóm | API dự kiến | Vai trò cần áp dụng |
| --- | --- | --- |
| Tài khoản | `GET /api/v1/auth/me` | Chủ tài khoản đã xác thực |
| Nguồn | `GET`, `POST /api/v1/admin/sources`; `PATCH /api/v1/admin/sources/{source_id}`; `POST /api/v1/admin/ingest/jobs`; `GET /api/v1/admin/quarantine`; `POST /api/v1/admin/quarantine/{record_id}/review` | D, A |
| Corpus | `GET /api/v1/admin/corpus/versions` | D, E, A |
| Corpus | `POST /api/v1/admin/corpus/versions/freeze` | A |
| Truy vấn | `POST /api/v1/copilot/query`, `/retrieval/structured`, `/retrieval/vector`, `/retrieval/graph`, `/retrieval/hybrid`; `GET /api/v1/copilot/history`, `/api/v1/evidence/{evidence_id}` | R, F, E, A; lịch sử chỉ của chính tài khoản |
| Đánh giá | `GET /api/v1/evaluation/golden-set`, `/runs/{run_id}/metrics` | E, A |
| Đánh giá | `POST /api/v1/evaluation/runs` | E, A |

Các lệnh CLI như `backend/scripts/freeze_corpus.py` chạy ngoài FastAPI nên không được lớp RBAC HTTP này bảo vệ; chỉ cấp quyền chạy script cho người vận hành có quyền phù hợp.

## Kiểm chứng

`backend/tests/test_api_roles.py` gọi trực tiếp từng route đã bảo vệ: thiếu/sai token bị `401`, `RESEARCHER` gọi từng API ghi bị `403`, JWT giả nhận vai trò cao hơn database vẫn bị `403`, tài khoản bị khóa và token reset bị `401`. Test API chức năng chạy với principal giả lập có quyền phù hợp để vẫn kiểm tra logic xử lý. Chạy từ gốc repo với `PYTHONPATH` bao gồm gốc repo và `backend`.
