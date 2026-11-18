# Kiểm thử GRAPH qua Web Chat — 18/11/2026

Code kiểm thử: `huyen-test`, commit `03bae48d32355c9d5f467df07bc60cd9831d9063`.

## Tiêu chí nghiệp vụ

1. Có quan hệ phù hợp và nguồn hợp lệ: trả lời có bằng chứng, đúng phạm vi câu hỏi.
2. Không có quan hệ phù hợp: báo không có dữ liệu; không tự tạo quan hệ.
3. Neo4j không kết nối được: báo lỗi truy xuất; không giả thành dữ liệu rỗng.
4. Trace phải chứng minh adapter thực sự truy vấn Neo4j.

## Phương pháp và giới hạn

Gửi HTTP qua FastAPI ASGI tới `POST /api/research/chat/sessions` và `POST /api/research/chat/sessions/{id}/messages`. Dùng engine do `research_chat.get_store()` tạo, cùng planner, graph adapter, reader và nguồn PostgreSQL thật. Instrument reader bằng wrapper chuyển nguyên lời gọi tới reader thật; lưu tên phương thức, số dòng và loại lỗi, không thay kết quả.

PostgreSQL dùng `default_transaction_read_only=on`. SessionStore tạm thay phần lưu lịch sử; dependency owner được thay bằng UUID test. Gemini được tắt để tách kiểm thử truy xuất khỏi sinh câu trả lời. Không chạy trình duyệt, JWT thật hoặc lưu lịch sử PostgreSQL trong đợt này. Intent classifier không khả dụng ở môi trường kiểm thử và engine dùng đường dự phòng hiện có; không coi đây là xác nhận chất lượng classifier. Không sửa code sản phẩm, corpus, graph hoặc tunnel.

Lỗi Neo4j được gây bằng driver thật tới một cổng loopback riêng không có dịch vụ, không ngắt Neo4j đang dùng. Lưu `ServiceUnavailable` ở reader và phản hồi đã che chi tiết ở chat.

## Kết quả đã xác nhận

- PostgreSQL và Neo4j đều kết nối được.
- Web Chat gọi graph thật: trace `graph_calls=1` đi kèm các lời gọi `versions`, `entities`, `neighborhood`, `nodes` đã hoàn tất. Không dùng riêng bộ đếm để kết luận.
- FPT và TCB có cạnh graph nhưng nguồn không replay được trong corpus hiện tại: `GRAPH_SOURCE_NOT_IN_ACTIVE_CORPUS`. Web Chat chuyển tìm báo cáo (`vector_calls=1`) và hết thời gian chờ, trả `GRAPH_CHAT_TIMEOUT`. Chưa chứng minh được ca trả lời thành công có nguồn hợp lệ.
- VCB / Chủ tịch: adapter nguồn trả rỗng trong probe trực tiếp; qua Web Chat tìm báo cáo tiếp rồi timeout. Vì vậy câu hỏi này chưa đạt kỳ vọng phản hồi rỗng rõ ràng. Timeout thuộc bước fallback; không có bằng chứng rằng truy vấn Neo4j bị timeout.
- Neo4j lỗi: reader thực sự phát sinh `ServiceUnavailable`; chat trả `SYSTEM_UNAVAILABLE / GRAPH_CHAT_UNAVAILABLE`, không trả `NO_DATA` và không tạo câu trả lời.
- G06, “Theo tin tức, ai là Chủ tịch VCB?”: adapter thật hoàn tất với 0 quan hệ/0 bằng chứng; chat trả `NO_DATA / GRAPH_NO_VERIFIED_RELATIONS`, `graph_calls=1`, `vector_calls=0`. Ca này đạt ranh giới rỗng so với lỗi truy xuất. Trace vẫn gán topic MULTI_HOP và source BCTC; không dùng kết quả PASS này để khẳng định planner hiểu đúng toàn bộ phạm vi nguồn.
- G05, câu hỏi đối tác VCB theo tin tức, là ca thăm dò: planner chọn EVENT_IMPACT / BCTC, không lọc loại quan hệ, và vướng lỗi nguồn. Không có oracle xác nhận quan hệ đối tác thực tế là rỗng, nên đánh dấu REVIEW, không tính là ca rỗng đã được xác nhận.

## Lỗi bổ sung từ kiểm thử độc lập

Chạy `test_vu_graph_independent_retest.py` cùng `test_web_chat_router.py`: **43 passed, 2 failed**. Hai ca lỗi dùng fixture biệt lập, không phải hai lỗi đã quan sát từ dữ liệu thật:

1. Hỏi công ty con của FPT nhưng cạnh `OTHER --HAS_SUBSIDIARY--> FPT` vẫn được chấp nhận.
2. Hỏi công ty liên kết của FPT nhưng cạnh `OTHER --HAS_ASSOCIATE--> FPT` vẫn được chấp nhận.

Nguyên nhân tại bước chọn facts: quan hệ có một đầu khớp ticker được nhận nhưng chưa kiểm tra FPT có phải chủ thể theo chiều nghiệp vụ. Cần kiểm tra chiều theo từng loại quan hệ; không áp một quy tắc chung cho `HOLDS_ROLE`, vì vai trò nhân sự có chiều người → công ty.

Khi tích hợp bộ kiểm thử vào backup-demo, hai ca trên được đánh dấu `xfail(strict=True)` để ghi nhận lỗi đã biết. Kết quả FAIL trong báo cáo/Excel là bằng chứng trước khi đánh dấu, vẫn được giữ nguyên. XFAIL không có nghĩa chức năng đã được sửa; nếu ca hết lỗi, strict XPASS yêu cầu cập nhật dấu này.

## Bàn giao và kiểm thử lại

Chưa đủ căn cứ đánh dấu toàn bộ chức năng đạt nghiệm thu. Cần đối chiếu source/chunk/hash của graph với corpus phục vụ, xử lý hoặc làm rõ hành vi fallback khi graph rỗng, sửa lỗi chiều quan hệ rồi chạy lại ca có dữ liệu và ca rỗng. Không bỏ qua kiểm tra nguồn để làm ca xanh.

Bằng chứng được giữ: `outputs/vu_graph_retest_20261118/live-source-run02.json`, `web-regression.xml`, `final-run/results.json` và Excel tổng hợp trong `final-run`. Lượt final giữ G01–G05 từ web-run02 và bổ sung G06; không phải sáu ca được chạy lại cùng một lượt. Các thư mục chạy trung gian đã được dọn, trace từng ca vẫn nằm đầy đủ trong JSON cuối. Kết quả: 2 PASS, 3 FAIL theo đầu ra nghiệm thu, 1 REVIEW. Hai ca dữ liệu lỗi nguồn trước rồi fallback timeout, không phải bằng chứng Neo4j mất kết nối. `baseline.xml` là lượt kiểm trước với 99 passed và 31 subtests passed, không cộng gộp với lượt hồi quy mới vì có ca trùng.

Bộ kịch bản nháp chưa thực thi đã được dọn; không tính vào số ca đã chạy.

Chạy lại từ thư mục repo với tunnel mở:

```powershell
.\.venv\Scripts\python.exe backend/scripts/run_vu_graph_web_retest.py web-run03
.\.venv\Scripts\python.exe backend/scripts/finalize_vu_graph_report.py web-run03
```

Script giữ nguyên kết quả cũ và yêu cầu tên thư mục lượt chạy mới.
