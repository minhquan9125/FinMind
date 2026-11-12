# Phân biệt yêu cầu độc lập và bằng chứng — 12/11/2026

Đóng băng trước lượt đo. Giữ nguyên classifier C=1, coefficients, intercepts,
training, taxonomy và matcher chính thức. Không thêm nguyên T038 vào mẫu.

## Một cách thử, không hiệu chỉnh sau khi xem điểm

- Tách ở dấu hỏi/chấm phẩy/xuống dòng và một số dấu nối yêu cầu (và, rồi,
  đồng thời, sau đó, kèm) khi vế sau là câu hỏi hoặc mệnh lệnh. Không chỉ thấy
  hai công ty, nhiều chỉ tiêu hoặc từ “và” là gán MIXED.
- Phân loại phần xin dẫn chứng rõ ràng (như “trích câu làm bằng chứng”, “dẫn
  nguồn cho câu trả lời”) và giải nghĩa viết tắt thành phần hỗ trợ, không tính
  như mục tiêu thứ hai. Trích nội dung báo cáo như yêu cầu độc lập vẫn là mục tiêu.
- Nếu chỉ còn một yêu cầu sau khi bỏ phần hỗ trợ, dùng điểm classifier của yêu
  cầu đó làm điểm hiệu lực. Giữ điểm toàn câu trong trace. Một câu đơn không có
  phần hỗ trợ bị bỏ thì giữ nguyên điểm toàn câu.
- Nếu còn ít nhất hai phần yêu cầu, dùng classifier đã đóng băng để chấm từng
  phần. Chỉ xét cặp có nhãn đứng đầu khác nhau và đều không phải MIXED.
- Mức hỗ trợ MIXED = giá trị lớn nhất của min(p_top_vế_a, p_top_vế_b) trên các
  cặp khác nhãn. Điểm MIXED mới = max(điểm MIXED toàn câu, mức hỗ trợ này).
  Các điểm khác giữ nguyên. Sắp xếp lại theo điểm rồi tên nhãn.
- Đây là heuristic tổng hợp bằng chứng, không phải xác suất đúng được hiệu chỉnh.
  Policy `intent-composition-support-v1`, type `COMPOSITION_SUPPORT_UNCALIBRATED`.
  Giữ điểm classifier toàn câu và từng vế trong trace; không gọi điểm mới là cosine.
  Không đưa vào consumer 04.2 hoặc dùng ngưỡng cũ 0,65/0,08.

## Phép kiểm tra

- 32 câu đối chứng mới được đóng băng trước chạy: bốn cách hỏi chức vụ / nội dung
  báo cáo / cả hai / chức vụ + dẫn chứng trên sáu công ty; tám ca ranh giới khác.
  Cùng tác giả soạn, không phải test mù. Chỉ dùng đánh giá, không fit classifier.
- Đo lại 84 dev, 47 gold cũ (+9 null quan sát), 8 known và 28 câu đã xem.
- So với classifier đã đóng băng và baseline cosine cũ. Báo mọi câu thay đổi,
  bao gồm các câu đang đúng thành sai; không sửa đáp án để xóa hồi quy.
- Điều kiện đề nghị bước kiểm tra/calibration tiếp: sửa T038 về MIXED, không
  tăng hồi quy so baseline trên bộ cũ, không làm sai thêm câu classifier đang đúng
  trên các tập đã xem và top-1 dev không giảm. Các ca chức vụ + dẫn chứng trong
  bộ đối chứng phải giữ PERSON_ROLE. Không tự giảm điều kiện nếu thử nghiệm thất bại.
- Nếu đạt, vẫn chưa phải nghiệm thu E2E hoặc đủ 90%; còn cần kiểm tra mới,
  calibration riêng, hợp đồng score với Huyền và source consumer thực tế.

Rủi ro: ranh giới câu tiếng Việt/viết tắt, mệnh lệnh thiếu chủ ngữ, phép phủ định,
hai vế cùng nhãn và câu có ý phụ. Các dạng chưa hỗ trợ được ghi giới hạn, không
mở rộng luật theo từng ID/ticker hoặc chỉnh sau khi nhìn kết quả lượt này.
