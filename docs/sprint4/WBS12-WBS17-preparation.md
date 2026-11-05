# WBS12 adapter fixture và chuẩn bị đánh giá WBS17

**Cập nhật 04/11/2026:** Phần WBS12 bên dưới ghi lại giai đoạn chuẩn bị fixture.
Nhánh GRAPH đã được nối WBS09 và kiểm thử trên Neo4j/PostgreSQL thật sau đó;
xem [WBS12-graph-router-live.md](WBS12-graph-router-live.md) và
[biên bản bàn giao](Nhan-WBS03-WBS08-WBS12-handoff-20261104.md). Phần chuẩn bị
WBS17 bên dưới vẫn là kế hoạch, chưa phải kết quả benchmark B1/B2.

Ngày 03/11/2026. Graph BCTN V4 đã READY ở phiên
`s4-bctn-b2550a0b-v4-20261102`; phần này **chưa nối WBS09 thật** và
**chưa phải kết quả B1/B2**.

## WBS12: đường nối đã chuẩn bị

`Sprint4GraphAdapter` nhận task GRAPH của `DecisionEngine`, giữ nguyên câu hỏi,
companies, periods, topic, entity_mentions và gắn `graph_version_id`,
`corpus_version_id` được cấu hình rõ. Adapter chỉ gọi hai hàm được tiêm vào:

- `query_fn(request) -> list[relation]`: WBS09 sẽ cung cấp hàm truy vấn có lọc;
  adapter không sinh Cypher. Mỗi relation cần `relation_id`, `relation_type`,
  `subject_id`, `object_id`, `review_status`, hai version ID, `matched_companies`,
  `matched_period`, `evidence`; `path` và `temporal` được giữ để hiển thị.
- `read_source_fn(document_id, chunk_id, corpus_version_id) -> source`: tầng đọc
  nguồn đã ghim cung cấp `chunk_text`, `locator`, ID tài liệu/chunk/corpus và
  `content_hash`. Với BCTN, triển khai thật có thể bọc
  `documents.annual_source_reader.read_annual_chunk` trong transaction chỉ đọc.

Đây là **hợp đồng nội bộ tạm cho fixture**, chưa khẳng định là chữ ký WBS09.
Khi Hưng bàn giao WBS09, chỉ viết lớp bọc chuyển kết quả thật sang dạng trên;
không sửa schema của Hưng theo fixture. Cần xác nhận cách WBS09 biểu diễn công ty
đã khớp (ticker/canonical ID), kỳ hiệu lực, đường đi và trạng thái duyệt.

Adapter loại quan hệ không `APPROVED`, kiểm tra đúng công ty, kỳ và version,
đọc lại nguồn bằng ID, kiểm tra SHA256 của text và yêu cầu quote xuất hiện trong text rồi mới trả
evidence. Sai phạm vi/nguồn không được trả một phần kết quả. `NO_DATA` khác
`GRAPH_TIMEOUT` và lỗi nguồn. Đọc nguồn cho câu GRAPH không đổi route thành BOTH.
Nếu live adapter chưa khởi tạo, `/api/hybrid-router/run` trả `GRAPH_NOT_READY`
hoặc `CONTENT_NOT_READY`, không dùng dữ liệu mock làm kết quả live.

## WBS17: khung đánh giá cần chốt với Huyền

Bộ câu hỏi `backend/tests/fixtures/router_acceptance_v2.json` hiện chỉ có nhãn
**route** và company; không có gold về relation, nguồn, thời gian hay câu trả lời.
Có thể lấy câu hỏi phù hợp từ đây làm *ứng viên*, rồi Huyền duyệt gold theo đúng
graph/corpus version. Không chấm retrieval bằng nhãn route đơn thuần.

Mỗi ca cần ghi trước khi chạy: `case_id`, `question`, `route_expected`,
`company/entity IDs`, `relation_type`, `direction`, `time_scope`,
`graph_version_id`, `corpus_version_id`, `expected_relation_ids`,
`expected_document_ids`, `expected_chunk_ids`, `reviewer`, `reviewed_at`.
Ca VECTOR có gold chunk riêng; ca BOTH có cả graph và vector gold. Nếu dữ liệu
thật chưa có, ghi `NOT_READY`, không tính là pass/fail chất lượng.

Gợi ý chọn ca đầu tiên để Huyền duyệt (chưa có gold):

| Nhóm | Câu hỏi ứng viên | Cần xác minh trước khi chấm |
| --- | --- | --- |
| GRAPH · quan hệ | TCB có những công ty con nào trong BCTN 2024? | Phiên graph `s4-bctn-b2550a0b-v4-20261102` có quan hệ TCB→TCBS/TechAMC/TCC; Huyền cần duyệt tập ID và phạm vi thời gian |
| GRAPH · liên kết | ELC có công ty liên kết nào trong BCTN 2024? | Phiên graph READY có hai cạnh HAS_ASSOCIATE; cần duyệt đúng nguồn/đáp án |
| GRAPH · chức vụ | Ai là chủ tịch FPT? | WBS04/WBS07 chưa xác nhận nạp quan hệ chức vụ vào phiên graph này; đánh dấu `NOT_READY` |
| GRAPH · rỗng | Một mã không có quan hệ được duyệt | Đúng tập graph được chốt; kỳ vọng `NO_DATA` |
| VECTOR | LNST FPT quý 2/2025 bao nhiêu? | Đúng corpus, chunk gold, đơn vị và kỳ |
| BOTH | Tìm công ty con TCB rồi xem lợi nhuận của chúng | Quan hệ APPROVED và chunk lợi nhuận cùng phạm vi; chưa xác nhận vector có dữ liệu công ty con |
| Lỗi | Tên công ty mơ hồ; sai thời gian; graph timeout | Kỳ vọng CLARIFY/NO_DATA/SYSTEM_UNAVAILABLE, không sinh citation giả |

Khi chạy thật, cố định cùng bộ câu hỏi, corpus, graph version, model, máy và
cấu hình cho B1/B2. Ghi từng câu: route thực tế, status/reason, entity/chiều/
thời gian, relation/chunk/source ID, citation mở lại được hay không, latency
từng nhánh và tổng, lỗi và owner. Báo cáo tổng hợp theo VECTOR/GRAPH/BOTH;
không mặc định B2 tốt hơn B1. Huyền kiểm tra hành trình chat → citation → Graph
Viewer, Nhân chạy benchmark, hai người đối chiếu ca sai và báo cáo full-load
News WBS16 trước khi đóng task.

## Kiểm tra đã chạy

`cd backend && .venv\\Scripts\\python.exe -m pytest tests/test_sprint4_graph_adapter.py tests/test_hybrid_router.py tests/test_live_adapters.py -q -p no:cacheprovider`

139 test adapter/router trọng tâm pass offline; bộ hồi quy router mở rộng 971 test pass.
Kết quả này xác nhận adapter/fixture và hồi quy router;
chưa chứng minh truy vấn Neo4j, đọc PostgreSQL hay chất lượng B1/B2 trên corpus thật.
