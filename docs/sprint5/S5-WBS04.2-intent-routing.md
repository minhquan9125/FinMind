# S5-WBS04.2 — Ngưỡng tin cậy và quy tắc chọn nhánh

Ngày: 11/11/2026. Đầu vào: code Nhân ở `81fa5541`, `IntentMatcher` của 04.1
và thư viện `s5-intent-library-v1` của 03.3. Đã đọc lại implementation và hợp đồng
04.1 trước khi bổ sung policy. Không sửa matcher, mẫu, vector hay taxonomy của Nhân.

Sản phẩm: cấu hình/bảng mapping, hàm quyết định và kiểm thử đủ 5 kết quả yêu cầu.
Hàm trả route/tín hiệu, không chạy retrieval hoặc AI fallback. Việc nối factory
WebChat và thực thi fallback 07.2 không được thực hiện trong task này.

## 1. Cấu hình và ánh xạ

| Cấu hình | Giá trị |
|---|---|
| CONFIDENCE_THRESHOLD | **0.65** |
| GAP_THRESHOLD | **0.08** |
| Nơi tiếp nhận tín hiệu fallback | **S5-WBS07.2** |

Đây là hai ngưỡng người phụ trách task đã chỉ định, không phải ngưỡng tự chọn
từ kết quả holdout, không khẳng định đã tối ưu production và không dùng điểm
graph_score/content_score của route model cũ.

| Tên trong đề bài | ID chuẩn của Nhân | Nhánh |
|---|---|---|
| SO_LIEU | NUMERIC | VECTOR |
| BCTC_BCTN | REPORT_CONTENT | VECTOR |
| NEWS | NEWS | VECTOR |
| CHUC_VU | PERSON_ROLE | GRAPH |
| QUAN_HE | ENTITY_RELATION | GRAPH |
| KET_HOP | MIXED | BOTH |
| XU_HUONG | TREND | BOTH |

Thực tế có **7 nhãn**, tương ứng đủ taxonomy Nhân đã bàn giao. Hàm nhận các alias
cố định trong đề bài để chạy ca mẫu; đầu ra giữ ID chuẩn, không đổi ID trong thư viện.
MIXED và TREND đủ ngưỡng đi BOTH theo **quyết định policy của yêu cầu lần này**;
không sửa định nghĩa ý định của 03.1. Không sao chép component_intents của mẫu
gần nhất thành các thành phần đã xác minh của câu hỏi mới.

## 2. Ba chốt chặn theo thứ tự

### Chốt 1 — ASK_CLARIFICATION trước khi phân loại

Thiếu công ty hiện tại và chưa có công ty hợp lệ trong ngữ cảnh đã xác minh cùng
phiên thì hỏi lại. Chỉ kế thừa khi `context_confirmed=true` và
`context_same_session=true`; ưu tiên công ty người dùng vừa chỉ định. Context có
nhiều công ty chưa phân giải phải hỏi lại, không tự chọn công ty đầu tiên.

Quý ngoài 1–4, ngày không tồn tại, period sai định dạng, công ty sai định dạng
hoặc câu hỏi không hợp lệ cũng hỏi lại. Khi chặn, route=null, need_fallback=false,
có clarification_question và không gọi matcher/encoder/retrieval/AI ngoài.

`company_ticker` phải do bước phân giải scope upstream xác minh; có thể truyền
`valid_tickers` để kiểm membership registry đã nạp, không cần truy vấn DB ở policy.
`period` nhận YYYY, YYYY-Q1..Q4, ngày ISO hợp lệ hoặc token thời gian do scope
resolver hỗ trợ; phân giải coverage/latest vẫn thuộc tầng scope/retrieval hiện có.
Không tự yêu cầu thêm kỳ khi đề bài chỉ yêu cầu công ty và kỳ chưa được chỉ định.

Mặc định `company_required=true` cho câu hỏi tài chính/báo cáo/chức vụ/quan hệ.
Server chỉ đặt false với yêu cầu không cần công ty, ví dụ tin thị trường chung;
đây không phải cờ do LLM hay người dùng tùy ý đặt để bỏ chốt.

### Chốt 2 — NEED_FALLBACK

Sau khi scope hợp lệ, lấy top_1/top_2 từ **hai nhóm khác nhau** trong `groups`
đã được IntentMatcher xếp hạng. Không lấy hai `examples`, vì chúng có thể cùng nhãn.
Điểm là cosine [-1,1], không phải xác suất. Không làm tròn điểm trước khi quyết định.

| Điều kiện | reason_code |
|---|---|
| top_1 < 0.65 và gap ≥ 0.08 | LOW_CONFIDENCE |
| top_1 ≥ 0.65 và gap < 0.08 | SMALL_GAP |
| top_1 < 0.65 và gap < 0.08 | LOW_CONFIDENCE_AND_SMALL_GAP |
| Matcher ném lỗi/timeout | CLASSIFICATION_ERROR |
| Output thiếu/sai, <2 nhóm, nhãn trùng/lạ, score sai kiểu/NaN/Inf, sai thứ tự hoặc ranking của câu khác | INVALID_CLASSIFICATION |

Tất cả trường hợp trên: decision=NEED_FALLBACK, need_fallback=true, route=null,
fallback_task=S5-WBS07.2. Hòa điểm có gap=0 phải fallback, không suy thành MIXED.
Đầu ra có `fallback_payload` gồm `question`, `scope`, `reason_code`,
`allowed_labels`, `candidates` và `score_type`. `candidates` giữ tối đa **3 nhóm
nhãn khác nhau** theo thứ tự matcher, mỗi nhóm có `rank`, `intent_label`, `score`;
đây không phải 5 câu ví dụ gần nhất. Điểm cosine không được diễn giải là xác suất.
Chỉ truyền scope đã phân giải (công ty, kỳ, nguồn công ty CURRENT/CONTEXT), không
chuyển toàn bộ lịch sử chat hoặc component_intents của ví dụ thành ý định câu mới.
Matcher lỗi hoặc output không hợp lệ thì candidates rỗng; không chuyển nhãn/điểm
chưa được kiểm tra. ASK_CLARIFICATION và SEARCH có fallback_payload=null.
Hàm thuần không được cung cấp question có thể trả question=null cho fixture;
caller thực tế phải truyền câu hỏi không rỗng, hoặc dùng IntentRoutingPolicy.
Không ép chọn top-1 hoặc route mặc định. Policy chỉ phát tín hiệu, không tự gọi
LLM hay retry. Deadline encoder do caller quản lý; exception timeout được chuyển
thành fallback, không tạo thêm thread hoặc bộ gọi AI trong task này.

### Chốt 3 — SEARCH với route chính thức

Chỉ khi scope/ranking hợp lệ và **top_1 ≥ 0.65, gap ≥ 0.08** mới trả SEARCH,
route theo bảng trên, need_fallback=false và gate=3. Giá trị bằng đúng ngưỡng
được chấp nhận. Chốt 1 ưu tiên hơn mọi lỗi/điểm phân loại; chốt 2 ưu tiên hơn mapping route.

## 3. Hàm sử dụng

Code: `backend/src/retrieval_orchestration/intent_routing.py`.

Hàm thuần nhận kết quả có sẵn hoặc bộ input kiểm thử:

```python
from src.retrieval_orchestration.intent_routing import decide_intent_route

result = decide_intent_route(
    {"groups": [
        {"intent_label": "PERSON_ROLE", "score": 0.88},
        {"intent_label": "NEWS", "score": 0.48}
    ]},
    company_ticker="VCB", period="2025",
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
```

Wrapper gọi matcher tối đa một lần, top_groups=3 và top_examples=5, chỉ sau
chốt 1. Hàm thuần không thể hủy embedding nếu caller đã thực hiện trước đó.

Đầu ra có decision, route, need_fallback, fallback_task, gate, reason_code,
scope (company_ticker/period/company_source), intent_label, top_1_score,
top_2_score, score_gap, clarification_question. Chốt 1 không đọc/công bố score;
chốt 2 chưa xác nhận nhãn nên intent_label=null. Chỉ SEARCH có route chính thức.
Đây là DTO policy mới, không thay enum `RouterOutput` hoặc API cũ.

## 4. Bảng chạy thử 5 ca bắt buộc

Các điểm dưới đây do đề bài cung cấp, không phải phép đo lại model thật.

| Ca | Nhãn/điểm đầu | Điểm thứ hai | Gap | Ticker | Đầu ra |
|---|---|---|---|---|---|
| 1 | CHUC_VU 0.88 | NEWS 0.48 | 0.40 | VCB | SEARCH / GRAPH |
| 2 | BCTC_BCTN 0.91 | NEWS 0.41 | 0.50 | FPT | SEARCH / VECTOR |
| 3 | KET_HOP 0.85 | NEWS 0.55 | 0.30 | FPT | SEARCH / BOTH |
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

Kiểm chứng sau bổ sung: **119 test passed**, gồm hồi quy matcher/library/dataset
và kiểm payload, alias, scope kế thừa, lỗi matcher, JSON hữu hạn, không sửa input.
Replay điểm model thật trong results.jsonl của mục 5 kiểm được **66 quyết định**:
50 NEED_FALLBACK đều giữ đúng top 3; 15 ASK_CLARIFICATION và 1 SEARCH không có
payload. Một ca thiếu scope tiếp tục bỏ qua. Các decision/route/reason_code giữ
nguyên; đây là replay điểm cũ, không phải lượt inference mới hoặc test AI fallback.
Báo cáo model thật cũ giữ nguyên để bảo toàn bằng chứng tại thời điểm chạy.
