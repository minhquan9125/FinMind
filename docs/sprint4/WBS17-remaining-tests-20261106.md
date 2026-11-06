# WBS17 — kiểm thử bổ sung, không sửa code sản phẩm

Theo yêu cầu tiếp tục task test, chỉ thêm công cụ kiểm thử và hồ sơ kết quả.
Không sửa `backend/src` hoặc `frontend/src`, không đổi câu hỏi/gold để làm test đạt.

## Ứng dụng đã khởi động

- Frontend: http://localhost:5173 — HTTP 200.
- Backend: http://127.0.0.1:8000/api/health — HTTP 200.
- Proxy frontend `/api/health` — HTTP 200.
- `npm run build` frontend thành công (132 module). Lần thử trong sandbox
  gặp spawn EPERM; chạy lại ngoài hạn chế tạo tiến trình con đã build được,
  nên không ghi EPERM thành lỗi ứng dụng.
- Collector thị trường tự động tắt bằng `FINMIND_LIVE_ENABLED=0` trong tiến trình
  backend của phiên kiểm thử; không sửa file cấu hình chung.
- `research_chat_live=true`, router LIVE, retrieval hybrid. Warmup tự động tắt
  theo cấu hình hiện có; model/cache có thể khởi tạo khi nhận câu hỏi đầu tiên.
- Không có khóa Gemini và chưa xác nhận Free Tier trong cấu hình hiện tại.
  Chưa chạy phép đo chất lượng câu trả lời sinh bởi LLM.
- Công cụ browser/native của phiên báo host/pipe unavailable. Không có ảnh hay
  thao tác UI được xác nhận, không đánh dấu E2E đạt. Graph Viewer helper vẫn
  trả mock theo code; cần Huyền/owner tích hợp kiểm tiếp trên trình duyệt thật.

## Kiểm thử 10 ca biên ở mức backend

Mỗi ca chạy 5 lần. Dùng câu hỏi nguyên văn trong Excel. Fixture được cô lập
trong tiến trình; alias trùng ánh xạ hai Company ID đã có trong bộ nguồn,
không sửa registry thật. Predictor dùng điểm cố định để kiểm policy/scope/
workflow, **không đo độ chính xác classifier đã huấn luyện**. Adapter fixture
không truy cập PostgreSQL/Neo4j. Kết quả không thay câu trả lời hay UI E2E.

| Ca | Kết quả backend | Phạm vi và phát hiện |
|---|---|---|
| TC_EDGE_01 | PASS_BACKEND 5/5 | Alias trùng hỏi lại, không gọi classifier/adapter |
| TC_EDGE_03 | PASS_BACKEND 5/5 | Câu thiếu công ty hỏi lại, không retrieval |
| TC_EDGE_04 | FAIL_BACKEND 5/5 | Policy chọn BOTH cho hai công ty; Excel kỳ vọng GRAPH. Cần owner router đối chiếu spec |
| TC_EDGE_05 | PASS_BACKEND 5/5 | Giữ năm 1900, fixture rỗng không trả fact. Chưa kiểm bộ lọc Neo4j thật trong ca này |
| TC_EDGE_14 | FAIL_BACKEND 5/5 | Câu tìm công ty con rồi nêu hoạt động chỉ tạo GRAPH, thiếu kế hoạch BOTH |
| TC_EDGE_15 | FAIL_BACKEND 5/5 | Cùng lỗi kế hoạch; timeout CONTENT kiểm độc lập hoạt động, nhưng không được coi luồng BOTH đã đạt |
| TC_EDGE_16 | PASS_BACKEND 5/5 | Graph NO_DATA khiến workflow dừng, không gọi content theo root |
| TC_EDGE_20 | PASS_BACKEND 5/5 | Quý 5 bị từ chối, hỏi lại trước classifier/adapter |
| TC_EDGE_21 | FAIL_BACKEND 5/5 | Câu hỏi hai quý chỉ còn `2025-Q2` trong scope/task, mất Q1 |
| TC_EDGE_22 | FOLLOWUP_REQUIRED 5/5 | Scope có cấu trúc chỉ còn 2026; câu gốc vẫn giữ 04/11/2026. Chưa kiểm callback/SQL giá, chưa kết luận sai ngày toàn luồng |

Timeout component dùng deadline 0,05 giây và delay fixture 0,25 giây. Nhánh
GRAPH bắt lỗi từ future của query cô lập; không chứng minh timeout driver/
mạng Neo4j. Nhánh CONTENT dùng `LiveContentAdapter` với coroutine chậm và
dependency Company ID fixture. Cả hai từ chối bịa dữ liệu khi timeout.
Không ngắt dịch vụ hoặc đổi timeout production.

Lượt chốt là `backend-probes03`. Giữ `backend-probes01/02` làm lịch sử điều
chỉnh fixture; ngưỡng mili giây quá ngắn ở lượt đầu có jitter lịch Windows,
nên không dùng lượt đó để chốt xử lý timeout. Không trộn các lượt thành
benchmark hiệu năng LIVE.

## TC_EDGE_24 trên backend ứng dụng đang chạy

Gọi nguyên câu hỏi Excel vào `/api/hybrid-router/run`:

| Trường hợp | Kỳ vọng | Thực tế | Kết quả |
|---|---|---|---|
| Không có bearer | 401/403 trước retrieval | HTTP 200 | FAIL_BACKEND |
| Bearer giả cố ý không hợp lệ | 401/403 trước retrieval | HTTP 200 | FAIL_BACKEND |

Đối chứng: `/api/research/chat/sessions` trả 401 cho cả hai trường hợp. Không
tạo session, không đăng nhập hoặc giả mạo tài khoản người dùng. Chưa kiểm
tài khoản hợp lệ nhưng thiếu role; không kết luận về proxy/deployment khác.

## Hồ sơ và trạng thái task

- `outputs/wbs17_remaining_tests_20261106/backend-probes03/`: 50 quan sát của
  10 ca component; 5 ca đạt kiểm tra đã chọn, 4 ca không đạt, 1 ca cần kiểm tiếp.
- `outputs/wbs17_remaining_tests_20261106/http-smoke01/`: health/proxy, đối
  chứng chat 401 và hai quan sát TC_EDGE_24 không đạt.
- `b1-answer-regression.xml`: 48 kiểm thử hồi quy offline về source/claim,
  citation, trình bày và scope/budget đạt. Không phải phép đo Answer thật
  cho 53 câu Excel, không gọi Gemini thật.
- Giữ nguyên kết quả 15 ca LIVE/150 lượt đo trước đó. Thêm kết quả component
  ở cột riêng trong Excel; không chép thành kết quả E2E hoặc thời gian B1/B2.
- Trong 38 ca chưa nghiệm thu toàn ca, 11 ca đã có thêm kiểm tra backend
  một phần; 27 ca còn lại chưa có lượt kiểm riêng theo định nghĩa Excel.
- WBS17 chưa hoàn thành: còn Answer/E2E, dữ liệu chức vụ/sự kiện, các fixture
  còn lại, đối chiếu nguồn/semantic và báo cáo full-load WBS16. Lỗi chuyển
  đúng owner theo bug log; task test không yêu cầu Nhân tự sửa tất cả lỗi.

Lệnh chạy lại (thư mục output phải mới):

```powershell
.\backend\.venv\Scripts\python.exe -m backend.scripts.wbs17_acceptance_probe `
  --workbook outputs/wbs17_nhan_huyen_20261106/SPRINT4_WBS17_NHAN_HUYEN_SHARED_20261106.xlsx `
  --output outputs/wbs17_remaining_tests_20261106/backend-probes-new

.\backend\.venv\Scripts\python.exe -m backend.scripts.wbs17_http_smoke `
  --workbook outputs/wbs17_nhan_huyen_20261106/SPRINT4_WBS17_NHAN_HUYEN_SHARED_20261106.xlsx `
  --output outputs/wbs17_remaining_tests_20261106/http-smoke-new
```
