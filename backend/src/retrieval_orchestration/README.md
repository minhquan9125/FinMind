# Luồng truy xuất bằng fixture và xử lý câu hỏi mơ hồ

Module thử nghiệm độc lập bằng Python3.11+ và thư viện chuẩn. Không cần API key,
vector, DB hoặc giao diện. Chỉ xử lý fixture cố định, chưa tạo đáp án tài chính.
Chưa nối module vào API backend đang chạy.

Từ thư mục gốc dự án, chạy hỏi đáp tương tác:

```powershell
python -X utf8 backend/src/retrieval_orchestration/hoi.py
```

Trong folder này có thể chạy ngắn hơn: `python -X utf8 hoi.py`.
Gõ câu hỏi rồi Enter để xem phản hồi tiếng Việt; gõ `exit` để thoát.
`/moi` xóa ngữ cảnh; `/json` xem JSON kỹ thuật của kết quả gần nhất.

Các lệnh để tiếp tục phiên cũ:

| Lệnh | Chức năng |
| --- | --- |
| `/lichsu` | Liệt kê các file lịch sử hợp lệ, mới nhất trước. |
| `/mo 1` | Mở phiên số 1 trong danh sách và khôi phục câu hỏi đang dở. |
| `/mo ten_file.json` | Mở file trong folder `chat_history`. |
| `/tomtat` | Xem mã, kỳ, chỉ tiêu đang được theo dõi và thông tin còn thiếu. |
| `/help` | Xem tất cả lệnh. |

Ví dụ: `lợi nhuận năm 2025` → `BID, sau thuế` → `không, là VCB` →
`ý tôi là năm 2024`. Có thể bổ sung nhiều thông tin trong một câu như
`VCB năm 2024` hoặc `sau thuế quý 2/2026`. Nếu nêu nhiều lựa chọn mâu thuẫn,
hệ thống hỏi lại thay vì chọn đại. `năm ngoái`, `quý này`, `quý trước` dùng ngày
của phiên và xử lý chuyển năm khi cần.

Phiên ghi nhớ thông tin bổ sung cho câu hỏi chỉ tiêu: ví dụ `lợi nhuận năm 2025`
→ `BID` → `sau thuế`. Có thể thay thông tin bằng `đổi sang VCB`, `năm 2024`,
`quý 2/2026`; `chủ đề trước` nhắc lại câu đang hỏi trong cùng phiên. Câu hỏi mới
đầy đủ được phân tích lại; không tự mượn kỳ còn thiếu của câu trước. Khi đổi phạm vi
so sánh/xu hướng/BCTN bằng câu rút gọn, hệ thống yêu cầu nhập lại đầy đủ để tránh ghép sai.
`năm nay` được giải theo ngày của phiên ở UTC+07 và hiển thị kỳ đã hiểu.
Ngữ cảnh hoạt động chỉ tồn tại trong lần chạy terminal. Khi thoát bằng `exit`, EOF
hoặc Ctrl+C, lịch sử được lưu UTF-8 vào `chat_history/session_<thời-gian>_<uuid>.json`
cạnh file `hoi.py`. Mỗi lần chạy có file riêng, gồm mã phiên, thời gian và toàn bộ
lượt hỏi/phản hồi cùng kết quả JSON kỹ thuật. Terminal in đường dẫn sau khi lưu.
`/moi` xóa ngữ cảnh nhưng vẫn giữ các lượt trước đó trong lịch sử của lần chạy.
Phiên chưa có lượt chat không tạo file. Khi chạy lại, gõ `/lichsu` rồi `/mo 1`
để tiếp tục. Chương trình phân tích lại các câu người dùng đã lưu; không dùng kết quả
hay số liệu trong phản hồi cũ làm bằng chứng. Ngày tương đối của lượt cũ giữ theo ngày
cũ, câu hỏi mới dùng ngày hiện tại. Lịch sử phiên tiếp tục được lưu thành file con riêng,
có `resumed_from`, `parent_session_id`, `continued_at`; file gốc không bị ghi đè.
Mở phiên rồi thoát mà chưa chat thêm không tạo bản sao. Nếu chuyển phiên khi đang chat
dở, chương trình lưu phần đang dở trước; khi lưu lỗi thì giữ nguyên phiên hiện tại.
Các file bị lỗi cấu trúc hoặc vượt giới hạn đọc được báo lỗi/bỏ qua, không làm mất
ngữ cảnh đang dùng. Ngữ cảnh không tự nạp khi vừa khởi động nếu chưa chọn `/mo`.

Phạm vi fixture theo đặc tả gồm VCB, BID, CTG, MBB, TCB, FPT, CMG, ELC, ITD, ICT.
SSI/ssi/SSi được báo ngoài phạm vi, không bị hiểu là thiếu công ty. Việc cập nhật
thông tin người dùng nhập không phải cào dữ liệu tài chính thật; dữ liệu vẫn là fixture.

Từ thư mục dự án chạy:

```powershell
cd backend/src/retrieval_orchestration
python -B -m unittest discover -s tests -v
```

Ví dụ tương tác trong Python khi đang ở folder trên:

```python
import asyncio
from retrieval_flow.intent import analyze, clarify
from retrieval_flow.orchestrator import orchestrate

result = asyncio.run(orchestrate("Tổng tài sản BID tại 30/06/2026?", "demo"))
print(result["status"])  # EVIDENCE_READY, dữ liệu giả lập

pending = analyze("Lợi nhuận BID quý 2/2026?", "demo")
print(pending["clarification_question"])
completed = clarify(pending, "sau thuế", "demo")
print(completed["decision"], completed["scope"])

print(asyncio.run(orchestrate("Tổng tài sản BID năm 2024?", "demo"))["status"])  # NO_DATA

class SlowRetriever:
    async def retrieve(self, scope, query_id, index_version):
        await asyncio.sleep(1)

print(asyncio.run(orchestrate("Tổng tài sản BID tại 30/06/2026?", "demo",
    retriever=SlowRetriever(), timeout_seconds=0.01))["reason_code"])  # RETRIEVAL_TIMEOUT
```

Luồng: B1 hiểu câu hỏi → chỉ SEARCH mới gọi retriever → kiểm tra schema, query,
index và scope/provenance → EVIDENCE_READY. Hỏi lại/ngoài phạm vi/không hỗ trợ
không gọi retrieval. RESOLVE_REFERENCE chỉ đọc evidence đã lưu đúng phiên.
NO_DATA khác INVALID_EVIDENCE_PACK, INSUFFICIENT_EVIDENCE và SYSTEM_UNAVAILABLE.
Nhánh lỗi không cung cấp evidence pack hoặc đáp án số. Timeout chỉ dùng adapter
async hợp tác với cancellation; kết quả trả muộn không trở thành thành công.

Package gồm contracts.py, fixtures.json, intent.py và orchestrator.py. Dữ liệu và
hash đều giả lập; không dùng như nguồn thật. B1 là grammar xác định cho các mẫu
tiếng Việt/Anh được liệt kê trong intent.py, không hiểu mọi cách diễn đạt và chưa
chứng minh toàn bộ48ca đặc tả. News tắt; một số cách hỏi ngoài grammar sẽ hỏi rõ.
Các trạng thái downstream là hợp đồng thử nghiệm, cần team chốt trước nối API.

Fixture kiểm tra luồng, parser/gate, phiên dữ liệu, isolation và lỗi; không chứng
minh độ chính xác vector, coverage nguồn thật, quyền nguồn hay citation thật.
Sau này thay retriever/reference adapter và chạy lại contract/integration tests.
