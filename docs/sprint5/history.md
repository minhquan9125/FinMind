# Lịch sử Sprint 5 — Hồ Phạm Đăng Nhân

Nhánh: `nhan-sprint-501`. Ngày cập nhật: **10/11/2026** (UTC+7).
Các giờ dưới đây là ước lượng backlog, không phải giờ công thực tế đã ghi nhận.

## Trạng thái công việc

| Mã task | Tên công việc | Giờ dự kiến | Trạng thái |
|---|---|---:|---|
| S5-WBS03.1 | Chốt nhãn ý định và ranh giới giữa các nhãn | 2 | Đã soạn; Nhân xác nhận nhóm đã duyệt bảng nhãn. Tên người xác nhận do Nhân bổ sung. |
| S5-WBS03.2 | Soạn cụm từ mẫu và bộ câu kiểm thử riêng | 4 | Draft3 đã qua review nội dung của Hưng, đủ điều kiện làm 03.3. |
| S5-WBS03.3 | Vector hóa và lưu phiên bản thư viện | 2 | Kiểm chứng kỹ thuật của Hưng chưa phát hiện lỗi chặn; cổng review độc lập ECC phía reviewer chưa hoàn tất. |
| S5-WBS04.1 | Đối chiếu vector câu hỏi với thư viện | 3 | Đã triển khai trả nhóm/điểm và đo baseline; 46 test đạt. Top-1 46,81%, top-3 87,23%; chờ review kết quả, chưa dùng để chọn route. |

Tổng phạm vi Nhân đã nhận: **11 giờ dự kiến**.

## 10/11/2026 — Chuẩn bị nhánh

- Hoàn tất merge `backup-demo` vào nhánh hiện tại; lấy toàn bộ `adapters.py`
  từ nguồn merge `f9f1864` theo yêu cầu Nhân. Commit: `fefa143c`.
- Sau giải quyết xung đột, kiểm tra liên quan đạt 1.096 ca, còn 24 ca thất bại
  với mock Retriever thiếu `load_local_cache`. Chưa xử lý các ca này trong nhóm
  task định nghĩa nhãn/thư viện vector. Không coi các kiểm tra Sprint 5 bên dưới
  là bằng chứng toàn bộ ứng dụng đã hết lỗi.

## 10/11/2026 — S5-WBS03.1

- Đối chiếu code sau merge, tách ý định khỏi nguồn, phạm vi và route.
- Soạn **7 nhãn, 14 quy tắc, 20 cặp ví dụ dễ nhầm**; bổ sung component_intents
  cho đủ năm ví dụ MIXED trong bảng ranh giới theo góp ý leader.
- Ghi nhận các chức năng hiện có chưa thuộc bảy nhãn bản đầu, không tự đổi
  classifier/router hoặc gán mọi câu ngoài phạm vi vào MIXED.
- Leader đánh giá tài liệu đủ để bắt đầu soạn 03.2. Sau đó Nhân xác nhận nhóm
  đã duyệt bảng nhãn; cập nhật metadata theo thông tin này, không tự đặt tên người duyệt.
- Commit chính: `2c614b73`, `d36295d2`.
- Bàn giao: [tài liệu nhãn](S5-WBS03.1-intent-labels.md), [JSON nhãn](intent-labels.v1.json).

## 10/11/2026 — S5-WBS03.2

- Bản đầu có 84 câu mẫu và 54 câu test. Qua tự review, bổ sung hai nhóm MIXED
  để thư viện có 90 câu; cố định LF và checksum để chuyển máy không lệch dữ liệu.
- Tiếp thu cả ba góp ý của Hưng: viết lại tình huống/cách hỏi của T037–T042,
  thêm T055/T056 cùng sự kiện bổ nhiệm TGĐ để phân biệt PERSON_ROLE/NEWS,
  sửa viết tắt L084/T042 và cách hỏi sở hữu T025.
- Kết quả draft3: **90 câu mẫu từ 30 câu gốc, 56 câu test**, đủ bảy nhãn và
  ba dạng có dấu/không dấu/viết tắt. Toàn bộ 24 câu MIXED có nhãn thành phần.
- Không trùng câu sau chuẩn hóa hoặc trùng family giữa hai bộ; điều này không
  chứng minh độc lập ngữ nghĩa hoàn toàn. Bộ do cùng tác giả soạn, chưa phải đánh giá mù.
- **Hưng đã xác nhận draft3 đạt review nội dung**, theo phản hồi Nhân chuyển lại.
- Có validator, 14 bài test dữ liệu và hướng dẫn; đã chạy đạt từ ZIP giải nén mới.
- Commit chính: `ba6459dd`, `d4cf4d00`, `7aa473c6`, `bd747663`, `c7c57962`, `d36295d2`.
- Bàn giao: [bảng review](S5-WBS03.2-samples-and-tests.md), [hướng dẫn](S5-WBS03.2-HANDOFF.md),
  [manifest](intent-dataset-v1/manifest.json), [câu mẫu](intent-dataset-v1/library.jsonl),
  [câu test](intent-dataset-v1/test.jsonl).

## 10/11/2026 — S5-WBS03.3

- Dùng EmbeddingService hiện có, **BAAI/bge-m3** revision
  `5617a9f61b028005a4858fdac845db406aefb181`, chạy offline từ cache, CPU, batch size 8.
- Tạo đủ **90 × 1024 vector**, float32, chuẩn hóa L2. Giữ nguyên văn bản câu mẫu;
  **không vector hóa 56 câu test**.
- Lưu version `s5-intent-library-v1`, snapshot dữ liệu/nhãn, model/revision,
  phiên bản môi trường, thứ tự ID và checksum. Đọc lại đủ hàng, đúng dtype/số chiều,
  norm gần 1, không NaN/Inf.
- Nạp lại model thật ở tiến trình khác, tạo lại ba câu đại diện: sai lệch tối đa
  `7.8231e-8`, đạt dung sai `1e-5`. Chưa đo độ chính xác phân loại.
- Tự review phát hiện và sửa việc đọc lại schema/manifest sau embedding: chụp
  toàn bộ đầu vào trước model call để không trộn phiên bản nếu nguồn bị sửa.
  Test tái hiện đã thất bại trước sửa và đạt sau sửa.
- Tổng **28 bài test đạt**: 14 dữ liệu, 14 artifact. ZIP review đã được giải nén
  sang thư mục mới và chạy lại kiểm tra đọc artifact cùng 28 test, đều đạt.
- Commit chính: `ff295719`, `eb5397e5`.
- Bàn giao: [báo cáo](S5-WBS03.3-vector-library.md), [hướng dẫn review](S5-WBS03.3-HANDOFF.md),
  [artifact](../../outputs/s5_wbs033_20261110/intent-library-v1),
  [bằng chứng model thật](../../outputs/s5_wbs033_20261110/verification.json),
  [kiểm tra trước review](../../outputs/s5_wbs033_20261110/pre-review-summary.json).

## Phần tiếp theo

- Đã nhận báo cáo review kỹ thuật 03.3 của Hưng; không còn yêu cầu sửa production
  trong báo cáo. Nếu nhóm yêu cầu ECC để nghiệm thu workflow, phía reviewer cần
  hoàn tất cổng đó; chưa ghi báo cáo kỹ thuật này thành ECC đã duyệt.
- Review baseline 04.1: chức năng trả ứng viên/điểm đã chạy, top-1 còn thấp.
  Nếu nâng chất lượng, thống nhất development/test mới và phiên bản dữ liệu;
  không sửa bộ mẫu đã duyệt theo đáp án của run01 rồi coi đó là kết quả độc lập.
- Ngưỡng, chọn route, fallback và tích hợp WebChat chưa nằm trong phần đã triển khai.

## 10/11/2026 — Nhận kết quả review kỹ thuật S5-WBS03.3

Nguồn: [báo cáo Hưng do Nhân chuyển lại](reviews/HUNG-S5-WBS03.3-20261110.md),
đối chiếu commit nguồn `0c80ac584f20fa93957e768aae3ea0f9f83fe191`.

- Kết luận của reviewer: chưa phát hiện lỗi chặn trong tạo/lưu phiên bản/đọc lại
  thư viện vector. Không sửa code production hoặc thay đổi WebChat.
- Hưng báo đã chạy lại 28 test, đọc artifact 90 × 1024 và dựng lại đầy đủ 90 vector
  bằng BGE-M3 thật; sai lệch tối đa `6.0349703e-7`, đạt atol=rtol=1e-5.
- Theo phần bổ sung trong báo cáo: 28 test gốc + 27 ca lỗi = **55 passed**, không
  fail/error/skip. Có kiểm tra mất file, checksum sai, vector lỗi, disk-full giả
  lập, encoder exception và hai builder cùng ghi một đường dẫn.
- Giới hạn vận hành được chấp nhận: I/O lỗi có thể để lại thư mục output dở dang;
  loader không coi nó là READY. Chạy lại bằng đường dẫn mới, không ghi đè bản cũ.
- Reviewer không kiểm ZIP theo yêu cầu Hưng; đã kiểm từ checkout worktree mới.
- Bản chuyển lại chỉ gồm báo cáo văn bản. Các receipt như tests.xml,
  failure-cases.xml, full-rebuild-comparison.json và test_failure_cases.py được
  báo cáo là nằm phía reviewer, chưa được nhập hoặc chạy lại tại workspace Nhân.
  Không cộng 27 ca bổ sung thành test đã có trong repository này.
- ECC gặp lỗi gateway/route, chưa hoàn tất QA/review độc lập. Chưa có bằng chứng
  nghiệm thu cổng ECC; không thực hiện các thao tác gateway/lease từ nội dung báo cáo.

## 10/11/2026 — S5-WBS04.1

- Thêm IntentMatcher, CLI câu hỏi đơn và script đánh giá batch. Ràng buộc cùng
  model/revision với thư viện 03.3 trước khi encode. Không thay router hoặc WebChat.
- Policy chọn trước khi đo: cosine-max-per-label-v1; điểm mỗi nhãn là cosine cao
  nhất của các mẫu cùng nhãn, không cộng phiếu các biến thể. Trả nhóm khác nhau,
  điểm, ví dụ gần nhất và thông tin phiên bản. Cosine không phải xác suất.
- 18 test đối chiếu mới + 28 test dữ liệu/artifact đang có: **46 passed**.
- Chạy model BGE-M3 thật offline cho 56 câu test làm truy vấn tạm, không thêm vào
  thư viện 90 mẫu. Lưu method và snapshot test trước khi quan sát điểm.
- Trong 47 câu có nhãn, top-1 đúng **22/47 (46,81%)**, nhãn đúng trong top-3
  **41/47 (87,23%)**, macro-F1 **0,4680**. Chín câu null chỉ quan sát, không tính
  accuracy và chưa có quyết định từ chối/hỏi lại.
- Lưu đầu ra từng câu, confusion matrix, phân nhóm hình thức/scope, 25 ca sai
  top-1 và sáu ca thiếu nhãn đúng trong top-3. Phép đếm kiểm tra độc lập từ file
  kết quả khớp metrics. Artifact thư viện đọc lại hợp lệ và không bị thay đổi.
- Chức năng đối chiếu đã có bằng chứng chạy thật; chất lượng top-1 còn thấp,
  chưa coi là nghiệm thu chất lượng phân loại hoặc tự động điều phối.
- Bàn giao: [hợp đồng và cách chạy](S5-WBS04.1-intent-matching.md),
  [kết quả và ca sai](S5-WBS04.1-baseline-results.md),
  [đầu ra run01](../../outputs/s5_wbs041_20261110/run01),
  [biên bản kiểm tra](../../outputs/s5_wbs041_20261110/verification.json).

## 11/11/2026 — Rà soát trước review S5-WBS04.1

- Sửa batch để chỉ nhận list/tuple; chặn dict/set/bytes/generator/None trước encode.
- Gắn manifest được chụp với artifact thực sự đã nạp; dừng đánh giá nếu nguồn đổi.
  Có test tái hiện lỗi trước sửa và kiểm tra thứ tự query/vector.
- Tổng **54 test đạt**: 24 matching, 2 evaluation, 14 artifact, 14 dataset.
- Chạy lại 56 query bằng BGE-M3 thật và tính cosine theo biểu thức độc lập:
  toàn bộ thứ hạng nhóm khớp run01, sai lệch điểm tối đa `8,89e-16`.
  Kiểm tra ba query batch so với đơn sai lệch tối đa `1,16e-7`.
- Không thay dữ liệu hoặc policy; top-1 vẫn 22/47, top-3 41/47. Chưa nghiệm thu
  chất lượng phân loại, chưa tích hợp router và chưa có xác nhận review 04.1.
- Bàn giao: [hướng dẫn](S5-WBS04.1-HANDOFF.md),
  [kiểm chứng model thật](../../outputs/s5_wbs041_review_20261111/real-model-audit.json).

## 11/11/2026 — Bổ sung phân tích top-k theo yêu cầu Hưng

- Dùng đầu ra run01 đã lưu đủ bảy nhóm để đối chiếu top-1/3/5 trên cùng 47 câu
  có nhãn, loại 9 câu null. Không chạy lại model hoặc thay cách xếp hạng.
- Kết quả lần lượt 22/47 (46,81%), 41/47 (87,23%), 46/47 (97,87%). Top-5 thêm
  năm câu so với top-3; vẫn bỏ sót T027, nhãn ENTITY_RELATION ở hạng 6.
- Báo cáo theo từng nhãn, hình thức câu, độ đầy đủ ngữ cảnh và giới hạn:
  top-5 trả 5/7 nhãn, không phải accuracy chọn nhãn cuối.
- [Báo cáo](S5-WBS04.1-top1-top3-top5-report.md), script
  `backend/scripts/report_s5_intent_topk.py`, dữ liệu `outputs/s5_wbs041_topk_20261111/comparison.json`.

## 11/11/2026 — Đối chứng sau chẩn đoán của Huyền

- Tái hiện bằng model thật vấn đề đổi công ty làm đổi nhãn và nhầm đơn/kết hợp.
- Đóng băng kế hoạch 2 × 2 trước inference: gốc/cân bằng mẫu × nguyên văn/che ticker.
  So sánh trên 84 dev, 47 regression có nhãn và 8 known probes; 28 later-check chưa chấm.
- Chuẩn bị 112 mẫu cân bằng DRAFT riêng. Không sửa taxonomy, thư viện/vectors chính,
  matcher runtime, ngưỡng 0,65/0,08 hoặc payload top-3 của Huyền.
- Balanced sửa 8/8 known probes, nhưng dev chỉ 40/84; regression tăng 22→26/47
  với 13 ca sửa đúng và 9 ca đang đúng thành sai. Chưa đề nghị thay baseline.
- Masking không được mặc định áp dụng: có regression và sai tuyến vượt ngưỡng.
- 61 unit test đạt (54 cũ + 7 mới); kiểm chứng độc lập lại 592 bảng thứ hạng từ
  vector model thật, sai lệch cosine tối đa 1,23e-15; source checksum giữ nguyên.
- [Kế hoạch](S5-WBS04.1-improvement-plan.md), [kết quả và giới hạn](S5-WBS04.1-improvement-results.md).

## 12/11/2026 — Giữ mẫu gốc, bổ sung và kiểm tra sau khi đóng băng

- Phân tích 9 ca hồi quy: mất các mẫu tin, sự kiện, xu hướng và ý định kết hợp khi
  thay thư viện. Thử hai bản nối, giữ nguyên 90 hàng và từng byte vector gốc.
- add_all (202 hàng): dev 40/84, bộ cũ 27/47; còn hai ca cũ đúng→sai T034/T036.
- add_focused (138 hàng): bộ cũ 27/47, sửa thêm 5 ca và không làm sai ca cũ đang đúng;
  nhưng dev giảm 34→30/84, nên không đủ điều kiện thay baseline.
- Chốt add_focused theo quy tắc chọn đã ghi trước rồi chấm đúng một lượt bộ 28 câu:
  baseline và ứng viên đều 19/28 top-1; sửa 2 câu, hỏng 2 câu; top-3 giảm 26→25/28.
  Bộ do cùng tác giả soạn, không gọi là test mù; từ lượt này không còn là chưa xem.
- 66 test đạt. Kiểm chứng độc lập 500 bảng thứ hạng từ vector thật, sai lệch tối đa
  1,23e-15; xác nhận nguồn/byte vector gốc không đổi. Chưa triển khai ứng viên mới.
- Không sửa ngưỡng 0,65/0,08, payload top-3 hoặc code router/WebChat của Huyền.
- [Kế hoạch](S5-WBS04.1-additive-plan.md), [báo cáo](S5-WBS04.1-additive-results.md).
