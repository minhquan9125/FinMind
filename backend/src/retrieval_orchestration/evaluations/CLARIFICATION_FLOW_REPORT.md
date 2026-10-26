# Kiểm tra cơ chế làm rõ không hỏi lặp

Hai hội thoại chạy qua SessionStore, corpus thật và Gemini thật. Không mô phỏng đăng nhập hoặc thao tác trình duyệt.

Trong các lượt cần làm rõ, số generation mới bằng 0. Nguồn/đơn vị chưa xác minh được giữ rõ trong đáp án.

## nợ

Người dùng: nợ của fpt trong quý 2 2026 là bao nhiêu

Hệ thống: Bạn muốn xem loại nợ nào? 1. Tổng nợ phải trả. 2. Nợ ngắn hạn. 3. Nợ dài hạn. 4. Nợ vay.

Trạng thái: ASK_CLARIFICATION; generation mới: 0

Người dùng: nợ

Hệ thống: Mình vẫn chưa xác định được nợ. Hãy chọn một mục dưới đây hoặc nhập số thứ tự. 1. Tổng nợ phải trả. 2. Nợ ngắn hạn. 3. Nợ dài hạn. 4. Nợ vay.

Trạng thái: ASK_CLARIFICATION; generation mới: 0

Người dùng: tổng

Hệ thống: Nợ phải trả của Công ty Cổ phần FPT tại cuối quý 2/2026 là 32,567,425,051,243 [1]

Nguồn chưa xác minh đơn vị của chỉ tiêu; giữ nguyên giá trị gốc.

Nguồn chưa xác định phạm vi báo cáo hợp nhất hay riêng lẻ.

Trạng thái: DRAFT_READY; generation mới: 1

## doanh thu

Người dùng: doanh thu FPT quý 2/2026

Hệ thống: Bạn muốn xem loại doanh thu nào? 1. Doanh thu trước giảm trừ. 2. Doanh thu thuần.

Trạng thái: ASK_CLARIFICATION; generation mới: 0

Người dùng: doanh thu

Hệ thống: Mình vẫn chưa xác định được doanh thu. Hãy chọn một mục dưới đây hoặc nhập số thứ tự. 1. Doanh thu trước giảm trừ. 2. Doanh thu thuần.

Trạng thái: ASK_CLARIFICATION; generation mới: 0

Người dùng: doanh thu

Hệ thống: Mình tạm dừng yêu cầu vì chưa xác định được doanh thu. Bạn có thể bấm một lựa chọn dưới đây, nhập tên cụ thể hoặc gõ /moi để bắt đầu lại. 1. Doanh thu trước giảm trừ. 2. Doanh thu thuần.

Trạng thái: CLARIFICATION_STALLED; generation mới: 0

Người dùng: thuần

Hệ thống: Doanh thu thuần của FPT trong quý 2/2026 là 13,788,503,461,199. [1]

Nguồn chưa xác minh đơn vị của chỉ tiêu; giữ nguyên giá trị gốc.

Nguồn chưa xác định phạm vi báo cáo hợp nhất hay riêng lẻ.

Trạng thái: DRAFT_READY; generation mới: 1

## Kiểm chứng bổ sung

25 ca chống lặp và lựa chọn; tổng regression liên quan 93 ca PASS. Frontend16PASS, VitebuildPASS; hội thoại cũ125PASS; B1131OK/2skip. Coverage executable-line clarifications.py96.4%, không branchcoverage.

Sau 3 lượt làm rõ cùng nội dung vẫn không bổ sung được thông tin, hệ thống chuyển CLARIFICATION_STALLED và giữ nút chọn. Đổi qua lại nhóm mơ hồ mà không bổ sung thông tin cốt lõi cũng bị giới hạn sau 6 lượt. Chọn một mục hoặc nhập tên rõ ràng vẫn tiếp tục được; /moi xóa phạm vi.

Bộ phân loại vẫn theo các chỉ tiêu đã khai báo; không khẳng định hiểu mọi câu tiếng Việt. Cơ chế chống lặp áp dụng chung cho các nhánh cần làm rõ, tránh tự đoán chỉ tiêu.