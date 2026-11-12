# Sửa mục tiêu NEWS và câu nhiều ý — 12/11/2026

Phạm vi: ba lỗi NV-13/NV-19/NV-20 đã được phân tích và Nhân đồng ý sửa.
Đây là phiên bản offline kế tiếp; giữ source, gold, model và kết quả cũ.

1. Viết test tái hiện ba lỗi, thêm câu âm phân biệt tìm bài với lấy số từ bài,
   danh sách chỉ tiêu và hai yêu cầu cùng nhãn. Chạy đỏ trước khi sửa.
2. Nhận diện mục tiêu thao tác trên bài tin ở đầu yêu cầu. Không coi mọi câu
   có chữ tin là NEWS. Tách thêm yêu cầu mở đầu bằng Đọc khi có vế độc lập.
3. Chỉ kết luận MIXED bằng hai nhãn mục tiêu rõ ràng trên các yêu cầu đã tách;
   không bỏ toàn bộ điều kiện ghép cũ dựa trên xác suất chưa hiệu chỉnh.
4. Đóng băng code trước đo; replay 313 câu đã xem, không được làm sai câu cũ
   đang đúng. Sinh vector BGE-M3 cùng revision cho phần câu mới tách khi thiếu.
   Audit tính lại xác suất từ vector/head, xác minh nguồn và giữ điểm thô.
5. Chạy toàn bộ unit test ý định Sprint 5, báo đầy đủ lỗi còn lại và history.

Không refit, không dùng mã công ty làm luật, không thay ngưỡng 0,65/0,08;
confidence=null, runtime_enabled=false. MIXED không mặc định là BOTH.
Bộ 20 câu nay là hồi quy đã xem, không gọi 20/20 (nếu đạt) là kiểm tra mù.
