# Ngữ cảnh dùng chung trước Router

Áp dụng trong `FinMind-news-release`, trên nền `origin/backup-demo` commit `7526860b`.

- `followup_scope.company_continuation` nhận diện một lượt chỉ đổi công ty, dùng chung cho context policy, parser thị trường và Hybrid Router. Không đưa toàn bộ lịch sử sang AI để đoán.
- Chỉ đổi mã: giữ chủ đề, kỳ và phạm vi đã xác nhận. Có câu hỏi trước đã lưu thì đổi tên công ty trong chính câu hỏi đó, rồi chạy lại pipeline.
- Nêu chủ đề mới: ưu tiên chủ đề mới, loại bộ lọc không tương thích. Ví dụ giá FPT → “còn VCB mà chủ tịch thì sao” đi nhánh quan hệ VCB, không giữ ngày giao dịch làm năm chức vụ.
- Khi đổi công ty, không giữ URL, anchor hoặc đoạn dẫn của bài cũ. Nguồn mới phải được truy xuất và kiểm tra lại.
- Nhiều công ty trong lượt trước: câu chỉ đổi mã phải hỏi rõ đối tượng so sánh, không tự thay một bên.
- Câu hỏi độc lập và nguồn/năm được chỉ rõ không tự kế thừa bộ lọc cũ.
- Nhận diện tên dựa trên registry/alias hiện có. Tên chưa có hoặc câu có nhiều cách hiểu vẫn cần làm rõ; không tự ghép danh tính.

Kiểm thử: ma trận 10 mã qua giá, NEWS, BCTN, BCTC, phân tích, Chủ tịch; đổi chủ đề giữa nguồn; loại URL cũ; alias nhiều từ; gọi qua service; trường hợp nhiều công ty. Test không chứng minh tất cả cách diễn đạt tự nhiên đều được hiểu đúng.

Các bản sửa chưa commit vẫn được giữ riêng. Safety stash trước khi nhập backup-demo: `safety-before-backup-demo-context-20261120`; patch sao lưu nằm trong `C:/NhanhFrontend/outputs/member-tests-fix-20261119/before-backup-pull-context/`.
