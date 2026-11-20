# Truy xuất HNSW + BM25 tại backend

Module trong `backend/src/vector_retrieval`. HNSW tìm theo ý nghĩa trên Supabase; BM25 tìm từ khóa trong cache backend; RRF hợp nhất hai danh sách theo `chunk_id`. Nguồn và hash được kiểm tra trước khi trả đoạn bằng chứng. Từ 23/10/2026, web `/research` dùng bộ chuyển corpus-bound của module này; CLI theo index bên dưới vẫn hoạt động độc lập. Xem [hợp đồng web LIVE](../retrieval_orchestration/notes/LIVE_CHAT_CONTRACT.md).

## Chuẩn bị

Dùng Python của backend có dependency dự án đã cài, cấu hình `DATABASE_URL` như hướng dẫn ở README gốc. Module không tự cài thư viện hoặc đổi schema. Model `BAAI/bge-m3` phải có sẵn trong cache máy khi tìm kiếm; mặc định chặn tải model. Nếu chủ động muốn tải, thêm `--allow-model-download` cho lần chạy đó. Build cache chỉ đọc nguồn, không nhúng lại vector và không gọi Gemini.

## Chạy từ gốc FinMind

Index v2 có 15.058 vector, UUID `434ef5e0-6516-578d-8d18-721d21347e01`. Lượt kiểm tra mới nhất ngày 22/10/2026 quan sát trạng thái `ACTIVE`; chỉ cần `--allow-building` khi index thực tế còn `BUILDING`. Module không tự đổi trạng thái hoặc đăng ký corpus.

Các lệnh bên dưới đọc **nguồn hiện tại**. Với bộ Golden/corpus-v2 đã thử, dùng mục **Đọc đúng snapshot đã tạo vector** vì nguồn hiện tại đã thay đổi so với bản tạo vector. Cờ `--allow-building` trong ví dụ vẫn dùng được với index ACTIVE.

Dựng cache một lần:

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend/src/vector_retrieval/hoi.py build --index 434ef5e0-6516-578d-8d18-721d21347e01 --allow-building
```

Nhập câu hỏi liên tục sau khi build thành công:

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend/src/vector_retrieval/hoi.py search --index 434ef5e0-6516-578d-8d18-721d21347e01 --allow-building
```

Gõ `exit` để thoát. Mỗi câu là một truy vấn độc lập, không dùng bộ nhớ hội thoại. Để chạy một câu và xem JSON:

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend/src/vector_retrieval/hoi.py search --index 434ef5e0-6516-578d-8d18-721d21347e01 --allow-building --question "Tổng tài sản FPT quý 2/2026" --company FPT --period 2026-Q2 --doc-type FINANCIAL_STATEMENT --json
```

Lọc tin tức theo nhà xuất bản và ngày (suy từ URL/ngày frozen, áp dụng trước khi lấy ứng viên ở cả hai nhánh):

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend/src/vector_retrieval/hoi.py search --index 434ef5e0-6516-578d-8d18-721d21347e01 --allow-building --source-snapshot backend/.tmp/corpus-v2.content.manifest.json --snapshot-sha256 86e880eef3b39ddf2515951252025a8f58e700f80416ba24d6fabfe324362bd7 --question "đợt tăng vốn FPT 171 triệu cổ phiếu" --company FPT --period 2026-09 --doc-type NEWS --publisher cafef --published-date 2026-09-29 --json
```

Có thể thay đường dẫn Python bằng `.venv\Scripts\python.exe` nếu máy dùng môi trường ở gốc FinMind. `--help` chỉ xem lệnh, không mở DB/tải model.

## Cache và kết quả

Cache nằm trong `vector_retrieval/.cache/<UUID>.json`, được bỏ qua khi commit. File chỉ giữ token, metadata, checksum và phiên bản index/tokenizer; không lưu nguyên đoạn văn, vector hoặc thông tin kết nối. Cache v2 có TTL 60 phút; cache v1 cũ bị `CACHE_VERSION_MISMATCH` và yêu cầu `build` lại. Index thay đổi hoặc cache hết hạn thì chạy lại `build`. Phiên nhập câu hỏi dùng lại cùng pool/model/BM25 index.

Bước build đọc metadata theo keyset tối đa 500 dòng/lượt, vẫn trong cùng transaction chỉ đọc. Chỉ ghi file cache sau khi đọc đủ và xác minh toàn bộ nguồn; lỗi giữa chừng giữ nguyên cache cũ. Không dùng OFFSET hoặc ghi cache thiếu chunk để tránh lỗi kết nối.

Hai nhánh dùng cùng phạm vi trước khi lấy ứng viên: công ty/kỳ/loại tài liệu + nhà xuất bản/ngày. Mặc định mỗi nhánh tối đa 50 ứng viên, trả 5 kết quả; `--top-k` từ 1–20 và `--candidates` tối đa 200. Bộ lọc hiện nhận một mã và một kỳ; `--publisher` chỉ `cafef|fireant` (suy từ URL frozen `cafef.vn`/`fireant.vn`), `--published-date` là `YYYY-MM-DD` (suy từ `locator.published_at` frozen), cả hai chỉ áp dụng cho NEWS và áp dụng trước top-k. Kỳ nhận `YYYY`, `YYYY-MM`, `YYYY-Q1..Q4`, `YYYY-MM-DD` và khớp tiền tố có ranh giới; không tự chuyển quý thành ngày hay đoán kỳ. Tách từ dùng chuẩn hóa Unicode và bỏ dấu nhất quán, chưa phải bộ tách từ chuyên sâu tiếng Việt.

Kết quả giữ điểm/thứ hạng riêng của HNSW, BM25 và điểm RRF, kèm chunk, document, locator, hash và nội dung. `scope` trả thêm `publisher`/`published_date`; `scope_mode=INDEX` thể hiện phạm vi index; không được coi đó là chứng nhận membership corpus đóng băng. Kết quả là đoạn truy xuất, chưa phải câu trả lời của Gemini.

## Lỗi cần xử lý

| Mã | Ý nghĩa |
| --- | --- |
| `CACHE_BUILD_REQUIRED` | Chạy `build` trước |
| `CACHE_EXPIRED` / `CACHE_STALE` / `CACHE_VERSION_MISMATCH` | Cache hết hạn, metadata đổi hoặc phiên bản không tương thích; cần build lại |
| `SOURCE_CHANGED` | Nguồn hiện tại khác bản dùng tạo vector; cần đồng bộ phiên bản nguồn/vector |
| `HASH_MISMATCH` | Nội dung dựng từ nguồn không khớp hash đã lưu |
| `INDEX_NOT_ACTIVE` | Index chưa ACTIVE, chỉ BUILDING mới được phép bằng cờ tường minh |
| `MODEL_MISMATCH` | Model/revision không khớp vector đã lưu |
| `INVALID_PUBLISHER` / `INVALID_PUBLISHED_DATE` | `--publisher` hoặc `--published-date` không hợp lệ |

Nguồn hiện tại có thể khác nguồn đã tạo vector. Ví dụ, tên FPT trong snapshot là `CTCP FPT`, còn bảng doanh nghiệp hiện tại ghi `Công ty Cổ phần FPT`; tên dùng trong header tài chính cũng đổi. Khi đọc nguồn hiện tại gặp `SOURCE_CHANGED`, build dừng và giữ cache cũ. Không xóa hash hoặc tự bỏ chunk để làm cho build thành công.

## Đọc đúng snapshot đã tạo vector

`sources.py` hỗ trợ nguồn lịch sử tường minh. Cần có file `backend/.tmp/corpus-v2.content.manifest.json` và pin SHA-256 payload đã chốt bên dưới. File snapshot và model cache không tự có khi clone Git; cần bàn giao snapshot đúng hash riêng. Không tự coi snapshot là corpus đã đăng ký trên database.

```powershell
$snapshot = 'backend/.tmp/corpus-v2.content.manifest.json'
$pin = '86e880eef3b39ddf2515951252025a8f58e700f80416ba24d6fabfe324362bd7'
$env:HF_HUB_CACHE = "$PWD/backend/src/vector_retrieval/.cache/huggingface"
backend\.venv\Scripts\python.exe -X utf8 backend/src/vector_retrieval/hoi.py build --index 434ef5e0-6516-578d-8d18-721d21347e01 --allow-building --source-snapshot $snapshot --snapshot-sha256 $pin
backend\.venv\Scripts\python.exe -X utf8 backend/src/vector_retrieval/hoi.py search --index 434ef5e0-6516-578d-8d18-721d21347e01 --allow-building --source-snapshot $snapshot --snapshot-sha256 $pin
```

Đây là truy vấn vector thật trên Supabase với nội dung gốc đã đóng băng, không phải số liệu mới nhất đọc từ các bảng nguồn. Kết quả JSON/human ghi rõ `source_provenance.mode=FROZEN_SNAPSHOT` và manifest hash, kể cả khi không có kết quả. Không truyền hai cờ snapshot thì vẫn đọc nguồn hiện tại như trước.

Resolver kiểm tra hash payload theo pin từ người gọi, số lượng tài liệu/chunk, trùng ID và hash nội dung; từng row Supabase tiếp tục phải khớp `content_hash`, `chunk_index` và locator đầy đủ. Dùng `source_chunk_id` trong locator để nối snapshot, giữ nguyên `chunk_id`/`document_id` thật của DB. Không sửa Supabase, không nhúng lại vector, không tự chuyển sang snapshot khi nguồn hiện tại lỗi. Thiếu một cờ hoặc manifest không hợp lệ bị từ chối trước khi mở DB/model.

Nếu dùng model cache cục bộ của lần kiểm thử này, đặt biến môi trường trước lệnh `search`:

```powershell
$env:HF_HUB_CACHE = "$PWD/backend/src/vector_retrieval/.cache/huggingface"
```

Cache BM25 vẫn chỉ chứa token/metadata; mỗi lần search đối chiếu nội dung bằng resolver đã chọn. Cache được dựng từ snapshot không tự làm chế độ đọc nguồn hiện tại chấp nhận nguồn đã thay đổi.

Kiểm tra ban đầu và nguyên nhân chặn: [báo cáo Golden trước sửa](reports/golden40-supabase-20261022.md). Không dùng số kiểm thử offline để tuyên bố đạt Golden hoặc có câu trả lời tài chính chính xác; PDF FPT 2024, tra giá, phép tính và từ chối cần nguồn/tầng xử lý tương ứng.

## Kết quả chạy thật sau sửa

Baseline: [Báo cáo Golden sau sửa](reports/golden40-snapshot-supabase-20261022.md) và [JSON chi tiết](reports/golden40-snapshot-supabase-20261022.json) (22/10/2026): 18 câu đủ nguồn chạy 72 lượt truy vấn, 36 ca sai mã/kỳ trả rỗng, 357 lượt hit khớp hash. Còn 9 câu thiếu PDF trong index và 13 câu ngoài tầng retrieval. Chưa có gold duyệt nên không công bố Recall/MRR hoặc điểm đúng câu trả lời; báo cáo ghi cả các hit đầu chưa khớp nhà xuất bản/ngày/chỉ tiêu.

Từ phiên này (cache v2): thêm `--publisher`/`--published-date` suy từ snapshot frozen (URL/published_at), áp dụng trước khi lấy ứng viên ở cả hai nhánh, mặc định không truyền giữ hành vi cũ. Cache v1 trước đó bị `CACHE_VERSION_MISMATCH` và yêu cầu dựng lại. Chưa chạy lại full Golden với filter mới trong phiên này; sẽ chạy lại sau khi build cache v2 trên Supabase thật.

Model đúng revision đã tải và xác minh hash trong `.cache/huggingface` ở máy này. Toàn bộ 76 kiểm thử offline của module đạt. Model/snapshot/cache không tự được bàn giao qua Git.

## Kiểm thử offline

```powershell
backend\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s backend/src/vector_retrieval/tests -b
```

Tests offline dùng DB/model giả lập ở ranh giới để kiểm tra thuật toán, cache, nguồn/hash, bộ lọc và CLI. Lượt Golden sau sửa phía trên dùng embedding câu hỏi thật và Supabase thật; lượt EXPLAIN riêng dùng vector đã lưu để chẩn đoán planner, không dùng làm điểm ngữ nghĩa. Chưa thêm cross-encoder.
