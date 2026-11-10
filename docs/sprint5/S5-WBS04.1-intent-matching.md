# S5-WBS04.1 — Đối chiếu vector câu hỏi với thư viện

Phụ trách: Hồ Phạm Đăng Nhân. Ngày thực hiện: 10/11/2026.
Giờ dự kiến backlog: 3 giờ; không phải giờ công thực tế đã ghi nhận.

## Phạm vi và hợp đồng đầu ra

Đối chiếu câu hỏi với thư viện `s5-intent-library-v1` bằng cùng model BAAI/bge-m3,
full revision `5617a9f61b028005a4858fdac845db406aefb181`. Không dùng điểm
graph_score/content_score của model router để thay cho độ tương đồng ý định.

`IntentMatcher` nhận artifact đã được `load_library` kiểm tra và dịch vụ embedding.
Constructor từ chối model/revision khác trước khi gọi encoder. `match` dùng
embed_query; `match_many` dùng embed_texts của cùng dịch vụ (embed_query hiện gọi
embed_texts cho một câu). Không bỏ dấu hoặc đổi chữ viết tắt trước embedding.

Đầu ra có câu hỏi, model/revision, version thư viện/dữ liệu/nhãn, groups và examples:

- groups: danh sách nhãn khác nhau theo thứ tự gần nhất, mỗi nhãn có score và
  best_example để truy về ID, văn bản, nhãn và component_intents của ví dụ mẫu.
- examples: những câu mẫu gần nhất; có thể có nhiều câu cùng nhãn hoặc cùng gốc.
- Điểm là cosine trong [-1, 1], không phải xác suất. component_intents nằm trong
  best_example, không phải khẳng định đã tách được thành phần của câu hỏi mới.

Mặc định trả ba nhóm và năm ví dụ. K lớn hơn số mục có sẵn được cắt theo số mục
thực có. K phải là số nguyên dương; câu rỗng, sai kiểu, vector sai chiều, NaN/Inf
hoặc norm 0 đều bị từ chối. Không thêm route, decision, ngưỡng, hỏi lại hoặc fallback.

## Cách xếp hạng đã chọn trước lượt đo

Policy: **cosine-max-per-label-v1**. Chuẩn hóa query và hàng vector thư viện khi
tính cosine; giữ đủ độ chính xác số để xếp hạng, không làm tròn trước khi so điểm.

Với mỗi nhãn, lấy điểm cao nhất trong các ví dụ có nhãn đó. Không cộng điểm hoặc
đếm phiếu từ các biến thể. Cách lấy max tránh việc tự cộng điểm chỉ vì nhiều câu,
nhưng không bảo đảm loại bỏ mọi ảnh hưởng do độ phủ/số mẫu khác nhau; MIXED có
18 mẫu trong khi mỗi nhãn cơ sở có 12. Đây là baseline, không khẳng định tối ưu.

Khi điểm bằng nhau: label tăng dần, rồi ID ví dụ tăng dần để kết quả ổn định.
Mỗi nhóm lấy ví dụ đầu tiên theo thứ tự đó làm bằng chứng. Không thay cách tính
hoặc chỉnh câu mẫu sau khi xem kết quả của lượt đánh giá hiện tại.

## Chạy câu hỏi đơn

Ở gốc FinMind, dùng Python đã cài dependency backend và có model đúng revision.
Ví dụ môi trường trên máy Nhân:

```powershell
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:TOKENIZERS_PARALLELISM='false'
$env:OMP_NUM_THREADS='4'
$env:MKL_NUM_THREADS='4'
.\backend\.venv\Scripts\python.exe backend/scripts/match_s5_intent.py --question "Ai được bổ nhiệm làm TGĐ DGC trong tháng 09/2025?" --top-groups 3
```

Nếu model chưa có cache, bước nạp offline sẽ thất bại; không thay bằng vector giả.
Không cần backend/web server, PostgreSQL, Neo4j hoặc Gemini để chạy đối chiếu này.

## Đánh giá bằng bộ test riêng

Lệnh sau dùng `test.jsonl` làm câu hỏi đánh giá, không thêm vector câu test vào
thư viện. Pin checksum test theo dataset manifest snapshot của artifact 03.3.

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/evaluate_s5_intent_matching.py --output outputs/s5_wbs041_20261110/run02
```

Không ghi đè thư mục kết quả có sẵn. Lượt đầu nằm trong
[run01](../../outputs/s5_wbs041_20261110/run01).
method.json và test-input.jsonl được lưu trước khi gọi model để giữ phương pháp,
checksum và đầu vào. results.jsonl lưu từng câu cùng toàn bộ bảy nhóm và năm ví dụ;
summary.json lưu metrics, confusion matrix, danh sách ca sai và phân nhóm kết quả.

56 câu gồm **47 câu có nhãn** (44 scope rõ + 3 scope thiếu) và **9 câu null**
(NEEDS_CONTEXT, OUTSIDE_TAXONOMY, UNRESOLVED). Chỉ 47 câu có nhãn dùng để tính
top-1 accuracy, top-3 recall và macro-F1 bảy nhãn. Chín câu null vẫn được xếp hạng
để quan sát, không tính thành đúng/sai và không tự gán nhãn OUT_OF_SCOPE.

Top-1 trong báo cáo là nhãn đứng đầu dùng cho phép đo baseline, không phải quyết
định routing. Chưa có ngưỡng chất lượng nghiệm thu được nhóm thống nhất; báo điểm
thực, không chọn một mức pass sau khi biết kết quả. Bộ test do cùng tác giả soạn
và đã qua review, không phải đánh giá mù/độc lập hoàn toàn.

Thời gian trong summary là tổng một batch, gồm cả nạp model lazy. Không diễn giải
thành p95 hoặc độ trễ mỗi request WebChat. Không thay đổi corpus/vector mẫu đã duyệt.

### Kết quả thực tế run01

| Chỉ số | Kết quả |
|---|---:|
| Top-1 đúng | 22/47 — 46,81% |
| Nhãn đúng trong top-3 | 41/47 — 87,23% |
| Macro-F1 bảy nhãn | 0,4680 |
| Ca sai top-1 | 25 |
| Ca không có nhãn đúng trong top-3 | 6 |
| Câu null chỉ quan sát | 9 |

Chất lượng top-1 còn thấp, nhất là REPORT_CONTENT và MIXED. Đây là giới hạn của
baseline đã đo, không phải bằng chứng chất lượng đạt chỉ vì unit test qua.
Chức năng trả nhóm/điểm đã có; chưa nên dùng nhãn đứng đầu để tự động chọn route.
Xem [phân tích toàn bộ ca sai](S5-WBS04.1-baseline-results.md).
Các metrics đã được tính lại trực tiếp từ results.jsonl bằng phép đếm riêng và
khớp summary; không chỉ đọc giá trị do hàm tổng hợp ban đầu trả ra.

## Unit test và hồi quy

18 bài test đối chiếu kiểm tra công thức cosine, điểm âm, nhóm max thay vì tổng,
thứ tự ID khi hòa điểm, model/revision, đầu vào lỗi, giữ nguyên dấu/thứ tự batch,
và tính metrics có loại câu null. Encoder giả chỉ dùng trong unit test.

Cùng 28 test dữ liệu/artifact đã có: **46 passed**, xem
[unit-tests.xml](../../outputs/s5_wbs041_20261110/unit-tests.xml).
Không cộng 27 test bổ sung được Hưng báo ở máy reviewer vào số test repository này.

```powershell
$env:PYTHONPATH=(Join-Path $PWD.Path 'backend')
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_s5_intent_matching.py backend/tests/test_s5_intent_library.py backend/tests/test_s5_intent_dataset.py -q -p no:cacheprovider
```

## Giới hạn bàn giao

Chỉ triển khai tìm ứng viên ý định và điểm tương đồng. Không sửa router cũ,
WebChat, trạng thái token, dữ liệu doanh nghiệp hoặc các lỗi ngoài phạm vi.
Review kỹ thuật 03.3 của Hưng đã được ghi nhận; cổng ECC phía reviewer chưa hoàn
tất và không được ghi thành đã duyệt nhờ task 04.1.
