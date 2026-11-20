# Web Chat → Hybrid Router → Neo4j

Ngày sửa: 08/11/2026. Nhánh làm việc: `backup-demo`.

## Hành vi

API `/api/research/chat/sessions/{session_id}/messages` nay dùng cùng DecisionEngine để nhận diện GRAPH/BOTH trước luồng Chat cũ. Nhân sự, HĐQT, chức vụ, cổ đông và các quan hệ được định tuyến sang reader Neo4j; không còn tự đổi thành tìm NEWS khi graph lỗi hoặc không có kết quả.

- GRAPH: đọc quan hệ từ Neo4j rồi đối chiếu các chunk chứng minh trên PostgreSQL. Việc đọc chunk theo ID không tính là tìm kiếm Vector/BOTH.
- BOTH: thực hiện graph trước, sau đó truy xuất nội dung theo mã đã xác định; bằng chứng hai nhánh phải cùng corpus/index. Chưa có ánh xạ ticker tin cậy cho công ty liên quan thì trả `GRAPH_COMPANY_MAPPING_REQUIRED`, không suy mã từ tên.
- VECTOR: giữ pipeline tài chính/giá/tin hiện có. Không khởi tạo hoặc gọi Neo4j cho tuyến này. Classifier lỗi không làm ngừng pipeline tài chính cũ.
- Context router được lưu trong `_hybrid_context`, dùng tiếp cho lượt hỏi sau. Câu xin nguồn dùng kết quả đã lưu, không truy vấn lại graph.
- Kết quả có `hybrid_router.route/tasks/graph_calls/vector_calls` để xác minh đường chạy.

## Kiểm tra nguồn

Dùng GraphViewerReader chỉ đọc các phiên READY. Quan hệ `SourcePersonOccurrence` vẫn là khẳng định trong phạm vi tài liệu, không trở thành danh tính toàn cục hoặc chức vụ hiện tại. Giữ trạng thái duyệt, loại quan hệ và năm nguồn; lọc Chủ tịch không bao gồm Phó Chủ tịch, nhóm HĐQT không tự bao gồm mọi chức vụ điều hành.

Graph đang có tham chiếu tới phiên corpus cũ. Bridge đọc lại nguồn gốc qua PostgresSourceReader trước, kiểm tra evidence/locator/quote/hash; chỉ nối sang chunk ở corpus phục vụ hiện tại khi:

1. Corpus FROZEN, index ACTIVE, chunk chưa superseded và document membership/hash hợp lệ.
2. Định danh tài liệu nguồn gốc, source table và source ID trùng.
3. Chunk content hash, toàn bộ văn bản và source SHA của hai phiên trùng.
4. Có đúng một chunk phù hợp trong phiên đang phục vụ.

Không sửa bản ghi graph, đổi trạng thái duyệt, tạo bằng chứng hoặc thêm dữ liệu. Không khớp thì dừng tại lỗi nguồn. `source_bindings` trong các quan hệ trả về ghi lại ID chunk cũ/mới cùng hash.

Evidence pack 1.1 đi vào bộ sinh/kiểm tra trích dẫn B1 sẵn có; mapping annual_reports → BCTN được bổ sung cho bằng chứng graph. Link tài liệu lấy từ source_url đã kiểm tra trên giao diện, giữ nguyên locator gốc.

## Xác minh

- Test qua chính API gửi tin nhắn ASGI bằng owner/provider/source cô lập: GRAPH không gọi retriever NEWS; follow-up giữ tuyến; xin nguồn không truy xuất lại; BOTH kiểm tra corpus/index; graph lỗi/timeout/hash sai không chuyển sang NEWS.
- Probe nguồn thật, không gọi Gemini: `backend/scripts/verify_web_chat_graph.py`.
- Kết quả ở `outputs/web-chat-router-20261108/live-source-smoke.json`: Chủ tịch FPT và Chủ tịch TCB đều có 1 quan hệ/1 chunk verified; danh sách HĐQT FPT có 7 quan hệ/2 chunk verified. Đây là số bản ghi theo nguồn tìm được, không phải chứng nhận toàn bộ HĐQT hiện tại.
- Câu Chủ tịch HĐQT VCB hiện NO_DATA trong graph được kiểm tra. Không bổ sung tên/chức vụ bằng suy đoán trong lần sửa này.
- Frontend: 78 test đạt; build thành công, còn cảnh báo kích thước bundle graph có sẵn.
- Hồi quy rộng: **2488 passed, 13 skipped**, xem `outputs/web-chat-router-20261108/regression.xml`. Bỏ qua riêng `backend/tests/test_wbs16_event_extractor.py` vì lỗi import `parse_dates_extended` đã có trước sửa; các test skipped không được tính là đạt.
- Sau chỉnh giới hạn Graph Viewer và ánh xạ ticker của graph chính thức: **85 test liên quan đạt**, gồm cả ca global graph không lưu ticker trong aliases (`final-adapters.xml`). Đây là tập kiểm tra có phần chồng với hồi quy rộng, không cộng hai con số thành tổng test riêng biệt.

## Chạy kiểm tra

Từ gốc repository, sau khi mở hai tunnel:

```powershell
.\.venv\Scripts\python.exe backend/scripts/verify_web_chat_graph.py
```

Khởi động lại backend để factory Chat nhận bridge mới:

```powershell
cd backend
..\.venv\Scripts\python.exe scripts/run_demo_backend.py
```

Trên web nên mở cuộc hội thoại mới và thử:

1. `Ai là Chủ tịch FPT?`
2. `Liệt kê các thành viên hội đồng quản trị FPT.`
3. `Có thể liệt kê ra không?`
4. `Vậy ai là phó chủ tịch?`
5. `Nguồn đâu?`

Kiểm tra `hybrid_router.route`, graph_calls/vector_calls và mở nguồn đã dùng, không chỉ xem có văn bản trả lời hay không.

## Giới hạn còn lại

Lượt đầu gửi bằng chứng thật sang Gemini bị bộ duyệt tự động từ chối. Sau đó người dùng xác nhận **Cho phép kiểm thử Gemini** cho hai câu FPT/TCB ngày 08/11/2026. Đã nghiệm thu trực tiếp qua service Chat mới với Neo4j/PostgreSQL/Gemini thật:

| Câu hỏi | Kết quả theo nguồn | Thời gian lần chốt | Tuyến |
|---|---|---|---|
| Ai là Chủ tịch FPT? | Trương Gia Bình, citation hợp lệ | 4,66 giây | GRAPH; 1 graph / 0 vector |
| Ai là Chủ tịch TCB? | Hồ Hùng Anh, citation hợp lệ | 4,30 giây | GRAPH; 1 graph / 0 vector |

Model thực trả về: `gemini-3.5-flash-lite`. Dùng corpus `a530bc8a-e0f6-5003-9b9b-9c61b24dbcf1`, index `315dfac5-f8af-4eda-bc05-20a252a03ef9`. Kết quả chi tiết ở `outputs/web-chat-router-20261108/live-gemini-answer-smoke.json`. Không ghi lịch sử người dùng hay thay đổi dữ liệu nguồn/graph.

Phát hiện câu TCB dùng “tới nay” của nguồn lịch sử: thêm bước neo cách diễn đạt này về **thời điểm tài liệu ghi nhận**, giữ nguyên support_quotes và số/ngày gốc. Bộ kiểm tra temporal ban đầu bắt nhầm cụm “hiện tại” trong câu cảnh báo phủ định; đã sửa checker và đánh giá lại phản hồi đã lưu offline, không sửa nội dung phản hồi hoặc gọi thêm Gemini cho việc sửa checker. Sau sửa trình bày: 51 test Chat/grounding/persona liên quan đạt. Các kiểm tra này không thay thế xác minh B3 hay xác nhận chức vụ đang đương nhiệm.

Đây là nghiệm thu **hai câu hỏi**, không phải tỷ lệ đúng toàn bộ Chat. API gửi tin nhắn đã có test ASGI với owner/provider cô lập; phần Gemini thật kiểm tra trực tiếp service, chưa phải thao tác đăng nhập trên trình duyệt. Script `backend/scripts/verify_web_chat_graph.py` vẫn chỉ đối chiếu nguồn nội bộ, không có nhánh gọi Gemini.

Lần sửa này chưa xử lý budget dùng chung 20 lượt, deadline sinh AI 600 giây, refresh token Chat, toàn bộ trang mock, câu tóm tắt lịch sử hoặc toàn bộ truy vấn nội dung BCTN thuần Vector. Câu hỏi chức vụ có thêm BCTN để chỉ nguồn đi GRAPH, nhưng điều đó không có nghĩa mọi câu hỏi BCTN đã được hỗ trợ.
