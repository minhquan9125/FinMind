# Sửa sau review Hưng — đóng băng trước đánh giá V4

Ngày 12/11/2026. Giữ nguyên V3 đã review và toàn bộ hash cũ. Module kế tiếp
`intent_request_review.py` dùng policy `intent-request-objectives-v2`, vẫn offline.

- Sửa từ hỏi ai so với acronym AI trước khi tách yêu cầu; giữ văn bản gốc cho
  embedding. Không dùng ticker, tên người, năm hoặc mã test làm ngoại lệ.
- Bổ sung câu chức danh + “là ai”, “giữ chức gì”, CEO/CFO và who is CEO/CFO.
  Giữ loại trừ bài tin, chép nguyên văn và mục tiêu số liệu về người giữ chức.
- Không sửa taxonomy đã APPROVED hoặc refit classifier. Nhãn đề xuất riêng,
  confidence=null, raw ranking không đổi; không áp ngưỡng cosine cho V4.

Đo lại 278 câu đã xem (các bộ V3 + 28 câu cuối từng dùng). Chúng là hồi quy,
không còn là final test độc lập. Điều kiện giữ ứng viên: không làm sai thêm
câu V3 đang đúng trên bất kỳ tập nào; lưu toàn bộ thay đổi và lỗi còn lại.

Probe mới gồm các cách hỏi do review gợi ý, có gold theo taxonomy hiện có.
Đây là kiểm chứng theo lỗi đã biết, không gọi là đánh giá mù. Dùng đúng BGE-M3
revision và tham số classifier đã chọn. Nếu model không chạy được thì ghi thiếu
nhãn cuối, không lấy unit test hoặc regex output thay kết quả model.

Ranh giới kế hoạch lợi nhuận để riêng ở DRAFT: hỏi số mục tiêu / tóm tắt kế hoạch /
đánh giá tính khả thi. Không đưa câu mơ hồ này vào accuracy để tự quyết thay nhóm.
Consumer mới của Huyền không có trong checkout; chỉ chuẩn bị contract và ca từ
chối metadata thiếu, chưa ghi đã sửa consumer hoặc đã chạy router thật.
