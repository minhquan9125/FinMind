# Đề xuất tối ưu phân loại ý định FinMind — 12/11/2026

## Kế hoạch đang áp dụng: hoàn thiện ý định v2 — 13/11/2026

Nhân giao quyền chọn phương án cho trợ lý và đã cho phép bắt đầu triển khai.
Phần này thay hướng triển khai v1 bên dưới cho công việc mới; các ghi chép cũ
được giữ để truy vết. Tài liệu nguồn: [đề xuất Hưng](../docs/sprint5/S5-INTENT-v2-gui-Nhan.md).
Trạng thái: ĐÃ SỬA CÁC LỖI XÁC NHẬN Ở R2 ĐỂ REVIEW; chưa nghiệm thu chất lượng kín hoặc
hiệu năng. Không ghi thành nhóm đã duyệt. Checklist hiện tại ở [todo](todo.md).

### Điều chỉnh sau đánh giá — ưu tiên đúng, tốc độ xử lý sau

Theo yêu cầu mới của Nhân, tập trung hoàn thiện chức năng và bằng chứng trước.
Mục tiêu hiệu năng 500 ms được giữ để truy vết nhưng hoãn tối ưu trong vòng này;
không ghi hiệu năng đã đạt hoặc suy 100% chính xác từ việc hoàn tất task.

Kiểm tra bổ sung phát hiện 16 biến thể của 7 family trong LIBRARY bị luật đổi
từ nhãn đúng của classifier sang nhãn sai, cùng lỗi lời chào che yêu cầu tư vấn
và bỏ qua yêu cầu ngữ cảnh. Bằng chứng ở
`outputs/s5_intent_v2_20261113/fix1/review-before.json`. Đây là kết quả trước sửa;
bản r2 đã được kiểm chứng ở `fix1/verification.json`: 409 test đạt, 627 ca đã
biết không hồi quy, 2.165 biến thể kiểm luật đạt và 33 ca gọi model thật đạt.
Model/vector/gold/điểm gốc giữ nguyên; bộ kín và review nhóm vẫn còn mở.

1. **Đóng băng và tái hiện lỗi** (nhỏ, rules/runtime tests): thêm test cho 7
   family sai và hai ca lời chào, kèm đối chứng chỉ chào, hỏi giá thật, thuật lại
   nguồn và yêu cầu trích bằng chứng. Các test phải thất bại đúng nguyên nhân
   trước sửa. Không sửa gold hoặc thay vector để làm mất lỗi.
2. **Sửa mục tiêu yêu cầu và lời chào** (vừa, rules/classifier + tests): lời chào
   chỉ là toàn bộ ý định khi câu thực sự chỉ chào; câu có tham chiếu vẫn cần
   context. Tách yêu cầu tìm/danh sách tin khỏi lấy số; nhận diện chức vụ dù nguồn
   là thông báo/báo cáo; phân biệt số kế hoạch đã công bố, giá mục tiêu trong tin
   với tự dự báo; phân biệt so sánh chất lượng với phép tính. Dùng quy tắc chung,
   không điều kiện theo ticker/ID. Luật chỉ đổi nhãn khi có bằng chứng đủ rõ;
   trường hợp chưa đủ phải giữ thông tin chưa rõ thay vì ép một nhãn mới.
3. **Kiểm không hồi quy** (vừa, tests/evaluator): kiểm lại 470 mẫu, 110 câu phát
   triển và 47 câu hồi quy theo nghĩa nhãn v2. Mọi lỗi đã biết phải được sửa,
   các ca trước đúng không đổi sai. Báo riêng nhãn, thành phần MIXED, trạng thái
   cần context/chưa rõ và cờ hạn chế; không coi nhãn đúng là đã sẵn sàng thực hiện.
   Thêm kiểm đổi ticker, có/không dấu, tiền tố lịch sự và nguồn trích dẫn.
   Các biến thể này là hồi quy, không phải câu kín độc lập.
4. **Freeze rồi đo bộ độc lập** (phụ thuộc đầu vào): giữ BGE, vector và classifier
   hiện tại khi sửa các lỗi luật đã xác nhận. Sau khi chốt ứng viên, đo ít nhất
   110 câu kín/10 mỗi nhãn do người khác soạn. Bộ AI soạn thêm nếu có phải ghi
   đúng nguồn và phạm vi, không tự thay cho xác nhận độc lập của nhóm. Giữ mục
   tiêu chất lượng đã định; ca không rõ không được bỏ khỏi mẫu số để làm đẹp số.
   Nếu dùng kết quả bộ kín để sửa, chuyển nó thành hồi quy và cần bộ kín mới.
5. **Bàn giao phần Nhân** (nhỏ, README/history): artifact, API, payload mẫu,
   lệnh chạy lại và báo cáo nhất quán; đề nghị Hưng review 11 nhãn/hàm, Huyền đối
   chiếu contract ở phần của mình. Không tự sửa consumer, Chat hoặc DB production.

Chỉ huấn luyện lại nếu còn bằng chứng lỗi từ classifier/dữ liệu sau sửa luật.
Không thay model để xử lý những ca model hiện đã xếp đúng. Vòng này hoàn thành
phần chức năng và bàn giao khi không còn lỗi đã biết, kiểm không hồi quy đạt và
bằng chứng đầy đủ; chốt nghiệm thu toàn task còn cần review/bộ kín của nhóm.

### Kết quả cần bàn giao

Một bộ phân loại nhận câu hỏi, trả nhóm ý định được đề xuất, các nhóm gần nhất,
loại điểm và những chỗ chưa rõ để Hưng gọi trong Chat và Huyền xử lý chính sách.
Các sản phẩm bắt buộc: schema v2, mẫu/test tách biệt, artifact vector/model,
module phân loại dùng chung, test và báo cáo chạy thật. Nhân thực hiện 03.1–03.3
và 04.1 mở rộng. Tích hợp Chat là 05.1 của Hưng; consumer/ngưỡng là phần Huyền.

### Phương án kỹ thuật đã chọn

- Giữ BAAI/bge-m3 và revision hiện có. Dùng embedding đóng băng với Logistic
  Regression huấn luyện lại cho đủ 11 nhãn. Không dùng nguyên trọng số 7 nhãn.
- Giữ cosine theo thư viện làm đối chứng trên cùng dữ liệu v2 và tìm ví dụ tham
  khảo. Điểm classifier, cosine và bằng chứng luật được lưu riêng.
- Chỉ có một mô hình embedding trong tiến trình, lấy từ dịch vụ backend hiện có.
  Nạp artifact/model phân loại một lần; mỗi câu chỉ tạo vector cần thiết, gom các
  vế độc lập trong cùng batch khi có thể. Không fine-tune BGE-M3 trong vòng này.
- Kế thừa các ranh giới đã kiểm tra của V7 trong module v2 riêng cho mục tiêu rõ
  ràng và tách nhiều ý. Sửa hai lỗi đã
  tái hiện: hỏi chênh lệch bằng tiền và thuật lại xu hướng trong bài báo.
  Không thêm luật theo mã công ty hoặc ID câu test.
- Chọn regularization bằng chia fold theo family trong LIBRARY; mọi biến thể của
  một tình huống ở cùng fold/split. Không chọn cấu hình trên bộ nghiệm thu kín.
- V1, classifier 7 nhãn, manifests, run01–run03 là lịch sử bất biến. V2 dùng tên,
  thư mục và version riêng. Một phiên bản được chọn rõ khi nạp; không trộn hai bộ.

### Quy ước 11 nhãn v2

| Nhãn | Phạm vi đã chọn |
|---|---|
| PRICE | Giá/khối lượng giao dịch và biến động số học cụ thể của dữ liệu thị trường. |
| NUMERIC | Giá trị, tỷ lệ, chỉ tiêu và chênh lệch số học tài chính, kể cả sản lượng được hỏi như chỉ tiêu hoạt động. |
| ANALYSIS | Nhận định, giải thích tài chính, xu hướng; bao gồm giải thích khái niệm/chỉ tiêu tài chính để giữ khả năng hỏi kiến thức hiện có. |
| NEWS | Tìm hoặc thuật lại nội dung bài tin, kể cả bài tin nói về giá hay xu hướng. |
| REPORT_CONTENT | Tìm/giải thích/tóm tắt nội dung BCTC/BCTN; tên báo cáo chỉ làm nguồn không tự quyết định nhãn. |
| PERSON_ROLE | Người, chức vụ và thời điểm giữ/bổ nhiệm/miễn nhiệm; gồm thành viên ban kiểm soát. |
| ENTITY_RELATION | Sở hữu, cổ đông cá nhân/doanh nghiệp, công ty con/liên kết và quan hệ doanh nghiệp. |
| COMPANY_OVERVIEW | Giới thiệu ngành, hoạt động và hồ sơ chung doanh nghiệp. |
| CONVERSATION | Chào hỏi, nối tiếp, chọn mục, hỏi nguồn câu trước, tổng hợp, phiên mới; không tự suy nội dung từ phiên khác. |
| OUT_OF_SCOPE | Yêu cầu đưa quyết định mua/bán, tự dự báo giá/giá mục tiêu, hoặc nội dung ngoài chức năng sản phẩm. |
| MIXED | Ít nhất hai mục tiêu khác nhóm có thể chỉ ra; danh sách nhiều chỉ tiêu cùng nhóm không tự là MIXED. |

Các quyết định ranh giới cần đưa vào tài liệu và cặp test ngay từ đầu:

- Hỏi giá tăng bao nhiêu đồng/% là PRICE; hỏi doanh thu tăng bao nhiêu là NUMERIC;
  yêu cầu nhận định tăng/giảm là ANALYSIS. Không chỉ nhìn chữ "tăng".
- "Bài báo nhận định xu hướng thế nào?" là NEWS; thuật lại báo cáo là REPORT_CONTENT.
- "P/E là gì?" thuộc ANALYSIS, với loại câu con kiến thức do Hưng xử lý tầng 2.
  Đây là lựa chọn thiết kế bổ sung so với bảng Hưng gửi, cần nêu khi bàn giao.
- Hỏi con số/nhận định đã được công bố trong nguồn không tự thành OUT_OF_SCOPE
  chỉ vì có từ dự báo/giá mục tiêu; phân biệt thuật lại nguồn với tự khuyến nghị.
- Hỏi doanh thu công ty con đã xác định là NUMERIC. Nếu phải tìm công ty con rồi
  lấy số của các công ty vừa tìm: MIXED (ENTITY_RELATION + NUMERIC).
- "Còn SSI?", "số 2" là CONVERSATION và cần ngữ cảnh hợp lệ. Chưa biết mã/kỳ
  không đồng nghĩa chưa biết ý định. Câu không hiểu rõ dùng trạng thái chưa xác định.
- MIXED chứa OUT_OF_SCOPE phải giữ thành phần bị hạn chế để tầng sau chặn phần
  đó. Chưa có chính sách xử lý từng phần thì chưa cho tự thực hiện toàn câu.
  MIXED không mặc định BOTH; ANALYSIS cũng không mặc định một nguồn duy nhất.

### Giao tiếp giữa ba phần

- Nhân cung cấp một điểm gọi phân loại, nhận câu hỏi và embedder đang dùng. Caller
  có thể cung cấp ngữ cảnh đã xác minh; Nhân không làm cơ chế lưu/kế thừa phiên.
- Kết quả giữ envelope base_ranking + resolution; thêm version schema/thư viện/
  classifier rõ ràng. Base ranking có các nhóm, điểm, ranking_policy, score_type.
  Resolution có nhãn đề xuất, reason, component_labels, explicit_evidence,
  unresolved_requests, confidence=null và runtime_enabled=false.
- Classifier v2 có policy mới, đề xuất intent-linear-v2; điểm vẫn được khai báo
  CLASSIFIER_PROBABILITY_UNCALIBRATED. Bằng chứng luật có policy v2 riêng và
  DECISION_EVIDENCE_NO_CONFIDENCE. Không gắn điểm nhãn gốc cho nhãn bị luật đổi.
- Đầu ra có trạng thái rõ: đề xuất được nhãn / cần ngữ cảnh / chưa xác định.
  Hai trạng thái sau không tạo nhãn nghiệp vụ thứ 12. V2 phải quy định rõ lúc nào
  intent_label có thể null; consumer cần kiểm trạng thái trước khi chọn nhánh.
- runtime_enabled=false nghĩa là đầu ra mới là đề xuất, chưa được phép tự cho
  SEARCH; hàm vẫn có thể được gọi thật trong Chat. Ngưỡng của Huyền chưa được
  áp dụng cho xác suất chưa hiệu chỉnh. Calibration chỉ làm sau nếu nhóm cần
  bật tìm kiếm thẳng, không gộp vào phạm vi classifier đề xuất lần này.
- Consumer hiện có hỗ trợ policy V7 nhưng còn 7 nhãn. Nhân gửi hợp đồng v2 và
  payload mẫu để Huyền cập nhật; không tự sửa intent_routing.py. Hưng nối Chat,
  slot và điều phối các luồng PRICE/CONVERSATION/OUT_OF_SCOPE theo tầng 2.
- Cấu hình sai, model/revision/artifact không khớp: báo lỗi kỹ thuật rõ ràng,
  không giả kết quả phân loại. Trong request không đọc lại file hoặc tải model
  qua mạng; chuẩn bị model cache và artifact tại bước khởi tạo.

### Dữ liệu và cách đo

- LIBRARY: tối thiểu 20 câu gốc khác tình huống mỗi nhãn (ít nhất 220 câu gốc),
  mỗi nhóm con có ít nhất 3 tình huống. Thêm biến thể có dấu/không dấu/viết tắt/
  lỗi gõ khi vẫn giữ nghĩa. Không tính ba biến thể là ba tình huống độc lập.
- DEVELOPMENT: tối thiểu 10 câu mỗi nhãn, không giao family với LIBRARY. Dùng
  phân tích lỗi; không gọi đây là đánh giá kín. Mọi lần chỉnh phải ghi version.
- REGRESSION: bộ cũ và hai lỗi TREND mới dùng để bảo vệ hành vi đã biết. Các câu
  cần đổi nhãn theo v2 có bản gán nhãn v2 riêng và lý do; không sửa gold v1.
- ACCEPTANCE: tối thiểu 10 câu mỗi nhãn do người khác soạn, giữ kín tới khi đóng
  băng bản ứng viên. Nhờ Huyền/Hưng cung cấp; không phải điều kiện để bắt đầu các
  bước của Nhân. Nếu chưa có thì bàn giao kỹ thuật được, chưa chốt chất lượng kín.
- Chọn phương pháp trên dữ liệu phát triển/validation; bộ kín chỉ đo sau freeze.
  Nếu dùng kết quả kín để sửa, tập đó chuyển thành hồi quy và cần bộ kín mới.
- Đo top-1, macro-F1, recall từng nhãn, confusion matrix, lỗi OUT_OF_SCOPE, kết
  quả chưa xác định và thành phần MIXED. Câu có gold mà chưa trả được nhãn tính
  là không đúng; không bỏ khỏi mẫu số để tăng accuracy.
- Lưu cosine và classifier trên cùng tập v2. Chỉ so với v1 ở các câu có ý nghĩa
  nhãn tương đương, báo mọi thay đổi; không trộn accuracy hai taxonomy khác nhau.
- Độ trễ p50/p95 tính toàn bộ hàm phân loại sau warmup, gồm tách/encode vế nếu có;
  báo riêng cold start và nhóm câu đơn/MIXED. Nêu máy, độ dài đầu vào và số lần đo.

### Các bước và checkpoint

1. Bảng nhãn + đầu ra mẫu (03.1, 04.1): viết schema v2 và cặp ranh giới; ghi bảng
   đổi nhãn/mã fallback. Đạt khi mọi ví dụ có một cách gán hoặc lý do chưa rõ,
   các loại điểm và trạng thái có nghĩa rõ. Kiểm bằng đọc chéo đặc tả.
2. Bộ câu (03.2): xây LIBRARY/DEVELOPMENT/REGRESSION và validator tách family,
   nhãn thành phần, nguồn, biến thể. Đạt khi đủ phủ và không rò rỉ. Kiểm bằng
   validator + review mẫu. Huyền/Hưng soạn bộ kín song song sau khi nhận bảng nhãn.
3. Artifact (03.3): encode bằng BGE-M3 hiện có, fit classifier 11 nhãn từ LIBRARY,
   lưu vector/NPZ/manifest. Đạt khi model/revision/shape/checksum khớp và tái tính
   được điểm mà không fit lại. Không dùng pickle hoặc ghi DB production.
4. Hàm dùng chung (04.1): nạp một lần, dùng embedder chia sẻ, trả envelope đúng
   contract và ví dụ tham khảo. Đạt khi test 11 nhãn, metadata lỗi, input rỗng,
   MIXED/CONVERSATION, startup lỗi và việc không nạp lặp đều qua bằng fake embedder.
5. Checkpoint phát triển: đánh giá thật trên DEVELOPMENT/REGRESSION; xử lý lỗi
   ranh giới bằng logic chung. Đạt khi không còn hồi quy chưa giải thích ở các
   câu cùng nghĩa nhãn; báo đầy đủ lỗi còn lại trước khi đóng băng.
6. Freeze + run04: ghi hash phương pháp/nguồn/dữ liệu trước đo, chạy bộ riêng và
   bộ kín với BGE-M3 thật, đo latency máy demo. Mọi lần đo ở thư mục mới.
7. Bàn giao: một gói phiên bản nhất quán gồm schema, library/vector/model,
   hàm/test, báo cáo và ví dụ gọi. Chia commit theo thay đổi để review được;
   không buộc tất cả vào một commit lớn. Hưng/Huyền đối chiếu phần tích hợp riêng.

### Tiêu chí chọn để chốt phần Nhân

- Artifact tái tạo được; unit/contract test đều đạt, không bỏ test hoặc bỏ ca sai.
- Trên bộ nghiệm thu kín: top-1 >= 90%, macro-F1 >= 0,85, recall từng nhãn >= 80%.
- Không có câu OUT_OF_SCOPE được phân loại thành yêu cầu trả lời thông thường
  trên tập nghiệm thu đã ghi; báo rõ mẫu số. Việc chặn thực tế trong Chat do phần
  policy/tích hợp kiểm tiếp, không dùng việc luôn chặn mọi câu để báo đúng nhãn.
- p95 <= 500 ms trên máy demo sau warmup cho dữ liệu đã mô tả; đo thực tế trước
  khi ghi đạt. Không loại câu MIXED chậm hoặc lần lỗi ra khỏi báo cáo.
- Nếu bất kỳ tiêu chí chưa đạt: trạng thái cần cải thiện, giữ nguyên ngưỡng và
  báo số thực. Không gọi bộ do cùng tác giả viết là nghiệm thu kín độc lập.
- Giao tiếp v2 được Hưng/Huyền kiểm tra ở phần của họ trước khi bật luồng thật.
  Chưa nối Chat không có nghĩa artifact chưa làm xong; cũng không suy Done toàn
  hệ thống từ kết quả riêng của Nhân. 01.2 vẫn là task riêng đang tạm dừng.

Mốc mục tiêu theo đề xuất Hưng: tài liệu nhãn/contract trước 15/11, bản triển khai
và báo cáo trước 18/11 nếu có môi trường model và bộ kín. Đây là kế hoạch cho lúc
bắt đầu triển khai. Bản triển khai và số đo hiện tại ở
[bàn giao v2](../docs/sprint5/intent-v2/README.md); giữ nguyên các ngưỡng nghiệm thu.

## Lịch sử phương án v1 (giữ nguyên để truy vết)

## Phạm vi hiện tại theo Nhân

Chỉ tiếp tục S5-WBS03.1–03.3 và S5-WBS04.1 của Nhân. Các mục consumer/ngưỡng/
fallback/router bên dưới là lịch sử hoặc phụ thuộc để biết, không phải việc Nhân
nhận làm. Bản review hiện tại dùng 192 test riêng của Nhân và audit 345 quyết định.
Chưa chốt Done: chờ Hưng review, vẫn ghi rõ lỗi phân loại và thử nghiệm V7 offline.

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

## Nhận diện lấy giá trị tài chính — sau REVIEW-03

Nhân đồng ý xử lý tiếp lỗi classifier chọn ENTITY_RELATION cho câu hỏi doanh
thu. Module mới bổ sung guard NUMERIC theo chỉ tiêu + thao tác lấy giá trị,
loại trừ đếm quan hệ, chức vụ/ngày, bài tin, trích nguyên văn và đánh giá.
Không có ngoại lệ ABC hoặc thay schema, vector/head, ngưỡng và router runtime.

Các lát: (1) test tái hiện và ca âm; (2) đóng băng logic rồi replay 293 câu đã
xem từ vector có sẵn, điều kiện không làm sai câu V4 đang đúng; (3) kiểm chứng
thêm các chỉ tiêu/cách hỏi, lưu mọi lỗi và audit; (4) báo cáo/history. Không
gọi 15 probe cũ là test mới; ranh giới kế hoạch lợi nhuận vẫn DRAFT.

## Sửa NEWS và yêu cầu mở đầu bằng Đọc

Nhân đồng ý sửa ba lỗi NV-13/NV-19/NV-20. Kế hoạch đóng băng riêng tại
`docs/sprint5/S5-WBS04.1-news-mixed-plan.md`. Viết test đỏ trên bản NUMERIC,
thêm mục tiêu bài tin và nhận diện vế Đọc độc lập ở module kế tiếp. Chỉ nâng
thành MIXED từ các mục tiêu rõ ràng; không nới ngưỡng ghép xác suất. Kiểm tra
hồi quy toàn bộ 313 câu đã xem và giữ model, training, nhãn, raw ranking.

## Hoàn thiện theo review vòng 2

Nhân đồng ý thực hiện tiếp. Kế hoạch máy đọc được và tiêu chí đóng băng ở
`outputs/s5_intent_review2_20261112/plan.json`. Sửa va chạm đọc/độc, lương/lượng
bằng bằng chứng có dấu và ngữ cảnh; đo các cách hỏi chức vụ/tin/giải thích mới.
Giữ source V3–V6. Dùng 313 hàng làm hồi quy; 32 probe bổ sung do cùng tác giả
soạn, 5 câu không chốt gold chỉ kiểm không ép nhãn từ quy tắc sai.

Đã đọc consumer thật từ nhánh Huyền, commit 8e854d47. Chuẩn bị bản sửa tại
nhánh Nhân: metadata thiếu/sai phải bị từ chối, không gửi AI fallback; MIXED
chưa xác minh thành phần không tự BOTH. Không thay ngưỡng hoặc source remote.
Kiểm tra luồng giá hiện có bằng analyze_live, giữ nhãn NUMERIC theo schema.
Chưa nối Web Chat hoặc tự phê duyệt các ranh giới nhóm chưa chốt.

Kết quả: 313 hàng không hồi quy, 27/27 probe có gold, 5/5 không ép nhãn; 276
test qua. prepare_intent_review không chấp nhận đề xuất NUMERIC của câu độc lập
chưa rõ mục tiêu; trả NEED_VALIDATION thay vì đổi nhãn tùy ý. Bản sửa consumer
và patch mới ở nhánh Nhân; chưa triển khai. Không dùng tỷ lệ chặn làm accuracy
router. Bản cuối run03 (metadata LF) và integration-final-checks.json; một trang bàn giao hiện tại.
