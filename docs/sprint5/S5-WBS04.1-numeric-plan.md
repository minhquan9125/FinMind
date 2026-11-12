# Guard lấy giá trị tài chính — đóng băng trước đo, 12/11/2026

Sửa lớp quyết định offline, không retrain BGE/classifier hoặc sửa score/gold.
Nhận NUMERIC khi có chỉ tiêu tài chính và yêu cầu lấy giá trị; loại trừ câu
đếm quan hệ/bài tin, chức vụ/ngày, nguyên văn, giải thích/tóm tắt/đánh giá.
Không ép kế hoạch lợi nhuận chưa rõ mục tiêu; giữ đề xuất nhãn ở DRAFT.

Giữ source V3/V4 cùng audit cũ. New policy: intent-request-objectives-v3,
confidence=null, raw ranking bất biến, runtime_enabled=false. Không dùng
ngưỡng 0,65/0,08 của Huyền cho loại quyết định mới.

Đánh giá:
- Replay 293 câu đã dùng ở V4, gồm cả 15 probe nay đã xem. Điều kiện: sửa
  REVIEW-03 và không làm sai bất kỳ câu V4 đang đúng nào. Lưu mọi thay đổi.
- Chuẩn bị 20 câu kiểm tra bổ sung với số liệu, đếm quan hệ, ngày/chức vụ,
  nội dung/tin/xu hướng và câu kết hợp. Cùng tác giả, có mẫu kiểm tra tương
  tự lỗi đã biết; không gọi là test mù độc lập. Đóng băng trước embedding.
- Chỉ một lượt đo sau đóng băng; giữ mọi ca sai. Không sửa gold/rule theo
  kết quả để ép 100%. Tái tính điểm từ vector, chạy toàn bộ test Sprint 5.

Chưa giải quyết consumer/calibration hoặc tích hợp Web Chat; không gọi sửa
được một câu là classifier đã hết nhạy ticker hay toàn bộ router đã đạt.
