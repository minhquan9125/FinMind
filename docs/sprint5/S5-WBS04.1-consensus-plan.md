# Đồng thuận cả câu và các yêu cầu — vòng phát triển 2, 12/11/2026

Đóng băng trước khi chấm vòng này. Không sửa/xóa kết quả vòng composition-support.
32 controls ở vòng trước giờ đã xem, chỉ là development, không gọi là test mới.

## Chẩn đoán vòng trước

- T038: vế chức vụ được PERSON_ROLE, vế chính sách được REPORT_CONTENT; min
  support 0,2513 chưa vượt score toàn câu PERSON_ROLE 0,2584.
- T003: hai thao tác cùng NUMERIC nhưng vế thiếu ngữ cảnh bị head nhận NEWS,
  dẫn tới nâng MIXED sai. So trực tiếp score cả câu/vế chưa bảo đảm ý độc lập.

## Quy tắc duy nhất của vòng 2

- Giữ nguyên classifier, các score toàn câu, segmentation và embedding đã lưu.
- Nếu có một yêu cầu sau khi loại hỗ trợ: đề xuất nhãn của yêu cầu đó, ghi riêng
  primary evidence; nếu câu không bị tách/loại gì thì dùng nhãn toàn câu.
- Nếu có nhiều yêu cầu: chỉ đề xuất MIXED khi tồn tại hai vế có nhãn đầu khác
  nhau, cả hai không phải MIXED, và cặp nhãn đó đúng bằng hai nhãn đầu toàn câu.
  Cả câu đã đứng MIXED đầu thì giữ nguyên. Nếu không có đồng thuận thì giữ nhãn cũ.
- Không tăng score MIXED hoặc ghép nhãn đề xuất với score của nhãn khác.
  Output `resolution.intent_label`, `confidence=null`, reason/component evidence;
  `base_ranking` giữ đúng nguyên vẹn classifier probabilities/version gốc.
- Đây là kết quả quyết định thực nghiệm, không phải top-k đã hiệu chỉnh. Báo
  accuracy/F1 nhãn cuối riêng; top-3/5 của base_ranking vẫn là của classifier gốc.
  Không áp ngưỡng 0,65/0,08 lên resolution và chưa nối consumer 04.2.

## Điều kiện không giảm sau khi xem điểm

Sửa T038; không còn ca cũ baseline đúng→sai; không làm hỏng thêm câu classifier
đang đúng trên 84 dev/47 cũ/8 known/28 đã xem/32 controls; dev không giảm; sáu
ca chức vụ + bằng chứng phải giữ PERSON_ROLE. Lưu tất cả điểm/ca thay đổi.

Nếu đạt các điều kiện development này, vẫn chưa là nghiệm thu E2E/90% hoặc có
confidence dùng trực tiếp. Bước kiểm tra mới và thiết kế calibration/contract
phải tách riêng, không sửa tiêu chí hoặc dùng lại các tập đã xem như test mù.
