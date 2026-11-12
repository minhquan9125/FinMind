# Đề xuất tối ưu phân loại ý định FinMind — 12/11/2026

Trạng thái: Nhân đã đồng ý thực hiện. Đã hoàn tất các bước 1–3 ngoài runtime;
checkpoint không có ứng viên đạt điều kiện không hồi quy. Chưa làm bước 4.
Kế hoạch trước fit được giữ nguyên trong `outputs/s5_intent_scorer_20261112/plan-snapshot.md`.
Task list: [todo.md](todo.md). Phạm vi ưu tiên: đầu ra Nhân đang cấp cho Huyền.

## Kết luận từ bằng chứng hiện có

- Embedding, thứ tự hàng, checksum và công thức cosine đã được kiểm chứng đúng.
- Matcher dùng cosine toàn câu và điểm lớn nhất của mỗi nhãn; đây là đối chiếu
  độ giống, không phải bộ phân loại được học trực tiếp để phân biệt bảy nhãn.
- Ticker có ảnh hưởng đã tái hiện, nhưng không phải nguyên nhân duy nhất. Nhầm
  câu đơn/MIXED vẫn xuất hiện sau che ticker.
- Giữ 90 mẫu gốc và thêm mẫu tăng bộ cũ 22→27/47; ứng viên chọn trước kiểm tra
  vẫn 19/28 trên bộ để dành, dev giảm 34→30/84. Chưa có bản thay thế đạt.
- 28 câu đã được chấm, không còn là holdout chưa xem. Không thay nhãn đúng, hạ
  ngưỡng hoặc bỏ ca sai để tạo kết quả đạt.

## Hướng khuyến nghị

Thử một bộ phân loại tuyến tính Logistic Regression trên embedding BGE-M3 đã
đóng băng. Nó học phân biệt bảy nhãn từ mẫu có nhãn thay vì gán nhãn theo đúng
một hàng xóm. Đây là giả thuyết kỹ thuật cần đo, không cam kết accuracy sẽ cao.

Giữ nguyên cosine-max-per-label-v1 làm baseline và truy câu mẫu giải thích.
Đây là mở rộng thử nghiệm của thiết kế đối chiếu, không tự coi bộ phân loại mới
là đã đáp ứng/thay thế yêu cầu cosine của S5-WBS04.1 hoặc tự nối vào 04.2.

Chỉ một ứng viên chính và một đối chứng cosine đại diện nhãn (centroid): gom
biến thể theo family rồi tính vector đại diện mỗi nhãn, lấy cosine query với
đại diện. Giữ cùng dữ liệu huấn luyện để so sánh phương pháp, không thêm mẫu mới
trong lượt này. Centroid là đối chứng chi phí thấp, chưa có bằng chứng tốt hơn.

## Các giả định và ranh giới

- Giữ bảy nhãn/taxonomy, model/revision BGE-M3, corpus và quyền truy cập hiện tại.
- Sử dụng vector cache đã kiểm chứng; không fine-tune BGE-M3, không thêm provider,
  LLM hay luật chọn nhãn theo ticker. Chưa có phép đo latency mới để cam kết tốc độ.
- Chỉ dùng các hàng LIBRARY để fit; mẫu thử nghiệm chưa được duyệt phải ghi DRAFT
  rõ trong artifact, không đổi trạng thái duyệt của dữ liệu cũ.
- Dùng cùng tập mẫu 90+112 làm đối chứng phát triển, cân trọng số theo family để
  các biến thể 3/4 câu không được coi như những nguồn độc lập tương đương.
- Chia validation theo family, giữ mọi bản có dấu/không dấu/viết tắt và đổi ticker
  của cùng một khung ở cùng fold; kiểm tra từng fold đủ nhãn trước khi fit.
- Chọn cấu hình/regularization chỉ từ validation ở tập training. Các tập 84 dev,
  47 gold cũ, 8 probe và 28 câu đã chấm dùng báo cáo phát triển/hồi quy, không gọi
  là đánh giá độc lập. Không đưa câu hoặc nhãn test vào fit hoặc calibration.
- Bộ kiểm tra cuối phải có câu mới/khung và công ty mới, đóng băng trước khi chọn
  theo kết quả; ghi rõ cùng tác giả soạn nếu có, không tự gọi là test mù.

## Hợp đồng điểm và ảnh hưởng tới Huyền

- Baseline vẫn xuất score_type=COSINE_SIMILARITY_NOT_PROBABILITY, groups top-3
  và ngưỡng 0,65/0,08 hiện có; không đổi chính sách của Huyền trong lượt thử.
- Classifier xuất nhóm riêng, score_type=CLASSIFIER_PROBABILITY_UNCALIBRATED,
  model/version và nguồn mẫu. Xác suất dự đoán chưa phải xác suất đúng thực tế
  nếu chưa kiểm tra calibration. Không đổi tên điểm classifier thành cosine.
- Không ghép nhãn mới với score/gap cosine cũ; không lấy cosine của mẫu làm điểm
  tin cậy cho nhãn classifier. Centroid cũng có phân bố cosine khác max-per-label.
- Báo top-1/3/5, macro-F1, lỗi đơn/MIXED, đổi công ty và hồi quy trước. Ánh xạ
  argmax nhãn sang tuyến không có ngưỡng chỉ là phép đo riêng, chưa phải policy.
- Sau khi ứng viên có chất lượng tốt mới chuẩn bị tập calibration riêng và đo
  đường cong coverage–sai tuyến cho 04.2. Không áp nguyên 0,65/0,08 lên loại điểm
  mới rồi báo đã so sánh công bằng hoặc đã sửa toàn luồng.
- Huyền vẫn có thể kiểm thử contract/policy bằng fixture hiện có; chẩn đoán chất
  lượng matcher còn mở. 07.2 của Hưng là phụ thuộc riêng, không thay bằng việc
  đẩy tất cả câu sang fallback hoặc gọi đó là chọn tuyến đúng.

## Thứ tự và các điểm dừng

1. Kiểm kê API/score_type hiện có của 04.2 nếu có source; chốt contract baseline
   và ứng viên, trường hợp loại điểm không hỗ trợ. Không đoán code phía Huyền.
2. Đóng băng splits theo family, cấu hình huấn luyện hữu hạn và chỉ số so sánh.
3. Thử classifier + centroid ngoài runtime, dùng cùng vector/data. Lưu toàn bộ
   kết quả, các ca giảm chất lượng và cấu hình không tốt; không sinh hàng loạt ZIP.
4. Chỉ giữ ứng viên khi top-1/macro-F1 dev tốt hơn, không làm sai câu cũ đang đúng
   theo ràng buộc hiện tại. Nếu không đạt, dừng đề nghị thay thế và phân tích lỗi;
   không giảm tiêu chí để chọn cho được một model.
5. Đóng băng ứng viên rồi đánh giá mới; báo nhãn và calibration/coverage riêng.
   Chỉ khi xác nhận được hợp đồng điểm và chất lượng mới đề nghị Huyền tích hợp.

Mốc 90% của S5-WBS04.3 thuộc kiểm thử router và phải có mẫu số/định nghĩa pass,
fallback hợp lệ và loại coverage rõ ràng. Không mặc định classifier accuracy
90% hoặc nhiều fallback là router đã đạt 90%.

## Rủi ro

| Rủi ro | Cách kiểm soát |
|---|---|
| Ít family độc lập, dễ quá khớp | Group split, regularization, hạn chế số cấu hình, báo hạn chế dữ liệu |
| MIXED có nhiều dạng thành phần | Giữ nhãn chính, đo lỗi đơn/kết hợp riêng; không khẳng định đã tách query |
| Xác suất khác cosine, làm hỏng ngưỡng | Kết quả riêng có score_type, không nối runtime, calibration riêng |
| Test đã xem tạo kết luận lạc quan | Chỉ dùng phát triển/hồi quy; đánh giá mới sau đóng băng |
| Chỉ số tăng nhờ từ chối phần lớn câu | Báo coverage và sai tuyến trong phần nhận, không chỉ đếm lỗi |

## Nguồn kỹ thuật

- [Sentence Transformers: Semantic Textual Similarity](https://www.sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html)
- [scikit-learn: Logistic Regression](https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression)
- [scikit-learn: Data leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage)
- [scikit-learn: Probability calibration](https://scikit-learn.org/stable/modules/calibration.html)

Kết quả: classifier dev 66/84 (baseline 34/84), regression 35/47 (22/47),
previous-check đã xem 24/28 (19/28). Còn T038 đúng→sai; centroid còn 3 ca hồi quy.
Không tự hạ điều kiện hoặc áp ngưỡng cũ: dừng ở checkpoint sau bước 3.
Xem `docs/sprint5/S5-WBS04.1-scorer-results.md`. Chưa thay matcher/router chính thức.

## Cập nhật sau kiểm tra đơn/kết hợp — 12/11/2026

Giữ nguyên điểm dừng của raw linear/centroid ở trên. Sau đó thử riêng lớp quyết
định theo từng yêu cầu: V1 thất bại, V2 sửa T038 nhưng còn lỗi kiểm soát, V3 thêm
quy tắc hẹp ROLE/REPORT theo taxonomy. Không đổi training/gold/head/ngưỡng cũ.

V3 đạt 41/47 hồi quy, 32/32 kiểm soát, không làm sai câu linear đang đúng trên
các tập đã đo. Đóng băng rồi kiểm tra 28 câu mới: 25/28; giữ nguyên ba lỗi sau
phép đo. Bộ 42 câu từng mới ở V2 được ghi rõ là đã xem khi làm V3. Lượt lỗi mã
hóa và lượt sửa UTF-8 đều được giữ lại, không đổi model/rules giữa hai lượt.

Đầu ra vẫn là offline advisory: resolution.confidence=null, raw ranking không
đổi. Chưa thực hiện calibration/coverage hoặc tích hợp 04.2; các việc này cần
hợp đồng tiêu thụ evidence riêng. Xem báo cáo objective-results và payload T038.

## Sửa sau review Hưng — 12/11/2026

S5-WBS01.2 tạm dừng theo yêu cầu Nhân. Tiếp tục đúng phần 04.1, giữ V3 và
checksum lịch sử; phiên bản kế tiếp nằm trong module riêng intent_request_review.

1. Viết test tái hiện AI/ai và đảo cách hỏi chức vụ/CEO; sửa tối thiểu, kiểm cả
   câu một ý, câu kết hợp thật và các mục tiêu bài tin/số liệu/trích nguyên văn.
2. Đóng băng trước đánh giá; dùng lại 278 câu đã xem để hồi quy với cùng head,
   embedding và gold. Không làm sai ca V3 đang đúng; không gọi chúng là test mới.
   Chạy probe review với model thật khi khả dụng, giữ cả lỗi thay vì sửa tiếp
   theo điểm đã xem. Không refit hoặc thay ngưỡng Huyền.
3. Ghi đề xuất ranh giới REPORT_CONTENT/NUMERIC/TREND riêng ở trạng thái chờ
   nhóm chốt; không đổi schema đã APPROVED. Ghi hợp đồng metadata bắt buộc và
   các trường hợp phải từ chối cho consumer 04.2, chưa sửa source chưa có ở local.

Điều kiện: test lỗi mới qua, audit V3 cũ còn qua, báo đầy đủ hồi quy và giới hạn;
chưa gọi là sẵn sàng nối router khi hợp đồng/nhãn còn mở. Kiểm bằng pytest tập
Sprint 5, replay từ vector và checksum nguồn. Tách sửa logic, đo và tài liệu.
