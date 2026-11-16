# S5-WBS09.1 — Kế thừa công ty, kỳ và chủ đề giữa các lượt

Nhân, 16/11/2026. **Hoàn thành triển khai và kiểm thử phần ngữ cảnh; sẵn sàng review.**
Chưa có xác nhận nghiệm thu của reviewer. Nhánh làm việc: `nhan-next-task-20261116`,
nền trước task: `14beea8d`.

## Hành vi đã hoàn thiện

Người dùng không cần nhắc lại mọi thông tin ở mỗi lượt. Sau câu “Lợi nhuận sau
thuế BID năm 2025”, câu “Còn VCB thì sao?” chuyển công ty sang VCB và giữ chỉ tiêu,
năm. “Còn quý hai cùng năm thì sao?” đổi sang quý 2 của năm 2025, không dùng lại
số cả năm hoặc tự chọn năm hiện tại. Khi người dùng ghi mã, kỳ hoặc chỉ tiêu mới,
dữ kiện mới được ưu tiên.

| Tình huống | Kết quả cần giữ |
| --- | --- |
| Đổi sang ACB, giữ chỉ tiêu và kỳ trước | ACB, cùng chỉ tiêu và kỳ; không hỏi chọn chỉ tiêu lại |
| Đổi quý, trước đó chỉ có một năm cụ thể | Giữ năm đó, dùng quý mới và cơ sở riêng quý |
| Chưa có năm hoặc trước đó có nhiều năm | Hỏi lại năm, không chọn tùy ý |
| BCTN FPT 2024 về chiến lược → Còn VCB/Vinamilk? | Giữ chủ đề và năm; thay cả công ty trong câu truy xuất |
| Còn VCB năm 2023? / Còn năm 2023? | Chỉ thay các dữ kiện người dùng nêu rõ |
| BCTN → câu hỏi số liệu / tin mới | Chuyển nguồn phù hợp, bỏ chủ đề BCTN cũ |
| Câu chức vụ → câu số liệu → đổi mã | Không giữ bộ lọc chức vụ/đồ thị cũ |
| Tin tháng 9 → hỏi doanh thu | Không lấy tháng xuất bản làm kỳ BCTC |
| Tiếp tục phiên đã lưu | Kế thừa ngữ cảnh; phiên gốc không bị thay đổi |
| Phiên mới hoặc `/new` | Không lấy chỉ tiêu và kỳ từ phiên trước |

“Tóm tắt kế hoạch doanh thu” trong ngữ cảnh BCTN vẫn hỏi nội dung báo cáo.
“Lợi nhuận ... bao nhiêu?” thiếu trước/sau thuế sẽ hỏi rõ, thay vì giữ chủ đề
BCTN. “Không giữ chỉ tiêu cũ” cũng không được âm thầm dùng lại chỉ tiêu cũ.
Sau một câu so sánh nhiều công ty, đổi một mã mà không rõ thay bên nào sẽ hỏi lại.

## Cách làm và phạm vi

Sửa `backend/src/retrieval_orchestration/live_research.py` tại lớp giải quyết scope
đang được Chat sử dụng. Tái sử dụng parser, từ điển chỉ tiêu và tên công ty hiện có;
không thêm model hay lời gọi AI. Context được sao chép trước khi thay đổi.
Đường lưu phiên, API và giao diện giữ contract hiện có.

Test ở `backend/tests/test_s5_wbs091_context.py`. Có các test tái hiện lỗi trước
khi sửa; sau đó kiểm cả parser, `LiveResearchService`, `WebChatRouter`/`DecisionEngine`,
API gửi tin nhắn, lưu/mở lại/tiếp tục phiên và cách ly người dùng.

Không thay refresh token của Quân, ngưỡng của Huyền hoặc classifier intent.
Không triển khai 09.2/09.3 và không sửa kết quả benchmark 13.2.

## Kết quả kiểm chứng

- **29/29 ca mới đạt**, gồm PostgreSQL thật.
- **Bộ kiểm cuối: 255 pass, 1 skip, 0 fail.** Gồm các suite ngữ cảnh, live research,
  an toàn kỳ/nguồn, BCTN, đồ thị, thị trường, làm rõ và lưu phiên.
- **Lượt full backend: 3482 pass, 69 fail, 25 skip, 2 xfail.** Đã kiểm báo cáo từng
  lỗi: 64 lỗi `ConnectionRefusedError` do DB thử riêng `127.0.0.1:15434` chưa chạy;
  5 lỗi `FileNotFoundError` do thiếu fixture WBS02 person identity. Không đổi test
  hay hạ tiêu chí để che các lỗi này. Danh sách nằm trong `verification.json`.
  Lượt full chạy trước hai bổ sung biên cuối (phủ định giữ chỉ tiêu và lợi nhuận
  chưa rõ trước/sau thuế); sau đó đã chạy lại toàn bộ bộ kiểm liên quan nêu trên.
- `git diff --check` đạt khi rà code.

PostgreSQL thật kiểm bằng `PostgresSessionStore` và SQL/RLS của `ChatRepository`:
tạo tài khoản giả lập, gửi câu hỏi nhiều lượt, mở lại, tiếp tục, tạo phiên mới và
từ chối truy cập từ người khác. Kết thúc rollback và xác nhận tài khoản/phiên thử
không còn. Adapter kiểm thử dùng savepoint trong một giao dịch ngoài để bảo đảm
rollback; **không đo isolation level hoặc xử lý giao dịch đồng thời** ở ca này.

Truy xuất nội dung được thay bằng kho rỗng có ghi scope; đồ thị được thay bằng
trạng thái không sẵn sàng. Planner/router/service vẫn chạy code thật; predictor
router dùng stub, không nạp BGE-M3. Vì vậy kết quả chứng minh việc truyền/lưu scope,
không chứng minh độ chính xác intent, nguồn tài chính, Neo4j thật hoặc câu trả lời AI.
API dùng ASGI TestClient, không phải thao tác trình duyệt. Không gọi Gemini.

## Chạy lại

Từ thư mục gốc dự án, với môi trường Python đã cài:

```powershell
$env:PYTHONPATH='backend'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& backend/.venv/Scripts/python.exe -X utf8 -m pytest `
  backend/tests/test_s5_wbs091_context.py -q -p no:cacheprovider
```

Mặc định ca DB thật bị skip. Có tunnel PostgreSQL và `backend/.env` cấu hình đúng,
bật ca DB rồi chạy lại lệnh trên:

```powershell
$env:RUN_S5_WBS091_DB_SMOKE='1'
```

Danh sách suite và thống kê từng ca của bộ kiểm cuối lưu tại
[`verification.json`](../../outputs/s5_wbs091_20261116/verification.json).
Muốn chạy full: thay đường dẫn test bằng `backend/tests`; cần DB thử riêng ở
15434 và fixture WBS02 tương ứng để đánh giá các phần đó.

Reviewer nên kiểm ranh giới đổi chủ đề, dữ kiện mới ưu tiên dữ kiện cũ, câu hỏi
làm rõ khi nhiều công ty/năm và câu truy xuất BCTN đã thay đúng tên công ty.
Việc nghiệm thu toàn luồng Web Chat vẫn cần bản tích hợp và kiểm trình duyệt.
