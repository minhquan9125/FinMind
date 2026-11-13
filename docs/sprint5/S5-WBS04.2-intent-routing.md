# S5-WBS04.2 — Ngưỡng tin cậy và quy tắc chọn nhánh

Khởi tạo: 11/11/2026; cập nhật an toàn: **13/11/2026**, trên code Nhân `c37060d6`.
Dùng `IntentMatcher` của 04.1 và thư viện `s5-intent-library-v1` của 03.3.
Đã đối chiếu cả classifier/resolution mới. Không sửa matcher, mẫu, vector,
classifier/head hoặc taxonomy của Nhân.

Sản phẩm: cấu hình/bảng mapping, hàm quyết định và kiểm thử đủ 5 kết quả yêu cầu.
Hàm trả route/tín hiệu, không chạy retrieval hoặc AI fallback. Việc nối factory
WebChat và thực thi fallback 07.2 không được thực hiện trong task này.

**Mặc định hiện tại: FALLBACK-ONLY.** Bộ 176 câu đã xem cho thấy cosine + ngưỡng
0,65/0,08 vẫn SEARCH sai 5/15 ca được chấp nhận. Vì chưa có chất lượng được nghiệm
thu, câu đủ scope/contract chỉ trả NEED_FALLBACK; không tự SEARCH dù điểm rất cao.
0,65/0,08 được giữ để chẩn đoán offline, không phải ngưỡng đã hiệu chỉnh production.
Thiếu scope vẫn hỏi lại, payload hỏng vẫn là lỗi contract. Tín hiệu fallback không
đồng nghĩa AI đã chạy; cần triển khai và kiểm chứng riêng S5-WBS07.2.

## 1. Cấu hình và ánh xạ

| Cấu hình | Giá trị |
|---|---|
| CONFIDENCE_THRESHOLD | **0.65** |
| GAP_THRESHOLD | **0.08** |
| allow_direct_search | **False**, mặc định không tự SEARCH |
| Nơi tiếp nhận tín hiệu fallback | **S5-WBS07.2** |

Đây là hai ngưỡng người phụ trách task đã chỉ định, không phải ngưỡng tự chọn
từ kết quả holdout, không khẳng định đã tối ưu production và không dùng điểm
graph_score/content_score của route model cũ.

| Tên trong đề bài | ID chuẩn của Nhân | Nhánh trong chế độ chẩn đoán |
|---|---|---|
| SO_LIEU | NUMERIC | VECTOR |
| BCTC_BCTN | REPORT_CONTENT | VECTOR |
| NEWS | NEWS | VECTOR |
| CHUC_VU | PERSON_ROLE | GRAPH |
| QUAN_HE | ENTITY_RELATION | GRAPH |
| KET_HOP | MIXED | Theo thành phần câu hỏi đã xác minh; thiếu thì fallback |
| XU_HUONG | TREND | BOTH |

Thực tế có **7 nhãn**, tương ứng đủ taxonomy Nhân đã bàn giao. Hàm nhận các alias
cố định trong đề bài để chạy ca mẫu; đầu ra giữ ID chuẩn, không đổi ID trong thư viện.
Review 12/11 thay quy tắc MIXED mặc định BOTH của bản đầu. Truyền
`query_components` và `query_components_confirmed=True` từ bộ phân tích câu hỏi
đã xác minh: tất cả cần VECTOR thì VECTOR, tất cả cần GRAPH thì GRAPH, cần cả hai
thì BOTH. TREND vẫn giữ mapping đã giao. Thiếu thành phần được xác minh thì trả
NEED_FALLBACK/MIXED_COMPONENTS_REQUIRED; không sao chép component_intents của mẫu
gần nhất hoặc suy thành phần chỉ từ nhiều nhãn gần điểm nhau.

## 2. Ba chốt chặn theo thứ tự

### Chốt 1 — ASK_CLARIFICATION trước khi phân loại

Thiếu công ty hiện tại và chưa có công ty hợp lệ trong ngữ cảnh đã xác minh cùng
phiên thì hỏi lại. Chỉ kế thừa khi `context_confirmed=true` và
`context_same_session=true`; ưu tiên công ty người dùng vừa chỉ định. Context có
nhiều công ty chưa phân giải phải hỏi lại, không tự chọn công ty đầu tiên.

Quý ngoài 1–4, ngày không tồn tại, period sai định dạng, công ty sai định dạng
hoặc câu hỏi không hợp lệ cũng hỏi lại. Khi chặn, route=null, need_fallback=false,
có clarification_question và không gọi matcher/encoder/retrieval/AI ngoài.
Đã chặn thêm Q 5/quý +5, quý 1.5 và danh sách chứa quý sai như 1,5 hoặc 1 và 5.
Danh sách/range hợp lệ 1,2; 1 và 2; 1–4 vẫn được nhận, kể cả khi dùng Q có khoảng
trắng. Quý sai nêu trong câu hiện tại ưu tiên hơn period hợp lệ từ context.

`company_ticker` phải do bước phân giải scope upstream xác minh; có thể truyền
`valid_tickers` để kiểm membership registry đã nạp, không cần truy vấn DB ở policy.
`period` nhận YYYY, YYYY-Q1..Q4, ngày ISO hợp lệ hoặc token thời gian do scope
resolver hỗ trợ; phân giải coverage/latest vẫn thuộc tầng scope/retrieval hiện có.
Không tự yêu cầu thêm kỳ khi đề bài chỉ yêu cầu công ty và kỳ chưa được chỉ định.

Mặc định `company_required=true` cho câu hỏi tài chính/báo cáo/chức vụ/quan hệ.
Server chỉ đặt false với yêu cầu không cần công ty, ví dụ tin thị trường chung;
đây không phải cờ do LLM hay người dùng tùy ý đặt để bỏ chốt.

### Chốt 2 — NEED_FALLBACK

Sau khi scope hợp lệ, **bắt buộc** hai khóa `ranking_policy` và `score_type`
không thiếu/null/rỗng, phải đúng cặp được hỗ trợ. Không có giá trị mặc định.
Payload hỏng ném `IntentClassificationContractError` với `code`, không tạo route
hay payload gọi AI. Caller xử lý lỗi contract riêng (không dùng catch-all để gọi
fallback và ghi phân loại thành công). Đây là lỗi kỹ thuật, không phải ý định thứ tám
hoặc một tuyến truy xuất mới.

Với cặp `cosine-max-per-label-v1` / `COSINE_SIMILARITY_NOT_PROBABILITY`,
lấy top_1/top_2 từ **hai nhóm khác nhau** trong `groups`
đã được IntentMatcher xếp hạng. Không lấy hai `examples`, vì chúng có thể cùng nhãn.
Điểm là cosine [-1,1], không phải xác suất. Không làm tròn điểm trước khi quyết định.

| Điều kiện | reason_code |
|---|---|
| Cosine hợp lệ nhưng chưa bật chẩn đoán SEARCH trực tiếp | DIRECT_SEARCH_DISABLED |
| top_1 < 0.65 và gap ≥ 0.08 | LOW_CONFIDENCE |
| top_1 ≥ 0.65 và gap < 0.08 | SMALL_GAP |
| top_1 < 0.65 và gap < 0.08 | LOW_CONFIDENCE_AND_SMALL_GAP |
| Matcher ném lỗi/timeout | CLASSIFICATION_ERROR |
| MIXED đủ ngưỡng nhưng thiếu thành phần query đã xác minh | MIXED_COMPONENTS_REQUIRED |
| Classifier/evidence đúng contract nhưng chưa hiệu chỉnh | UNCALIBRATED_CLASSIFICATION |
| Nhãn đầu base_ranking khác resolution.intent_label | LABEL_DISAGREEMENT |

Tất cả trường hợp trên: decision=NEED_FALLBACK, need_fallback=true, route=null,
fallback_task=S5-WBS07.2. Hòa điểm có gap=0 phải fallback, không suy thành MIXED.
Đầu ra có `fallback_payload` gồm `question`, `scope`, `reason_code`,
`allowed_labels`, `candidates` và `score_type`. `candidates` giữ tối đa **3 nhóm
nhãn khác nhau** theo thứ tự matcher, mỗi nhóm có `rank`, `intent_label`, `score`;
đây không phải 5 câu ví dụ gần nhất. Loại điểm đi kèm candidates phải được giữ
nguyên; cosine không được diễn giải là xác suất, probability chưa hiệu chỉnh
không được gọi là độ tin cậy đã kiểm chứng.
Chỉ truyền scope đã phân giải (công ty, kỳ, nguồn công ty CURRENT/CONTEXT), không
chuyển toàn bộ lịch sử chat hoặc component_intents của ví dụ thành ý định câu mới.
Matcher lỗi thì candidates rỗng. Output hỏng/nhãn trùng hoặc lạ, score sai kiểu,
NaN/Inf, sai thứ tự hoặc ranking của câu khác là **lỗi contract**, không chuyển
nhãn/điểm chưa được kiểm tra. ASK_CLARIFICATION và SEARCH có fallback_payload=null.
Hàm thuần không được cung cấp question có thể trả question=null cho fixture;
caller thực tế phải truyền câu hỏi không rỗng, hoặc dùng IntentRoutingPolicy.
Không ép chọn top-1 hoặc route mặc định. Policy chỉ phát tín hiệu, không tự gọi
LLM hay retry. Deadline encoder do caller quản lý; exception timeout được chuyển
thành fallback, không tạo thêm thread hoặc bộ gọi AI trong task này.

### Chốt 3 — SEARCH với route chính thức

**Chỉ dùng trong chẩn đoán offline** khi khởi tạo policy với
`allow_direct_search=True` hoặc truyền cờ đó vào hàm thuần. Không lấy cờ từ
request hoặc LLM. `IntentRoutingPolicy.decide()` từ chối request cố ghi đè cờ;
giá trị cấu hình phải là bool thật, không nhận chuỗi "true" hoặc số 1.

Trong chế độ này, scope/ranking cosine hợp lệ và **top_1 ≥ 0.65, gap ≥ 0.08**, cùng đủ
thành phần query nếu MIXED, mới trả SEARCH, route theo bảng trên,
need_fallback=false và gate=3. Giá trị bằng đúng ngưỡng
được chấp nhận. Chốt 1 ưu tiên hơn mọi lỗi/điểm phân loại; chốt 2 ưu tiên hơn mapping route.

## 3. Hàm sử dụng

Code: `backend/src/retrieval_orchestration/intent_routing.py`.

Hàm thuần nhận kết quả có sẵn hoặc bộ input kiểm thử. Ví dụ sau bật chế độ
chẩn đoán rõ ràng để kiểm nhánh, không phải cấu hình để chạy production:

```python
from src.retrieval_orchestration.intent_routing import decide_intent_route

result = decide_intent_route(
    {"ranking_policy": "cosine-max-per-label-v1",
     "score_type": "COSINE_SIMILARITY_NOT_PROBABILITY",
     "groups": [
        {"intent_label": "PERSON_ROLE", "score": 0.88},
        {"intent_label": "NEWS", "score": 0.48}
    ]},
    company_ticker="VCB", period="2025", allow_direct_search=True,
)
# decision=SEARCH, route=GRAPH, need_fallback=False, gate=3
```

Wrapper dùng trực tiếp `IntentMatcher` của Nhân và chặn **trước khi nhúng query**:

```python
from src.retrieval_orchestration.intent_routing import IntentRoutingPolicy

# matcher = IntentMatcher(library, embedder), pin model/revision theo 04.1.
policy = IntentRoutingPolicy(matcher)
result = policy.decide(
    "Ai là Chủ tịch HĐQT?",
    company_ticker=None,
    context_company_ticker="VCB",
    context_confirmed=True,
    context_same_session=True,
    period="2025",
)
# Mặc định NEED_FALLBACK khi scope/contract hợp lệ, kể cả cosine đủ điểm.
```

Wrapper gọi matcher tối đa một lần, top_groups=3 và top_examples=5, chỉ sau
chốt 1. Hàm thuần không thể hủy embedding nếu caller đã thực hiện trước đó.

Đầu ra có decision, route, need_fallback, fallback_task, gate, reason_code,
scope (company_ticker/period/company_source), intent_label, top_1_score,
top_2_score, score_gap, clarification_question, classification_evidence.
Chốt 1 không đọc/công bố score;
chốt 2 chưa xác nhận nhãn nên intent_label=null. Chỉ SEARCH có route chính thức.
Đây là DTO policy mới, không thay enum `RouterOutput` hoặc API cũ.

## 4. Bảng chạy thử 5 ca bắt buộc

Các điểm dưới đây do đề bài cung cấp, không phải phép đo lại model thật.
Các ca SEARCH được kiểm với `allow_direct_search=True` trong chẩn đoán offline;
ở mặc định các ca scope/contract hợp lệ đều cần fallback trước truy xuất.

| Ca | Nhãn/điểm đầu | Điểm thứ hai | Gap | Ticker | Đầu ra |
|---|---|---|---|---|---|
| 1 | CHUC_VU 0.88 | NEWS 0.48 | 0.40 | VCB | SEARCH / GRAPH |
| 2 | BCTC_BCTN 0.91 | NEWS 0.41 | 0.50 | FPT | SEARCH / VECTOR |
| 3 | KET_HOP 0.85 + thành phần đã xác minh PERSON_ROLE, REPORT_CONTENT | NEWS 0.55 | 0.30 | FPT | SEARCH / BOTH |
| 4 | BCTC_BCTN 0.85 | Không cần đọc | Không cần đọc | null | ASK_CLARIFICATION |
| 5 | CHUC_VU 0.68 | NEWS 0.64 | 0.04 | VCB | NEED_FALLBACK=true, route=null |

Test tại `backend/tests/test_s5_intent_routing.py` còn kiểm biên 0.65/0.08,
scope ưu tiên hơn classification lỗi, quý/ngày sai không gọi matcher,
context khác phiên/chưa xác minh/mơ hồ, mọi mapping nhãn, score âm/lỗi,
và ghép với lớp IntentMatcher thật bằng encoder/vector unit test.

Chạy từ gốc repo:

```powershell
$env:PYTHONPATH = (Join-Path $PWD.Path 'backend')
.venv\Scripts\python.exe -m pytest backend/tests/test_s5_intent_routing.py backend/tests/test_s5_intent_matching.py backend/tests/test_s5_intent_evaluation.py backend/tests/test_s5_intent_library.py backend/tests/test_s5_intent_dataset.py -q -p no:cacheprovider
```

Điều kiện bàn giao: bảng ngưỡng/mapping và hàm có đủ năm kết quả đã kiểm.
Không lấy unit test làm accuracy hoặc nghiệm thu E2E WebChat; không sửa số liệu
baseline 04.1. Phần thực thi fallback thuộc S5-WBS07.2 và tích hợp runtime là
bước nối tiếp, không tự ghi là đã chạy trong task này.

## 5. Chạy kiểm tra với model thật ngày 11/11/2026

Đã dùng BAAI/bge-m3 revision `5617a9f61b028005a4858fdac845db406aefb181`
từ cache local, offline/CPU 4 thread, với chính thư viện 90 × 1024 của Nhân.
Bằng chứng ở `outputs/s5_wbs042_20261111/real-model-run01/report.json`
và `results.jsonl`; không ghi đè artifact 03.3 hoặc run01 của 04.1.

- 11 ca wrapper: 4 ASK_CLARIFICATION (thiếu công ty/quý 5/ngày sai),
  7 NEED_FALLBACK theo score/gap thật. Tổng số gọi matcher ở chốt 1: **0**.
- Nhúng lại đủ 56 câu test của Nhân: thứ tự nhóm khớp **56/56**, sai lệch score
  tối đa khoảng `1.64e-7`; top-1 vẫn **22/47**, top-3 **41/47**. Không tuyên bố tăng accuracy.
- Với scope fixture được cung cấp riêng cho kiểm policy: **43 NEED_FALLBACK,
  11 ASK_CLARIFICATION, 1 SEARCH/VECTOR, 1 bỏ qua routing**. Ca bỏ qua S5-T-029
  nêu công ty Bình Minh nhưng chưa có ticker được xác minh; không tự gán BMP.
- Ca SEARCH là S5-T-006, nhãn đúng NUMERIC: score `0.6684055`, gap `0.0951497`.
  Các câu null vẫn chỉ là quan sát, không tính accuracy bảy nhãn.
- Không có lỗi thực thi/JSON score không hữu hạn; không gọi LLM fallback hoặc DB.
  Hash thư viện và báo cáo gốc trước/sau trùng nhau.

Scope trong lượt chạy 56 câu được điền theo input, không phải đánh giá bộ trích
thực thể runtime. Chỉ một câu được chọn route trực tiếp nên chưa đủ đánh giá
chất lượng GRAPH/BOTH thật; năm ca nghiệm thu điểm cố định ở mục 4 vẫn được
kiểm bằng unit test. Tỷ lệ fallback cao là giới hạn vận hành cần ghi khi bàn giao,
không tự giảm ngưỡng hoặc sửa thư viện theo bộ test này.

## 6. Bàn giao ứng viên sang S5-WBS07.2

Đã bổ sung payload top 3 theo hướng dùng nhiều ứng viên tại bước fallback.
Ví dụ nhãn đầu PERSON_ROLE=0.68, NEWS=0.64, MIXED=0.60 vẫn trả
NEED_FALLBACK, route=null; cả ba nhãn và điểm được giữ trong candidates,
không tự chọn BOTH chỉ vì có nhiều nhãn. Ngưỡng và matcher của Nhân giữ nguyên.

Bên 07.2 nhận question, scope và candidates để phân loại lại. Chỉ được xác nhận
nhãn thuộc allowed_labels; candidates là gợi ý, không thay thế allowlist bảy nhãn.
Output phải qua contract/validator của 07.2 trước khi ánh xạ bằng bảng mục 1.
Nếu kết quả lỗi/không hợp lệ/timeout thì không tự chuyển thành SEARCH hoặc dùng
nhãn đầu làm đáp án. Việc gọi provider, kiểm tra response và nối WebChat thuộc
bước tích hợp 07.2, chưa được thực thi hay nghiệm thu trong policy 04.2 này.

Kiểm chứng lịch sử ngày 11/11 sau bổ sung: **119 test passed**, gồm hồi quy matcher/library/dataset
và kiểm payload, alias, scope kế thừa, lỗi matcher, JSON hữu hạn, không sửa input.
Replay điểm model thật trong results.jsonl của mục 5 kiểm được **66 quyết định**:
50 NEED_FALLBACK đều giữ đúng top 3; 15 ASK_CLARIFICATION và 1 SEARCH không có
payload. Một ca thiếu scope tiếp tục bỏ qua. Các decision/route/reason_code giữ
nguyên; đây là replay điểm cũ, không phải lượt inference mới hoặc test AI fallback.
Báo cáo model thật cũ giữ nguyên để bảo toàn bằng chứng tại thời điểm chạy.

## 7. Contract consumer sau review 12/11

| Đầu vào | Xử lý |
|---|---|
| Metadata thiếu/null/rỗng, cặp policy/type không khớp, nhãn/score/rank hỏng | Ném IntentClassificationContractError; không tạo tín hiệu gọi AI |
| Cosine max-per-label hợp lệ | DIRECT_SEARCH_DISABLED mặc định; chỉ diagnostic mới xét 0,65/0,08 |
| intent-linear-v1 + CLASSIFIER_PROBABILITY_UNCALIBRATED | NEED_FALLBACK/UNCALIBRATED_CLASSIFICATION; không xét ngưỡng cosine |
| intent-request-objectives-v1..v4 hoặc intent-request-consensus-v1 + DECISION_EVIDENCE_NO_CONFIDENCE | confidence phải khai báo null; cần fallback xác minh |
| Envelope gồm base_ranking và resolution, nhãn khác nhau | NEED_FALLBACK/LABEL_DISAGREEMENT; giữ cả hai nhãn và lý do |

Envelope hợp lệ có dạng `{"base_ranking": {...}, "resolution": {...}}`;
hai phần tự khai báo metadata riêng. Không trộn thêm groups/intent_label/policy
ở cấp ngoài để tạo hai cách diễn giải. Consumer không sửa ranking gốc.

`classification_evidence` giữ snapshot `base_ranking` (tối đa 3 nhóm nhãn/điểm gốc),
`resolution` (nhãn cuối, confidence=null, reason, component_labels) và
`label_disagreement`. Snapshot này cũng có trong fallback_payload để 07.2 thấy
cả hai nguồn quyết định. Không gán điểm của nhãn gốc cho nhãn cuối. Khi đi nhánh
chưa hiệu chỉnh, intent_label/top_1_score/top_2_score/score_gap ở đầu ra policy
đều null; điểm gốc chỉ được giữ ở đúng phần evidence/candidates với score_type gốc.
Ngay cả hai nhãn trùng nhau cũng chưa đủ để SEARCH khi confidence còn null.

Đây là contract phía 04.2 để xử lý an toàn đầu ra mới, không thay đổi trạng thái
duyệt/calibration của classifier Nhân hoặc tự kết luận tích hợp WebChat đã xong.

Caller cần tách lỗi dữ liệu khỏi nhánh fallback:

```python
from src.retrieval_orchestration.intent_routing import (
    IntentClassificationContractError, decide_intent_route,
)

try:
    result = decide_intent_route(producer_output, question=question, company_ticker="FPT")
except IntentClassificationContractError as error:
    # Trả lỗi contract theo API của caller; ghi error.code, không gọi AI ở đây.
    raise
# Chỉ result["need_fallback"] == True mới là dữ liệu bàn giao cho S5-WBS07.2.
```

Ví dụ MIXED có score cosine hợp lệ và đủ ngưỡng:

```python
result = decide_intent_route(
    ranking, question=question, company_ticker="FPT",
    query_components=["NUMERIC", "NEWS"], query_components_confirmed=True,
    allow_direct_search=True,  # Chỉ chẩn đoán offline.
)
# SEARCH/VECTOR: hai mục tiêu đều dùng tài liệu.
# PERSON_ROLE + ENTITY_RELATION -> GRAPH.
# PERSON_ROLE + REPORT_CONTENT -> BOTH.
```

`query_components_confirmed` là xác nhận của caller đã phân giải mục tiêu câu
hỏi; không lấy từ best_example hoặc tự bật vì cosine cao. Ít nhất hai nhãn thành
phần khác nhau, không chứa MIXED; alias được chuẩn hóa. Dữ liệu thành phần đã
xác nhận nhưng sai cấu trúc là lỗi contract. Chốt scope và ngưỡng cosine vẫn
ưu tiên trước việc chọn tuyến theo thành phần.

Kiểm chứng lịch sử sau sửa review 12/11: **267 test ý định Sprint 5 qua**; bao gồm 105 test
policy và test dùng trực tiếp resolution của Nhân. Bằng chứng mới trong
`outputs/s5_wbs042_retest_20261112/fix01/`. Suite toàn dự án chưa chạy được vì
thu thập test lỗi import `hoi`/`retrieval_flow` ở ba test chat/contracts cũ;
không lấy các test này làm bằng chứng toàn ứng dụng qua hoặc calibration đạt.

## 8. Tổng hợp lỗi và sửa ngày 13/11

| Vấn đề đã xác nhận | Xử lý hiện tại |
|---|---|
| Thiếu metadata khiến probability bị hiểu thành cosine | Bắt buộc policy/type, lỗi contract riêng; giữ hồi quy |
| Probability/evidence mới chưa hiệu chỉnh | Không dùng ngưỡng cosine, fallback xác minh; không tự tạo confidence |
| Nhãn gốc và nhãn cuối lệch nhau | Giữ riêng cả hai với lý do; LABEL_DISAGREEMENT |
| MIXED từng mặc định BOTH | Chỉ diagnostic theo query components đã xác minh; thiếu thì fallback |
| Cosine đủ điểm vẫn sai tuyến 5/15 | Tắt SEARCH mặc định; không tự hạ/tăng ngưỡng từ dữ liệu đã xem |
| Q 5, quý +5, quý 1.5, quý 1,5 bỏ lọt chốt 1 | Kiểm toàn bộ số/list/range quý; sai thì hỏi lại trước matcher |

Ngưỡng/mapping được giữ để tái tạo và đánh giá, không phải bật lại SEARCH tự động.
Chế độ chẩn đoán vẫn tái hiện 5/15 sai: không nói model đã được sửa vì kết quả
chế độ mặc định an toàn. Bật lại SEARCH cần tiêu chí sai tuyến/độ phủ được chốt,
tập calibration và tập nghiệm thu giữ kín riêng. Không dùng cùng một bộ để
chỉnh ngưỡng rồi báo chất lượng độc lập.

Bằng chứng mới trong `outputs/s5_wbs042_review_20261113/fix02/`: kiểm lại đủ
176 vector BGE-M3 đã lưu; mặc định 176 NEED_FALLBACK, 0 SEARCH với scope fixture
trung tính. Model vẫn chỉ đúng nhãn 78/167; độ phủ truy xuất trực tiếp bằng 0,
tỷ lệ sai trên số SEARCH không xác định, không phải accuracy 100%.

Sau sửa 13/11: **299 test ý định Sprint 5 qua** (137 policy, 162 dữ liệu/matcher/
scorer/luật). 32 ca mới đã quan sát fail trước sửa và qua sau sửa. Suite toàn dự
án tiếp tục bị chặn ở collect bởi ba test cũ thiếu hoi/retrieval_flow, lưu tại
fix02/full-suite-collection.log. Không sửa các task đó để làm đẹp kết quả.
