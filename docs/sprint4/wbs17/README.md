# WBS17 — bộ ca nháp và runner truy xuất B1/B2

**Cập nhật 08/11:** đã review và kiểm thử snapshot `backup-demo` mới nhất; xem [kết quả và các điều kiện còn thiếu](../WBS17-backup-demo-review-20261108.md). Kết quả 06/11 bên dưới không tự áp dụng cho nhánh mới.

**Cập nhật 06/11:** cấu hình VECTOR local đã được sửa và cache đã dựng; lỗi lọc năm BCTN đã khắc phục. Xem [biên bản sửa và kiểm LIVE](../WBS17-vector-period-fix-20261106.md). Các giá trị “trước sửa” bên dưới là bằng chứng chẩn đoán, không phải cấu hình hiện tại.

Ngày 06/11/2026. Phụ trách benchmark: Hồ Phạm Đăng Nhân; Huyền xác nhận gold và kiểm E2E theo phân công. Đây là công cụ chuẩn bị đánh giá, **chưa phải báo cáo nghiệm thu WBS17**.

## Những gì đã chuẩn bị

- `cases.draft.json`: 18 ca cho doanh nghiệp, chức vụ, sự kiện, VECTOR, BOTH và ca lỗi. Ba ca G01–G03 READY dùng N30/N40/N18 đã nhập graph, có ID, ngày, thuộc tính và trích dẫn để review. 15 ca NOT_READY ghi lý do cụ thể.
- Cả 18 ca đều DRAFT. Việc một quan hệ đã được chấp nhận để nạp **không tự biến đáp án cho cả câu hỏi thành gold được duyệt**.
- `backend/scripts/wbs17_benchmark.py`: chạy B1/B2, lưu từng request/response, tách warmup, đổi thứ tự giữa các lượt đo, ghi lỗi và xuất JSON/Markdown tổng hợp. Không tạo session chat, không ghi graph/review store.
- Bộ ca và bằng chứng trích dẫn nằm trong Git; không cần `.tmp` để đọc hoặc chạy bộ ca. Các receipt chạy thử mặc định lưu ngoài Git.

## Phạm vi so sánh

Kết quả kiểm thử bổ sung (component/API, tách riêng benchmark LIVE) ở
[báo cáo các ca còn lại](../WBS17-remaining-tests-20261106.md).
Các script probe chỉ kiểm phần backend đã mô tả, không xác nhận Answer/UI
và không tự sửa code sản phẩm khi tìm thấy lỗi.

**Bộ chạy hiện tại là Excel chung 53 ca**, không tiếp tục mở rộng bộ JSON
18 ca nháp. Xem [cách chạy Excel chung](SHARED_WORKBOOK.md). Lượt đầy đủ
đọc 15 ca READY_RETRIEVAL và ghi rõ 38 ca thiếu setup; mỗi ca READY có
1 warmup và tối thiểu 5 lượt đo/profile. Tài liệu G01–G03 và JSON nháp dưới
đây được giữ làm lịch sử chuẩn bị runner, không phải bộ đề riêng cho Nhân.

| Profile | API hiện có | Chấm được |
|---|---|---|
| B1 | `/api/search/filtered` — tìm kiếm vector dense | Chunk/document nguồn kỳ vọng, xác minh nguồn, scope, latency |
| B2 | `/api/hybrid-router/run` — router và retrieval | Các mục trên, thêm route và cấu trúc quan hệ/chiều/ngày/phiên |

Đây là **so sánh mức truy xuất**, chưa đại diện cho toàn bộ B1/B2 trả lời văn xuôi. B1 không xuất cạnh graph nên không chấm relation precision/recall cho B1 hoặc coi thiếu cạnh là lỗi của B1. Dense ở B1 và hybrid/graph ở B2 là khác biệt của hai phương án; phải giữ cùng corpus, embedding model, máy và điều kiện đo. Không suy ra B2 tốt hơn từ một PASS tổng hợp có tập kiểm tra khác nhau.

G01–G03 chỉ yêu cầu tìm thấy một quan hệ mục tiêu và nguồn mẫu; câu hỏi có thể có thêm kết quả hợp lệ. `gold.complete=false` nên không tính relation precision/recall. Trước khi dùng để chấm chất lượng toàn câu, reviewer phải duyệt đủ tập kết quả và lựa chọn nguồn kỳ vọng công bằng cho cả hai phương án. Một bảng sở hữu có thể cần nhiều chunk chứng minh; một chunk mẫu không tự chứng minh đủ toàn bộ quan hệ.

## Chạy kiểm tra kế hoạch ngay, không gọi mạng

Trong PowerShell tại thư mục gốc FinMind:

```powershell
.\backend\.venv\Scripts\python.exe -m backend.scripts.wbs17_benchmark `
  --dry-run `
  --output backend/.tmp/wbs17-plan-review
```

Mở `plan.json` xem payload từng ca và `manifest.json` xem bộ ca/config/hash. Thư mục output phải mới để không ghi đè bằng chứng cũ. Chạy lại dùng tên khác.

## Checklist xác nhận với Huyền

1. Đọc câu hỏi, scope, quan hệ mục tiêu, ngày, tỷ lệ và `review_context.source_refs`; mở nguồn gốc để đối chiếu.
2. Chọn đủ gold chunk/document và tập quan hệ kỳ vọng. Phân biệt nhãn liên doanh với liên kết, phần trăm sở hữu với biểu quyết. Nếu chỉ làm ca mục tiêu thì giữ `complete=false` và ghi rõ giới hạn.
3. Sửa trực tiếp bản sao bộ ca: chỉ đặt `gold.status=APPROVED` sau khi review thật, điền `reviewer`, `reviewed_at` có múi giờ. Không ký thay người khác. Gold nháp vẫn có thể chạy thu thập nhưng không được chấm PASS/FAIL.
4. Với ca NOT_READY, giải quyết `blocked_reason` rồi mới đổi READY. Chức vụ/sự kiện cần phiên graph có dữ liệu phù hợp và cập nhật scope ở cả suite/config.
5. Ca timeout, nguồn mâu thuẫn hoặc sai phiên cần môi trường kiểm thử và cơ chế tạo lỗi có kiểm soát. Không tạo lỗi bằng nội dung câu hỏi hoặc sửa dữ liệu production. Runner này chưa tự tiêm lỗi; chưa triển khai harness thì giữ NOT_READY.
6. E2E chat → citation → Graph Viewer, chất lượng câu trả lời, full-load WBS16 và review-store sync có checklist/bằng chứng riêng; runner không tự chứng nhận các phần đó.

## Chuẩn bị một lượt đo thật

Kiểm tra cấu hình local ngày 06/11: `HYBRID_ROUTER_MODE=live`, `HYBRID_ROUTER_INDEX_ID` đang trống, `RESEARCH_CORPUS_VERSION_ID=33d33730-0f0a-5274-a7f8-8d32a6be07e8`, trong khi corpus BCTN của bộ ca là `b2550a0b-c423-5c50-9b15-6fb6af12e2c6`. Model cấu hình local là `BAAI/bge-m3@5617a9f61b02`. Đây là kiểm tra Settings local, chưa phải kiểm kê index/embedding hoặc cấu hình tiến trình server đang chạy. Phải xác nhận index vector có dữ liệu thuộc corpus chung trước khi chạy; không chỉ điền một UUID cho qua bước kiểm tra. Chưa thay cấu hình ứng dụng hoặc tạo embedding trong công việc chuẩn bị này.

Sao chép `run-config.example.json` và suite sang thư mục local, ví dụ `backend/.tmp/wbs17-input/`. Sau đó:

- Điền URL thực tế của hai API, `embedding_model_ref`, `deployment_ref` (commit và receipt cấu hình server), `machine_ref`.
- Xác nhận backend B2 chạy `HYBRID_ROUTER_MODE=live`. Kiểm `RESEARCH_CORPUS_VERSION_ID`, `HYBRID_ROUTER_INDEX_ID`, `SPRINT4_GRAPH_VERSIONS`, registry và embedding model khớp scope. Không đổi `.env` đang dùng chỉ để chạy kế hoạch nháp.
- Giữ tunnel PostgreSQL/Neo4j mở. Hai API dùng cùng môi trường và corpus; `top_k=5` ở baseline, đối chiếu cấu hình CONTENT B2 tương ứng.
- Chỉ đặt `operator_confirmed_same_environment=true` sau khi kiểm cấu hình server. Runner kiểm corpus/index/graph trả về khi API cung cấp; model và cấu hình triển khai là xác nhận của người chạy, không có API tự chứng minh chúng.
- Nếu cần bearer, thêm `token_env` vào profile và nạp token vào biến môi trường tại máy. Không lưu token, mật khẩu hoặc URL chứa credentials trong config. Runner không đăng nhập hoặc tự tạo token.

```powershell
.\backend\.venv\Scripts\python.exe -m backend.scripts.wbs17_benchmark `
  --suite backend/.tmp/wbs17-input/cases.json `
  --config backend/.tmp/wbs17-input/run-config.json `
  --output backend/.tmp/wbs17-run-01 `
  --warmups 1 --repeats 5 --timeout 180
```

READY/DRAFT được gọi API để thu thập, nhưng ghi UNREVIEWED. NOT_READY được bỏ qua và liệt kê lý do. Không biến timeout/HTTP lỗi thành NO_DATA. Lỗi không dừng các ca sau. Không chạy đồng thời hoặc retry ngầm; lượt warmup và thứ tự đo đều được lưu. Lượt đầu sau khi khởi động không tự được coi là phép đo cold-start có kiểm soát.

## Đầu ra và cách đọc

- `manifest.json`: snapshot suite/config, hash, HEAD của runner, thời điểm UTC và tham số; ghi trước request đầu tiên để giữ nguồn gốc nếu bị ngắt.
- `results.jsonl`: mỗi ca/profile/lượt một dòng; request, response, normalized facts, HTTP status, latency và kết quả kiểm tra. Bằng chứng lưu ở mức truy xuất, không có câu trả lời văn xuôi do API chưa trả câu trả lời.
- `summary.json`: số ca đã chấm, PASS/FAIL, lỗi HTTP/transport/schema, trạng thái ứng dụng, lỗi scope và nhóm ca.
- `report.md`: bảng B1/B2 để đọc nhanh. Latency là thời gian HTTP trọn vòng; p50/p95 chỉ lấy HTTP 200, kể cả lỗi ứng dụng trả HTTP 200, nên phải đọc cùng bảng trạng thái. Warmup không nằm trong số đo tổng hợp. Không so sánh latency giữa hai profile nếu chỉ một bên có kết quả hợp lệ.

PASS của gold không đầy đủ chỉ nghĩa là đạt các mục tiêu đã chọn. Chỉ khi gold APPROVED và `complete=true` mới chấm precision/recall tập quan hệ (khóa thực thể, chiều, loại, ngày và phiên). Trích dẫn/source_verified là bằng chứng kỹ thuật, không tự thay thế kiểm nghĩa nghiệp vụ hoặc việc mở citation trên giao diện.

Sau lượt đo thật, Nhân tổng hợp ca sai, ảnh hưởng và owner; Huyền bổ sung E2E, nhóm đối chiếu full-load News. Giữ các giới hạn còn mở trước khi quyết định đóng WBS17.
