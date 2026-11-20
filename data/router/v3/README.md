# Router dataset v3 (đã duyệt nhãn)

Bản này sửa trực tiếp các vấn đề trong review của bộ 200 câu v2:

- bỏ mẫu lặp `Cho tui xem` và cụm gợi nhãn `không cần tìm công ty con`;
- thêm 51 câu ngắn thiếu kỳ/thời điểm nhưng vẫn xác định được nhu cầu truy xuất;
- chuyển `fixture`, `graph mock` và trạng thái hỗ trợ khỏi lời người dùng sang metadata;
- `paraphrase_group` nay là alias của `semantic_group`, chỉ gom câu giữ cùng nghĩa và độ đủ scope;
- `leakage_group` rộng hơn và là đơn vị chia tập; hai mẫu tài sản công ty con R168/R200 nằm cùng nhóm chống rò rỉ;
- tách `retrieval_need_route` khỏi `expected_decision` và `execution_route`;
- classifier nhận nguyên văn câu gốc trước bước làm rõ; decision layer chịu trách nhiệm hỏi lại;
- thêm đối chứng chéo: có năm nhưng vẫn thiếu scope, và không có năm cụ thể nhưng có mốc tương đối đủ rõ;
- sinh lại tags/capability từ câu hiện tại, không kế thừa metadata wording cũ;
- ghi riêng yêu cầu tính toán, đổi đơn vị và locator nguồn.

`router_dataset.csv` có thêm hai cột tường minh `semantic_group` và `leakage_group`;
giữ `paraphrase_group` để tương thích và cho nó trỏ tới `semantic_group`.
`router_annotations.json` giữ metadata review và quyết định router.
`router_splits.json` giữ split 140/30/30 theo `leakage_group`.
V3 là bộ dữ liệu độc lập đang được giữ lại; các phiên bản router cũ đã được loại bỏ.

`router_challenge_set.json` là tập kiểm thử độc lập, không thuộc train/validation/test.
Tập này cố ý gồm câu có năm nhưng vẫn phải hỏi lại, câu không có năm cụ thể nhưng
đủ thời gian theo policy, câu kế thừa ngữ cảnh và câu có quý không hợp lệ. Các câu
không được trùng nguyên văn với bộ chính hoặc development; case ngữ cảnh dùng cách
nói, cặp công ty, chỉ tiêu và dạng kỳ khác B25. Không được trộn các case này vào dữ
liệu huấn luyện. Khi người dùng không nêu phạm vi báo cáo, giá trị là `UNKNOWN`,
không tự coi là `CONSOLIDATED`.

Đây vẫn là dữ liệu tổng hợp. Nhãn của 200 câu đã được duyệt ở phiên bản
`router-v3-reviewed-2026-10-28` và được phép dùng để train. Việc duyệt nhãn không
đồng nghĩa các capability đã chạy thật; trạng thái planned/mock vẫn là cổng độc lập.

Challenge dùng mốc cố định `2026-10-28T10:00:00+07:00`, múi giờ
`Asia/Ho_Chi_Minh` và snapshot mock `router-challenge-snapshot-2026-10-28`.
Mỗi case ghi riêng capability, chế độ `MOCK` hoặc `NON_EXECUTING_ACCEPTANCE`, và
khả năng trả lời hiện tại để không nhầm việc chọn đúng tuyến với có dữ liệu thật.
