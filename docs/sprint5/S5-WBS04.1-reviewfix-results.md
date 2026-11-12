# Xử lý review Hưng — S5-WBS04.1, 12/11/2026

Hai lỗi code Hưng nêu được xác nhận và sửa trong ứng viên offline kế tiếp
(V4, policy `intent-request-objectives-v2`). Giữ nguyên V3 đã review để đối
chiếu; không thay source/artifact cũ, classifier, taxonomy hoặc router runtime.

## Đối chiếu từng nhận xét

| Nhận xét | Kết luận và xử lý |
|---|---|
| V3 nhận acronym AI thành từ hỏi ai | Đúng. Test trên V3 tái hiện tách sai câu doanh thu AI/cloud. Bản mới bảo vệ acronym trước khi xét từ hỏi và khôi phục nguyên văn cho embedding. Giữ “AI giữ chức…” khi là câu hỏi viết hoa. |
| Thiếu “Chủ tịch … là ai?”, “giữ chức gì”, CEO | Đúng. Bổ sung cách hỏi đảo vị trí, không dấu, CEO/CFO và who is CEO/CFO; vẫn loại mục tiêu bài tin, nguyên văn và số liệu lương. |
| Ranh giới kế hoạch lợi nhuận cần chốt | Hợp lý. Đã viết đề xuất riêng ở DRAFT; không tự đổi schema APPROVED hoặc gold hiện có. |
| Consumer Huyền mặc định cosine khi thiếu metadata | Theo bằng chứng Hưng báo, đây là lỗi contract ở consumer. Source consumer mới chưa có trong checkout nên chưa tái hiện/sửa trực tiếp ở phía đó. Đã ghi ma trận ca phải từ chối và bốn điểm cần thống nhất. |
| Chưa có nhãn cuối cho câu bổ sung do thiếu model | Đã bổ sung kiểm tra model thật cho 15 probe theo góp ý, kèm mọi nhãn cuối và điểm. Đây là bộ do Nhân soạn lại từ review, không khẳng định trùng bộ riêng chưa nhận được của Hưng. |
| Chưa tích hợp router/Web Chat | Đúng và vẫn chưa thực hiện trong vòng này. Không suy chất lượng E2E từ unit test. |

## Cách sửa và giới hạn

File mới: `backend/src/retrieval_orchestration/intent_request_review.py`.
Dùng bản đã sửa `requests()` cùng `resolve_objectives()` trong file này;
không trộn parser V1 với resolver mới khi tái tạo V4.

Guard AI xử lý khác biệt chữ hoa trước bước bỏ dấu/chuyển chữ thường. Có
guard hẹp cho danh sách doanh thu AI/cloud dùng chung câu hỏi “bao nhiêu”, kể
cả “Hãy cho biết…”. Không phải bộ phân tích cú pháp tiếng Việt hoàn chỉnh.
Không có điều kiện theo ticker, tên người, năm hoặc mã test. Không thêm luật
ép câu numeric đang bị classifier nhận sai thành đúng sau khi thấy kết quả.

`base_ranking` giữ nguyên. Nhãn đề xuất nằm ở `resolution`, confidence=null,
score_type vẫn `DECISION_EVIDENCE_NO_CONFIDENCE`, runtime_enabled=false.

## Kết quả chạy

18 ca unit test mới kiểm tra lỗi, các cách hỏi phổ biến và ca âm. Lượt đầu
trên V3: 10 fail/6 pass; sau khi bổ sung hai ca câu mệnh lệnh + danh sách phát
hiện thêm thiếu sót và sửa guard. Cả 18 ca cuối đạt. Giữ XML cả các lượt lỗi.
Toàn bộ bộ test Sprint 5 gồm 101 cũ + 18 mới = **119/119 test đạt**.

| Bộ đã xem | V3 đúng | V4 đúng |
|---|---:|---:|
| Hồi quy cũ, 47 câu có nhãn | 41 | 41 |
| Phát triển, 84 câu | 70 | 70 |
| Kiểm soát, 32 câu | 32 | 32 |
| Chẩn đoán, 8 câu | 6 | 6 |
| 28 câu đã dùng ở vòng trước | 24 | 24 |
| 42 câu từng mới ở V2 | 39 | 39 |
| 28 câu từng kiểm tra cuối V3 | 25 | 25 |

278 hàng gồm 9 câu null; không tính chúng vào accuracy. Không có nhãn nào
thay đổi so với V3 trên 278 hàng này. Chúng là hồi quy đã xem, không gọi là
test mới độc lập. Kết quả V3 không tăng vì các câu lỗi bổ sung chưa nằm trong
bộ cũ; không dùng điều đó để nói sửa lỗi vô tác dụng hoặc đã giải quyết hết.

15 probe review dùng BGE-M3 revision và head C=1 đã lưu: **14/15 đúng**,
head linear nguyên bản đúng 12/15 trên cùng câu. Probe là theo lỗi đã biết,
không phải test mù và chưa đại diện cho accuracy toàn bộ câu hỏi thực tế.
Hai biến thể câu mệnh lệnh bổ sung chỉ được kiểm ở unit test, chưa có phép đo
model riêng; không tính chúng vào mẫu số 15.

Câu còn sai REVIEW-03: “Doanh thu AI và cloud của doanh nghiệp ABC là bao nhiêu?”
kỳ vọng NUMERIC, quyết định ENTITY_RELATION. Parser đã giữ một yêu cầu nhưng
classifier vẫn sai; không đổi nhãn hoặc thêm ngoại lệ ABC để tăng điểm.

## Bằng chứng có thể chạy lại

`outputs/s5_intent_reviewfix_20261112/run02/` là lượt hiện tại. `cases.json`,
`parts.json`, `results.json` giữ đầy đủ query/gold/phần tách/nhãn cuối/điểm gốc.
`method.json` giữ checksum trước đo. Không training lại hay calibration.

19 văn bản mới được vector hóa ở run01; run02 dùng lại đúng vector đó khi hoàn
thiện guard theo unit test, không gọi model lại hoặc chọn tham số bằng gold.
Giữ snapshot source run01 đúng checksum và development-note.json; không giả
vờ source lịch sử vẫn trùng với file hiện tại. Lỗi đường dẫn cache tương đối
được sửa trước khi tạo run02, không đổi dữ liệu hoặc kết quả model.

Audit run02 tái hiện 293 quyết định (278 hồi quy + 15 probe), tự tính lại
probability từ vector/coefficients; sai lệch tối đa dưới 1e-10. Kiểm nguyên
raw ranking và snapshot lịch sử. Replay quy tắc không thay review ngữ nghĩa
độc lập. Audit V3 cũ vẫn qua với mọi nguồn đóng băng không đổi.

Dùng môi trường backend hoặc dependency trong
`requirements-s5-objectives-check.txt`; audit không cần model weights/DB/API:

```powershell
$env:PYTHONPATH=(Join-Path $PWD.Path 'backend')
$env:PYTHONUTF8='1'
python backend/scripts/audit_s5_intent_reviewfix.py
python backend/scripts/audit_s5_intent_objectives.py
$tests=(Get-ChildItem backend/tests/test_s5_intent_*.py).FullName
python -m pytest $tests -q -p no:cacheprovider
```

Nhờ Hưng review lại module mới, đặc biệt guard danh sách AI/cloud và các ca âm.
Nhóm/Huyền xem [đề xuất ranh giới và contract DRAFT](S5-WBS04.1-boundary-and-consumer-DRAFT.md).
Chưa đề nghị chốt tích hợp 04.2: chưa calibration, chưa có source consumer mới,
chưa kiểm chứng E2E. Task 01.2 đang tạm dừng theo yêu cầu Nhân.
