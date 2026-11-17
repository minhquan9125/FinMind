# S5-WBS13.2 — Đánh giá router và fallback trên bộ câu riêng

Người thực hiện: Nhân. Ngày bắt đầu: 16/11/2026. Backlog: 3 giờ dự kiến,
không phải thời gian đã làm. Task 01.2 được giữ nguyên ở `tasks/s5-wbs012/` và đã tạm dừng.

## Phạm vi và quyết định

Đánh giá code tại commit đang checkout, không sửa bộ phân loại, luật Chat,
router, ngưỡng hoặc logic của thành viên khác. Dùng 60 câu mới, đủ 11 nhãn v2,
có dấu/không dấu/viết tắt, câu kép và thiếu dữ kiện. Kỳ vọng được ghi và khóa
checksum trước lượt chạy đầu. Đây là bộ bổ sung do người triển khai tự soạn,
chưa phải bộ kín độc lập được reviewer gán nhãn.

Đo riêng nhãn của classifier BGE-M3, quyết định gate, route planner và nhánh
Chat thực tế trong harness. Giữ nguyên các nhánh giá/phân tích/tin có sẵn,
không gọi mọi nhánh đó là VECTOR. MIXED phải kiểm cả thành phần, không tự là BOTH.

Tái sử dụng `LiveResearchService`, `WebChatRouter`, `DecisionEngine` và provider
Gemini thật khi fallback được code yêu cầu. Thay dữ liệu truy xuất bằng biên
rỗng có ghi trace để không đụng DB, Neo4j, lịch sử hay sinh câu trả lời tài chính.
Đây là đánh giá tích hợp định tuyến; không phải E2E Web Chat hoặc đo toàn thời
gian trả lời với dữ liệu thật. Ghi rõ các thành phần được thay trong báo cáo.

## Các bước và kiểm chứng

1. Ghi kỳ vọng, kiểm trùng với train/dev/bộ benchmark đã biết, khóa bộ câu.
   Kiểm chứng: validator từ chối ID trùng, câu trùng, nhãn sai, MIXED thiếu thành phần.
2. Viết scorer và test trước: lỗi/timeout vẫn trong mẫu số; nhãn đúng không
   che route sai; tỷ lệ fallback dựa trên lời gọi thật; không bỏ ca sai.
3. Chạy model thật, đo cold start riêng; lưu đầu ra từng câu, thời gian,
   phân loại/route/gate và fallback; sinh JSON/CSV/báo cáo tự động.
4. Kiểm chứng kết quả, checksum, giới hạn và lệnh chạy lại. Hoàn tất gói review,
   giữ nguyên lỗi sản phẩm để chuyển đúng người xử lý.

Không đặt ngưỡng pass 90% cho 13.2: backlog yêu cầu đo/báo cáo. Không thay bộ
câu hay ngưỡng để đạt một tỷ lệ. Kết luận chất lượng trên nhãn tạm cần review.

Theo dõi ở [todo.md](todo.md). Đầu ra dự kiến: fixture, runner, test scorer và
`outputs/s5_wbs132_20261116/`; chỉ một báo cáo kết quả chính, không nhân bản MD.
