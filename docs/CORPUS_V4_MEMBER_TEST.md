# Chạy kiểm thử corpus-v4 trên máy thành viên

> Hướng dẫn chạy hiện tại: [CORPUS_V4_QUICK_START.md](CORPUS_V4_QUICK_START.md). Các mục ZIP/snapshot local dưới đây là lịch sử, không áp dụng cho reader nguồn Supabase mới. Trạng thái triển khai xem receipt deployment/activation và kiểm thử thực tế, không suy ra từ các ghi chú cũ bên dưới.

> Phương án mới nhất: docs/CORPUS_V4_REUSE_EXISTING_SOURCES.md — backend dùng lại payload gốc trên Supabase, chỉ bổ sung metadata lịch sử; không cần ZIP trên máy thành viên. Kế hoạch 676 bản đã bị thay thế và chưa được ghi DB.

> Cập nhật theo quyết định mới: nguồn sẽ được backend đọc theo phiên bản từ Supabase, không yêu cầu thành viên nhận ZIP hoặc cấu hình snapshot local. Các mục ZIP bên dưới là hướng dẫn cũ, chỉ giữ cho người chuẩn bị release kiểm tra offline. Xem docs/CORPUS_V4_SHARED_SOURCES.md cho phương án hiện tại. Chưa ghi nguồn chung, đăng ký hoặc kích hoạt v4; không bật cấu hình đề xuất trước khi được duyệt.

Corpus-v4 chưa được kích hoạt. Chỉ chuyển cấu hình sau khi người phụ trách xác nhận audit đạt, đăng ký corpus và duyệt chuyển default.

## 1. Nhận đúng code và artifact

Clone/pull commit bàn giao có reader snapshot, API corpus và script check_corpus_v4.py. Nhận file corpus-v4-artifacts.zip, giải nén tại gốc FinMind; giữ cấu trúc outputs/corpus-v4-clean-mapped-20261022. Gói không chứa .env, mật khẩu hoặc mô hình embedding.

Từ thư mục backend:

```powershell
npm run check:v4
```

Lệnh kiểm tra manifest, snapshot, 7.158 chunk và 72.096 row clean offline. Exit 2 với DATABASE_NOT_CHECKED là chưa kiểm tra DB, không phải nội dung snapshot sai. Thiếu artifact/hash sai sẽ báo lỗi và dừng.

## 2. Kiểm tra DB trước khi chạy

Cài .venv và backend/requirements.txt theo README; cấu hình DATABASE_URL do nhóm cấp trên máy mình. Không gửi .env vào Git hoặc chat.

```powershell
npm run check:v4 -- --database
```

Giao dịch chỉ đọc. INCOMPLETE_INGEST nghĩa là chưa đủ chunk; VECTOR_OR_SOURCE_FAILURE nghĩa là vector/locator/hash hoặc snapshot không khớp. Đọc outputs/corpus-v4-member-handoff-20261022/audit.json để biết chi tiết. Công cụ không tự sửa DB.

## 3. Cấu hình sau khi đã được duyệt

Lấy ID/hash từ runtime.env.proposed do công cụ tạo, không lấy ID từ Golden Set v2 hoặc ingest manifest. Đổi SOURCE_SNAPSHOT_PATH thành đường dẫn thực tế trên máy mình. Đường dẫn ví dụ C:/NhanhFrontend không dùng nguyên trên máy khác.

Ba biến phải cùng release: DEFAULT_CORPUS_VERSION_ID, DEFAULT_CORPUS_MANIFEST_SHA256, SOURCE_SNAPSHOT_PATH. Không chạy script sao chép đè toàn bộ .env.

```powershell
npm run check:v4 -- --database --runtime
npm run dev
```

Chế độ runtime yêu cầu registry FROZEN, index ACTIVE, đúng cấu hình/snapshot. Nếu lỗi thì chưa chạy kiểm thử nghiệm thu. Khởi động lại backend sau khi đổi cấu hình vì settings/snapshot có cache.

## 4. Test qua API thật

Mở http://127.0.0.1:8000/docs. Với POST /api/search, bỏ document_id nếu tìm toàn corpus và dùng corpus_version_id v4 đã đăng ký, query thực tế, top_k=5. Response phải trả đúng corpus/index ID. Nếu client cũ ghim v2 thì phải chọn đúng release trước.

- Q31–Q39: đối chiếu với các câu hỏi hiện có, nhưng không giữ ID chunk/index/evidence v2 làm gold v4. Nhãn gold v4 phải được rà riêng.
- FPT Q2/2026: tìm tiền và tương đương tiền, rồi RETAINED_EARNINGS (bsa90). Mở từng nguồn và so đúng giá trị. Việc tìm được không tự chứng minh đúng câu trả lời.
- Không xuất hiện “đơn vị chưa xác minh”; chỉ tiêu chưa được Excel duyệt vẫn không được gán đơn vị suy đoán. WORKBOOK_APPROVED không được coi là VERIFIED_SNAPSHOT.
- Tìm tin tức, phiên giá và chỉ số. Vector không thay phép tính đếm/trung bình/cực trị; không chấm những câu đó chỉ bằng top-k.
- Upload PDF/JSON và tìm trong file upload để kiểm tra hồi quy index riêng.
- Dùng một bản sao snapshot bị sửa để kiểm tra từ chối. Không sửa artifact gốc hoặc .env đang phục vụ thành viên khác.

Trước khi kết luận nghiệm thu, lưu request/response và corpus/index ID thực tế. HTTP 200 không đủ: nội dung và citation phải đúng nguồn. Không tắt hash/source fingerprint để ép kết quả.

## 5. Giới hạn bàn giao hiện tại

Gói artifact và test offline không thay cho audit DB đủ 7.158 vector, đăng ký/kích hoạt được duyệt và chạy API thật trên máy clone mới. Không tự động coi 61 row có mapping là toàn bộ 72.096 row đã xác minh đơn vị. Không xóa corpus cũ khi v4 hoạt động.
