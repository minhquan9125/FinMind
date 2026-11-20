# S5-WBS09.1 — Kế thừa công ty, kỳ và chủ đề giữa các lượt

Người thực hiện: Nhân. Bắt đầu 16/11/2026. Task 01.2 vẫn tạm dừng;
13.2 đã có kết quả riêng, không sửa kết quả đánh giá đó trong task này.

## Tiêu chí và phạm vi

- Câu tiếp nối giữ công ty, kỳ và chủ đề đang hỏi; dữ kiện mới ghi đè dữ kiện cũ.
- Đổi quý trong cùng năm phải dùng năm của hội thoại khi xác định duy nhất.
- Đổi nguồn/chủ đề không mang theo bộ lọc tài chính, báo cáo hoặc đồ thị không phù hợp.
- Thiếu hoặc mơ hồ phải hỏi lại; phiên mới và `/new` không lấy ngữ cảnh phiên trước.
- Lịch sử, phiên gốc khi tiếp tục và dữ liệu context đầu vào không bị sửa ngoài ý muốn.
- Chỉ xử lý ngữ cảnh: không sửa refresh token, ngưỡng intent hoặc task 09.2/09.3.

## Thực hiện

- [x] Tái hiện lỗi bằng test trước khi sửa; xác nhận baseline các test liên quan.
- [x] Sửa tối thiểu đường Chat thật và kiểm thử đổi mã/kỳ/chủ đề.
- [x] Kiểm tích hợp lưu/đọc lại/tiếp tục phiên, cách ly người dùng và phiên mới.
- [x] Chạy hồi quy, rà diff và ghi báo cáo có lệnh tái chạy, kết quả và giới hạn.

Kiểm thử tự động sẽ dùng parser/router/service thật, dữ liệu truy xuất giả lập
có ghi rõ. Không coi đây là bằng chứng chất lượng câu trả lời tài chính hoặc E2E trình duyệt.

Kết quả: **hoàn thành triển khai, sẵn sàng review**; 29 ca mới đạt, bộ kiểm cuối
255 pass / 1 skip (gồm kiểm PostgreSQL thật có rollback). Lượt full backend:
3482 pass / 69 fail / 25 skip / 2 xfail; phân loại lỗi môi trường/fixture ở
[báo cáo bàn giao](../../docs/sprint5/S5-WBS09.1-context.md).
