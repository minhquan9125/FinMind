# Ý định v2 — bản triển khai của Nhân, 13/11/2026

Phần này giúp FinMind nhận biết người dùng đang muốn làm gì trước khi tìm dữ
liệu. Ví dụ hỏi giá thuộc PRICE, hỏi doanh thu thuộc NUMERIC, hỏi chủ tịch là ai
thuộc PERSON_ROLE. Hưng dùng kết quả này để điều phối Chat; Huyền xử lý chính
sách chấp nhận/fallback. Bản hiện tại sẵn sàng review kỹ thuật, **chưa chốt Done**.

## Sản phẩm đã có

- **03.1:** [schema 11 nhãn](../intent-labels.v2.json), có mã fallback, định nghĩa
  và nhóm con. Trạng thái OWNER_AUTHORIZED_PENDING_TEAM_REVIEW; chưa giả định
  nhóm đã duyệt. ANALYSIS gồm giải thích kiến thức như “P/E là gì?”.
- **03.2:** 220 tình huống gốc, 20 mỗi nhãn, 4 mỗi nhóm con; mở rộng thành
  **470 câu mẫu** có dấu, không dấu, viết tắt và một số lỗi gõ. 110 câu phát triển
  được tác giả test riêng soạn mà không đọc thư viện; vẫn là DEVELOPMENT,
  không phải nghiệm thu kín của người trong nhóm. Không trùng sau chuẩn hóa,
  mọi biến thể cùng family/split. Các tình huống là dữ liệu giả định để gán ý định.
- **03.3:** vector thật 470 × 1024 và classifier tuyến tính 11 lớp, BAAI/bge-m3
  revision `5617a9f61b028005a4858fdac845db406aefb181`. Chọn C=10 bằng 4 fold
  theo family chỉ trong LIBRARY. Không đưa DEVELOPMENT vào fit/chọn C.
- **04.1:** [hàm classify_intent](../../../backend/src/retrieval_orchestration/intent_v2_classifier.py),
  dùng embedder backend, cache artifact theo phiên bản và encoder, có khóa lúc
  nạp lần đầu. Mỗi câu tạo một vector toàn câu; các vế dùng bằng chứng luật.
  Chưa rõ một vế thì giữ unresolved_requests, không tự đoán thành phần MIXED.

V1 và các báo cáo cũ được giữ nguyên. Artifact v2 nằm tại
`outputs/s5_intent_v2_20261113/artifact-v2/`, gồm library, vectors.npy,
classifier.npz, fit.json và manifest có checksum. READY_FOR_REVIEW là trạng thái
đóng gói kỹ thuật, không phải được nhóm duyệt hoặc cho phép tìm kiếm thẳng.

## Hưng gọi như sau

```python
from src.documents.embeddings import get_embedding_service
from src.retrieval_orchestration.intent_v2_classifier import classify_intent

embedder = get_embedding_service()  # dùng lại singleton của ứng dụng
result = classify_intent("Chủ tịch HĐQT FPT là ai?", embedder=embedder)
print(result["resolution"])
```

Model phải có sẵn trong cache. Chuẩn bị và warmup tại startup; đặt
HF_HUB_OFFLINE=1 / TRANSFORMERS_OFFLINE=1 khi chạy với cache cục bộ. Hàm phân
loại không chủ động tải model; embedder được caller cung cấp chịu trách nhiệm
khởi tạo. Việc chạy hàm đồng bộ ngoài event loop của Chat do Hưng tích hợp.

Đầu ra có base_ranking, resolution, reference_ranking và các version:

| Phần | Loại điểm / chính sách | Cách hiểu |
|---|---|---|
| base_ranking | intent-linear-v2 / CLASSIFIER_PROBABILITY_UNCALIBRATED | Top 3 mô hình; giữ nguyên khi luật đổi nhãn. |
| resolution | intent-request-objectives-v2-11 / DECISION_EVIDENCE_NO_CONFIDENCE | Nhãn đề xuất và bằng chứng; confidence=null, runtime_enabled=false. |
| reference_ranking | cosine-max-per-label-v1 / COSINE_SIMILARITY_NOT_PROBABILITY | Top 3 nhóm, 5 câu gần nghĩa trên **thư viện v2**; policy chỉ tên cách tính cosine. |

Resolution chứa question, reason, explicit_evidence, component_labels,
unresolved_requests, contains_restricted_component và status:

- PROPOSED: có nhãn để consumer kiểm tiếp; không đồng nghĩa SEARCH.
- NEEDS_CONTEXT: câu nối tiếp/chọn mục/hỏi nguồn chưa có context đã xác minh.
  Chỉ caller được cung cấp context={"verified": True}; module không kế thừa phiên.
- UNRESOLVED: thành phần MIXED hoặc một vế chưa xác định đủ; không tự thực hiện.

Consumer hiện đọc policy/7 nhãn cũ nên **chưa tương thích v2**. Huyền cần chấp
nhận rõ 11 nhãn, policy v2 và kiểm status/flag hạn chế trước khi tích hợp. Nhân
không sửa consumer của Huyền. Không áp 0,65/0,08 cho xác suất chưa hiệu chỉnh;
MIXED không mặc định BOTH. Nhãn OUT_OF_SCOPE hoặc thành phần tương ứng cần
policy phía sau xử lý, classifier không tự chọn route hoặc trả lời.

## Kết quả và giới hạn

| Tập / phương pháp | Đúng top-1 |
|---|---:|
| DEVELOPMENT: cosine trên thư viện v2 | 77/110 (70,0%) |
| DEVELOPMENT: classifier thuần | 100/110 (90,9%) |
| DEVELOPMENT: classifier + luật sau sửa | 110/110 (100%) |
| Hồi quy 47 câu cũ có gold, chuyển nghĩa nhãn sang v2 | 47/47 |

DEVELOPMENT đã dùng để sửa lỗi nên 100% là kết quả phát triển/hồi quy. Chưa có
bộ kín độc lập, **không suy ra đạt 90% trên câu mới**. CV theo family trên LIBRARY
chỉ khoảng 55,6% accuracy / 55,2% macro-F1, cũng cho thấy khả năng tổng quát hóa
cần kiểm tiếp. Giữ nguyên trọng số model sau lần fit; các sửa sau đó chỉ ở luật.

Trong DEVELOPMENT, 10 câu OUT_OF_SCOPE đều giữ đúng nhãn và 10 câu MIXED đều
đủ thành phần. Đây là kiểm phân loại; chưa chạy router để kết luận số ca chặn
thực tế. Tám câu hội thoại vẫn NEEDS_CONTEXT, được tính đúng **nhãn** nhưng chưa
sẵn sàng thực hiện. Bộ hồi quy giữ nguyên file gold v1, ánh xạ riêng TREND →
ANALYSIS và NUMERIC có nguồn PRICE duy nhất → PRICE; 9 câu chưa có gold không
được tự gán. Sáu MIXED cũ có đủ thành phần. Macro-F1 hồi quy tính cả 11 nhãn có
ba nhãn không xuất hiện là 0,727; không dùng nó để nghiệm thu taxonomy mới.

Lượt đo cuối gọi API thật 110 lần, CPU 4 thread: **p50=568 ms, p95=1514 ms**,
đúng nhãn 110/110. Lượt đầu CPU 2 thread có p50=953 ms, p95=2460 ms.
Mục tiêu p95≤500 ms **chưa đạt**. Profiling 1/2/4 thread cho thấy tạo vector
BGE-M3 chiếm phần lớn thời gian. Các cấu hình này chỉ dùng trong tiến trình đo;
không sửa dịch vụ embedding hoặc cấu hình ứng dụng của nhóm. Không đổi model,
hạ tiêu chí hoặc dùng vector cache để báo độ trễ giả. Thời gian trên chưa gồm
nạp model lạnh; warmup API của lượt cuối là 763 ms khi model đã ở RAM.

Hai lỗi TREND cũ, AI/ai, đọc/độc, chức vụ, nguồn bài tin, giá mục tiêu, trích bằng
chứng và nhiều ý đều có kiểm thử. Unit/contract v2 hiện **117 test đạt**; kiểm
thử bằng vector giả xác minh chức năng, tách khỏi phép đo model thật. Toàn bộ
kiểm thử Sprint 5 của Nhân đạt **343/343**, không lỗi/skip. Huấn luyện lại từ
vector đã lưu cho coefficients/intercepts giống hệt; chênh lệch lớn nhất bằng 0.

Bằng chứng chính trong `outputs/s5_intent_v2_20261113/`:

- `verification.json`: kiểm checksum/nguồn, tái fit và đối chiếu API thật với vector đã lưu.
- `run04-development/`, `run04-regression/`: số liệu từng nhãn, ma trận nhầm lẫn,
  từng câu và snapshot nguồn trước đo. Các lần DEVELOPMENT đã dùng để sửa lỗi.
- `warm-latency-final/`: thời gian từng lần gọi thật và cấu hình máy/thread;
  `cpu-profile/` là khảo sát tạo vector riêng, không phải nghiệm thu.
- `all-sprint5-tests.xml`, `v2-tests.xml`: kết quả kiểm thử.
- `vector-cache/`: vector LIBRARY/DEVELOPMENT tách biệt và nguồn đóng băng trước encode.

## Chạy lại và review

Từ thư mục repo, dùng Python môi trường backend và PYTHONPATH=backend:

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_s5_intent_v2_rules.py backend/tests/test_s5_intent_v2_runtime.py backend/tests/test_s5_intent_v2_dataset.py -q -p no:cacheprovider
backend/.venv/Scripts/python.exe backend/scripts/build_s5_intent_v2.py --output outputs/v2-rebuild-new
backend/.venv/Scripts/python.exe backend/scripts/evaluate_s5_intent_v2.py --output outputs/v2-dev-rerun-new
backend/.venv/Scripts/python.exe backend/scripts/evaluate_s5_intent_v2.py --legacy --output outputs/v2-regression-rerun-new
```

Các runner từ chối ghi đè. Build/evaluate dùng vector BGE thật đã lưu để tái tạo
nhanh; không coi thời gian đó là tốc độ runtime. `benchmark_s5_intent_v2.py`
nhận encoder đã nạp, gọi API thật từng câu và đo lại vector mỗi lần.
`encode_s5_intent_v2.py` dùng cho việc tái encode tại thư mục cache mới; cần
chuẩn bị model trước. Môi trường đo ghi trong method.json (NumPy 1.26.4,
Torch 2.6.0); NumPy cục bộ hiện khác yêu cầu ≥2.1 trong requirements, cần kiểm
trên môi trường chuẩn khi tích hợp. Không thay requirements của nhóm trong task này.

Hưng review ranh giới 11 nhãn, API và các câu còn mơ hồ. Huyền đối chiếu contract
ở phần của mình. Để chốt chất lượng: nhận ít nhất 110 câu kín độc lập (10/nhãn),
đóng băng commit trước khi mở bộ đó, đo đủ top-1/macro-F1/recall/ma trận nhầm
lẫn và OUT_OF_SCOPE, rồi đo p95 trên máy demo. Còn thiếu bộ kín và chưa đạt
tốc độ thì giữ trạng thái chưa nghiệm thu; phần Chat/E2E thuộc task tích hợp.
