# WBS17 — bằng chứng chạy và bàn giao

Code runtime đã đo: `d06f500`. Bản sửa phân biệt nguồn BCTN với nhu cầu
CONTENT, nhận diện yêu cầu chép câu/đọc tiểu sử, phân biệt đơn vị VNĐ với
mã VND, và giữ BOTH khi cần tìm quan hệ rồi đọc hoạt động/cơ sở hợp nhất.
Benchmark dùng production search/router code trong app thử cục bộ với
PostgreSQL chỉ đọc; không chứng minh deployment thật có auth hay UI E2E.
API thử nghiệm cổng 8012 đã dừng; tunnel và dữ liệu máy chủ giữ nguyên.

File chung đã cập nhật trực tiếp:
`outputs/wbs17_nhan_huyen_20261106/SPRINT4_WBS17_NHAN_HUYEN_SHARED_20261106.xlsx`.
Đã kiểm bằng Microsoft Excel chỉ đọc: 15 ca Done, 38 Blocked, guard chưa
nghiệm thu Answer/UI, công thức route và 292 ghi chú nguồn còn nguyên.

| Điều kiện WBS17 | Bằng chứng hiện có | Trạng thái |
|---|---|---|
| Bộ đề chung | 53 Test_ID trong Excel, cùng câu hỏi và nguồn | Đã chuẩn bị |
| VECTOR/GRAPH/BOTH trên dữ liệu sẵn có | 15 ca, 150 lượt đo + 30 warmup, một commit/model/corpus | Đã chạy retrieval |
| Ba nhóm quan hệ | Doanh nghiệp có dữ liệu; chức vụ/sự kiện chưa publish đủ vào graph chat | Còn phụ thuộc WBS02/04/05/09 |
| Chất lượng câu trả lời B1/B2 | API benchmark hiện chỉ trả retrieval; Answer để trống | Chưa đánh giá |
| Lỗi/timeout/hồi quy | 196 test router/adapter/nguồn/runner đạt; chưa thay 26 ca controlled fixture của Excel | Có hồi quy backend, chưa đủ nghiệm thu ca lỗi/E2E |
| Chat → citation → Graph Viewer | Graph Viewer API frontend vẫn mock; phần Huyền giữ nguyên | Chưa nghiệm thu |
| Full-load WBS16 | Có thống kê corpus; chưa tìm thấy manifest/receipt full-News cần đối chiếu | Chưa nghiệm thu |
| Bàn giao và giới hạn | Log từng lượt, bảng B1/B2, nguồn replay, bug log và owner | Đã ghi rõ |

Đã chạy 15 ca đủ dữ liệu từ bộ Excel chung: 150 lượt đo, 30 lượt warmup. 38 ca còn thiếu dữ liệu/fixture được ghi Blocked, không tính thành ca đạt.

**Trạng thái: đang làm.** Chưa có phép đo chất lượng câu trả lời B1/B2, E2E thật hoặc nghiệm thu full-load WBS16. Không ký thay Huyền và không khẳng định B2 tốt hơn B1.

B2 khớp route trong Excel ở 15/15 ca (5 lượt/ca); trạng thái kỳ vọng ở 15/15 ca. Lỗi HTTP: 0; lỗi transport/schema: 0.

| Test_ID | Route kỳ vọng | Route B2 (số lượt) | Trạng thái B2 | B1 / B2 median ms |
|---|---|---|---|---|
| TC_GRAPH_01 | GRAPH | {'GRAPH': 5} | {'OK': 5} | 2428.822 / 2351.782 |
| TC_GRAPH_02 | GRAPH | {'GRAPH': 5} | {'OK': 5} | 2298.716 / 2218.755 |
| TC_GRAPH_03 | GRAPH | {'GRAPH': 5} | {'OK': 5} | 2937.068 / 3651.38 |
| TC_VECTOR_01 | VECTOR | {'VECTOR': 5} | {'OK': 5} | 2216.843 / 8547.573 |
| TC_VECTOR_02 | VECTOR | {'VECTOR': 5} | {'OK': 5} | 1969.457 / 7579.908 |
| TC_VECTOR_03 | VECTOR | {'VECTOR': 5} | {'OK': 5} | 2330.962 / 6725.538 |
| TC_VECTOR_04 | VECTOR | {'VECTOR': 5} | {'OK': 5} | 2973.953 / 6490.128 |
| TC_VECTOR_05 | VECTOR | {'VECTOR': 5} | {'OK': 5} | 3177.722 / 7345.446 |
| TC_VECTOR_06 | VECTOR | {'VECTOR': 5} | {'OK': 5} | 3060.666 / 6700.987 |
| TC_BOTH_01 | BOTH | {'BOTH': 5} | {'OK': 5} | 2552.038 / 9449.213 |
| TC_BOTH_02 | BOTH | {'BOTH': 5} | {'OK': 5} | 2058.314 / 8813.472 |
| TC_BOTH_03 | BOTH | {'BOTH': 5} | {'OK': 5} | 2262.545 / 14363.901 |
| TC_VECTOR_07 | VECTOR | {'VECTOR': 5} | {'OK': 5} | 2857.166 / 6697.23 |
| TC_VECTOR_08 | VECTOR | {'VECTOR': 5} | {'OK': 5} | 2179.915 / 7273.095 |
| TC_VECTOR_09 | VECTOR | {'VECTOR': 5} | {'OK': 5} | 2322.485 / 6510.286 |

## Chênh lệch bằng chứng còn mở

- TC_VECTOR_09: B2 chưa trả chunk bảng lợi nhuận gộp PDF trang 170 (0103319d-5b4f-5829-aea2-e7023a81b4b6) trong cả 5 lượt. Hit mẫu là chỉ tiêu khác hoặc nội dung ngoài mục tiêu. Đây là lỗi truy xuất cần Vũ/owner VECTOR và Nhân phân tích ranking, không được coi route đúng và API OK là câu trả lời đạt.
- TC_GRAPH_03 và TC_BOTH_03: thiếu một chunk so bộ tham chiếu FTEL gốc; nguồn gốc vẫn active/đúng hash, envelope nhập lại dùng tập bằng chứng khác. Cần review tập nguồn bắt buộc trước khi chấm độ đủ bằng chứng.

## Cách đọc kết quả

- Done trong Excel chỉ nghĩa là đã chạy đủ lượt; Route_Match chỉ kiểm route. Các ô Answer vẫn trống; gold UNREVIEWED nên chưa có điểm chất lượng PASS/FAIL.
- Diagnostic gold_chunks so danh sách chunk tham chiếu gốc, không thay thế review ngữ nghĩa. Không tự bỏ nguồn khỏi gold để làm ca đạt. FTEL có biên bản đối chiếu riêng.
- B1 là dense retrieval có lọc company/document-period; B2 tự giải scope từ câu hỏi. Thời gian HTTP gồm cả xử lý adapter, warmup loại khỏi p50/p95. p95 với 5 lượt là giá trị lớn nhất mẫu.
- Log trước sửa (live01 và pilot) được giữ riêng. Run live02 dùng một commit/config cố định trong manifest, không trộn kết quả giữa môi trường.

## Việc còn lại để đóng WBS17

1. Nhân/Huyền thống nhất route và bằng chứng bắt buộc cho các ca có diagnostic lệch; ghi người duyệt bộ test, thời điểm và giới hạn gold.
2. Hưng/Vũ/Quân hoàn tất mapping, review và publish dữ liệu chức vụ/sự kiện vào graph chat. Chưa dùng graph nguồn riêng hoặc fixture thay cho dữ liệu chat thật.
3. Nhân dựng fixture cho ca lỗi có kiểm soát; kết quả hồi quy unit/integration không được chép thành kết quả 26 ca Excel hoặc E2E.
4. Quân/owner answering nối đầu ra retrieval với answering B1/B2 cùng model/prompt/budget. Lưu câu trả lời thật rồi đánh giá claim, thời gian, bằng chứng.
5. Huyền/owner Graph Viewer nối API thật và kiểm chat → citation → Graph Viewer; không nghiệm thu bằng dữ liệu mock.
6. Vũ cung cấp manifest/receipt full-News WBS16 để đối chiếu tổng nguồn, reject, retry, orphan và tải lại. corpus-audit.json chỉ là thống kê corpus hiện tại.

## Hồ sơ

- live02/manifest.json, results.jsonl, summary.json, report.md: cấu hình/hash, mọi request, thống kê.
- assessment.json, comparison.csv: đối chiếu từng ca và nguyên nhân Blocked.
- ftel-source-check.json: ba chunk FTEL xác minh bằng reader nguồn, hash và locator.
- corpus-audit.json: 44.930 chunk, 977 NEWS/192 tài liệu NEWS; không thiếu embedding. Không thay thế báo cáo full-load WBS16.
- expected-source-replay.json: 39 tham chiếu của 15/15 ca được đọc lại, kiểm active, document binding, hash và locator; không thay thế review mọi claim trong câu trả lời.
- router-final-regression.xml: 196 test router/adapter/nguồn/runner đạt. integration-regression.xml lưu thêm lượt kiểm graph pipeline trước đó; không cộng các lượt trùng thành test mới. Không có phép đo UI trong các kiểm tra này.
