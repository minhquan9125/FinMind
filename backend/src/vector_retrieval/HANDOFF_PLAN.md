# Bàn giao cho model tiếp theo — vector_retrieval

## Chỉ thị mới nhất của người dùng

> “checkpoint và soạn lại plan để t kêu model khác nào vì bạn sắp hết token r, model đó tự chạy tự sửa ko gọi ecc worker”

**Model tiếp theo tự đọc, lập luận, sửa, chạy test và review. Không gọi ECC worker, OmniRoute inference hoặc sub-agent.** Đây là yêu cầu trực tiếp mới nhất, thay cho mặc định gọi worker trong AGENTS.md ở lần tiếp tục này. Chỉ đọc các receipt ECC cũ khi cần bằng chứng; không khởi động lại các workflow đã hoàn thành, không reset bộ đếm hoặc gọi worker để review.

Chỉ sửa mã sản phẩm trong `backend/src/vector_retrieval`. Được đọc dependency liên quan để hiểu giao diện; không sửa frontend, API cũ, B1, OHLCV hoặc các module khác. Supabase **chỉ đọc**; không migration, ingest, sửa nguồn, đổi trạng thái index, đăng ký corpus hoặc nhúng lại vector. Không git add/commit/push. Không gọi Gemini hoặc gửi dữ liệu tài chính lên API embedding. Không in `.env`, DSN, token hoặc key.

## Đã làm xong — không làm lại

| Hạng mục | Bằng chứng |
| --- | --- |
| HNSW/dense + BM25 + RRF, CLI build/search | `backend.py`, `ranking.py`, `hoi.py` |
| Đọc đúng snapshot gốc thay nguồn đã thay đổi | `sources.py`, caller pin + kiểm tra hash/locator/vị trí từng row |
| Đọc metadata theo keyset 500 dòng để tránh ngắt kết nối | `backend.py`; đủ 15.058 chunk qua 31 trang trong 13,16 giây ở lượt candidate |
| CLI tích hợp chạy thật | Build exit 0; search Q01 exit 0, 5 hit có provenance/hash hợp lệ |
| Kiểm thử offline | **76 test đạt** sau tích hợp |
| Model embedding | Đã tải đủ và kiểm tra hash; **không tải lại** |
| Golden trên Supabase thật | 18 câu đủ nguồn × 4 biến thể = **72 lượt truy vấn không lỗi**, 36 ca sai mã/kỳ trả rỗng; 357 lượt hit khớp hash |

Kết quả hiện tại **chưa phải 18 câu trả lời tài chính đúng** hoặc 40/40 đạt. Module trả đoạn bằng chứng; không sinh đáp án cuối. Bộ Golden v6 chưa có gold được duyệt nên chưa công bố Recall/MRR.

Đọc theo thứ tự, không tải toàn bộ lịch sử chat:

1. File này.
2. `reports/golden40-snapshot-supabase-20261022.md` — kết quả và điểm còn yếu.
3. `README.md` — cách chạy hiện tại.
4. `backend.py`, `ranking.py`, `sources.py`, `hoi.py` và các test liên quan tới phần định sửa.
5. `.work/FINAL_GOLDEN_CHECKPOINT.md` nếu cần receipt/hash/lịch sử quyết định. Không mặc định xem checkpoint pause cũ là trạng thái hiện tại.

## Dữ liệu và cấu hình phải giữ

- Workspace: `D:\Win\Capstone 1\FinMind`.
- Python: `backend\.venv\Scripts\python.exe`; dependency đã có.
- Index: `434ef5e0-6516-578d-8d18-721d21347e01`, lần kiểm tra cuối **ACTIVE**, 15.058 chunk. Trước đây BUILDING; không sửa DB để khớp ghi chú cũ.
- Snapshot: `backend/.tmp/corpus-v2.content.manifest.json`, 675 tài liệu/15.058 chunk; canonical payload SHA-256 `86e880eef3b39ddf2515951252025a8f58e700f80416ba24d6fabfe324362bd7`.
- Snapshot có envelope `{manifest_sha256, manifest: {schema_version, documents: [{chunks: [...]}], ...}}`; **không** có danh sách chunks phẳng ở root. Source ID nằm trong `locator.reconstruction.source_chunk_id`, khác UUID chunk/document lưu ở DB.
- Model: `BAAI/bge-m3`, revision `5617a9f61b028005a4858fdac845db406aefb181`, cache `backend/src/vector_retrieval/.cache/huggingface`.
- Weights: 2.271.145.830 byte, SHA-256 chính thức `b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38`. `.work/embedding-download.json` ghi đã xác minh. Không cần OmniRoute để chạy model embedding này.
- Cache BM25: `.cache/<indexUUID>.json`, TTL 60 phút. Hết hạn thì build lại từ đúng snapshot; không sửa timestamp/checksum để bỏ qua hạn.
- Golden: `Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md`; SHA-256 lúc chạy `403b9d49eed3192ae2a2212a1b5469ac019ee37771fb95cb51a2efbefac3a65b`.

Nguồn hiện tại đã đổi tên FPT từ `CTCP FPT` thành `Công ty Cổ phần FPT`, làm đổi header/fingerprint tài chính. Vì vậy bài test dùng **vector thật trên Supabase + nội dung snapshot gốc khớp hash**, không giả là dữ liệu nguồn mới nhất. Phải giữ `FROZEN_SNAPSHOT` và manifest hash trong kết quả; không tự fallback giữa hai chế độ nguồn.

## Plan tiếp tục theo thứ tự

### Bước 1 — Xác nhận trạng thái nhanh

- Kiểm tra git status và các file sắp sửa; giữ nguyên thay đổi sẵn có của người dùng. `backend/src/retrieval_orchestration/chat_history/web/` đã untracked từ trước, không thuộc task.
- Kiểm tra file snapshot/model có sẵn. Nếu Supabase/index/nguồn đã đổi thì ghi rõ, không tự chọn index khác hoặc sửa dữ liệu.
- Giữ báo cáo hiện tại làm baseline. Helper `.work/golden_snapshot_live.py` hiện ghi cố định vào báo cáo ngày 22/10; trước khi chạy phiên bản mới phải đổi đường dẫn output hoặc lưu baseline riêng để không ghi đè bằng chứng cũ.
- Không chạy lại toàn bộ test/model download khi chỉ đang đọc. Chạy test phù hợp sau thay đổi; chạy cả module trước bàn giao.

### Bước 2 — Xử lý độ chính xác của phạm vi nguồn và xếp hạng

Ba quan sát thật cần xem trước:

| Ca | Hiện tượng | Cần xác minh |
| --- | --- | --- |
| Q03 | Đề yêu cầu CafeF, top 1 lại là FireAnt về cùng sự kiện | Có đúng bài CafeF trong phạm vi không; thêm khả năng khóa nhà xuất bản nếu đủ metadata |
| Q08 | Đề nhắc 05/08/2026, top 1 ghi 06/08/2026 | Đối chiếu bài gốc/ngày trong snapshot và UTC/Asia/Ho_Chi_Minh; không đổi ngày cho vừa đáp án |
| Q31 | Hỏi tiền và tương đương tiền tại kỳ, top 1 là tiền đầu kỳ trong lưu chuyển tiền tệ | Phân biệt chỉ tiêu/số dư/thời điểm với dòng tiền, không lấy hit đầu làm đáp án mặc định |

Hướng triển khai đề xuất, model tự chọn chi tiết trong phạm vi folder:

1. Khảo sát metadata publisher/ngày/section/metric thực sự có trong snapshot và row DB. Chỉ truy vấn SELECT. Không giả định có `chunk_text`, cột publisher hoặc schema khác khi chưa đọc.
2. Thêm bộ lọc tùy chọn cho nguồn/ngày chính xác nếu có cơ sở, mặc định không truyền giữ hành vi cũ. Bộ lọc áp dụng **trước lấy ứng viên ở cả dense lẫn BM25**, không chỉ lọc cuối danh sách.
3. Metadata dùng lọc phải đúng phiên bản nội dung đang đọc. Không lấy publisher/ngày live đã thay đổi rồi gắn nhãn cho nội dung lịch sử không khớp. Nếu cần suy từ header snapshot, đọc renderer và quy định định dạng rõ ràng, có kiểm thử; không đoán từ câu trả lời mẫu.
4. Nếu thêm trường cache, nâng phiên bản/validator và fingerprint tương ứng; cache cũ phải bị yêu cầu build lại. Không làm mất kiểm tra index/model/TTL/hash hoặc tính nguyên tử khi build lỗi.
5. Cải thiện phân biệt chỉ tiêu và cơ sở kỳ bằng quy tắc tổng quát suy được từ câu hỏi/metadata. Không hardcode `Q01`…`Q40`, ID chunk đúng hoặc đáp án Golden vào code/query/filter.
6. Nếu đúng publisher/ngày/tài liệu không có trong index, trả rỗng hoặc lý do thiếu nguồn. Không thay bằng bài gần nghĩa rồi khẳng định đúng bài được hỏi.

Viết test hồi quy cho các nhóm lỗi trên trước hoặc cùng bản sửa. Kiểm tra default compatibility, lọc sai trả rỗng, không rò index/phạm vi, hash/source mismatch và cache lỗi giữ file cũ. Tự chạy và tự review diff; **không gọi worker**.

### Bước 3 — Chạy lại 18 câu đủ nguồn

- Nguyên văn trường “Câu hỏi đã sửa” là query; bộ lọc chỉ suy từ chính câu hỏi. Không đưa “Cần lấy đủ”, đáp án tham khảo hoặc gold IDs vào đầu vào.
- Chạy có lọc / không lọc, top 5 và top 10, sai mã / sai kỳ; thêm sai publisher/ngày nếu vừa bổ sung chức năng.
- Giữ cùng snapshot/index/model khi so baseline; báo thay đổi dữ liệu nếu có. Kiểm tra hash nội dung và locator, không chỉ đếm hit.
- Đánh giá top-k có đủ từng ý cần trả lời; tách rõ “luồng chạy”, “bộ lọc đúng” và “đúng/đủ bằng chứng”. Chưa có gold duyệt thì chỉ kết luận tạm thời, không tự tạo Recall/MRR chính thức.
- Bản trước: median có lọc 1,97 giây; không lọc 2,18 giây; lượt đầu 35,32 giây gồm khởi tạo model. Biến thể không lọc tái sử dụng query vector nên không dùng hai số này làm so sánh thuật toán độc lập.

### Bước 4 — Giữ đúng phạm vi 22 ca chưa đủ điều kiện

- **9 câu PDF Q21–Q29:** đúng PDF FPT 2024 chưa nằm trong index. Có local reference PDF nhưng chưa được phép tự ingest/đổi corpus. Ghi thiếu nguồn, không thay bằng dữ liệu clean 2024. Chỉ lập bước nhập PDF riêng nếu user cho phép mở rộng DB write.
- **13 câu khác:** 9 phép tính, 2 tra phiên giá, 2 từ chối. Đây là tầng SQL/Decimal/answering riêng, không chấm như vector recall và không thêm toàn bộ engine mới chỉ để ghi “40/40”. Ghi rõ việc cần bàn giao nếu user muốn mở rộng.
- Không bật Gemini/B3 hoặc nối API/frontend trong task retrieval này khi chưa được giao thêm.

### Bước 5 — Bàn giao

- Chạy test phù hợp, full module regression và một lượt CLI thật.
- Ghi báo cáo tiếng Việt có trường hợp thành công/thất bại, top-k/locator/hash, độ trễ và các hạn chế còn lại.
- Cập nhật checkpoint trong module; liệt kê đúng file đã sửa và lệnh chạy. Không commit/push thay user.

## Lệnh đã được kiểm chứng

Từ gốc FinMind, PowerShell:

```powershell
$env:HF_HUB_CACHE = "$PWD/backend/src/vector_retrieval/.cache/huggingface"
$indexId = '434ef5e0-6516-578d-8d18-721d21347e01'
$snapshotPath = 'backend/.tmp/corpus-v2.content.manifest.json'
$manifestPin = '86e880eef3b39ddf2515951252025a8f58e700f80416ba24d6fabfe324362bd7'

backend\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s backend/src/vector_retrieval/tests -b
backend\.venv\Scripts\python.exe -B -X utf8 backend/src/vector_retrieval/hoi.py build --index $indexId --source-snapshot $snapshotPath --snapshot-sha256 $manifestPin
backend\.venv\Scripts\python.exe -B -X utf8 backend/src/vector_retrieval/hoi.py search --index $indexId --source-snapshot $snapshotPath --snapshot-sha256 $manifestPin
```

Lệnh search cuối mở phiên nhập liên tục; `exit` để thoát. `--question "..." --json` để thử một câu. `--company`, `--period`, `--doc-type` là bộ lọc hiện có. Model offline mặc định; không cần bật `--allow-model-download` khi cache đã sẵn.

Nếu sandbox Windows chặn fixture tạm, xử lý đúng quyền chạy test; không sửa test thành bỏ kiểm tra hoặc coi PermissionError là pass.

## Prompt chuyển model có thể dán nguyên văn

> Đọc `backend/src/vector_retrieval/HANDOFF_PLAN.md`, báo cáo Golden sau sửa và checkpoint cuối. Tiếp tục theo plan từ bước khảo sát chất lượng phạm vi nguồn/xếp hạng; phần snapshot, paging, model và baseline đã xong. Bạn tự sửa, tự chạy test và tự review, **không gọi ECC/OmniRoute worker hoặc sub-agent**. Chỉ sửa trong `backend/src/vector_retrieval`; Supabase chỉ đọc; không gọi Gemini, không tải lại model, không commit/push. Giữ báo cáo baseline, không hardcode đáp án/ID Golden, không tuyên bố 40/40 khi còn thiếu PDF và tầng tính toán/từ chối. Tiến hành việc đã đủ thông tin, ghi rõ blocker thật và cập nhật checkpoint khi dừng.
