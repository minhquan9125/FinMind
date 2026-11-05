# Đánh giá task Hồ Phạm Đăng Nhân — 05/11/2026

Tuần đánh giá: 02–08/11/2026, tuần 2 Sprint 4. Nhánh local: `nhan-sprint-411`, HEAD `0147b6e` tại thời điểm đọc. Căn cứ: bảng phân công người dùng gửi, mã nguồn và tài liệu local, lịch sử Git, test chạy lại. Đây là đề xuất trạng thái để nhóm nghiệm thu, không phải thay đổi bảng phân công.

## Phạm vi và mức chắc chắn

Đã khảo sát cấu trúc dự án, điểm vào backend/frontend, nguồn/chunk/vector, chat và answering B1, router, extractor, kiểm duyệt, metadata, graph store/retrieval, Graph Viewer, migration và tài liệu bàn giao Sprint 4. Đọc sâu WBS03/WBS08/WBS12 và các phụ thuộc WBS17. Không tuyên bố đã đọc từng dòng toàn bộ dữ liệu, OCR, dependency hoặc thực hiện kiểm toán mọi chức năng sản phẩm.

Kiểm tra trực tiếp trong lượt này:

- 246/246 test đạt trong 11 file WBS03, WBS08, WBS09, router, adapter và đọc lại citation. Có cảnh báo cấu hình pytest-asyncio/Pydantic; không có test lỗi trong tập chạy này.
- `backend/.tmp/WBS03_NEW_46_REVIEW_20261105/verify_package.py`: `passed=true`, 46 ID mới duy nhất, loại trừ 23 ID cũ, toàn bộ PENDING; kiểm file/hash/quote cục bộ đạt.
- Mã Graph Viewer vẫn gọi fixture, chưa gọi API graph thật.
- Không có listener local tại các cổng tunnel 15433/17687 và API 8000/8012 khi kiểm tra. Không chạy lại Neo4j/PostgreSQL/HTTP live trong lượt đánh giá; số liệu live dưới đây là bằng chứng bàn giao ngày 03–04/11, không phải phép đo mới ngày 05/11.

## Kiến trúc liên quan

- `backend/src/main.py`: ghép API tài liệu, search, auth, thị trường, research chat và hybrid router.
- `documents` và `vector_retrieval`: ingest/chunk/locator, đọc lại nguồn và dense/BM25/RRF; là nền B1 và nhánh VECTOR.
- `retrieval_orchestration` và `b1_answering`: hội thoại, lịch sử, truy xuất, trả lời và citation.
- `sprint4_runtime`: contract 2.1.0, registry/chuẩn hóa thực thể và trích xuất quan hệ doanh nghiệp.
- `person_role`, `documents/news_event_extractor.py`, `graph_review`: nhánh chức vụ, sự kiện, kiểm nguồn và quyết định duyệt.
- `graph/sprint4_store.py`, `wbs09_pipeline.py`, `relation_retrieval.py`: ghi graph theo phiên, tích hợp các extractor, công bố READY và truy vấn có giới hạn.
- `hybrid_router/adapters.py`, `graph_source.py`, API `hybrid_router.py`: nối truy vấn graph với router, đọc lại nguồn trước khi trả citation.
- Frontend research chat dùng `/api/research/chat/sessions`; Graph Viewer có đường dữ liệu fixture riêng. Thành công ở `/api/hybrid-router/run` chưa chứng minh giao diện chat đang dùng toàn bộ luồng B2.

## Trạng thái đề nghị

| Task | Lịch | Kết luận theo bằng chứng | Cách cập nhật phù hợp |
|---|---|---|---|
| S4-WBS03 — quan hệ doanh nghiệp | Tuần 1, hạn 30/10, 6 giờ | Đã có extractor, nguồn thật, contract và test; còn mở độ bao phủ và lô ứng viên mới | Hoàn thành phần extractor trên phạm vi mẫu đã bàn giao; ghi rõ phần mở rộng đang review. Nếu nhóm yêu cầu bao phủ toàn corpus để nghiệm thu thì vẫn cần xác nhận tiêu chí đó |
| S4-WBS08 — ghi Neo4j | Tuần 1, hạn 30/10, 7 giờ | Đạt phạm vi writer/fixture; có thêm bàn giao 13 cạnh thật đã duyệt | Đề nghị Đã hoàn thành phần WBS08; đối chiếu pipeline hai hệ thống đầy đủ tiếp tục ở WBS07/WBS09 |
| S4-WBS12 — GRAPH vào router | Tuần 2, hạn 05/11, 5 giờ | Đã nối retrieval thật; có HTTP thật trong bàn giao BCTN và test chạy lại | Đề nghị Đã hoàn thành trong phạm vi graph BCTN đã kiểm chứng, kèm giới hạn chức vụ/sự kiện/đa công ty; không để Chưa bắt đầu |
| S4-WBS17 — B1/B2 và bàn giao chung | Tuần 2, hạn 08/11, 13 giờ chung | Đã chuẩn bị khung ca và chạy kiểm tra kỹ thuật; chưa đủ benchmark/E2E/full-load | Đang chuẩn bị/đang làm, chưa hoàn thành. Công Nhân là 7 giờ, Huyền 6 giờ |

Trong tuần này Nhân có 12 giờ dự kiến cho WBS12 và phần WBS17, không phải 18 giờ. Không có dữ liệu giờ thực tế để kết luận vượt công. Các mốc bàn giao tuần 1 nằm sau deadline dự kiến, nhưng không đủ dữ liệu để quy nguyên nhân chậm cho một người.

## WBS03: đã có và còn thiếu

Đã có rule HAS_SUBSIDIARY, HAS_ASSOCIATE, OWNS_SHARES, COOPERATES_WITH; xác định chiều, giữ tỷ lệ/ngày khi có nguồn, chặn phủ định/dự kiến/đồng xuất hiện. Có rule bảng sở hữu và test phân biệt phần trăm sở hữu với biểu quyết, tránh khớp prefix tên pháp nhân. Tất cả đầu ra mới là ứng viên, không tự phê duyệt.

Theo bàn giao 04/11, đã xử lý 20 BCTN/17.664 chunk, 23 ứng viên cũ được WBS06 kết luận 13 APPROVED và 10 REJECTED. Rule bảng sau đó tạo tổng 69 ứng viên; 46 ID mới đã được đóng gói riêng ngày 05/11. Không cộng 69 ứng viên thành 69 quan hệ đã được chấp nhận; 23 ID cũ vẫn giữ quyết định WBS06 tương ứng.

Lô 46 mới chưa đủ điều kiện nạp: thiếu consolidation_basis/accounting_basis tương ứng khi muốn APPROVED; 9 ca CMG chưa có ngày, N01 chưa resolve endpoint; FTEL có hai canonical ID; N29/N39 cần phân biệt sở hữu 49,52% và biểu quyết 80,15%; N18 cần chốt cách biểu diễn liên doanh. CMG còn lỗi OCR và bảng chưa phân loại rõ. Chưa có gold toàn corpus để công bố precision/recall. Đây là phần review/độ bao phủ còn mở; việc còn ứng viên PENDING tự nó không làm mất kết quả triển khai extractor đã đạt.

Nguồn: [bàn giao ba task](Nhan-WBS03-WBS08-WBS12-handoff-20261104.md), [rule bảng](WBS03-ownership-tables-20261104.md), [46 ứng viên mới](WBS03-new46-handoff-20261105.md).

## WBS08 và WBS12: bằng chứng đạt và giới hạn

Writer có khóa theo phiên + ID, chỉ lấy APPROVED, giao dịch theo batch, chạy lại không trùng, chặn batch đổi nội dung, giữ provenance/thời gian, chỉ publish khi đủ batch; phiên READY bất biến. Có script đối chiếu hash, ID, chiều, thuộc tính và evidence.

Biên bản 03–04/11 ghi graph `s4-bctn-b2550a0b-v4-20261102`, batch `approved-13-v4`: 13/13 cạnh duyệt khớp, không thiếu/thừa/trùng. Đây là 11 HAS_SUBSIDIARY và 2 HAS_ASSOCIATE, chưa chứng minh graph thật đủ ba nhóm quan hệ doanh nghiệp/chức vụ/sự kiện.

WBS12 dùng intent/slots, registry, truy vấn WBS09 có tham số và bước đọc lại nguồn PostgreSQL; kiểm document/chunk/corpus/index, locator, hash và quote. Đọc nguồn bằng ID vẫn giữ route GRAPH. Bàn giao HTTP thật: TCB 2025 trả GRAPH/OK, 2 quan hệ/4 citation; ELC 2024 trả 7 quan hệ/43 lượt evidence nhưng chỉ 10 chunk riêng; FPT 2025 và TCB 2001 trả NO_DATA trong graph được ghim. NO_DATA không chứng minh doanh nghiệp không có quan hệ ngoài graph này.

Giới hạn: chưa kiểm live chức vụ/sự kiện; adapter trả GRAPH_MULTI_COMPANY_SCOPE_UNSUPPORTED khi nhiều công ty; API trả JSON retrieval, chưa phải câu trả lời văn xuôi. Không lấy số evidence lớn làm số nguồn độc lập. `source_verified=true` xác nhận nguồn khớp phiên, không tự chứng minh mọi diễn giải nghiệp vụ đúng.

Nguồn: [WBS08](WBS08-graph-store.md), [WBS12 live](WBS12-graph-router-live.md), [WBS09](WBS09-graph-retrieval.md).

## Những điểm chặn WBS17

1. **Chưa có bộ gold và báo cáo B1/B2 chạy thật.** Tài liệu WBS12-WBS17 mới là khung chuẩn bị. Fixture route không chứa đủ nhãn quan hệ/nguồn/thời gian để chấm retrieval hoặc câu trả lời. `backend/.tmp/benchmark.json` là benchmark pgvector WBS20 ngày 21/10, không phải B1/B2 Sprint 4; file có tên wbs17 tháng 10 cũng không phải bằng chứng cho task Sprint 4 này.
2. **Graph Viewer vẫn mock trong checkout hiện tại.** `frontend/src/pages/graph/api.js` import graphFixture và trả fixture; GraphPage dùng rootOptions/mock và đường dẫn mock://. WBS15 ghi Đã hoàn thành trong bảng chưa khớp mã nguồn nhánh này. Cần Huyền kiểm tra nhánh/PR tích hợp, nối API thật và lưu bằng chứng E2E.
3. **Thiếu nghiệm thu pipeline chung qua review store.** Tài liệu WBS09 và WBS06 ghi review store chung/receipt còn thiếu trên VPS tại lần kiểm trước. Không khẳng định DB hiện tại vẫn thiếu vì chưa truy vấn live ngày 05/11. Cần Vũ/Hưng cung cấp receipt triển khai và mẫu chunk → review → hai DB → retrieval, đủ ba nhóm quan hệ.
4. **Chưa thấy báo cáo full-load News đủ điều kiện nghiệm thu trong tài liệu đã khảo sát.** Cần nhận báo cáo WBS16 và receipt mẫu WBS09.5, phân biệt có runner/extractor với đã chạy toàn bộ News và đối chiếu xong.
5. **Bằng chứng bàn giao còn phụ thuộc file local.** Gói 46 ca, batch duyệt và kết quả chi tiết nằm ở backend/.tmp, bị Git ignore. Có file tại máy này không đồng nghĩa người nhận đã nhận được. Cần gói bàn giao có manifest/hash hoặc cách tái tạo, không kèm thông tin kết nối bí mật.

## Việc làm tiếp theo, theo ưu tiên

1. **05/11 — Nhân:** cập nhật bảng task theo phạm vi trên; gửi gói 46 ca và manifest cho Huyền qua kênh nhóm đang dùng, yêu cầu quyết định gắn original_candidate_id. Không chờ 46 ca được duyệt hết mới chuẩn bị benchmark.
2. **05/11 — Nhân + Huyền:** chốt một bộ gold nhỏ trước, bao phủ VECTOR/GRAPH/BOTH, ba nhóm quan hệ và ca lỗi. Mỗi ca có scope, version, quan hệ/chiều/thời gian, source/chunk ID, đáp án và người duyệt. Ca chưa có dữ liệu ghi NOT_READY, không tính pass.
3. **05–06/11 — Nhân:** làm runner B1/B2 và lưu JSONL từng câu trên cùng corpus/model/cấu hình. Đo route, đúng thực thể/chiều/thời gian, chất lượng evidence/citation, lỗi từng nhánh và latency; giữ câu trả lời để phân tích ca sai. Tách cold start khỏi đo khi đã warmup. Không gán B2 tốt hơn B1 trước khi có số liệu.
4. **Song song — Huyền/Vũ/Hưng/Quân:** Huyền xác minh nhánh Graph Viewer và E2E; Vũ/Hưng bàn giao review-store receipt cùng graph chức vụ/sự kiện đủ điều kiện; Quân bàn giao BOTH và answering có nguồn. Nhân cung cấp contract/output GRAPH, không cần tự làm lại phần của mọi người.
5. **07–08/11 — Nhân + Huyền:** chạy benchmark thật, kiểm tra citation qua giao diện, hồi quy B1, nhận báo cáo full-load WBS16; tổng hợp ca lỗi, mức ảnh hưởng, owner và giới hạn. Chỉ đóng WBS17 khi cả benchmark của Nhân và E2E của Huyền đạt.

Nếu chưa có dữ liệu đủ ba nhóm/tuyến vào 08/11, bàn giao phần đã đo kèm danh sách NOT_READY và phụ thuộc cụ thể; không ghi toàn bộ WBS17 là hoàn thành.

## Tình trạng Git và khả năng bàn giao

Commit `398acf6` đã chứa kết nối GRAPH có kiểm nguồn và tài liệu bàn giao; câu trong tài liệu 04/11 nói còn working tree đã cũ đối với phần này. Commit `2c98109` bổ sung rule bảng/registry r2. Hiện còn thay đổi chưa commit ở script extractor, rule bảng, relation_extractor, test bảng, tài liệu rule bảng, history và tài liệu 46 ca mới. Test 246 ca ở trên chạy trên working tree hiện tại, không bảo đảm checkout chỉ từ HEAD có cùng toàn bộ kết quả cải tiến. Cần review và commit phần đã thống nhất trước khi nhóm tái lập bằng Git.

Lượt đánh giá này không sửa mã nghiệp vụ, không duyệt ứng viên, không ghi database, không gửi thông điệp cho thành viên khác, không commit/push. Chỉ tạo báo cáo này và chạy kiểm tra local.
