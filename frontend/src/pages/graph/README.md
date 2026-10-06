# Graph Viewer mẫu

Chạy `npm run dev` trong `frontend/`, mở `/graph` hoặc `/graph?company=VCB`. Chọn root, bấm **Mở rộng từ node đang chọn**, rồi bấm một node mới để mở tiếp. Node ở hop 2 không thể mở rộng. Bấm đường nối để xem provenance mẫu trong Drawer.

Thử `/graph?fixture=empty`, `/graph?fixture=error` và `/graph?fixture=loading`. Trang chỉ dùng fixture tại `mock.js`; `api.js` là chỗ sau này thay bằng lời gọi FastAPI. `graphModel.js` tính khoảng cách từ root và giới hạn node hiển thị ở hai hop; Cytoscape.js tự làm layout, pan và zoom. Khi nối Neo4j, backend vẫn phải kiểm giới hạn hop.

Chạy `node --test src/pages/graph/graphModel.test.js` từ `frontend/` để kiểm tra giới hạn hai hop, provenance mẫu và trạng thái empty/error.

Fixture dùng tên node/quan hệ đang có trong `backend/src/graph/graph_store.py`. Neo4j hiện lưu `source`, `source_file` trên báo cáo và `json_pointer` trên quan sát/giá, không lưu provenance như thuộc tính của mọi quan hệ. Vì vậy `edge.provenance` ở đây là dữ liệu hiển thị mẫu được tổng hợp từ bản ghi liên quan, **không phải schema edge Neo4j**. `mock://` không phải URL hay tệp nguồn thật.
