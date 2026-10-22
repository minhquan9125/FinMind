# Thành viên kiểm thử corpus-v4

Release đã được đăng ký FROZEN và index ACTIVE ngày 22/10/2026. Bản triển khai local đã qua kiểm tra nguồn đầy đủ, API thật và 190 test hồi quy. Kết quả chi tiết: [báo cáo kiểm thử](../outputs/corpus-v4-reuse-audit-20261022/Ket_qua_kiem_thu.md).

Backend tìm vector và đọc đúng phiên bản nguồn trên Supabase. Không cần ZIP hoặc snapshot local. Không thêm `chunk_text` vào DB.

Pull code bàn giao, cài backend theo README và nhận DATABASE_URL riêng từ nhóm. Sau khi release được xác nhận ACTIVE, đặt trong `backend/.env`:

```dotenv
DEFAULT_CORPUS_VERSION_ID=33d33730-0f0a-5274-a7f8-8d32a6be07e8
DEFAULT_CORPUS_MANIFEST_SHA256=73f2e87a1cf5cd50a8fec3ee825e8bad211070c9e994b37c45a61ee86c6723c1
SOURCE_READ_BACKEND=supabase
SOURCE_SNAPSHOT_PATH=
```

Giữ nguyên kết nối và các cấu hình khác. Model phải khớp `BAAI/bge-m3@5617a9f61b02`. CPU vẫn truy vấn được; máy chưa có model cần tải lần đầu.

Từ thư mục `backend` chạy:

```powershell
npm run check:sources
npm run dev
```

Kiểm tra nguồn chỉ đọc DB, không tải model. Kết quả đúng: `status: PASS`, `checks: 7158`, corpus ID ở trên và index `e3725b7d-1a39-5196-b000-3496dbab388f`.

Mở http://127.0.0.1:8000/docs, chọn `POST /api/search`, Try it out, gửi:

```json
{"query":"FPT quý 2 năm 2026 tiền và tương đương tiền","top_k":5}
```

Bỏ `document_id` khi tìm toàn corpus. Response phải có đúng corpus/index ID và các kết quả có `chunk_id`, `document_id`, `text`. Dùng document ID để gọi `GET /api/documents/{document_id}/chunks` rồi đối chiếu kỳ báo cáo, nội dung và đoạn được dẫn.

Test thêm Q31–Q39, `bsa90`, tin tức, giá, chỉ số và hồ sơ doanh nghiệp. HTTP 200 không tự chứng minh đáp án đúng. Vector không thay phép tính đếm, tổng, trung bình hoặc cực trị; phép tính giá phải dùng reader lịch sử giới hạn theo corpus. Golden40 V6 còn là đề xuất v2, cần rà evidence v4 trước khi chấm benchmark. Không tự gán đơn vị cho chỉ tiêu chưa xác minh.

`CORPUS_NOT_READY`: chưa sẵn sàng. `SHARED_SOURCE_MISSING`: thiếu nguồn chung. `SHARED_SOURCE_CORRUPTED` hoặc `SOURCE_CHANGED`: nguồn không khớp hash. Không bỏ kiểm tra hash để ép chạy. Khởi động lại backend sau khi đổi `.env`.

Bằng chứng từng bước khi đã hoàn tất: `outputs/corpus-v4-reuse-audit-20261022/deployment.json`, `activation.json`, `shared-source-check.json`, `http-smoke.json`. Không coi file còn thiếu là PASS. Upload JSON/PDF cần kiểm tra riêng; smoke nguồn chung không thay benchmark hay kiểm thử toàn dự án.
