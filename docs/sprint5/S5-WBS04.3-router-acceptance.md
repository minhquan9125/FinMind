# S5-WBS04.3 — Bộ kiểm thử router độc lập và Excel bàn giao

Ngày: 13/11/2026. Phụ thuộc: contract 04.2 và bộ mẫu/test 03.2.

## Thiết kế và kế hoạch thực hiện

Yêu cầu: tạo câu thử từ góc nhìn người dùng, ghi kỳ vọng trước kết quả, ghi nhãn,
loại điểm, lý do và quyết định/nhánh; chỉ PASS khi coverage và tỷ lệ thành công
đạt ít nhất 90%. Người dùng đã chọn đo cả code coverage và nhóm hành vi.

Chọn kết hợp ba lớp: câu mới được soạn chỉ từ contract nhãn 03.1; hồi quy bộ
test 03.2; và đầu vào kiểm chứng policy theo contract 04.2. Chỉ chạy unit test
cũ sẽ thiếu oracle mới; chỉ chạy câu hỏi model sẽ thiếu lỗi protocol/ngưỡng.

Không sửa mẫu, trọng số, nhãn, policy hoặc ngưỡng để làm test qua. Không tự bật
SEARCH trong chế độ mặc định. Chế độ diagnostic phải ghi riêng. Câu cần hỏi lại
phải chặn trước matcher; fallback đúng contract không chứng minh phân loại đúng.

### Ngưỡng và cách chấm đã chốt trước khi chạy

- Line coverage của riêng module policy 04.2: >=90%.
- Branch coverage của cùng module: >=90%.
- Nhóm hành vi đã định nghĩa và thực sự được chạy: >=90%.
- Tỷ lệ ca policy khớp kỳ vọng: >=90%.
- Tỷ lệ thành công câu mới: >=90%, đồng thời kiểm riêng độ đúng nhãn và tuyến
  nghiệp vụ đề xuất. Không tính NEED_FALLBACK là một nhãn hay một lần tìm kiếm đúng.
- Hồi quy 03.2: >=90% trên câu có gold label; câu null báo riêng.
- Thiếu model, không chạy được hoặc metric thiếu không được ghi PASS.

Policy hiện fallback-only. Bảng luôn giữ actual_decision/actual_route thực tế;
candidate_route chỉ là tuyến suy ra từ nhãn/thành phần dự đoán, không phải nhánh
đã gọi retrieval. Điểm cosine và xác suất classifier chưa hiệu chỉnh ghi riêng.
Task 04.3 không chứng minh Chat/07.2 đã chạy hoặc chất lượng câu trả lời truy xuất.

### File và các bước

- [x] `docs/sprint5/router-acceptance-v1/business.jsonl`: 80 câu mới, gồm 70 câu
  cân bằng 7 nhãn và 10 ca thiếu dữ kiện/kỳ sai. Soạn trong context riêng không
  đọc implementation, test cũ hoặc kết quả model; cố định trước inference.
- [x] `backend/scripts/evaluate_s5_router.py`: oracle policy theo contract,
  chạy model BGE-M3/trọng số V7 đã lưu, đo coverage, ghi raw JSON và Excel.
- [x] `backend/tests/test_s5_router_acceptance.py`: kiểm chính công cụ chấm và
  các đầu vào policy. Quan sát fail trước khi triển khai runner.
- [x] Kiểm trùng câu mới với thư viện/test cũ và khóa checksum trước inference.
- [x] Chạy toàn bộ, giữ cả ca sai và metric dưới ngưỡng; không chọn lại câu sau
  khi đã biết điểm. Excel có tổng quan, câu mới, hồi quy, policy, coverage và ca sai.
- [x] Rà kết quả, kiểm Excel mở được và hash code/dữ liệu gốc không đổi.

## Giới hạn về độc lập

Soạn câu mới trong context không đọc implementation giúp giảm oracle đi theo
code. Đây là bộ do AI hỗ trợ soạn theo taxonomy đã công bố, không phải đánh giá
mù do hội đồng người dùng độc lập giữ kín. Bộ 03.2 đã được xem trong phát triển,
nên chỉ dùng làm hồi quy. Không gộp hai bộ để che chất lượng thấp của bộ mới.

## Kết quả

**Kết luận nghiệm thu: FAIL — chưa đạt 90% trên bộ câu hỏi mới.** Đã tạo và
chạy bộ kiểm thử, có bảng kỳ vọng/thực tế và Excel; không đồng nghĩa chất lượng
bộ phân loại đã đạt để tự SEARCH trong production.

Lần chạy cuối: `outputs/s5_wbs043_20261113/run02`, kết thúc lúc
**15:01:41 +07:00 ngày 13/11/2026**. Model BGE-M3 thật, revision
`5617a9f61b028005a4858fdac845db406aefb181`, classifier đã lưu của Nhân và
resolution V7/v5. Không huấn luyện, hiệu chỉnh hoặc thay mẫu. Đã encode mới
179 văn bản gồm câu hỏi và thành phần tách ra; CPU, batch_size=4, 197,47 giây
cho toàn bộ bước embedding. Đây không phải latency của từng request.

| Cổng nghiệm thu | Kết quả thực tế | Ngưỡng | Trạng thái |
|---|---:|---:|---|
| Line coverage riêng policy 04.2 | 258/264 = 97,73% | >=90% | PASS |
| Branch coverage cùng module | 129/136 = 94,85% | >=90% | PASS |
| Nhóm hành vi định nghĩa trước | 32/32 = 100% | >=90% | PASS |
| Ca contract/policy độc lập | 170/170 = 100% | >=90% | PASS |
| Câu mới đúng toàn bộ tiêu chí áp dụng | 58/80 = 72,50% | >=90% | FAIL |
| Nhãn V7 đúng trên câu mới đủ scope | 56/70 = 80,00% | >=90% | FAIL |
| Tuyến V7 đề xuất đúng và đủ bằng chứng thành phần | 53/70 = 75,71% | >=90% | FAIL |
| Hồi quy 03.2, câu có nhãn | 43/47 = 91,49% | >=90% | PASS |

814/814 unit test liên quan intent và công cụ 04.3 đạt; xem `unit-tests.txt`.
Kết quả này chứng minh contract/công cụ, không thay thế tỷ lệ đúng model ở trên.
9 câu null của 03.2 chỉ ghi quan sát, không tự gán gold hoặc cộng vào accuracy.
Các file code/dữ liệu đầu vào được kiểm SHA-256 trước/sau và không thay đổi.

### Chi tiết bộ mới

| Nhãn gold | Đúng nhãn | Đúng tuyến đề xuất | Số câu |
|---|---:|---:|---:|
| NUMERIC | 7 | 7 | 10 |
| REPORT_CONTENT | 7 | 8 | 10 |
| NEWS | 8 | 8 | 10 |
| PERSON_ROLE | 8 | 8 | 10 |
| ENTITY_RELATION | 8 | 8 | 10 |
| TREND | 10 | 10 | 10 |
| MIXED | 8 | 4 | 10 |

Trong 70 câu này, 51 câu đúng đồng thời nhãn, thành phần và tuyến. Có 19 ca
sai ít nhất một tiêu chí model. Ví dụ:

- `S5-043-N006`: chỉ xin hai giá đóng cửa và chênh lệch tuyệt đối, gold
  NUMERIC/VECTOR; V7 trả TREND/BOTH. Classifier top-1 probability chưa hiệu chỉnh
  là 0,2177; cosine top-1 lại là NUMERIC, 0,6114. Không đánh đồng hai loại điểm.
- `S5-043-N019`: xin sao chép hàng trong BCTN, gold REPORT_CONTENT; V7 trả NEWS.
  Cùng tuyến VECTOR vẫn sai ý định nên ca này FAIL.
- `S5-043-N045` và `N048`: hỏi số lượng/tỷ lệ sở hữu của quan hệ, gold
  ENTITY_RELATION/GRAPH; V7 tách thêm NUMERIC và trả MIXED chưa đủ xác minh.
- `S5-043-N062`, `N064`, `N066`, `N068`, `N069`: V7 nhận MIXED nhưng chưa có
  đầy đủ bằng chứng hai loại yêu cầu rõ ràng để xác minh thành phần, nên không
  tự gán BOTH. `N061` và `N070` còn sai nhãn MIXED.

10/10 ca thiếu dữ kiện/kỳ sai đều ASK_CLARIFICATION và gọi matcher **0 lần**.
`N075`, `N076`, `N077` còn lệch **mã lý do**: oracle ban đầu ghi
AMBIGUOUS_CONTEXT_COMPANY, policy trả MISSING_COMPANY khi context không được
cung cấp/chưa xác nhận/khác phiên. Đây là điểm cần thống nhất enum giữa oracle
và contract; hành vi hỏi lại an toàn đã đúng, không phải lỗi chọn tuyến hoặc
gọi AI ngoài. Giữ nguyên gold đã khóa và ghi 3 sai lệch này, không sửa để tăng điểm.

### GRAPH/BOTH và giới hạn phạm vi

Đã thấy model đề xuất GRAPH và BOTH. Với bộ mới, tuyến đề xuất gồm
VECTOR=26, GRAPH=17, BOTH=13; 14 câu đủ scope chưa xác minh được tuyến.
Theo tuyến gold, đúng VECTOR 25/33, GRAPH 17/22, BOTH 11/15.

Chạy riêng diagnostic cosine với opt-in rõ ràng có 8 ca SEARCH, gồm
VECTOR=2, GRAPH=3 (`N033`, `N035`, `N046`), BOTH=3 (`N054`, `N059`, `N067`).
Cả 8 khớp tuyến gold trên bộ này; kích thước nhỏ và không làm thay đổi kết luận
toàn bộ bộ test. Không dùng kết quả này để bật lại SEARCH mặc định.

**Quyết định policy thực tế vẫn là 70 NEED_FALLBACK, 10 ASK_CLARIFICATION;
route=null.** Không có retrieval/AI fallback/Chat/Neo4j/UI được thực thi trong
04.3. Chưa thể dùng báo cáo này để khẳng định câu trả lời sau 07.2 đúng. Không
sửa production để test qua. Nhân cần đối chiếu classifier/tách mục tiêu trên
19 ca model sai; Huyền và Nhân cần chốt 3 enum lý do của oracle/context.

### File bàn giao và cách chạy lại

- Excel duy nhất của bản cuối: [S5_WBS04_3_ROUTER_ACCEPTANCE_20261113.xlsx](../../outputs/s5_wbs043_20261113/run02/S5_WBS04_3_ROUTER_ACCEPTANCE_20261113.xlsx).
  Sáu sheet: `Tong_quan`, `Cau_hoi_moi`, `Hoi_quy_03_2`, `Policy_04_2`,
  `Coverage`, `Ca_sai`. Có đủ 80 và 56 Test_ID; sheet ca sai giữ 22 ca mới
  và 4 ca hồi quy. Không chấm Pass cho null-label thất bại hoặc mất kết quả.
- Log gốc cùng thư mục: `results.json`, `policy-results.json`, `summary.json`,
  `method.json`, `business-frozen.json`, `policy-frozen.json`, `coverage.json`,
  `behavior-coverage.json`, `coverage-html/index.html`, `unit-tests.txt`.
- Lần `run01` được giữ làm lịch sử. Sau review đã bổ sung so thành phần MIXED,
  đưa cả ca null-label thất bại vào danh sách lỗi và xuất đủ cột kỳ vọng.
  `run02` chạy model thật lại với cùng gold/hash; không dùng điểm giả hoặc sửa gold.

Từ thư mục FinMind, PowerShell:

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = 'backend'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$intentTests = @(Get-ChildItem 'backend/tests/test_s5_intent_*.py' | ForEach-Object { $_.FullName })
.\.venv\Scripts\python.exe -m pytest @intentTests backend/tests/test_s5_router_acceptance.py -q
.\.venv\Scripts\python.exe backend/scripts/evaluate_s5_router.py --output outputs/s5_wbs043_20261113/run03
```

Chọn tên output mới để bảo toàn bằng chứng; CLI từ chối ghi đè. Exit code 1
của run02 là **FAIL nghiệm thu**, không phải lỗi kết nối/model. Cần có model
cache đúng revision, thư viện 03.3 và head đã lưu (đường dẫn trong method/script).
Venv dùng thêm `coverage==7.17.3`; không chỉnh requirements production.
Đây là kiểm thử module intent có phạm vi, không phải full-project/E2E.
