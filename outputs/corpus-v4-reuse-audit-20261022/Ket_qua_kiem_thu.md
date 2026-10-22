# Kết quả triển khai và kiểm thử corpus-v4

Ngày 22/10/2026. Đã triển khai nguồn dùng chung, đăng ký v4, đổi cấu hình mặc định trên máy này và thử API thật. Không cần ZIP/snapshot local trên máy thành viên.

| Nội dung kiểm tra | Kết quả |
| --- | --- |
| Vector và locator trên Supabase | Đủ 7.158/7.158; đúng hash, chiều 1.024 và chuẩn hóa vector; không thiếu tài liệu |
| Đọc lại nội dung từ nguồn Supabase | PASS 7.158/7.158; không gặp SOURCE_CHANGED |
| Phạm vi v4 | 675 tài liệu; membership 72.096 dòng tài chính và 737 phiên giá |
| Trạng thái | Corpus FROZEN; index ACTIVE; default local đã chuyển v4 |
| Bộ test nguồn, tài chính, upload, API và lọc truy vấn | 190 test PASS; còn cảnh báo deprecation thư viện, không có test thất bại |
| API thật dùng model BGE-M3 và DB thật | 40 câu + 3 truy vấn giá/chỉ số/hồ sơ: 43 request HTTP 200; Q40 trả tập rỗng |
| Q31–Q39 | 12/12 dòng evidence đúng observation ID, đúng kỳ và đúng cách hiển thị giá trị của release; Q39 có cả Q1 và Q2 |
| Mở lại nguồn Q31 | Đọc được 10 chunk của đúng tài liệu; đoạn từ tìm kiếm khớp đoạn mở lại |
| FPT 2024 và Q2/2026 qua reader tài chính | Mỗi kỳ đọc đúng một bản clean trong corpus, mỗi kỳ 160 dòng |
| Giá VCB ngày 15/04/2026 | Lấy close lịch sử 59,46, price_scale=1.000 từ payload đã ghim |

## Đã sửa gì để tránh lặp lỗi thành viên gặp?

- Backend dùng locator/index để đọc đúng phiên bản nguồn gốc đã ghim trên Supabase. Không lấy nguồn live mới nhất để dựng đoạn của vector cũ. Vẫn kiểm tra hash nguồn, fingerprint phần báo cáo, membership dòng và hash chunk.
- Một metadata root dùng lại 43 payload gốc và giữ metadata còn thiếu. Không ghi 676 bản sao nguồn, không thêm chunk_text hay bảng/cột mới. Các bảng membership chỉ lưu liên kết và hash theo corpus.
- Câu tài chính có công ty/kỳ rõ ràng được lọc đúng phạm vi đó trước khi xếp hạng vector. Nhãn chỉ tiêu từ danh mục nguồn được dùng để lấy đúng các dòng phù hợp; alias tỷ suất/biên lợi nhuận được kiểm tra để tránh nhầm lợi nhuận gộp và biên lợi nhuận gộp.
- Truy vấn vẫn tạo query vector và xếp hạng theo độ tương đồng trong tập ứng viên. Cách này là vector có bộ lọc; cần ghi rõ khi so với baseline vector thuần.
- Crawler mới dùng payload ID theo nội dung, tránh ghi đè payload lịch sử. Chưa chạy lại crawler toàn bộ trong lần kiểm thử này.
- Đã cô lập cấu hình của test dùng DB giả lập khỏi .env thật; không tắt kiểm tra hash để làm test qua.

## Phạm vi chưa thể gọi là “40 đáp án đã chứng nhận đúng”

HTTP 200 và hash đúng xác nhận luồng truy vấn/đọc nguồn. Các câu cần tính toán, xác minh đơn vị, từ chối trả lời hoặc citation đúng trang PDF vẫn cần chấm theo loại câu:

- Q21–Q29 yêu cầu chứng cứ từ đúng PDF: chunk clean không thay cho bằng chứng đúng trang/cột PDF đã chốt. Kiểm thử này chưa chứng nhận citation PDF cho nhóm đó.
- Đơn vị/phạm vi chưa xác minh phải được trả lời là chưa xác minh. Riêng bsa90 Q2/2026 đang WORKBOOK_APPROVED, chưa phải VERIFIED_SNAPSHOT. Không tự khẳng định đơn vị nguồn đã được chứng nhận.
- Tỷ lệ trong chunk có định dạng làm tròn; giá trị gốc đầy đủ được giữ trong facts. Không dùng chữ đã làm tròn để tính lại đáp án chính xác.
- Các phép tính giá dùng reader theo corpus. API /api/search chỉ trả đoạn liên quan; nó chưa phải luồng sinh câu trả lời, tính toán và kiểm chứng câu trả lời đầy đủ.
- Q40 được kiểm tra trả rỗng khi thiếu kỳ. Q30 và các câu từ chối khác cần lớp kiểm chứng câu trả lời; không xem top-k của retriever là đáp án.
- Chưa test trên máy vật lý của từng thành viên. Thành viên cần dùng cùng code/cấu hình, chạy check:sources trước; nguồn đang được corpus tham chiếu cần được giữ theo chính sách retention phù hợp.

## Sáng mở lên chạy thế nào?

Trên máy này, từ thư mục backend:

API GPU thử nghiệm cổng 8014 đã được dừng để giải phóng bộ nhớ. Backend cổng 8000 không chạy sẵn; khởi động bằng lệnh dưới đây khi cần test.

```powershell
npm run check:sources
npm run dev
```

Thành viên khác pull code bàn giao rồi làm theo docs/CORPUS_V4_QUICK_START.md, nhất là bốn khóa corpus/hash/source backend trong .env. Không gửi .env vào Git. Cần khởi động lại backend cũ để nạp cấu hình mới. Chưa commit hoặc push các thay đổi trong công việc này.

## Bằng chứng

- deployment.json: một metadata root đã được ghi và đọc lại.
- activation.json: registry/membership và index ACTIVE, corpus cũ được giữ.
- configuration.json: bốn khóa cấu hình local đã chuyển.
- shared-source-check.json: toàn bộ 7.158 chunk qua reader nguồn chung.
- http-smoke.json: request/response của 43 truy vấn cuối.
- financial-evidence-check.json: 12 dòng evidence Q31–Q39 và trạng thái đơn vị.
- cold-start-check.json: API khởi động từ .env thật, không override corpus/source; từ chối corpus không tồn tại bằng 409.
- regression-tests.xml: bộ 190 test.
- ../corpus-v4-member-handoff-20261022/audit.json: audit DB và runtime cuối.
