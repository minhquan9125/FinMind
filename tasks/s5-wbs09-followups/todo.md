# S5-WBS09.2 và S5-WBS09.3 — Nhân

Bắt đầu 17/11/2026, trên phần 09.1 tại `98a2926d`.

- [x] 09.2: tái hiện câu liệt kê nối tiếp và tổng quan công ty đang nói (6 lỗi trước sửa).
- [x] 09.2: giữ đúng chủ đề; công ty mới được ưu tiên; mơ hồ hỏi lại.
- [x] 09.2: kiểm parser/router/service/API; 15 ca mới, bộ hồi quy 139 pass / 1 skip.
- [ ] 09.3: tổng hợp từ các câu trả lời có nguồn của phiên hiện tại.
- [ ] 09.3: giữ nguyên nguồn, đánh lại số citation; không gộp dữ kiện khác kỳ/mã.
- [ ] 09.3: kiểm phiên mới, `/new`, tiếp tục phiên, dữ liệu nguồn hỏng và giới hạn kích thước.
- [ ] Kiểm hồi quy, frontend hiển thị citation, báo cáo và commit bàn giao.

Quyết định: tổng hợp theo cách trích chọn các ý đã trả lời có nguồn, không gọi AI,
không suy diễn số mới hoặc đọc lịch sử người dùng khác. Các lần hỏi lại/lỗi/không có
bằng chứng được ghi là phần thiếu. Có giới hạn dung lượng và thông báo khi lược bớt.
Không sửa refresh token, ngưỡng intent hay cách tính nhận định xu hướng.
