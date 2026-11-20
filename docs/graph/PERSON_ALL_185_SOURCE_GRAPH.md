# Đối chiếu và nạp đủ 185 quan hệ theo nguồn

Ngày 04/11/2026 đã rà toàn bộ 185 bản được báo cáo WBS06 chấp nhận nội dung. Không loại bản nào trong 185; hai bản REJECTED trong tập gốc 187 vẫn giữ nguyên lịch sử. Kết quả đã nạp Neo4j và đọc lại đủ 185 bản của 10 công ty.

Phiên nguồn: 8db2d940-c0c1-5743-87d4-5a952429da3b. Lưu dưới SourcePersonGraphVersion, SourcePersonOccurrence, SourcePersonCompany và SOURCE_PERSON_CLAIM. Đó là graph các phát biểu mà nguồn tài liệu ghi nhận, không phải một registry toàn cục đã gộp mọi người. Phiên READY của hai quan hệ TCB theo WBS06/WBS09 trước đó vẫn có 2 cạnh GRAPH_RELATION.

## Kết quả theo công ty

| Công ty | Quan hệ theo nguồn |
|---|---:|
| BID | 29 |
| CMG | 9 |
| CTG | 36 |
| ELC | 15 |
| FPT | 8 |
| ICT | 5 |
| ITD | 11 |
| MBB | 26 |
| TCB | 31 |
| VCB | 15 |
| Tổng | 185 |

185 là số bản ghi quan hệ. Một người có thể xuất hiện nhiều lần, nhiều chức vụ, nhiều nguồn. Mỗi SourcePersonOccurrence giữ ID theo lần xuất hiện nguồn, không gộp chỉ vì trùng tên; không khẳng định có 185 người khác nhau.

## Những phần đã sửa

- Lỗi CRLF khi đọc báo cáo khiến dấu chấm kết thúc chức vụ bị giữ lại; sửa parser và thêm test Windows newline.
- Tách đúng dòng của người, giữ đoạn nguồn và offset nguyên bản. 162 bản khớp chức vụ trực tiếp hoặc alias rõ; 16 bản dùng cả tiêu đề nhóm và dòng tên; 3 bản giữ chứng cứ ô bảng xuống dòng; 1 bản chú thích lỗi OCR điêu hành/điều hành theo kết quả source review.
- Ba chức danh web chỉ ghi “Thành viên độc lập” hoặc “Phó Chủ tịch” được giữ đúng mức nguồn ghi, không thêm HĐQT vào phát biểu mới. Giá trị cũ còn trong original_position và ghi chú sửa.
- Một bản Đặng Thị Việt Hà đổi APPOINTS sang HOLDS_ROLE: roster chứng minh chức vụ nhưng chưa chứng minh sự kiện bổ nhiệm. original_relation_type và origin_extraction_id giữ nguyên để đối chiếu.
- Chọn đúng lần xuất hiện trong cùng tài liệu khi một người có nhiều chức vụ/sự kiện. Giữ các predicate lịch sử/từ nhiệm/yêu cầu từ nhiệm khác nhau; không đổi đề nghị thành sự kiện đã xảy ra.
- Không đặt ngày hiệu lực giả từ năm báo cáo. Các trường thời gian không được khẳng định khi nguồn chưa đủ chi tiết. Report year chỉ là năm của tài liệu.

Đã replay nguồn trực tiếp cho cả 185 bản trên 276 chunk của audit đầy đủ. Bản xuất cuối dùng 237 đoạn trích nguyên văn ở 110 chunk, mỗi đoạn có document/corpus/index/hash/locator/offset. Báo cáo nguồn gốc cũng được kiểm SHA256 trước khi xuất. Bản sửa được tính lại bằng quy tắc xác định; thay vai trò/đoạn nguồn ngoài kế hoạch sẽ bị chặn.

## Giới hạn của phiên nguồn

Trạng thái SOURCE_REVIEWED áp dụng cho phát biểu trong tài liệu và bằng chứng, không tự nâng mọi danh tính thành resolved toàn cục. Lịch sử 126 PENDING và 2 REJECTED trong review store cũ giữ nguyên. Các bản sửa có ID phiên mới và ledger riêng, không ghi đè ứng viên bất biến hay phục hồi bản đã bị từ chối.

Graph nguồn được tách label và quan hệ khỏi GraphEntity/GRAPH_RELATION, nên chat dùng graph WBS09 hiện tại không tự dùng toàn bộ 185 bản như danh tính hoặc chức vụ hiện hành. Tích hợp truy vấn source graph vào chat là một bước riêng, phải trả rõ phạm vi nguồn và các hạn chế này.

## Lưu trữ và nghiệm thu

Ledger bất biến trong public.raw_payloads:

- payload_id: ace11ac9-567c-5403-bb5f-ec23ad7a8760
- source_uri: finmind:source-person-claim-ledger:8db2d940-c0c1-5743-87d4-5a952429da3b
- SHA256: 44adc6b82fea0ace2e9301e6e7aa6f8286accee5e943973d8781cc4889d648f4

Biên bản outputs/person-all-185-20261104/readback.json xác nhận đủ 185 ID gốc, tên, công ty, chức vụ/loại quan hệ sau sửa, chiều cạnh, quotes và hash. Chiều bổ nhiệm/miễn nhiệm là Company → Person. Source graph nạp nguyên tử và chỉ READY sau khi đối chiếu đủ tập ID và mọi thuộc tính; chạy lại cùng phiên không tạo bản trùng.

Các file cùng thư mục: live-source-audit.json, repairs.json, publish-dry-run.json, publish-receipt.json, readback.json và Xem_185_tren_Neo4j.cypher. Câu Cypher đầu tiên hiển thị đủ graph; câu sau thống kê theo công ty và liệt kê nguồn.

## Kiểm thử và thay đổi hiệu năng

Bộ 92 test mục tiêu đạt; thêm một test writer/reconcile đạt trong lượt kiểm 6 test source-claims. Sửa đọc nguồn theo lô và dùng cache chung trong cùng transaction, tránh đọc embedding và snapshot lặp lại. Prefetch chỉ nạp membership rows; source vẫn được replay/so hash riêng, không tự coi bản được cache là nguồn đã xác minh. Không commit/push các thay đổi.
