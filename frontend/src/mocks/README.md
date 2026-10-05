# Shared UI preview

Chạy trong `frontend/`:

```powershell
npm run dev
```

Mở `http://localhost:5173/?ui=components`. Trang này chỉ xuất hiện khi chạy Vite ở chế độ development. URL `/` vẫn mở giao diện hiện tại.

Chọn **Bộ dữ liệu mẫu** trên trang để xem bảng tương ứng: doanh nghiệp (10 dòng), watchlist (4), sources (6), traces (7), corpus (6) và cấu hình (4). Gõ từ khóa hoặc chọn trạng thái để thử FilterBar. Bốn nút `success`, `empty`, `error`, `loading` cho phép kiểm tra từng trạng thái bảng. `loading` được giữ lại để nhìn rõ Skeleton.

`userMock.js` chứa dữ liệu User, `adminMock.js` chứa dữ liệu Admin. Mỗi bộ có `success`, `empty`, `error`; các mã và trạng thái Admin được đối chiếu với `interface/admin/js/mockData.js`. `componentMock.js` chứa menu và hàm `getMockRows()` dùng riêng cho trang thử. Tất cả đều là dữ liệu minh họa, không phải kết quả từ backend.

Một page sau này có thể dùng shared UI như sau:

```jsx
import { DataTable, FilterBar, StatusBadge } from "../../shared/ui/index.js";
import { getSources } from "./api.js";

// columns và filters là cấu hình của riêng page.
// Page giữ rows, loading, error bằng useState rồi truyền cho DataTable.
```

Đặt dữ liệu mẫu của mỗi page trong `pages/<ten-page>/mock.js`, hàm lấy dữ liệu trong `pages/<ten-page>/api.js`. Lúc làm UI, `api.js` trả Promise từ mock. Khi backend FastAPI sẵn sàng, chỉ thay phần thân hàm trong `api.js` bằng `fetch` hoặc `shared/api/client.js`; props và JSX của page vẫn giữ nguyên. Không đưa API key hoặc mật khẩu vào frontend.

`Sidebar` nhận `groups`, `activeId`, `onSelect` từ parent. Parent tự quyết định chuyển page sau này; shared Sidebar hiện chỉ hiển thị menu và trạng thái active.
