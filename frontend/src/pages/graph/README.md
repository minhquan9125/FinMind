# WBS15 — Graph Viewer và bằng chứng

Trang /graph gọi trực tiếp API riêng của WBS09 theo docs/sprint4/WBS15-graph-viewer-api-contract.md (graph-viewer-v1); không gửi câu hỏi qua Chat.

- GET /api/graph/versions: chọn phiên READY (mặc định phần tử đầu do API trả).
- GET /api/graph/entities: tự tải tối đa 50 thực thể của phiên đang chọn vào dropdown; chọn thực thể để xem graph. Tìm theo mã, ID hoặc tên và lọc loại khi nhiều kết quả; q bỏ trống là liệt kê trong phiên, không liệt kê chéo phiên.
- GET /api/graph/neighborhood: một phiên + một root, lọc loại/ngày, 1–2 hop, limit 1–100.
- GET /api/graph/relations/{id}?graph_version_id=...: bấm cạnh để lấy đầy đủ extraction, thời gian, review và evidence.

api.js dùng VITE_API_BASE_URL (mặc định cùng origin, Vite proxy /api tới localhost:8000), gửi Bearer token bằng authorization.js. Không đổi cấu hình BE/Chat.

## Mở từ Chat

/graph?graph_version_id=GRAPH-ID&entity_id=ENTITY-ID&relation_id=RELATION-ID

Giữ đúng phiên, root và bộ lọc khi tải; không tự đổi phiên của deep link. Nếu relation không có trong kết quả, báo rõ, không mở cạnh khác thay thế. ID được encode bằng URLSearchParams/encodeURIComponent.
Có thể truyền hops, limit, relation_type (lặp được), from, to. Đổi phiên/root/bộ lọc sẽ hủy request cũ và bỏ lựa chọn cạnh cũ; phản hồi cũ không được render.

## Hiển thị

GraphCanvas dùng Neovis.js (Neo4j-contrib): node tròn, bố cục force-directed, kéo/thả và zoom. Neovis nhận dữ liệu từ API qua public datasets; dataFunction không mở driver Bolt, FE không chứa thông tin đăng nhập Neo4j. Nhãn rút gọn nằm trong node; hover hoặc chọn node xem tên đầy đủ. Cạnh khác thời điểm vẫn giữ ID riêng và nhãn ngày.

Tái sử dụng GraphCanvas và giới hạn hai hop. Hai cạnh khác ID/thời điểm không gộp. Drawer tải chi tiết riêng và đối chiếu chiều, thời gian, thuộc tính, review với cạnh trên graph. Giữ nguyên quote và locator. PDF chỉ thêm #page từ open.page backend cung cấp; News mở URL web, không dùng locator.page làm trang PDF.
open.status=UNAVAILABLE hoặc URL không an toàn: không tạo link, vẫn giữ quote/locator. URL ngoài có thể đòi quyền hoặc ngừng hoạt động sau khi backend trả về; UI không coi AVAILABLE là kiểm chứng HTTP nguồn ngoài.

Rỗng, nhiều kết quả/truncated, 409, 503/504, không tìm thấy thực thể/quan hệ và lỗi nguồn có trạng thái riêng. 401/403 chuyển về đăng nhập. Không lấy fixture thay lỗi API.

## Cập nhật dữ liệu và phiên nhân sự

Viewer đọc dữ liệu trực tiếp qua API, không ghim ID phiên hoặc danh sách quan hệ. Khi trang đang hiển thị, tự tải lại mỗi 30 giây và khi quay lại tab; có nút **Cập nhật ngay**. Giữ nguyên phiên, root, bộ lọc và node đang mở. Phiên READY mới xuất hiện trong danh sách để người dùng chọn; không tự đổi phiên của deep link. Fixture không chạy polling.

Ngoài GraphVersion/GraphEntity/GRAPH_RELATION, hỗ trợ contract `person-source-claims-v1` của SourcePersonGraphVersion/SourcePersonOccurrence/SourcePersonCompany/SOURCE_PERSON_CLAIM. Phiên này có nhãn **Nhân sự theo nguồn**, scope `SOURCE_DOCUMENT_ASSERTIONS`, review `SOURCE_REVIEWED`; giữ từng lần xuất hiện của tên người, chiều quan hệ và cả sáu loại chức vụ/sự kiện. Không gộp danh tính hoặc khẳng định đương nhiệm. Năm báo cáo không thay ngày hiệu lực; truy vấn có bộ lọc ngày không nhận các claim chưa xác nhận ngày.

Người nạp dữ liệu cần ghi vào cùng Neo4j mà backend kết nối, đúng một trong các contract trên và công bố phiên `READY`. Push code lên Git không tự nạp dữ liệu vào DB. Schema/contract mới cần bổ sung adapter; thêm bản ghi hoặc phiên theo contract đã hỗ trợ không cần nối lại giao diện.

## Fixture và kiểm tra

Chỉ bật fixture khi có query:
- /graph?fixture=success
- /graph?fixture=empty|error|loading|truncated|source-unavailable

mock.js là fixture UI minh họa theo contract, có Company/Person/Event, cạnh song song, PDF và News; không giả là dữ liệu Neo4j đã nghiệm thu hoặc gói 13 ca thật của Nhân. Không tạo thêm file fixture.
Mặc định /graph luôn gọi API thật.

Từ frontend:
node --test src/pages/graph/graphModel.test.js
npm run build

Test kiểm tra token/query, contract, phiên/phạm vi, extraction, quote/locator, cạnh song song, rỗng/truncated, lỗi, hủy request và timeout. Nghiệm thu Neo4j/dữ liệu thật còn phụ thuộc phiên READY backend đã triển khai.
