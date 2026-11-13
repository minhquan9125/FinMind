# S5-WBS07.1 — Điều kiện fallback và JSON phân loại

Ngày: 13/11/2026. Cơ sở: code 04.2 của Huyền, giữ nguyên sau merge 19256961.
Người dùng đã chốt làm theo code hiện tại, không thay bằng quy tắc ngưỡng mới
trong đề bài 07.1. Task này chốt contract và validator; gọi provider, timeout
thực tế và nối Web Chat thuộc 07.2.

## 1. Điều kiện gọi theo 04.2 hiện tại

04.2 kiểm công ty/kỳ trước, rồi kiểm contract của bộ phân loại. 07.1 nhận kết
quả đã kiểm đó, không chạy lại embedding hoặc tự quyết định từ một con số score.

| Đầu ra 04.2 / reason_code | Cho gọi AI ngoài |
|---|---|
| ASK_CLARIFICATION: thiếu/mơ hồ công ty, kỳ sai, câu hỏi sai | Không; giữ hỏi lại |
| SEARCH ở chế độ diagnostic đã bật rõ ràng | Không; giữ quyết định nội bộ |
| NEED_FALLBACK / DIRECT_SEARCH_DISABLED | Có, kể cả cosine cao; mặc định hiện tại |
| NEED_FALLBACK / LOW_CONFIDENCE, SMALL_GAP, LOW_CONFIDENCE_AND_SMALL_GAP | Có; các reason này xuất hiện trong diagnostic |
| NEED_FALLBACK / CLASSIFICATION_ERROR | Có; wrapper 04.2 bắt lỗi matcher/timeout |
| NEED_FALLBACK / UNCALIBRATED_CLASSIFICATION, LABEL_DISAGREEMENT | Có; không áp ngưỡng cosine lên V7/probability |
| NEED_FALLBACK / MIXED_COMPONENTS_REQUIRED | Có; chưa đủ căn cứ chốt route cho MIXED |
| IntentClassificationContractError, handoff thiếu/sai/mâu thuẫn hoặc cũ | Không; caller xử lý lỗi contract nội bộ |

Handoff phải giữ đủ company_ticker/period/company_source trong scope và các
trường score_type/candidates/allowed_labels của payload nội bộ. Thiếu trường
khác với khai báo null. Không đổi scope đã mất period thành một request không
lọc kỳ; không suy loại điểm khi metadata thiếu hoặc sai.
company_source chỉ nhận CURRENT/CONTEXT khi có công ty; không có công ty thì
nguồn phải là null. Nhánh SEARCH diagnostic cũng kiểm scope, reason và mapping
của nhãn đơn trước khi giữ kết quả; nhánh ASK yêu cầu câu hỏi lại là chuỗi
không rỗng. SEARCH của MIXED vẫn do 04.2 xác định từ thành phần query ở chế độ
diagnostic, không dùng 07.1 để bật SEARCH trong chế độ mặc định.

0,65/0,08 vẫn là cấu hình diagnostic của 04.2; không thay đổi chúng hoặc bật
SEARCH mặc định. Không thêm ngoại lệ “BOTH đủ dữ kiện thì bỏ fallback” vào chế
độ mặc định. Đầu ra rỗng/hỏng contract của matcher vẫn là lỗi contract như 04.2,
không giả thành lỗi kỹ thuật để gọi AI. Không gọi lại fallback khi validation
thất bại; caller chuyển sang hỏi lại.

## 2. Nhãn trên đường truyền và JSON request

Nhân có bảy nhãn nghiệp vụ tiếng Anh. Theo yêu cầu 07.1, request/response AI
dùng bảy alias và một lệnh CLARIFY. Không sửa taxonomy hay thêm mẫu CLARIFY vào
thư viện vector.

| Nhãn AI | Nhãn nội bộ của Nhân | Route khi chấp nhận |
|---|---|---|
| SO_LIEU | NUMERIC | VECTOR |
| BCTC_BCTN | REPORT_CONTENT | VECTOR |
| NEWS | NEWS | VECTOR |
| CHUC_VU | PERSON_ROLE | GRAPH |
| QUAN_HE | ENTITY_RELATION | GRAPH |
| XU_HUONG | TREND | BOTH theo mapping 04.2 hiện có |
| KET_HOP | MIXED | VECTOR/GRAPH/BOTH theo các thành phần query đã xác minh |
| CLARIFY | Không phải nhãn nghiệp vụ | ASK_CLARIFICATION |

Request chỉ có ba khóa sau, conversation_scope luôn có đúng hai khóa:

```json
{
  "question": "Ai là Chủ tịch HĐQT VCB năm 2024?",
  "conversation_scope": {"company_ticker": "VCB", "period": "2024"},
  "allowed_labels": ["SO_LIEU", "BCTC_BCTN", "NEWS", "CHUC_VU", "QUAN_HE", "XU_HUONG", "KET_HOP", "CLARIFY"]
}
```

Scope lấy từ kết quả 04.2, gồm công ty/kỳ hiện tại hoặc ngữ cảnh cùng phiên đã
được xác nhận. Không gửi một lượt chat trước chưa được xác minh. Không có kỳ
thì period=null; truy vấn không cần doanh nghiệp có thể dùng company_ticker=null
khi caller chỉ định company_required=false. Không gửi lịch sử chat, candidates,
điểm vector, ví dụ thư viện, reason hay evidence nội bộ ra provider trong contract
tối thiểu này. Handoff nội bộ 04.2 vẫn giữ nguyên top-3/evidence cho chẩn đoán;
07.1 không chuyển thẳng toàn bộ handoff đó thành request mạng.

prepare_fallback_request còn trả validation_context ở cấp nội bộ, tách khỏi
request. 07.2 chỉ gửi prepared['request'] ra provider và truyền
**prepared['validation_context'] vào validator khi nhận response. Context này
có query_components/query_components_confirmed; không gửi chúng hoặc toàn bộ
prepared ra ngoài.

## 3. JSON response

```json
{
  "intent_label": "CHUC_VU",
  "route": "GRAPH",
  "confidence": 0.85,
  "extracted_company": "VCB",
  "extracted_period": "2024",
  "reason": "Câu hỏi tra cứu người giữ chức Chủ tịch HĐQT."
}
```

Bốn khóa bắt buộc: intent_label, route, confidence, reason. Hai khóa extracted_*
không bắt buộc, nhận string hoặc null; không có thì dùng scope đã xác minh.
null cũng giữ nguyên giá trị đã xác minh, không xóa bộ lọc. extracted_* chỉ xác
nhận scope, không tự tạo thêm bộ lọc: nếu scope tương ứng đang null mà AI trả
giá trị mới, validator từ chối cả khi AI chọn ASK_CLARIFICATION. Caller phải
phân giải/xác minh công ty và kỳ từ câu hỏi hoặc context trước khi gọi; nếu
chưa xác minh kỳ thì provider giữ extracted_period=null hoặc bỏ khóa đó.
Không nhận khóa ngoài sáu khóa trên, Markdown fence, đoạn văn kèm JSON, khóa
trùng hoặc NaN/Infinity. reason phải là chuỗi không chỉ có khoảng trắng.
JSON Schema request/response được export trong module Python để 07.2 tái sử dụng.

confidence phải là số hữu hạn trong [0,1], không nhận bool/chuỗi, và >=0,60.
Đây là điểm do provider tự khai báo và ngưỡng kiểm kết quả theo yêu cầu 07.1,
không phải cosine, không phải xác suất đã calibration, không chứng minh chất
lượng phân loại. Không dùng nó để đổi ngưỡng 04.2.
API nhận JSON text hoặc dictionary đã parse từ SDK. Kiểu số của dictionary
được kiểm trước schema; complex/Decimal không được giả thành số JSON hợp lệ
hoặc thoát ra dưới dạng lỗi so sánh của thư viện.

## 4. Kiểm kết quả và hành vi an toàn

1. Kiểm request và trạng thái provider. Timeout/lỗi provider trả FALLBACK_FAILED
   cùng ASK_CLARIFICATION; validator không tự gọi mạng hoặc tạo timer.
2. Parse JSON nghiêm ngặt, kiểm schema, nhãn/route và confidence.
3. Kiểm nhãn khớp route. CLARIFY chỉ được ASK_CLARIFICATION; các nhãn khác cũng
   được ASK_CLARIFICATION khi provider cần hỏi lại.
4. Với KET_HOP có route truy xuất: prepare lấy thành phần từ resolution V7
   policy intent-request-objectives-v5 khi intent=MIXED và
   reason=TWO_EXPLICIT_REQUEST_TYPES. Hai bản classification_evidence phải
   khớp, confidence=null, runtime_enabled=false, unresolved_requests rỗng,
   explicit_evidence phủ đủ nhãn thành phần khác nhau. Dùng lại bộ tách request
   thuần luật của V7 để kiểm các đoạn evidence thuộc đầy đủ câu hỏi hiện tại;
   evidence của câu cũ hoặc câu chưa có phần mới trả lỗi contract trước mạng.
   Kết quả đi vào validation_context để caller chuyển cho validator. Không lấy
   components của câu mẫu, điểm phân loại hoặc reason từ AI làm bằng chứng.
   VECTOR + VECTOR vẫn VECTOR, GRAPH + GRAPH vẫn GRAPH, GRAPH + VECTOR mới
   BOTH; theo hàm 04.2. MIXED chỉ có chứng cứ classifier/consensus chưa được
   xác minh vẫn hỏi lại. Caller khác vẫn có thể cấp thành phần đã xác minh
   qua hai tham số query_components/query_components_confirmed.
5. Công ty/kỳ AI trích phải đúng định dạng và khớp scope đã xác minh khi scope
   đó có giá trị. Không để provider tự đổi hoặc thêm công ty/kỳ. Scope null
   mà AI tự gán giá trị trả UNVERIFIED_COMPANY/UNVERIFIED_PERIOD; không biến
   điểm tự khai cao thành bằng chứng xác minh scope. Công ty cần tra cứu mà
   vẫn chưa có scope xác minh thì ASK_CLARIFICATION. valid_tickers có thể được
   caller cấp để kiểm registry; validator không truy vấn DB.
6. Chuẩn hóa ký hiệu trước khi so kỳ: Q3/2025, q3-2025, quý 3/2025,
   quý 3 năm 2025 và 2025-Q3 cùng thành 2025-Q3; 04/11/2025 thành 2025-11-04.
   Không gộp năm với quý, ngày cuối quý với cả quý, hoặc kỳ tương đối với một
   năm tự đoán. Không thêm kỳ khi scope=null. Chốt scope 04.2 vẫn kiểm tính
   hợp lệ, ngày/quý sai và các dạng dấu gạch đã sửa; helper mới chỉ chuẩn hóa
   ký hiệu của một kỳ đơn, không phân giải thời gian hay coverage.

Vi phạm các bước kiểm response trả FALLBACK_FAILED, intent_label=CLARIFY,
route=ASK_CLARIFICATION, confidence=null và reason_code cụ thể. JSON hợp lệ
có thể trả FALLBACK_VALIDATED với route ASK_CLARIFICATION nếu AI chủ động hỏi
lại. Kết quả chuẩn hóa có canonical_intent để caller nối về bảy ID của Nhân;
CLARIFY có canonical_intent=null. Không nâng ASK thành SEARCH vì có score cao.

## 5. API bàn giao và kế hoạch kiểm chứng

File thực thi: backend/src/retrieval_orchestration/intent_fallback_contract.py.

- prepare_fallback_request(policy_result, *, question, company_required=True,
  valid_tickers=None): trả need_fallback/decision/route/reason_code/request
  và validation_context nội bộ.
  Request chỉ có khi 04.2 cho fallback; handoff hỏng ném lỗi contract trước mạng.
- validate_fallback_response(raw, *, request, timed_out=False, provider_error=None,
  company_required=True, valid_tickers=None, query_components=None,
  query_components_confirmed=False): trả kết quả chuẩn hóa, không gọi provider.
- REQUEST_JSON_SCHEMA, RESPONSE_JSON_SCHEMA: schema tái sử dụng cho 07.2.

Kế hoạch triển khai trên nhánh người dùng đang làm, không tạo nhánh khác:

- [x] Viết test trước cho gate 04.2 mặc định/diagnostic, lỗi/timeout nội bộ,
  scope sai và payload tối thiểu không lộ candidates/history.
- [x] Viết test JSON đúng/sai, thiếu trường, nhãn/route lạ, nhãn lệch route,
  confidence 0,60 và hai phía biên, bool/NaN, timeout/provider lỗi.
- [x] Kiểm KET_HOP theo thành phần, thiếu/conflict scope, các kỳ đã từng sửa;
  kiểm input không bị sửa và thất bại không biến thành route truy xuất.
- [x] Chạy test mới thấy fail, triển khai module, chạy toàn bộ intent/archive
  và ghi đúng giới hạn của suite dự án.
- [x] Đối chiếu ba file 04.2 vẫn nguyên như trước khi làm 07.1. Không commit/push
  cho đến khi người dùng yêu cầu.

07.2 phải nối provider, áp deadline thật và chuyển trạng thái lỗi/timeout vào
validator; giữ request đi cùng response của đúng lượt gọi, truyền cùng cấu
hình company_required/valid_tickers đã dùng khi chuẩn bị và chuyển tiếp
validation_context. KET_HOP không suy thành phần từ reason của provider. Validator kiểm cấu
trúc và sự nhất quán, không chứng minh AI chọn đúng ý định chỉ vì JSON hợp lệ.
Chưa lấy unit test này làm bằng chứng đã gọi AI thật, đã nối Web Chat hoặc đã
đạt chất lượng production trên tập nghiệm thu độc lập.

## 6. Kết quả kiểm chứng và bàn giao

Đủ ba đầu mục của 07.1: bảng kích hoạt/loại trừ theo code 04.2 đã chốt, JSON
request/response cùng schema máy đọc, và validator có test các lỗi cần bắt.
Ba file mới: module contract, test_s5_intent_fallback_contract.py, tài liệu này.
Không sửa file task Nhân hoặc ba file 04.2. Các kết quả kiểm chứng dưới đây
được ghi nhận trước khi commit/push phần 07.1.

- **191 test 07.1 qua**, trong tổng **617 test intent/archive qua** ở lượt
  kiểm tra bàn giao mới nhất.
- Đã quan sát 25 ca hành vi fail khi API còn chưa triển khai, sau đó qua.
  Rà soát độc lập phát hiện hai lỗi: scope thiếu trường bị thay bằng null và
  kiểu số SDK làm schema ném lỗi. Đã bổ sung 16 ca, quan sát 14 fail/2 pass
  trước sửa, và tất cả qua trên bản cuối.
- Kiểm tra lại trước bàn giao phát hiện thêm: AI tự thêm scope chưa xác minh,
  handoff nhận company_source không hợp lệ, và nhánh SEARCH/ASK chưa kiểm đủ
  contract. Bổ sung 34 ca so với bản 126 test; đã quan sát 15 lỗi scope và 9
  lỗi handoff fail trước sửa. Sau sửa, các ca hỏi lại không giữ scope tự bịa;
  truy vấn có công ty hợp lệ nhưng không yêu cầu kỳ vẫn hoạt động với kỳ null.
- Review nối 07.2 bổ sung 31 ca cho đường truyền thành phần V7, evidence cũ và
  chuẩn hóa kỳ; quan sát 18 ca fail trước sửa và 2 ca stale-evidence fail trước
  khi bổ sung ràng buộc câu hiện tại. Trên snapshot 345 resolution đã lưu:
  345/345 tạo request hợp lệ; 42 câu MIXED gồm 24 có TWO_EXPLICIT_REQUEST_TYPES.
  Với JSON provider viết tay, 24 câu này qua validator (16 BOTH, 8 VECTOR);
  18 câu chưa có thành phần xác minh vẫn ASK_CLARIFICATION. Scope replay là
  fixture theo ticker đầu tiên thấy trong câu và period=null; đây không phải
  benchmark resolver, model, provider hay UI. Bằng chứng mới:
  outputs/s5_wbs071_20261113/review03/v7-replay.json.
- Schema request/response đã được kiểm bằng Draft202012Validator.check_schema.
  Các fixture thực thi có đủ VECTOR/GRAPH/BOTH/ASK_CLARIFICATION và thất bại an
  toàn; bằng chứng ở outputs/s5_wbs071_20261113/contract-examples.json. Đây là
  JSON viết tay làm đầu vào kiểm contract, không phải phản hồi AI thật.
- Suite toàn dự án vẫn dừng lúc collect test_chat_history.py và
  test_chat_regression.py do thiếu `hoi`, test_contracts.py do thiếu
  `retrieval_flow`. Các lỗi này đã có trước task; không ghi toàn ứng dụng PASS.
  Log mới nhất: outputs/s5_wbs071_20261113/review02/full-suite-final.log.
  Bộ hồi quy mới nhất: outputs/s5_wbs071_20261113/review03/intent-suite-final.xml.
  Kết quả hàm và checksum ba file: outputs/s5_wbs071_20261113/review03/verification.json.
  Các log ở thư mục cha là kết quả các bản trước, không thay cho lượt kiểm mới.

Chạy riêng phần 07.1 từ thư mục gốc FinMind:

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_s5_intent_fallback_contract.py -q -p no:cacheprovider
```

Ví dụ 07.2 sử dụng contract sau khi tự áp timeout và gọi provider:

```python
from src.retrieval_orchestration.intent_fallback_contract import (
    prepare_fallback_request, validate_fallback_response,
)

prepared = prepare_fallback_request(result_042, question=question)
if prepared['need_fallback']:
    # Chỉ gửi prepared['request'] ra provider, giữ validation_context ở server.
    # provider_text và provider_timed_out do runner 07.2 cung cấp.
    validated = validate_fallback_response(
        provider_text, request=prepared['request'], timed_out=provider_timed_out,
        **prepared['validation_context'],
    )
# Nếu need_fallback=False: giữ ASK_CLARIFICATION/SEARCH của 04.2, không gọi AI.
```

Trước khi nối 07.2 vào backend, cài dependency bằng đúng interpreter đang chạy
backend (từ thư mục gốc FinMind):

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -c "from importlib.metadata import version; print(version('jsonschema'))"
```

requirements đã chốt jsonschema==4.26.0; không cần thêm dependency hay che lỗi
cài thiếu bằng một kết quả phân loại. Venv kiểm thử hiện dùng đúng 4.26.0.
07.2 cần cấu hình Gemini trả JSON theo schema tương thích của provider, sau đó
vẫn kiểm bằng RESPONSE_JSON_SCHEMA và validator này. JSON bọc Markdown fence
tiếp tục bị từ chối; không nới parser để nhận văn bản lẫn JSON. Chưa gọi Gemini
hoặc kiểm chế độ schema của provider trong task 07.1.
