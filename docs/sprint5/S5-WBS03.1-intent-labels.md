# S5-WBS03.1 — Chốt nhãn ý định và ranh giới giữa các nhãn

Phụ trách: Hồ Phạm Đăng Nhân. Ngày soạn: 10/11/2026. Giờ dự kiến theo WBS: 2;
không phải giờ thực tế đã ghi nhận.

**Trạng thái: bản đề xuất v2 sau đối chiếu code backup-demo, chờ nhóm thống nhất.** Bảng nhãn và ví dụ
đã soạn; chưa có xác nhận nhãn của nhóm, chưa thay classifier/router đang chạy.
Bản dữ liệu kèm theo: [intent-labels.v1.json](intent-labels.v1.json).
Giữ tên file JSON để có một bản dùng chung; revision nội dung hiện tại là
`s5-intent-labels-v1-draft2` (bảy ID chưa đổi, chưa đóng phiên bản chính thức).

## 1. Cách hiểu

Nhãn trả lời câu hỏi: **người dùng muốn lấy loại thông tin gì?** Tên tài liệu,
công ty, kỳ, định dạng và nhánh tìm kiếm là các thuộc tính khác.

Ví dụ: “Theo BCTN FPT 2025, doanh thu là bao nhiêu?” có ý định SỐ LIỆU,
nguồn BCTN, công ty FPT, kỳ 2025. Không gắn hai ý định chỉ vì có chữ BCTN.

Chỉ định nghĩa bảy nhãn trong phạm vi task. S5-WBS03.2 dùng cùng nhãn để viết
thư viện; 03.3 lưu nhãn cùng vector/model/version; 04.1 trả nhóm gần nhất và
điểm. Chọn nhánh, ngưỡng, hỏi lại và fallback thuộc 04.2; không triển khai ở đây.

## 2. Bảng nhãn đề xuất

| ID ổn định đề xuất | Tên hiển thị | Khi dùng | Không dùng khi | Ví dụ |
|---|---|---|---|---|
| NUMERIC | Số liệu | Lấy giá trị, tỷ lệ hoặc so sánh/chênh lệch số học của chỉ tiêu tài chính/giá tại phạm vi cụ thể | Hỏi chiều hướng/đánh giá; đếm quan hệ hoặc hỏi ngày bổ nhiệm chỉ vì đáp án có số | “Lợi nhuận sau thuế FPT năm 2025 bao nhiêu?” |
| REPORT_CONTENT | Nội dung BCTC/BCTN | Tìm, trích, tóm tắt, giải thích BCTC/BCTN; đọc chính sách, chiến lược, đoạn mô tả/tiểu sử trong các báo cáo đó | Nội dung bài tin/thông báo được hỏi như một bài tin; tên BCTN chỉ làm nguồn cho câu hỏi số liệu/chức vụ/quan hệ | “BCTN FPT 2024 trình bày chiến lược phát triển thế nào?” |
| NEWS | Tin tức | Tìm/liệt kê/trích nguyên văn/tóm tắt/đối chiếu bài tin hoặc thông báo; hỏi nội dung tin bổ nhiệm/sự kiện như một bài tin | Xác định người giữ chức hoặc cạnh quan hệ; lấy một con số từ bài đã chỉ định; yêu cầu tự đánh giá xu hướng thay vì thuật lại nội dung tin | “Tóm tắt tin bổ nhiệm lãnh đạo FPT trong tuần.” |
| PERSON_ROLE | Chức vụ | Xác định người, chức vụ, đơn vị hoặc ngày/giai đoạn bổ nhiệm, miễn nhiệm, giữ chức theo nguồn/phạm vi | Xin bài tin về bổ nhiệm; yêu cầu chép nguyên văn một hàng đã xác định; suy người đương nhiệm từ năm báo cáo | “Ai giữ chức Chủ tịch HĐQT FPT tại thời điểm được hỏi?” |
| ENTITY_RELATION | Quan hệ | Xác định/liệt kê/đếm quan hệ sở hữu của người hoặc doanh nghiệp, công ty con/liên kết/mẹ, đối tác; tìm thực thể tham gia sự kiện cụ thể | Thông tin chỉ về chức vụ một người; chỉ số tài chính; mô tả bài tin; hồ sơ một công ty đã biết không yêu cầu quan hệ | “FPT có những công ty con trực tiếp nào?” |
| TREND | Xu hướng | Nhận định tăng/giảm/trái chiều, diễn biến hoặc tác động dựa trên chuỗi giá và/hoặc tài chính theo thời gian | Chỉ đọc một giá trị hoặc tính chênh lệch đã xác định; nhiều chỉ tiêu cùng phục vụ một nhận định không tự là MIXED | “Giá và tình hình tài chính FPT cho tín hiệu xu hướng thế nào?” |
| MIXED | Kết hợp | Có ít nhất hai mục tiêu thông tin khác nhãn, kể cả tìm quan hệ/thực thể rồi dùng kết quả đó đọc/đánh giá nội dung thuộc nhãn khác | Chỉ có hai công ty, hai kỳ, nhiều chỉ tiêu, câu dài hoặc từ “và”; các mục chỉ cùng một nhãn | “Tìm công ty con của FPT rồi so sánh doanh thu các công ty đó.” |

**BCTC và BCTN là hai giá trị nguồn riêng trong một nhóm nội dung báo cáo**,
không đánh đồng hai loại tài liệu. Đề xuất thuộc tính nguồn: `BCTC`, `BCTN`,
`NEWS`, `PRICE`; danh sách rỗng khi không chỉ định nguồn. Không tự suy BCTC.
Các ID trên là contract đề xuất cho thư viện mới, không phải enum đã được
backend hiện tại hỗ trợ sẵn.

## 3. Quy tắc ranh giới

1. **Đọc mục tiêu, không chỉ khớp từ khóa.** Có chữ “bổ nhiệm” không mặc định
   PERSON_ROLE; có chữ “báo cáo” không mặc định REPORT_CONTENT.
2. **Nguồn không tạo ý định thứ hai.** “Theo bài X, cổ tức bao nhiêu?” là NUMERIC
   với nguồn NEWS. “Theo BCTN, A có phải công ty con B?” là ENTITY_RELATION.
3. **Trích nguyên văn phân theo loại nội dung được yêu cầu.** Khi người/hàng đã
   xác định và chỉ cần chép câu trong BCTC/BCTN: REPORT_CONTENT; chép đoạn trong
   bài tin/thông báo được yêu cầu như một bài tin: NEWS. REPORT_CONTENT không bao
   trùm mọi văn bản có nguồn. Nếu chưa biết loại nguồn và không có ngữ cảnh hợp lệ,
   để UNRESOLVED thay vì đoán. Khi phải tìm người rồi trích tiểu sử trong BCTN
   về người vừa tìm: MIXED (PERSON_ROLE + REPORT_CONTENT). Yêu cầu dẫn nguồn
   hoặc trích bằng chứng chỉ để chứng minh cùng một fact không tự tạo MIXED.
4. **Chức vụ khác tin chức vụ.** Hỏi ai/ngày nào giữ hoặc được bổ nhiệm: PERSON_ROLE.
   Xin tin/bài/thông báo về việc bổ nhiệm: NEWS. Từ “vừa”, “mới”, “hôm nay” không
   tự quyết định nhãn; chúng còn là phạm vi thời gian cần xác nhận.
5. **Số không đồng nghĩa số liệu tài chính.** “Có bao nhiêu công ty con?” là
   ENTITY_RELATION; “bổ nhiệm ngày nào?” là PERSON_ROLE. Tỷ lệ sở hữu cụ thể gắn
   cạnh doanh nghiệp thuộc ENTITY_RELATION, không gán NUMERIC chỉ vì có `%`.
6. **So sánh số học khác nhận định.** “Giá đầu/cuối kỳ và chênh lệch bao nhiêu?”
   là NUMERIC. “Xu hướng giá tăng hay giảm, dựa vào đâu?” là TREND. Một nhận
   định xu hướng sử dụng giá + doanh thu + lợi nhuận vẫn là TREND nếu đó là
   một mục tiêu trả lời thống nhất.
7. **Kết hợp phải nêu được các thành phần.** Ghi hai nhãn thành phần hoặc nhu
   cầu phụ thuộc đầu ra bước trước. “Doanh thu và lợi nhuận FPT” vẫn NUMERIC;
   “tóm tắt BCTN và các tin mới” là MIXED nhưng có thể chỉ cần truy xuất văn bản.
   MIXED không tự là BOTH, cũng không có nghĩa mọi câu phải có graph.
8. **Thiếu scope không xóa ý định.** “Doanh thu năm 2025 bao nhiêu?” vẫn nhận
   biết được NUMERIC nhưng thiếu công ty. Việc hỏi lại do bước điều phối sau
   quyết định; không thêm nhãn nghiệp vụ ASK_CLARIFICATION vào bảy nhãn.
9. **Ngữ cảnh phải đã được xác minh.** “Còn công ty đó?” một mình chưa đủ để
   gán nhãn. Nếu chưa có ngữ cảnh hợp lệ, để chưa xác định; không tự mượn công
   ty/kỳ từ phiên khác. Thiếu công ty không luôn là lỗi, ví dụ tin thị trường.
10. **Không ép mọi câu vào bảy nhãn.** Chào hỏi, yêu cầu tổng hợp hội thoại,
    hỏi nguồn của câu trả lời trước, khái niệm đầu tư, hoặc câu vô nghĩa có
    thể nằm ngoài thư viện này. Giữ trạng thái ngoài phạm vi/chưa rõ để task
    sau xử lý, không nhét vào MIXED để đủ nhãn.
11. **Dữ liệu thiếu không đổi ý định.** Graph rỗng, tài liệu chưa nạp, token hết
    hạn, lỗi kết nối hoặc không đủ quyền là kết quả xử lý, không phải nhãn mới.
12. **Hình thức không đổi nghĩa.** Có dấu/không dấu/viết tắt/paraphrase giữ cùng
    nhãn khi nghĩa đủ rõ; viết tắt mơ hồ phải đánh dấu cần ngữ cảnh, không đoán.
13. **Người, công ty mẹ và tên chỉ tiêu không tự quyết định nhãn.** Hỏi cổ phần
    ông X nắm giữ là ENTITY_RELATION; hỏi chức vụ ông X là PERSON_ROLE. “BCTC riêng
    của công ty mẹ FPT” là phạm vi báo cáo của câu NUMERIC/REPORT_CONTENT, khác với
    “Công ty mẹ của X là ai?”. “EPS là gì?” hỏi khái niệm, khác “EPS FPT 2025 bao nhiêu?”.
14. **Giá trị runtime không phải nhãn chuẩn.** Không sao chép topic, source_type,
    operation hoặc route do router dự đoán vào dữ liệu gán nhãn như đáp án đúng.
    Người gán nhãn đọc yêu cầu và ngữ cảnh hợp lệ; nguồn không được yêu cầu để []
    dù runtime tự chọn BCTC/BCTN. Có thể lưu kết quả runtime riêng để đối chiếu.

## 4. Các cặp dễ nhầm

Đây là ví dụ ranh giới của 03.1, **không phải bộ test độc lập hoặc thư viện
embedding của 03.2**. Không lấy nguyên các cặp này vào cả mẫu và holdout sau này.
Kỳ/ngày trong ví dụ là phạm vi câu hỏi, không khẳng định dữ kiện thực tế.

Năm ví dụ MIXED trong bảng có `component_intents` tương ứng trong JSON:

| Ví dụ | component_intents |
|---|---|
| B09.b | [ENTITY_RELATION, NUMERIC] |
| B10.b | [PERSON_ROLE, NEWS] |
| B12.b | [PERSON_ROLE, REPORT_CONTENT] |
| B14.b | [ENTITY_RELATION, TREND] |
| B16.a | [REPORT_CONTENT, NEWS] |

| Cặp | Câu A / nhãn | Câu B / nhãn | Điểm phân biệt |
|---|---|---|---|
| B01 | “Doanh thu FPT 2025 bao nhiêu?” / NUMERIC | “Tóm tắt chiến lược FPT trong BCTN 2025.” / REPORT_CONTENT | Giá trị chỉ tiêu / nội dung tài liệu |
| B02 | “Theo BCTN 2024, doanh thu FPT bao nhiêu?” / NUMERIC | “Tìm BCTN FPT 2024.” / REPORT_CONTENT | Chỉ nguồn / tìm tài liệu |
| B03 | “Ai là Chủ tịch HĐQT FPT tại ngày được hỏi?” / PERSON_ROLE | “Tìm các tin về việc bổ nhiệm Chủ tịch HĐQT FPT.” / NEWS | Fact vai trò / tập bài tin |
| B04 | “VCB bổ nhiệm ông X ngày nào theo BCTN?” / PERSON_ROLE | “Trích nguyên văn hàng bổ nhiệm ông X trong BCTN VCB.” / REPORT_CONTENT | Xác định thời điểm / chép hàng đã biết |
| B05 | “FPT sở hữu bao nhiêu phần trăm công ty X?” / ENTITY_RELATION | “Biên lợi nhuận gộp FPT bao nhiêu phần trăm?” / NUMERIC | Thuộc tính cạnh / chỉ tiêu tài chính |
| B06 | “FPT có bao nhiêu công ty con?” / ENTITY_RELATION | “Tổng tài sản FPT là bao nhiêu?” / NUMERIC | Đếm tập quan hệ / đọc chỉ tiêu |
| B07 | “Theo bài tin X, mức cổ tức FPT là bao nhiêu?” / NUMERIC | “Tóm tắt bài tin X về cổ tức FPT.” / NEWS | Một giá trị / nội dung bài tin |
| B08 | “Giá FPT đầu/cuối tháng và chênh lệch bao nhiêu?” / NUMERIC | “Giá FPT đang có xu hướng tăng hay giảm?” / TREND | Tính số / nhận định diễn biến |
| B09 | “So sánh doanh thu FPT và CMG năm 2025.” / NUMERIC | “Tìm công ty con của FPT rồi so sánh doanh thu các công ty đó.” / MIXED | Hai công ty không tạo MIXED / graph discovery rồi số liệu |
| B10 | “Doanh thu và lợi nhuận FPT năm 2025?” / NUMERIC | “Ai là Chủ tịch FPT và có những tin bổ nhiệm nào?” / MIXED | Nhiều chỉ tiêu cùng nhãn / hai mục tiêu khác nhãn |
| B11 | “FPT có quan hệ hợp tác với công ty X không?” / ENTITY_RELATION | “Tóm tắt tin về hợp tác FPT và công ty X.” / NEWS | Xác nhận cạnh / đọc tin |
| B12 | “Chép câu ghi chức vụ ông X trong BCTN đã chỉ định.” / REPORT_CONTENT | “Tìm người được bổ nhiệm rồi trích tiểu sử người đó trong BCTN.” / MIXED | Nội dung đã định danh / phụ thuộc bước tìm người |
| B13 | “Trong sự kiện X, doanh nghiệp nào tham gia?” / ENTITY_RELATION | “Bài tin X mô tả sự kiện đó thế nào?” / NEWS | Event → Company / nội dung bài |
| B14 | “Đánh giá xu hướng FPT từ giá và lợi nhuận.” / TREND | “Liệt kê đối tác FPT rồi đánh giá xu hướng từng doanh nghiệp đó.” / MIXED | Một nhận định đa tín hiệu / khám phá quan hệ rồi nhận định |
| B15 | “Tóm tắt chính sách kế toán trong BCTC FPT.” / REPORT_CONTENT | “Theo BCTC, dòng tiền hoạt động FPT bao nhiêu?” / NUMERIC | Giải thích chính sách / giá trị chỉ tiêu |
| B16 | “Tóm tắt BCTN và tin mới của FPT.” / MIXED | “Tóm tắt hai BCTN FPT 2024 và 2025.” / REPORT_CONTENT | Hai loại mục tiêu nguồn / cùng loại nội dung nhiều kỳ |
| B17 | “Trích nguyên văn đoạn bổ nhiệm ông X trong bài tin đã chỉ định.” / NEWS | “Trích nguyên văn đoạn bổ nhiệm ông X trong BCTN đã chỉ định.” / REPORT_CONTENT | Cùng thao tác chép, khác loại nội dung |
| B18 | “EPS FPT năm 2025 bao nhiêu?” / NUMERIC | “EPS là gì?” / null (OUTSIDE_TAXONOMY) | Giá trị chỉ tiêu / khái niệm đầu tư ngoài thư viện bản đầu |
| B19 | “Theo BCTC riêng của công ty mẹ FPT, doanh thu 2025 bao nhiêu?” / NUMERIC | “Công ty mẹ của công ty X là doanh nghiệp nào?” / ENTITY_RELATION | Phạm vi báo cáo riêng / xác định quan hệ mẹ–con |
| B20 | “Ông X giữ chức vụ gì tại FPT?” / PERSON_ROLE | “Ông X sở hữu bao nhiêu cổ phần FPT?” / ENTITY_RELATION | Chức vụ / sở hữu, cùng nhắc một người |

Ví dụ biến thể cùng ý định: “ai la chu tich hdqt fpt?” và “Ai là Chủ tịch HĐQT
FPT?” đều PERSON_ROLE. Viết tắt “CT” một mình chưa đủ để mặc định Chủ tịch.

## 5. Đề xuất dữ liệu gán nhãn cho 03.2

Mỗi câu có `id`, `text`, `intent_label`, `source_types`, `operation`,
`component_intents` nếu MIXED, `annotation_status`, `scope_status`, `annotation_note`, `split` và
`label_schema_version`. `source_types` có thể rỗng nếu không yêu cầu nguồn;
không suy chứng cứ hợp lệ chỉ từ thuộc tính này.

Tách trạng thái nhận diện nhãn khỏi scope: câu có thể đã rõ NUMERIC nhưng
scope chưa đủ. Câu chưa xác định hoặc ngoài phạm vi có `intent_label=null`
và trạng thái tương ứng, không đưa vào thư viện như nhãn thứ tám. Bộ test
sau này vẫn cần các câu này để quan sát giới hạn; xử lý từ chối/hỏi lại ở 04.2.

Trong 03.1 chưa tạo câu mẫu huấn luyện, heldout, vector hoặc điểm tương đồng.
Nhóm phải thống nhất bảng nhãn trước khi đóng phiên bản dùng cho các bước sau.

### Quy ước để hai người gán nhãn giống nhau

- `LABELED`: `intent_label` là một trong bảy ID. Các trạng thái NEEDS_CONTEXT,
  OUTSIDE_TAXONOMY, UNRESOLVED có `intent_label=null`, kèm lý do trong annotation_note.
- MIXED phải ghi ít nhất hai nhãn thành phần khác nhau trong sáu nhãn cơ sở;
  không ghi MIXED làm thành phần. Việc tìm thực thể rồi đọc nội dung chỉ tạo MIXED
  khi bước sau có mục tiêu khác nhãn. Các câu không phải MIXED để component_intents rỗng.
- Thiếu công ty/kỳ nhưng đã rõ mục tiêu: vẫn LABELED, scope_status=PARTIAL.
  Chỉ dùng annotation_status=NEEDS_CONTEXT khi thiếu ngữ cảnh làm chưa rõ cả ý định.
- `operation` là mô tả ngắn thao tác được yêu cầu, chưa phải enum điều khiển runtime.
  Trạng thái gán nhãn không quyết định route hay hành vi hỏi lại. Nếu tách mẫu
  theo công ty/kỳ, phải giữ đúng liên kết mỗi công ty với kỳ tương ứng, phạm vi
  hợp nhất/riêng và lũy kế/riêng quý; các thuộc tính đó không tạo nhãn ý định mới.

Ví dụ dưới đây chỉ minh họa quy ước, không dùng làm mẫu embedding hoặc test độc lập:

| Câu | intent_label | annotation_status | scope_status | component_intents / lý do |
|---|---|---|---|---|
| Doanh thu năm 2025 bao nhiêu? | NUMERIC | LABELED | PARTIAL | [] — thiếu công ty |
| Còn công ty đó? | null | NEEDS_CONTEXT | NEEDS_CONTEXT | [] — chưa có hội thoại trước hợp lệ |
| EPS là gì? | null | OUTSIDE_TAXONOMY | NOT_APPLICABLE | [] — hỏi khái niệm, ngoài bảy nhãn bản đầu |
| Trích đoạn ghi chức vụ ông X trong nguồn đã chỉ định. | null | UNRESOLVED | PARTIAL | [] — giả định chưa có nguồn hoặc ngữ cảnh xác định loại nội dung |
| Tóm tắt BCTN 2025 và tin mới hôm nay của FPT. | MIXED | LABELED | RESOLVED | [REPORT_CONTENT, NEWS] |

Riêng câu hỏi tác động sự kiện như “Tin bổ nhiệm ảnh hưởng FPT thế nào?” cần
nhóm thống nhất thêm nếu chưa rõ người hỏi muốn tác động lên giá/tài chính hay
nội dung khác. Không tự gán TREND chỉ vì có chữ “ảnh hưởng”; tạm UNRESOLVED nếu
ngữ cảnh chưa làm rõ. Đây không phải thay đổi chức năng EVENT_IMPACT hiện có.

### Kết quả rà soát nội bộ ngày 10/11/2026

Đã làm rõ ranh giới trích bài tin/BCTN và bổ sung quy ước trạng thái, thành phần
MIXED cùng ví dụ thiếu ngữ cảnh. Bảng đủ làm đầu vào để nhóm review 03.1; chưa có
bằng chứng về độ chính xác phân loại hay chất lượng vector. Các phép đo đó thuộc
03.2–04.1. Xác nhận nhãn của nhóm vẫn đang chờ, không coi việc rà soát nội bộ là duyệt thay.

## 6. Đối chiếu code hiện tại và điểm cần nhóm chốt

Đã đọc, chưa sửa:

- `backend/src/retrieval_orchestration/hybrid_router/intent_policy.py`:
  `resolve_intent` có business rules/topic và route. Các topic hiện tại không
  tương đương một-một bảy nhãn thư viện, ví dụ SOURCE_FACT_LOOKUP có thể gồm
  đọc số liệu hoặc chép văn bản; MARKET_ANALYSIS có thể gồm xu hướng.
- `backend/src/retrieval_orchestration/hybrid_router/schemas.py`:
  `RouterScope` đã tách source_type, topic, metric_code, person/position/event
  và route_hint. Không đổi enum của RouterOutput trong task này.
- `backend/src/retrieval_orchestration/retrieval_flow/intent.py`: đường fixture
  cũ có thể chặn BCTN + số liệu hoặc News. Không lấy các hạn chế fixture này
  làm định nghĩa ý định mới; không tự sửa runtime để khớp đề xuất.

Các điểm cần nhóm xác nhận cùng bản đề xuất v2:

1. Bảy ID và việc giữ BCTC/BCTN là subtype nguồn, chung nhãn nội dung báo cáo.
2. Các cặp B03/B04/B07/B12: vai trò, tin bổ nhiệm, số trong bài tin và trích
   nguyên văn được phân theo mục tiêu chứ không theo từ khóa.
3. MIXED bao gồm hai mục tiêu khác nhãn; không bắt buộc GRAPH+VECTOR và không
   tự gán BOTH. Routing sẽ được chốt ở task của người phụ trách 04.2.
4. Hồ sơ doanh nghiệp không chỉ rõ báo cáo, khái niệm đầu tư/tổng hợp hội thoại giữ ngoài bảy nhãn thư viện trong bản
   đầu; không làm mất các chức năng đó ở hệ hiện tại khi tích hợp sau này.

Trường xác nhận: **người xác nhận — chưa có; thời điểm — chưa có**. Nhân đã
chuẩn bị bảng và ví dụ để review, không ghi thay quyết định của nhóm.

**Phản hồi leader do Nhân chuyển lại:** tài liệu đủ cho S5-WBS03.1 và bắt đầu
soạn câu mẫu 03.2; trước khi dùng JSON làm chuẩn chung cần bổ sung thành phần cho
năm ví dụ MIXED và để nhóm xác nhận bản nhãn. Đã bổ sung thành phần vào JSON và
bảng mục 4. Phản hồi này không được ghi thành nhóm đã duyệt; trạng thái xác nhận
chung vẫn đang chờ. WebChat cần các task thư viện mẫu, vector hóa và tích hợp sau.

## 7. Tin nhắn gửi nhóm khi review

Nhân đã cập nhật bảng nhãn S5-WBS03.1 bản v2 gồm 7 nhóm và 20 cặp ví dụ dễ nhầm. Đề xuất
tách ý định khỏi nguồn/route: hỏi số trong BCTN vẫn NUMERIC, hỏi tin bổ nhiệm
khác hỏi người giữ chức; MIXED không tự là BOTH. Nhờ nhóm xem 4 điểm mục 6 để
thống nhất bản đề xuất v2, sau đó Nhân dùng đúng bản này viết thư viện và bộ test riêng
ở 03.2. Đây là tài liệu đề xuất, chưa đổi router đang chạy.

## 8. Đối chiếu lại code sau khi chọn adapters.py của backup-demo

Ngày 10/11/2026, nhánh `nhan-sprint-501`: HEAD `ae049bf5`, nguồn merge
`f9f1864` (origin/backup-demo). adapters.py đã khớp nguồn merge; merge chưa được
commit. Phần này mô tả working tree hiện tại, không chỉ code của HEAD cũ.

### Phạm vi đã khảo sát

Đã lập danh mục và checksum 665 file nguồn được Git theo dõi, quét AST các file
Python trong danh mục, không thấy lỗi cú pháp. Đây là kiểm tra cấu trúc tự động,
không phải tuyên bố đã review thủ công từng dòng của 665 file. Đọc sâu các đường
khởi động/API, WebChat và session, chính sách/scope/kế hoạch router, adapter graph,
truy xuất quan hệ, live retrieval, admin news, embedding và frontend chat/graph.
Các vùng auth, ingestion/OCR, dữ liệu thị trường, pipeline, migrations và giao diện
khác được khảo sát qua cấu trúc và điểm gọi liên quan; không chạy lại toàn hệ thống.

### Các điểm làm thay đổi hoặc bổ sung bản đề xuất

| Bằng chứng trong code hiện tại | Kết luận cho 03.1 v2 |
|---|---|
| `api/routers/research_chat.py::get_store` khởi tạo LiveResearchService; `chat_logic.py::append_turn` gọi engine.answer. `api/routers/hybrid_router.py` có endpoint router riêng. | Thư viện 7 nhãn chưa được nối vào WebChat. Không ghi hoàn thành tích hợp chỉ vì đã có router hoặc giao diện chat. |
| `intent_policy.py::resolve_intent` có COMPANY_PROFILE, INVESTING_KNOWLEDGE, PORTFOLIO_EDUCATION, SECTOR_RESEARCH, EVENT_IMPACT, OVERALL_COMPARISON. | Bảy nhãn theo WBS chưa bao phủ mọi chức năng đang có. Giữ chúng ngoài thư viện bản đầu hoặc UNRESOLVED tùy câu; không tự gán MIXED hoặc thêm nhãn thứ tám. |
| `decision_engine.py::ScopeResolver.resolve` tự gán source_type BCTN cho GRAPH và BCTC cho nhiều trường hợp khác. | Nguồn router chọn mặc định không phải yêu cầu nguồn của người dùng; dữ liệu chuẩn không được học theo mặc định này. |
| `decision_engine.py::DecisionEngine.decide` gọi predictor trả graph_score/content_score khi policy chưa chọn route; ArtifactPredictor dùng model router riêng. | Đây là điểm route của mô hình hiện có, không phải cosine similarity của thư viện ý định Sprint 5. 04.1 phải trả nhóm ý định + điểm riêng. |
| `decision_engine.py` giữ targets theo từng công ty/kỳ; reporting_filters phân biệt hợp nhất/riêng và YTD/STANDALONE_QUARTER. | So sánh nhiều công ty/kỳ vẫn NUMERIC nếu cùng mục tiêu. Từ “công ty mẹ” trong phạm vi báo cáo không tự là ENTITY_RELATION. Bổ sung B19. |
| `adapters.py::_relationships` ánh xạ entity_id qua registry sang resolved_companies, rồi engine truyền kết quả sang nhánh nội dung khi BOTH. | Giữ ca MIXED khám phá công ty con rồi đọc số liệu. Tên công ty trong graph chưa ánh xạ được không phải lý do đổi nhãn hoặc tự đoán ticker. |
| `documents/embeddings.py` có embed_texts/embed_query và chuẩn hóa L2; core/config.py pin BAAI/bge-m3 cùng revision. | Có thể tái sử dụng dịch vụ ở 03.3/04.1; 03.1 chưa tạo vector. Nhãn, library version và model/revision phải được lưu riêng, không dùng model route làm model embedding. |

### Đối chiếu topic hiện có với bảy nhãn

Đây là hướng dẫn đọc câu hỏi, không phải bảng chuyển đổi enum tự động:

| Topic runtime | Cách xem trong thư viện mới |
|---|---|
| FINANCIAL_RESEARCH, FINANCIAL_COMPARISON, SOURCE_FACT_LOOKUP | Có thể NUMERIC, REPORT_CONTENT hoặc NEWS tùy mục tiêu và loại nội dung; không ánh xạ 1–1. |
| RELATIONSHIP_LOOKUP, PERSON_LOOKUP | PERSON_ROLE khi hỏi chức vụ; ENTITY_RELATION khi hỏi sở hữu/cạnh; xin bài tin bổ nhiệm vẫn NEWS dù policy hiện có thể trả GRAPH. |
| PRICE_ANALYSIS, MARKET_ANALYSIS | TREND khi thực sự hỏi diễn biến giá/tài chính; khái niệm hoặc phân tích khác không tự là TREND. |
| MARKET_DAILY_DIGEST | NEWS nếu yêu cầu tổng hợp tin; chưa gán chỉ từ tên topic. |
| MULTI_HOP | MIXED khi xác định được ít nhất hai nhãn thành phần, không chỉ vì có hai bước thực thi. |
| COMPANY_PROFILE | “FPT hoạt động trong lĩnh vực nào?” ngoài bảy nhãn bản đầu; nếu yêu cầu tóm tắt phần lĩnh vực trong BCTN xác định thì REPORT_CONTENT. |
| INVESTING_KNOWLEDGE, PORTFOLIO_EDUCATION | Ngoài thư viện bản đầu; không ngừng hỗ trợ chức năng đang có khi tích hợp về sau. |
| SECTOR_RESEARCH, INDUSTRY_ANALYSIS, EVENT_IMPACT, OVERALL_COMPARISON | Phải đọc mục tiêu cụ thể; UNRESOLVED nếu chưa đủ quy ước. Không tự coi tất cả là MIXED. |

### Quan sát chạy offline và giới hạn

Chạy 15 câu qua ScopeResolver + DecisionEngine với ngày tham chiếu 10/11/2026,
predictor stub, không gọi adapter, DB, Neo4j, Gemini hay embedding. Kết quả chỉ
chứng minh hành vi policy/scope trên các câu đó, không đo độ chính xác mô hình.

- “Theo BCTN 2024, doanh thu FPT bao nhiêu?”: topic FINANCIAL_RESEARCH,
  source_type BCTN, route VECTOR. Giữ nhãn chuẩn NUMERIC.
- “Tìm các tin về việc bổ nhiệm Chủ tịch HĐQT FPT.”: policy trả GRAPH /
  RELATIONSHIP_LOOKUP / BCTN. Nhãn chuẩn vẫn NEWS; ghi nhận khác biệt, không sửa
  đáp án để khớp implementation hiện tại.
- “Tóm tắt bài tin về cổ tức FPT.”: trả VECTOR / FINANCIAL_RESEARCH / BCTC.
  Dữ liệu chuẩn phải giữ NEWS và nguồn NEWS theo yêu cầu, không học nguồn BCTC đó.
- “FPT hoạt động trong lĩnh vực nào?” được policy nhận COMPANY_PROFILE;
  “EPS là gì?” được nhận INVESTING_KNOWLEDGE. Việc nằm ngoài thư viện bảy nhãn
  không có nghĩa toàn ứng dụng không hỗ trợ các câu này.
- “Tìm công ty con của FPT rồi so sánh doanh thu các công ty đó.” trả BOTH /
  MULTI_HOP. Giữ MIXED với ENTITY_RELATION + NUMERIC.

Bằng chứng máy đọc nằm tại `outputs/s5_wbs031_20261110/post-merge-reassessment.json`
và `source-inventory.json`. Bản v2 bổ sung B17–B20, quy tắc 13–14 và bảng đối chiếu;
giữ nguyên bảy ID. Chưa sửa runtime hoặc 24 ca test thất bại đã báo ở lần kiểm tra merge.
Nhóm cần xác nhận rõ việc giữ hồ sơ doanh nghiệp/kiến thức đầu tư ngoài thư viện
bản đầu trước khi đóng phiên bản; nếu muốn mở rộng phải thống nhất lại phạm vi WBS.
