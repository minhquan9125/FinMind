# WBS17 — phần kiểm thử của Hồ Phạm Đăng Nhân

Ngày tổng hợp: 08/11/2026. Phạm vi: benchmark, đối chiếu truy xuất và phân tích
ca sai của Nhân (phân công 7 giờ). Không thực hiện hoặc ký thay phần E2E của Huyền.

**Đã có bộ kết quả bàn giao phần truy xuất. Phần Nhân chưa nghiệm thu đầy đủ**
vì còn thiếu benchmark GRAPH/BOTH cho chức vụ/sự kiện và phép đo Answer B1/B2.
Lỗi đã ghi nhận không bắt buộc Nhân tự sửa tất cả mới được bàn giao kết quả test.

## Bản đo và bằng chứng

Chốt bộ đo retrieval `live02` ngày 06/11, runtime commit
`d06f50011cc55d6c0f3dd38810e4dcb5d0c5e209`. Không gọi đây là kết quả của
`backup-demo`; kết quả kiểm nhánh đó ngày 08/11 được giữ riêng.

- Cùng corpus `b2550a0b-c423-5c50-9b15-6fb6af12e2c6`, index
  `ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d`, model `BAAI/bge-m3@5617a9f61b02`.
- 15 câu từ Excel chung, mỗi câu 5 lượt/profile; tổng 150 lượt đo, 30 warmup.
  Warmup không tính vào p50/p95. Mỗi profile có 75 lượt đo.
- B1 là dense retrieval với bộ lọc tài liệu đã cung cấp; B2 tự giải scope và
  thực thi router. Cùng môi trường không có nghĩa hai hệ có cùng thuật toán,
  ngân sách bằng chứng hoặc đều tự nhận diện scope.
- Logs: `outputs/wbs17_completion_20261106/live02/{manifest.json,results.jsonl,summary.json}`.
  Kết quả tổng hợp lại: `outputs/wbs17_nhan_handoff_20261108/analysis.json`, có
  SHA256 của ba đầu vào; đã đối chiếu số đo với summary gốc. Không chạy lại
  hoặc sửa log cũ trong lượt tổng hợp này.

## Kết quả so sánh

| Chỉ tiêu | B1 | B2 |
|---|---:|---:|
| Lượt đo | 75 | 75 |
| HTTP lỗi / lỗi transport-schema | 0 / 0 | 0 / 0 |
| Retrieval trả OK | 75 | 75 |
| HTTP p50 | 2.428 ms | 6.891 ms |
| HTTP p95 | 4.666 ms | 13.472 ms |
| Câu trả lời được chấm chất lượng | Chưa có | Chưa có |

Đơn vị trong bảng là mili giây. B2 khớp route kỳ vọng ở 15/15 câu, 75/75 lượt.
Với 6 câu GRAPH/BOTH có quan hệ đích, kiểm tra subject/object, loại quan hệ,
ngày `as_of`, phiên graph và thuộc tính yêu cầu không ghi lệch trong 30 lượt B2.
Đây là kiểm quan hệ đích trong gold một phần, không phải precision/recall toàn bộ
quan hệ hoặc xác nhận mọi fact trong một câu trả lời.

Theo nhóm route kỳ vọng (B1 vẫn chỉ là VECTOR baseline):

| Nhóm câu | Số lượt/profile | B1 p50/p95 ms | B2 p50/p95 ms |
|---|---:|---:|---:|
| VECTOR | 45 | 2.550 / 3.517 | 6.891 / 9.460 |
| GRAPH | 15 | 2.429 / 6.574 | 2.352 / 6.581 |
| BOTH | 15 | 2.263 / 6.714 | 9.517 / 17.158 |

Không kết luận B2 tốt hơn B1. B2 lấy thêm bằng chứng cho một số câu quan hệ,
nhưng có ca truy xuất kém hơn và thường tốn thêm thời gian. Không lấy p50/p95
HTTP retrieval làm thời gian chat/LLM. Với 5 lượt/câu, p95 của từng câu là số lớn
nhất trong mẫu; chưa phải ước lượng tail latency ổn định hay kiểm thử tải đồng thời.

## Đối chiếu nguồn và ca sai

39 tham chiếu nguồn của 15 câu đã replay ở ngày 06/11: active, document binding,
hash và locator đạt. Đó là nguồn tham chiếu của đề, không phải bằng chứng rằng
mọi chunk cả B1/B2 trả về đều hỗ trợ đúng mục tiêu câu hỏi. Gold vẫn DRAFT;
không tự duyệt, thay câu hỏi hoặc bỏ chunk để làm kết quả đạt.

| Ca/phát hiện | Kết quả thực tế | Phân loại và người nhận |
|---|---|---|
| TC_VECTOR_04, B1 | Cả 5 lượt top-5 không có chunk của bài News được hỏi; trả các đoạn BCTN về cổ tức. B2 có chunk tham chiếu 5/5 | Lệch nguồn mục tiêu của dense baseline. Vũ/owner VECTOR nhận phân tích ranking; Nhân lưu request/response và đo lại sau bàn giao |
| TC_VECTOR_09, B2 | 0/1 chunk tham chiếu trong cả 5 lượt; thiếu bảng lợi nhuận gộp trang PDF 170. B1 có chunk này cả 5 lượt | Lỗi truy xuất B2; scope hiện có metric PROFIT chung, cần owner VECTOR/router điều tra truy vấn/ranking. Chưa chứng minh đây là nguyên nhân duy nhất |
| TC_GRAPH_03, TC_BOTH_03 | B2 trả 6/7 chunk tham chiếu, thiếu `5b177f33-e141-55c4-938c-a82f0090a0b4`; quan hệ đích vẫn khớp | Cần review bộ bằng chứng FTEL bắt buộc. Nhân/Huyền chốt gold từ nguồn; không tự gọi thiếu chunk là sai toàn bộ quan hệ |
| TC_VECTOR_09, B1: periods | Raw diagnostic báo không khớp vì scope trả `2025` và `2025-YEAR`, yêu cầu `2025` | Hai nhãn cùng năm, chưa phải bằng chứng lấy sai năm. Ghi lưu ý evaluator, giữ nguyên log. Không mở bug dữ liệu sai kỳ chỉ từ cảnh báo này |

B1 không lấy đủ chunk cho một số câu quan hệ là giới hạn quan sát được của
baseline top-5; gold chưa đầy đủ nên không biến số chunk khớp thành tỷ lệ đúng
câu trả lời. Danh sách từng câu và chunk xem bảng chi tiết ở cuối.

## Kiểm tra bổ sung phục vụ báo cáo của Nhân

- Trên nhánh benchmark ngày 06/11: 196 kiểm tra hồi quy router/adapter/nguồn/
  runner đạt; không cộng các lượt chạy trùng thành số test mới.
- Trên backup-demo `f9f1864d` ngày 08/11: 359 backend tests đạt và 11 ca biên
  kiểm một phần backend: 7 đạt, 4 chưa đạt. Predictor/coverage trong các probe
  component là fixture; không phải phép đo classifier, Answer hoặc E2E.
- Hồi quy chéo bộ graph của Nhân trên backup-demo: 19 đạt/6 thất bại. Ghi rủi ro
  tích hợp về replay nguồn, phiên READY, scope, kỳ sai và timeout; chưa sửa sản
  phẩm hoặc merge. Xem `WBS17-backup-demo-review-20261108.md`.

## Trạng thái phần Nhân và đầu vào còn thiếu

| Việc của Nhân | Trạng thái | Cần gì tiếp |
|---|---|---|
| Chạy B1/B2 trên 15 câu sẵn dữ liệu, lưu từng lượt | Đã làm | Log/manifest và bảng số đo đã có |
| Đối chiếu route, quan hệ đích, chiều/ngày/phiên, nguồn và thời gian | Đã làm trong 15 câu | Chất lượng Answer chưa được suy ra từ các kiểm tra retrieval |
| Phân tích ca sai và chuyển đúng owner | Đã làm | Bug Log và bảng trên; không tự sửa thay owner |
| Benchmark 12 câu GRAPH/BOTH chức vụ/sự kiện | Chờ đầu vào | Owner dữ liệu/graph chat bàn giao phiên phục vụ và mapping. Graph nguồn 185 claims chưa tự thỏa điều kiện này |
| Đo chất lượng Answer B1/B2 | Chờ đầu vào | Owner Answer bàn giao hai pipeline cùng model/prompt/budget và cấu hình Gemini hợp lệ; sau đó Nhân chạy/lưu/chấm kết quả thật |
| Gold chung | Chưa chốt duyệt | Nhân/Huyền thống nhất route và bằng chứng bắt buộc; ghi người duyệt/thời điểm thật |
| Đối chiếu full-load News | Chờ báo cáo WBS16 | Vũ bàn giao manifest/hash, tổng đầu vào/thành công/lỗi, rerun, review và đối chiếu hai DB; Nhân tổng hợp sau khi nhận |

E2E câu hỏi → chat → citation → Graph Viewer thuộc Huyền. Việc chưa kiểm được
Chrome không phải phần Nhân cần làm thay. Không coi E2E của Huyền là lý do để
không bàn giao các kết quả Nhân đã làm; cũng không dùng báo cáo này để đóng
toàn bộ WBS17 khi các phép đo của Nhân ở bảng trên vẫn còn chờ.

Khi nhận đủ đầu vào, Nhân chạy tiếp trên một commit tích hợp cố định, ghi run
mới và giữ kết quả cũ. Không trộn latency/quality giữa commit d06f500 và
backup-demo. Không mặc định phải sửa hết bug mới được kết thúc lượt kiểm thử.

## Bảng từng câu

Các phân số là số chunk tham chiếu xuất hiện / số chunk tham chiếu của câu.
Đây là diagnostic trên gold DRAFT, không phải recall hoàn chỉnh hoặc điểm
Answer. Hai giá trị B1/B2 tách bằng dấu `;`. Các lượt cùng câu có tập tham chiếu
khớp ổn định; log mỗi lượt vẫn là bằng chứng gốc.

| Ca | Route B2 | B1 p50/p95 (ms) | B2 p50/p95 (ms) | Chunk tham chiếu B1 ; B2 |
|---|---|---:|---:|---|
| TC_BOTH_01 | BOTH | 2552 / 6714 | 9449 / 11750 | 0/4 ; 4/4 |
| TC_BOTH_02 | BOTH | 2058 / 2130 | 8813 / 9517 | 1/3 ; 3/3 |
| TC_BOTH_03 | BOTH | 2263 / 4217 | 14364 / 17158 | 3/7 ; 6/7 |
| TC_GRAPH_01 | GRAPH | 2429 / 4666 | 2352 / 2824 | 0/4 ; 4/4 |
| TC_GRAPH_02 | GRAPH | 2299 / 3157 | 2219 / 2307 | 1/3 ; 3/3 |
| TC_GRAPH_03 | GRAPH | 2937 / 6574 | 3651 / 6581 | 3/7 ; 6/7 |
| TC_VECTOR_01 | VECTOR | 2217 / 3008 | 8548 / 9460 | 3/3 ; 3/3 |
| TC_VECTOR_02 | VECTOR | 1969 / 2500 | 7580 / 12444 | 1/1 ; 1/1 |
| TC_VECTOR_03 | VECTOR | 2331 / 2385 | 6726 / 8020 | 1/1 ; 1/1 |
| TC_VECTOR_04 | VECTOR | 2974 / 3517 | 6490 / 6891 | 0/1 ; 1/1 |
| TC_VECTOR_05 | VECTOR | 3178 / 6496 | 7345 / 8258 | 1/1 ; 1/1 |
| TC_VECTOR_06 | VECTOR | 3061 / 3411 | 6701 / 6903 | 1/1 ; 1/1 |
| TC_VECTOR_07 | VECTOR | 2857 / 3543 | 6697 / 13472 | 1/1 ; 1/1 |
| TC_VECTOR_08 | VECTOR | 2180 / 2550 | 7273 / 7546 | 1/1 ; 1/1 |
| TC_VECTOR_09 | VECTOR | 2322 / 2793 | 6510 / 6878 | 1/1 ; 0/1 |
