# Trả lời B1 với retrieval và Gemini

Module riêng cho WBS21, WBS26 và WBS31. Đã triển khai hàm Python và CLI; frontend/API chat hiện tại chưa tự chuyển sang module này.

## Cấu trúc package

Các file được chia theo trách nhiệm để dễ tìm và mở rộng:

```text
b1_answering/
├── application/   # luồng hội thoại và dịch vụ trả lời
├── cli/           # giao diện dòng lệnh
├── config/        # limits.json
├── core/          # policy và quản lý ngân sách
├── docs/          # contract và yêu cầu tích hợp
├── evidence/      # prompt và ràng buộc trích dẫn
├── providers/     # kết nối Gemini
├── tests/         # kiểm thử offline
├── tools/         # công cụ migration package
├── __main__.py    # python -m src.b1_answering
└── hoi.py         # lệnh cũ được giữ tương thích
```

Lệnh `hoi.py` hiện tại vẫn chạy như trước. Có thể chạy CLI qua module bằng `python -m src.b1_answering --example --json`. Import mới nên dùng `src.b1_answering.application.service`, `src.b1_answering.application.dialogue`, `src.b1_answering.core.policy`, `src.b1_answering.evidence.citations` và `src.b1_answering.providers.gemini`. Các import cũ như `src.b1_answering.service` và `src.b1_answering.policy` vẫn được giữ làm bí danh tương thích.

## Chạy thử từ thư mục FinMind

```powershell
python -X utf8 backend/src/b1_answering/hoi.py
```

Nhập câu hỏi liên tục, trả lời bổ sung mã/kỳ/chỉ tiêu khi được hỏi. `/moi` bắt đầu hội thoại mới, `exit` thoát. Bộ nhớ hội thoại dùng `DialogueSession` bao quanh `ChatSession` hiện có; ngân sách giữ suốt tiến trình, kể cả sau `/moi`. CLI này giữ phiên trong RAM; chức năng lịch sử JSON của CLI/API chat cũ vẫn ở module cũ.

Ví dụ có sẵn trong retrieval fixture: **Tổng tài sản BID tại 30/06/2026 là bao nhiêu?** Câu ngoài dữ liệu mẫu có thể hỏi lại hoặc báo không có bằng chứng; không tự cào hay tạo số liệu.

Ví dụ minh họa có giá trị hoàn toàn giả lập, chạy một lần rồi thoát:

```powershell
python -X utf8 backend/src/b1_answering/hoi.py --example
```

Gọi Gemini trên project Free Tier đã xác nhận:

```powershell
python -X utf8 backend/src/b1_answering/hoi.py --live
```

Key lấy từ biến môi trường `GEMINI_API_KEY`. Nếu chưa có và đang chạy terminal tương tác, chương trình yêu cầu nhập ẩn, chỉ giữ key trong RAM. Không ghi key vào file, trace hoặc log. `--live` dùng xác nhận Free Tier của dự án này; không tự kiểm tra hay thay đổi billing của Google. Hết quota thì trả lỗi, không retry hoặc đổi model tự động. Retrieval của chế độ này **vẫn là fixture**, còn bước sinh nháp gọi Gemini thật.

Nếu `python` đang thiếu `httpx`, dùng Python trong môi trường backend hiện có:

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend/src/b1_answering/hoi.py
```

Thêm `--question "câu hỏi"` để hỏi một câu rồi thoát; thêm `--json` để xem envelope, manifest, trace và ngân sách. Với chế độ một câu hoặc `--example`, stdout của `--json` là một JSON object, banner gửi sang stderr.

## Hiểu câu bổ sung theo ngữ cảnh

CLI dùng `dialogue.DialogueSession`: khi đang hỏi trước/sau thuế, có thể trả lời `sau`, `SAU NHÉ`, `chọn sau`, `trước`, `truoc` hoặc `trc`. Mã và kỳ đã cung cấp được giữ trong lúc bổ sung; từ ngắn không có ngữ cảnh sẽ được hỏi rõ thay vì đoán chỉ tiêu. Có hỗ trợ các alias như `TTS`, `LNST`, `LNTT` và cách viết liền `năm2025`.

Ví dụ: `lợi nhuận là bao nhiêu` → `CMG` → `sau` → `2025`. Nếu hỏi `nợ của FPT 2025 sau thuế`, hệ thống hỏi chọn nợ phải trả hay lợi nhuận sau thuế, giữ FPT/năm 2025 khi bạn chọn. Chỉ tiêu đã nhận diện nhưng chưa hỗ trợ như nợ, doanh thu, EPS, ROE, P/E, P/B được báo rõ; không tự tạo số liệu. Câu hỏi mới thay phạm vi cũ; `/moi` xóa ngữ cảnh; các phiên không dùng chung ngữ cảnh.

Đây là bộ phân tích xác định bằng quy tắc và alias, chưa phải hiểu mọi câu tiếng Việt tự do. Nhận diện câu hỏi không có nghĩa fixture có dữ liệu: SSI vẫn ngoài danh sách mã mẫu, và CMG/FPT đúng mã/kỳ vẫn có thể không có bằng chứng. Thay đổi này chỉ nối vào CLI B1, chưa thay luồng chat web/API.

## Cấu hình

Chỉnh [config/limits.json](config/limits.json). Các giá trị mặc định dành cho phát triển:

| Trường | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `version` | `b1-limits-v1` | Phiên bản cấu hình |
| `model` | `gemini-3.5-flash-lite` | Model được ghim trong phiên bản này |
| `max_input_tokens` | 16384 | Trần input, đếm cả system prompt và schema |
| `max_output_tokens` | 2048 | Gửi vào `maxOutputTokens` của Gemini |
| `read_timeout_seconds` | 600 | Timeout đọc; service dùng chung deadline cho đếm token và sinh nháp |
| `max_generation_calls` | 20 | Số lần sinh nháp tối đa trên một `Budget` |
| `max_total_tokens` | 65536 | Tổng token đã dùng hoặc còn đặt trước trên một `Budget` |
| `max_cost_usd` | 0 | Chỉ cho phép policy Free Tier của phiên bản này |

Đây không phải quota Google đã xác minh. Free Tier vẫn dùng token và có hạn mức. Policy dựa trên xác nhận Free Tier, không bảo đảm miễn phí nếu tài khoản/project bị chuyển sang billing có phí. Cấu hình sai, bool thay số, số không hữu hạn hoặc model ngoài phiên bản bị từ chối. Khi thay contract/model/prompt cần cập nhật phiên bản và kiểm thử tương ứng.

Trước sinh nháp, giữ ngân sách `input + max_output_tokens`. Usage hợp lệ mới hoàn phần chưa dùng; timeout, hủy hoặc thiếu usage giữ nguyên khoản đặt trước. Không coi lỗi là dùng 0 token. Ngân sách theo instance/tiến trình, chưa có kho dùng chung nhiều server hoặc hạn mức theo tài khoản. Hàm không truyền `budget` sẽ tạo ngân sách riêng cho lần gọi; bên tích hợp cần dùng chung instance để áp trần nhiều lượt.

## Hàm chính và luồng

```python
from src.b1_answering.hoi import FixtureProvider
from src.b1_answering.policy import Budget, Limits
from src.b1_answering.service import answer_question

limits = Limits.load()
budget = Budget(limits)
result = await answer_question(
    "Tổng tài sản BID tại 30/06/2026?", "demo-session",
    provider=FixtureProvider(limits), limits=limits, budget=budget,
)
print(result["answering"])
```

Import từ backend hoặc cấu hình `PYTHONPATH=backend`. `complete_retrieval(question, result, provider=..., limits=..., budget=...)` nhận trực tiếp envelope của retrieval, phù hợp khi bên gọi đã có `ChatSession`. Dùng `GeminiProvider` thay `FixtureProvider` cho Gemini thật; adapter yêu cầu key và xác nhận Free Tier rõ ràng.

Luồng: hiểu câu hỏi → retrieval cũ → nếu `EVIDENCE_READY`, chuẩn bị nguồn → đếm token → giữ ngân sách → sinh nháp → ghi usage → ràng buộc claim/citation. Các nhánh hỏi lại, ngoài phạm vi, không có dữ liệu hoặc lỗi retrieval không gọi Gemini.

Envelope cũ được giữ, thêm `answering` gồm `status`, `reason_code`, `message`, `draft`, `claims`, `citations`, `manifest`, `trace`, `budget`. Manifest ghi phiên bản config/prompt, model yêu cầu/model thực trả về, giới hạn, chế độ retrieval và thành phần bật/tắt. B3 Evidence Gate, B3 Answer Verification và tools đều tắt.

## Trích dẫn và giới hạn

Adapter đọc được phần `text` có metadata `thoughtSignature`, ghép các phần trả lời bị chia nhỏ và bỏ qua phần có `thought: true`. Chữ ký và nội dung suy nghĩ không được đưa vào đáp án hay log. Trường nội dung không hỗ trợ và kiểu dữ liệu sai vẫn bị từ chối.

Khi kiểm thử `--live --json`, xem `answering.reason_code`: `GEMINI_BLOCKED` là phản hồi bị chặn; `GEMINI_EMPTY_RESPONSE` là không có phần trả lời; `INVALID_GEMINI_JSON` là phần trả lời không phải JSON object hợp lệ; `INVALID_GEMINI_RESPONSE` là cấu trúc phản hồi sai. Không tự gọi lại khi lỗi. Nếu chưa đọc được usage, ngân sách vẫn giữ khoản dự phòng; `tokens_reserved` không phải số token thực tế đã dùng.

V1 dùng **trích nguyên văn**: nội dung mỗi claim phải xuất hiện trong mọi đoạn được claim đó trích. Claim không có ID, ID lạ hoặc số liệu/diễn giải ngoài nguồn bị chặn. Đây là kiểm tra ràng buộc trích đoạn, chưa phải kiểm chứng đầy đủ ý nghĩa hay tính đúng đắn của nguồn.

`citations.resolve_citation(evidence_id, evidence)` trả bản sao đoạn nguồn cùng locator; mã nguồn, chunk, hash và vị trí được giữ nguyên. Fixture chỉ có trang/bảng nội bộ; chưa tạo link PDF thật. Nguồn thiếu, trùng ID, locator sai hoặc pack khai báo mâu thuẫn không được sinh đáp án. Việc phát hiện nguồn mâu thuẫn/sai scope thuộc contract của retrieval; module không tự phân xử hai tài liệu thật.

Chờ Nhân bàn giao retrieval có lọc và Vũ bàn giao locator tương thích để tích hợp nguồn thật và kiểm tra link mở được. Chưa nối giao diện hiện có trong bước này, chưa gọi Gemini live khi nghiệm thu offline.

## Kiểm thử

```powershell
backend\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s backend/src/b1_answering/tests -b
```

Sau khi sắp xếp package, 131 kiểm thử offline pass và 2 kiểm thử bỏ qua do quyền tạo symlink trên Windows. Bộ kiểm thử bao gồm HTTP giả lập, metadata/chữ ký, schema, ID/locator, claim ngoài nguồn, timeout/cancel, quota/budget, CLI, migration package và launcher. Bộ hồi quy retrieval/hội thoại cũ có 125 kiểm thử pass. Kết quả offline không thay thế kiểm tra quyền key, quota, model thực tế hoặc chất lượng retrieval thật.

Tài liệu Google đã đối chiếu: [model](https://ai.google.dev/gemini-api/docs/models), [GenerateContent](https://ai.google.dev/api/generate-content), [CountTokens](https://ai.google.dev/api/tokens), [giá/Free Tier](https://ai.google.dev/gemini-api/docs/pricing).
