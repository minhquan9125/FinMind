# WBS17 — kiểm chứng backup-demo ngày 08/11/2026

`backup-demo` giúp mở thêm phạm vi kiểm thử, nhưng chưa đủ nghiệm thu WBS17.
Đã kiểm bản remote `f9f1864db273eb47fec18bc9df864140819ce9be`, không merge đè
nhánh `nhan-sprint-411` (`a58ab63f` trước lượt này). Hai phía có 16/32 commit
riêng. Snapshot tách biệt nằm trong `backend/.tmp/backup-demo-review-20261108`.

## Phần mới hữu ích

| Phần | Đóng góp cho WBS17 | Giới hạn đã kiểm |
|---|---|---|
| WBS15 Graph Viewer | Frontend mặc định gọi API thật, auth, phiên READY, neighborhood và nguồn PDF/News | API/model tests đạt; chưa thao tác giao diện đã đăng nhập |
| Auth router | Chặn không token/token sai trước khi khởi tạo retrieval | Backend chạy thật trả 401 ở cả hai biến thể TC_EDGE_24; chưa kiểm tài khoản hợp lệ thiếu role |
| Scope/router | Giữ nhiều quý, ngày giá cụ thể, thêm bộ lọc chức vụ và sự kiện nhân sự | TC_EDGE_21/22 đạt phần scope; chưa xác nhận câu trả lời thật |
| Người/chức vụ | Neo4j có phiên nguồn 185 quan hệ, Graph Viewer đọc được | SOURCE_DOCUMENT_ASSERTIONS, chưa phải danh tính toàn cục/chức vụ hiện tại và không tự đi vào chat graph WBS09 |
| WBS16 News | Có runner manifest, resume, gate và đối chiếu export | Có công cụ/test không thay báo cáo chạy full trên manifest đã chốt |

## Kết quả chạy

Hồ sơ: `outputs/wbs17_backup_demo_20261108/`.

- `selected-tests.xml`: **359 đạt**. Router/scope/auth, Graph Viewer, temporal,
  live-research guards, Answer offline, News runner và source-person claims.
  Các test này chủ yếu dùng fixture; không phải 359 ca E2E hay 53 câu Excel.
- `frontend-tests.log`: **77 đạt**, không skip. Frontend build đạt bằng dependency
  đúng lockfile. Có cảnh báo bundle GraphCanvas lớn; chưa đo hiệu năng UI.
- `auth-mutation.log`: tạm bỏ guard `/run` trong snapshot khiến test bắt lỗi;
  đã phục hồi file byte-for-byte. Không đổi sản phẩm trên nhánh Nhân.
- `http-smoke01/`: health frontend/backend/proxy 200; chat sessions 401 và router
  401 với không token/token sai. Không giả mạo tài khoản hoặc tự cấp quyền.
- `live-graph-readback-canonical.json`: đọc **7 phiên READY** thật. Số cạnh theo
  phiên là 2, 34, 3, 13, 1, 1, 185. Hai phiên 1 cạnh là smoke fixture, không
  cộng vào dữ liệu nghiệp vụ đã nghiệm thu. Đọc tối đa 3 thực thể/5 path mỗi
  phiên; **77 lượt tham chiếu** có source replay đạt, không phải full-load.
  Kiểm document/chunk, phiên tài liệu, hash tái dựng, locator và quote. Không
  suy ngày giữ chức từ năm báo cáo. Không ghi PostgreSQL/Neo4j.

Các lần đọc thử trước file `canonical` dùng so sánh hash metadata không đúng
ngữ nghĩa BCTN hoặc giả định evidence đầy đủ trường. Chỉ file `canonical` dùng
làm kết luận nguồn. Hash của whole snapshot phải qua source reader chuẩn,
không so trực tiếp với `documents.sha256`.

## Chạy lại 11 ca biên đã có kiểm tra backend

10 ca component chạy 5 lần/ca; câu hỏi giữ nguyên Excel. Predictor là fixture,
không đánh giá classifier đã huấn luyện. Vì code mới yêu cầu coverage, harness
cung cấp **năm 2024 giả lập** cho kỳ symbolic; không coi đó là coverage DB thật.
Harness chỉ bỏ tham số constructor `verify_sources` mà backup-demo chưa hỗ trợ.
Không sửa router/adapters để làm kết quả đạt. Lượt chốt `edge-probes03`.

| Ca | Kết quả phần backend | Nhận xét |
|---|---|---|
| EDGE_01, 03, 05, 20 | Đạt 5/5 mỗi ca | Alias trùng/thiếu công ty/quý sai hoặc graph fixture rỗng |
| EDGE_21 | Đạt 5/5 | Giữ đủ Q1 và Q2/2025; Answer abstention chưa kiểm |
| EDGE_22 | Đạt 5/5 | Giữ 2026-11-04 trong task; test callback giá của nhánh đạt, giá thật/UI chưa kiểm |
| EDGE_24 | Đạt 2/2 biến thể API thật | Không token/token sai trả 401 |
| EDGE_04 | Chưa đạt 5/5 | BOTH trong khi Excel kỳ vọng GRAPH; cần đối chiếu spec |
| EDGE_14, 15 | Chưa đạt 5/5 mỗi ca | Câu công ty con rồi nêu hoạt động vẫn chỉ GRAPH, thiếu BOTH |
| EDGE_16 | Chưa đạt 5/5 | GRAPH thay vì BOTH; phần graph rỗng chặn content vẫn đạt |

Tổng **7 ca đạt kiểm tra backend được chọn, 4 ca chưa đạt**. Không có kết luận
toàn ca/Answer/E2E. EDGE_14 còn trả `GRAPH_ERROR_TimeoutError` thay vì
`GRAPH_TIMEOUT`; component CONTENT timeout của EDGE_15 đạt độc lập.
Lượt 01 chưa chạy hết do khác constructor; lượt 02 chưa có coverage fixture,
không dùng lỗi setup đó làm kết luận lỗi sản phẩm.

`normal-routing.json` là chẩn đoán policy cho 27 câu thường với điểm classifier
cố định. Không dùng các lệch route ở file đó làm số lỗi classifier hay tỷ lệ
chất lượng, vì câu không bị policy ghi đè vẫn phụ thuộc predictor fixture.

## Phát hiện trước khi tích hợp

**Mức cao — các guard graph của nhánh Nhân chưa có đủ trên backup-demo.**
Chạy nguyên bộ `test_wbs09_graph_pipeline.py` hiện tại của Nhân cùng fixture
nguyên bản trên snapshot mới: **19 đạt, 6 thất bại**, xem
`local-graph-regression.xml`. Đây là khác biệt giữa hai nhánh, không khẳng định
6 lỗi mới vừa được bạn cùng nhóm tạo ra trong commit cuối.

- `LiveGraphAdapter` chưa nhận callback `verify_sources`, nhưng gắn
  `source_verified=True` cho evidence được đọc từ Neo4j. Khi tích hợp cần giữ
  bước replay nguồn từ PostgreSQL đã có ở nhánh Nhân.
- Thiếu `RelationRetrieval.all_versions_ready`: chưa giữ guard phân biệt
  thiếu phiên READY với kết quả graph rỗng.
- Kỳ sai bị bỏ qua ở `_period_window`; adapter không trả
  `GRAPH_UNSUPPORTED_PERIOD`. Scope resolver có guard quý sai nhưng không thay
  được hợp đồng adapter khi gọi trực tiếp hoặc từ caller khác.
- Scope chứa ticker chưa ánh xạ bị rút bớt; chưa giữ guard cho yêu cầu nhiều
  công ty/quan hệ giữa hai công ty của nhánh Nhân.
- Timeout chưa giữ mã lỗi riêng. Hai kiểm tra kỳ sai/period-window cùng phản
  ánh một nhóm vấn đề; không gọi đây là 6 bug nghiệp vụ độc lập.

Do đó chưa dùng toàn bộ backup-demo thay cho nhánh đã benchmark 06/11.
Phần Graph Viewer/auth/scope mới hữu ích, nhưng kết quả cũ không tự áp dụng cho
commit mới. Chưa thực hiện merge hoặc thay đổi code sản phẩm trong lượt này.

## Còn gì để bàn giao WBS17

Excel chung được cập nhật T–W, môi trường và Bug Log; giữ nguyên 53 câu hỏi,
gold, kết quả LIVE 06/11 và sheet E2E của Huyền. Task vẫn **IN_PROGRESS**.

1. Owner tích hợp giữ guard graph của Nhân khi ghép phần mới; xác định một
   commit tích hợp duy nhất để chạy lại B1/B2 trên cùng cấu hình/corpus/model.
2. Quân/nhóm cấu hình Gemini bằng kênh riêng. Máy hiện chưa có key và chưa xác
   nhận Free Tier; chưa chạy Answer thật, không dùng câu trả lời fixture thay.
3. Huyền thực hiện E2E đã đăng nhập: chat → citation → Graph Viewer, source,
   lỗi và hồi quy. Công cụ browser timeout; mở Chrome bằng native tool hết
   thời gian chấp thuận. Chưa có ảnh/thao tác UI được xác nhận trong lượt này.
4. Chốt gold/phạm vi các ca chức vụ, sự kiện. 185 claims theo tài liệu không tự
   thỏa câu hỏi về người đang giữ chức ở ngày cụ thể. Chạy các fixture còn thiếu.
5. Nhận báo cáo full-load WBS16: manifest/hash, tổng đầu vào, thành công/lỗi,
   review, rerun và đối chiếu PostgreSQL–Neo4j. Số News hoặc runner có sẵn chưa
   đủ nghiệm thu bước này.

Ứng dụng snapshot đang phục vụ tại http://localhost:5173 và
http://127.0.0.1:8000. Collector tự động tắt trong tiến trình test. Không sửa
`.env`, không gửi secret vào log, không ghi/duyệt/nạp graph hoặc review store.

Lệnh đọc lại graph/nguồn, sau khi tunnel mở:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/wbs17_backup_demo_readback.py `
  --snapshot backend/.tmp/backup-demo-review-20261108 `
  --output outputs/wbs17_backup_demo_20261108/readback-rerun.json
```
