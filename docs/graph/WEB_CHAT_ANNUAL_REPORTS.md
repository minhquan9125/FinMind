# Web Chat đọc BCTN — 08/11/2026

Đã bỏ chặn `SOURCE_NOT_AVAILABLE` khi người dùng nêu BCTN/báo cáo thường niên. Thay đổi nằm trong backend chính, không cần chạy một backend riêng.

## Luồng đã nối

- Câu hỏi nội dung BCTN chọn `source_type=BCTN`, `doc_type=ANNUAL_REPORT`, không chuyển sang NEWS hoặc đòi mã chỉ tiêu tài chính của BCTC.
- Câu hỏi chức vụ/quan hệ vẫn dùng Hybrid Router/Neo4j theo contract hiện có. Bỏ chặn BCTN không tự bổ sung các quan hệ còn thiếu trong graph.
- Câu BCTN có nhắc “tin”, “công bố”, “PDF” không bị nhánh AdminNews chọn nhầm một bài NEWS.
- Dùng lại Vector/BM25/RRF hiện có và embedding đã lưu. Không chia chunk, tạo embedding hoặc nạp lại source vào DB.
- Lọc theo `locator.reporting_year`; không dùng ngày công bố làm năm báo cáo. BCTN mới nhất lấy năm thực có trong corpus theo từng công ty, không suy từ năm hiện tại.
- Chuyển sang BCTN loại bỏ metric/kỳ BCTC còn trong context. Hỏi tiếp một năm giữ chủ đề BCTN đã hỏi; đổi sang BCTC rõ ràng quay lại luồng tài chính.
- Đọc lại chunk được chọn qua annual_source_reader; kiểm tra corpus FROZEN/index ACTIVE, membership/hash, document alias, PDF page và locator. Lệch công ty/năm thì từ chối bằng chứng.
- Với corpus do `admin_shared_index.merge_shared` tạo: xác minh alias theo source_index_version_id của manifest đã ghim và chunk ID theo đúng công thức sao chép của producer. Phải tìm được duy nhất một chunk cha trong corpus FROZEN/index ACTIVE, cùng document/hash/locator/membership và cùng nguồn gốc release. Không chấp nhận alias cũ chỉ vì nó tồn tại.
- Trả bằng chứng BCTN trong evidence pack 1.1 để bộ answering/trích dẫn hiện có sử dụng. Đường dẫn tài liệu và trang PDF giữ từ nguồn.

## Cache

Cache lexical nâng lên **v4** để thay nhãn kỳ cũ bằng năm báo cáo và đọc đúng locator JSON ở cả dạng object/dạng text từ PostgreSQL. Cache v2/v3 không được tái sử dụng; backend sẽ dựng lại một lần. Bản cache tạo trong lượt thử v3 có năm BCTN rỗng cũng bị vô hiệu hóa, không sửa dữ liệu nguồn để chữa lỗi cache.

Khởi động lại backend sau khi cập nhật code và đợi warmup ready trước khi demo. Không chạy đồng thời backend cũ/mới dùng chung cache.

## Câu hỏi thử

1. `Tóm tắt chiến lược FPT trong báo cáo thường niên năm 2025.`
2. `BCTN BID năm 2025 nói gì về quản trị rủi ro?`
3. `Theo BCTN VCB năm 2025, định hướng phát triển là gì?`
4. Hỏi tiếp: `Còn năm 2024?`
5. `BCTN FPT mới nhất nói gì về chiến lược?`

Thiếu tài liệu đúng năm hoặc không có đoạn chứng minh thì trả thiếu bằng chứng; không lấy năm khác để thay thế.

## Xác minh

- Test API gửi tin nhắn: câu hỏi BCTN đi Vector, không gọi Graph, trả citation BCTN qua provider cô lập.
- Test năm báo cáo khác năm công bố, đổi source/context, metadata JSON text, cache cũ, replay trang sai năm, nguồn sai công ty/năm và gộp chunk trùng giữa Graph/Vector.
- `backend/scripts/verify_web_chat_annual.py`: kiểm tra RAG/nguồn thật của 10 công ty, không gọi Gemini. Kết quả tại `outputs/web-chat-annual-20261108/live-source-smoke.json`.
- Dữ liệu thật: **10/10 công ty** BID, CMG, CTG, ELC, FPT, ICT, ITD, MBB, TCB, VCB; mỗi công ty trả 5 bằng chứng BCTN 2025, đúng symbol/reporting_year/pdf_page và qua replay hash nguồn. Thời gian truy xuất sau warmup **4,91–5,84 giây/câu**. Đây là nghiệm thu truy xuất và tính toàn vẹn bằng chứng, không phải chứng nhận mọi câu trả lời AI đều đúng.
- Corpus kiểm tra: `a530bc8a-e0f6-5003-9b9b-9c61b24dbcf1`; index `315dfac5-f8af-4eda-bc05-20a252a03ef9`.
- Hồi quy rộng: **2580 passed, 13 skipped, 1 failed**, xem `outputs/web-chat-annual-20261108/regression.xml`. File WBS16 lỗi import đã có trước được tách riêng; skipped không tính là đạt. Ca lỗi là `JourneyTests.test_caller_cancellation_and_late_response` của orchestrator fixture, dùng deadline 1 ms: lượt chạy riêng đạt nhưng chạy cả bộ có lỗi lặp lại; không coi cả suite đã xanh và chưa sửa deadline trong task BCTN này.
- Kiểm thử tập trung BCTN/Graph/Vector: 121 passed trước khi bổ sung kiểm tra alias kế thừa; 42 test reader/BCTN/Graph liên quan sau sửa alias đều đạt. Các tập có phần chồng nhau, không cộng thành tổng test riêng biệt.

Không gửi thêm bằng chứng BCTN sang Gemini trong lượt kiểm tra nguồn này. Phần sinh câu trả lời được kiểm tra bằng provider cô lập; kiểm thử Gemini thật trước đó chỉ áp dụng hai câu chức vụ FPT/TCB, không tính là nghiệm thu nội dung BCTN.

Khi bàn giao, áp dụng cùng thay đổi nối router ở `PUSH_WEB_CHAT_ROUTER_FILES.txt`; không chỉ lấy một file live_research.py rồi bỏ các dependency reader/contract/cache.
