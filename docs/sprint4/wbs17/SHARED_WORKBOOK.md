# Chạy bộ Excel chung WBS17

File `outputs/wbs17_nhan_huyen_20261106/SPRINT4_WBS17_NHAN_HUYEN_SHARED_20261106.xlsx`
là nguồn câu hỏi chung. Không phát triển thêm bộ 18 câu nháp song song.
Runner đọc trực tiếp Master, ghi chú JSON và cấu hình corpus/index/graph;
giữ nguyên Test_ID, câu hỏi và đáp án nguồn. Có 15 READY_RETRIEVAL; 38 ca
còn lại được bỏ qua với lý do setup. READY_FIXTURE không chạy trên LIVE.

```powershell
.\backend\.venv\Scripts\python.exe -m backend.scripts.wbs17_benchmark `
  --workbook outputs/wbs17_nhan_huyen_20261106/SPRINT4_WBS17_NHAN_HUYEN_SHARED_20261106.xlsx `
  --case-ids TC_GRAPH_01 TC_GRAPH_02 TC_GRAPH_03 `
  --config backend/.tmp/wbs17-pilot-config.json `
  --output outputs/wbs17_pilot_20261106/run-new `
  --warmups 1 --repeats 5 --timeout 180
```

Bỏ `--case-ids` để lấy đủ 53 ca và chạy các ca READY. Thêm `--dry-run`
để kiểm tra kế hoạch trước khi gọi API. Cấu hình local phải có model,
deployment, machine và xác minh cùng môi trường trước khi chạy LIVE.

B2 nhận nguyên câu hỏi, không được gợi sẵn scope từ đáp án. B1 dùng bộ lọc
company/document-period được ghi riêng trong `b1_context` của manifest.
Năm số liệu 2024 trong báo cáo 2025 vẫn giữ câu hỏi gốc; xem Scope_Note.
Đây là baseline có bộ lọc tài liệu, không phải so sánh hai bộ nhận diện scope.

Import Excel không suy ra người duyệt bộ test từ người duyệt dữ kiện nguồn:
gold vẫn DRAFT, kết quả UNREVIEWED, có `diagnostic_checks` để đối chiếu kỹ thuật.
Không dùng các kiểm tra này làm tỷ lệ PASS/FAIL hoặc kết luận B2 tốt hơn B1.
`summary.json.by_case` có p50/p95, route và trạng thái theo từng ca/profile.
Các ô Answer và kết quả E2E để trống đến khi chạy pipeline tương ứng.

Trước khi đo, dùng warmup/`HybridRetriever.prepare_cache` để xác minh hoặc
xây lại cache BM25 nếu hết hạn; không sửa timestamp để vượt kiểm tra TTL.
Nếu tiền kiểm phát hiện cache hết hạn, giữ log lượt lỗi, làm mới cache rồi
chạy thư mục mới; không gộp các lần chạy với setup khác nhau.
