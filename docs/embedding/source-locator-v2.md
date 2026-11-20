# Locator v2 và bộ dựng nội dung từ nguồn Supabase

## Trạng thái hiện tại: đã bỏ cột chunk_text ngày 19/10/2026

Các mục phía dưới là nhật ký các giai đoạn trước. Migration
`20261019000100_drop_chunk_text.sql` đã được áp dụng: bảng `text_chunks`
không còn cột `chunk_text`. Vector, ID, hash, locator và liên kết được giữ nguyên.
Người dùng đã chấp nhận mất khả năng đọc lại text của ba chunk hồ sơ công ty
superseded thuộc corpus-v1; không tạo bản sao nguồn lịch sử cho chúng.

- 2.048 chunk hiện hành được dựng lại và so chính xác với text cũ trước khi xóa cột.
- Fingerprint của mọi trường còn lại trong 2.051 bản ghi không đổi sau migration.
- Mẫu đọc nguồn COMPANY_PROFILE, NEWS, PRICE_HISTORY và MARKET_INDEX thành công sau khi bỏ cột.
- Upload mới lưu bản nguồn PDF/JSON trong bảng `raw_payloads` đã có trong ERD
  (`upload-source-v1`, bytes gốc mã hóa base64), không lưu text từng chunk.
  Locator trỏ payload và cấu hình chunk; bộ đọc kiểm tra hash nguồn và hash chunk.
- Không có upload word-window-v1 cũ trong DB khi áp dụng. Migration chặn chunk
  không có locator, ngoại trừ ba ID lịch sử người dùng đã chấp nhận mất text.
- 80 test liên quan đạt. Luồng PDF được kiểm tra với bộ trích xuất thay thế;
  chưa tuyên bố đã kiểm thử upload PDF thật end-to-end với model thật.
- Manifest vẫn có nội dung đã dựng trong artifact theo định dạng corpus-v1;
  không sửa manifest đã đóng băng hoặc ghi text trở lại bảng chunk.

Cần cập nhật và khởi động lại backend trên các máy thành viên trước khi sử dụng
schema mới. Backend cũ còn SELECT/INSERT chunk_text sẽ lỗi.
Không thay đổi chính sách retention hoặc tự thêm bảng nguồn lịch sử.

Phạm vi đã chốt: chuẩn hóa locator và viết bộ đọc nội dung nguồn. Giữ `text_chunks.chunk_text`, không đổi schema, không chuyển API search sang bộ đọc mới và không tự ghi locator vào Supabase.

## Contract

Các khóa locator cũ (`source_table`, `source_id`, `section`, `row_keys`, các metadata nguồn) được giữ nguyên. `db_chunking.chunk_section` bổ sung đối tượng `reconstruction`:

| Trường | Ý nghĩa |
|---|---|
| `schema_version` | `source-locator-v2` |
| `chunker_version`, `max_words` | Phiên bản và cấu hình cần dùng để dựng nguồn/chunk |
| `document_id`, `source_chunk_id`, `chunk_index` | ID tài liệu, ID chunk nguồn và vị trí. ID lưu DB vẫn tính cùng index như trước. |
| `section_index` | Mục nguồn tương ứng |
| `row_start`, `row_end` | Khoảng dòng trong mục đã chuẩn hóa, đầu bao gồm/cuối không bao gồm |
| `char_start`, `char_end` | Khoảng ký tự trên thân mục chuẩn hóa, không phải offset HTML/PDF nguyên bản |
| `source_view_sha256` | Hash của định danh nguồn, nhãn mục, tiêu đề và danh sách có thứ tự `[row_key,row_text]` |
| `content_hash` | SHA-256 nội dung chunk gồm tiêu đề lặp và thân đoạn |

Hash source view là **dấu vân tay phiên bản nội dung chuẩn hóa**, không phải bản lưu lịch sử. Không có snapshot nguồn bất biến mới được tạo ở bước này. Thay đổi bất kỳ dòng/tiêu đề trong cùng mục sẽ bị phát hiện, kể cả ngoài khoảng dòng chunk; đây là kiểm tra bảo thủ. Không lấy văn bản bản mới thay bản cũ. Tin `pN` chỉ số đơn vị sau chuẩn hóa/tách câu theo budget; không mặc định là đoạn N của HTML.

Chỉ thêm locator không đổi text/hash/chunk ID, không tăng phiên bản chunker. Locator mới lớn hơn locator cũ vì có fingerprint và thông tin vị trí, không sao chép nội dung bài vào locator.

## Bộ đọc

`db_source.fetch_locator_document` dùng truy vấn SELECT tham số hóa:

- Tin: lấy một `article_id` từ `news_articles`.
- Tài chính: lấy một `report_id` và các observation/metric/kỳ/công ty liên quan.
- Hồ sơ công ty: lấy một `company_id`.
- Giá: lấy dữ liệu theo symbol, gồm chỉ báo và công ty để dựng tổng kết tháng đúng cách.
- Chỉ số: lấy dữ liệu theo `index_symbol`.

`chunk_reconstruction.reconstruct_chunk(conn, locator, expected_hash)` đọc nguồn, dựng đúng danh sách dòng/tiêu đề và kiểm tra hash/ID. `expected_hash` phải lấy từ bản ghi chunk tin cậy, không lấy từ request người dùng tùy ý. Caller nên dùng transaction `readonly=True, isolation='repeatable_read'` để nhiều SELECT dùng cùng snapshot.

Hàm thuần `reconstruct_document_chunk` dùng khi caller đã có SourceDocument (có thể tái sử dụng theo batch để tránh truy vấn lặp). Kết quả chứa `text`, `content_hash`, `source_chunk_id`, `document_id`.

Lỗi có mã: `INVALID_LOCATOR`, `UNSUPPORTED_VERSION`, `INVALID_HASH`, `SOURCE_MISSING`, `SOURCE_MISMATCH`, `SOURCE_CHANGED`, `HASH_MISMATCH`. Lỗi kết nối/SQL không bị che thành thành công. Không fallback sang `chunk_text`, file local hoặc vector để đoán chữ.

Locator cũ chưa có reconstruction bị từ chối rõ ràng. Chưa backfill DB: việc tạo metadata cho chunk cũ chỉ được làm khi dựng nguồn hiện tại khớp chính xác hash/ID cũ; không gắn fingerprint mới cho chunk đã lệch. Nếu cần truy nguồn lịch sử sau thay đổi, phải triển khai nguồn theo phiên bản riêng trước khi bỏ text.

## Kết quả kiểm tra 19/10/2026

- 78 test chunker, locator, reconstruction, ingest và manifest đạt; gồm 5 nhóm nguồn, tin dài bị tách, nguồn đổi, nguồn mất, locator sai và ID không đổi.
- Chỉ đọc Supabase, tạo locator v2 trong bộ nhớ: 1.750 tin + 204 giá + 88 chỉ số + 3 hồ sơ = **2.045 chunk** dựng lại đúng text/hash hiện có.
- 3 hồ sơ FPT/MBB/VCB vẫn lệch vì ngành/sector đã được bổ sung sau lần tạo vector; không sửa lại chúng trong bước này.
- Truy vấn đích và dựng lại mẫu thực tế của cả 5 nhóm nguồn đều thành công. Mẫu tài chính tạo từ nguồn hiện có, chưa có chunk tài chính được lưu để đối chiếu.

## Chưa thực hiện

Không xóa cột text; không cập nhật vector/corpus/locator DB; không chuyển API tìm kiếm; không thay đổi retention 30 ngày; không sửa nhãn đơn vị/kỳ trong chunker hiện có. Kiểm tra hash chỉ chứng minh dựng đúng nội dung, không xác nhận số liệu/đơn vị/kỳ đã đạt chuẩn để promote bằng chứng tài chính.

## Cập nhật tiếp theo ngày 19/10/2026

Sau khi người dùng đồng ý tiếp tục:

- Đối chiếu 3 hồ sơ FPT/MBB/VCB: không có citation trực tiếp nhưng đều thuộc corpus-v1. Đã tạo 3 chunk/vector mới với model ghim hiện tại, đánh dấu supersede và liên kết 3 chunk cũ; không xóa/ghi đè text hoặc vector cũ, không sửa manifest corpus-v1.
- Đã backfill **chỉ locator_json** cho 2.045 chunk hiện hành còn thiếu v2; 3 chunk mới đã có v2. So fingerprint mọi cột ngoài locator trước/sau xác nhận không đổi ID/text/vector/timestamps trong bước backfill.
- Tổng DB: 2.051 chunk = 2.048 hiện hành có v2 + 3 lịch sử còn nguyên text. Chạy lại backfill chỉ đọc: 0 cập nhật cần thiết.
- Script `backend/scripts/backfill_source_locators.py` mặc định read-only; `--apply` chỉ cập nhật locator_json sau đối chiếu chính xác text/hash/ID. Batch bị từ chối nếu có nguồn lệch, thiếu hoặc loại chưa hỗ trợ; 3 chunk superseded không được gắn fingerprint của nguồn mới.
- 39 test backfill/reconstruction/ingest đạt. API search vẫn đọc chunk_text; chưa xóa cột. Các ghi chú “chưa cập nhật DB” ở phần trên mô tả trạng thái trước lượt tiếp tục này.

Ba chunk lịch sử vẫn cần text hoặc nguồn phiên bản cũ để tái hiện corpus-v1. Không coi 2.048 chunk mới khớp nguồn là bằng chứng có thể xóa text của toàn bộ 2.051 chunk.

## Chuyển phần đọc API ngày 19/10/2026

Đã chuyển `repository.get_chunks` và `repository.vector_search` sang đọc nội dung từ nguồn đối với chunk có locator v2. Các route search, chunk details và vocabulary dùng chung bộ đọc. Mỗi lượt fetch + dựng nguồn chạy trong transaction READ ONLY REPEATABLE READ; source document được cache trong phạm vi batch kết quả.

- V2: lấy nguồn, dựng chunk, so hash và đối chiếu text giữ lại trong DB. Text trả về là text đã dựng từ nguồn. Không fallback sang text lưu nếu nguồn đổi, mất hoặc sai hash.
- Nguồn không xác minh được trả HTTP 409 với `reason_code`, không trả kết quả bằng chứng chưa kiểm chứng. Lỗi cơ sở dữ liệu/mạng vẫn là lỗi hạ tầng, không giả thành thành công.
- Upload word-window-v1 cũ chưa có locator nguồn vẫn dùng text DB, có kiểm tra hash. Chunk db-v1 thiếu locator v2 bị từ chối.
- Tài liệu `file_type=DB` chọn index db-v1 theo cấu hình model/chunk size hiện tại; PDF/JSON upload vẫn dùng word-window-v1. Đây chưa phải chọn manifest corpus đã đóng băng hay tìm kiếm toàn corpus: `/api/search` vẫn giới hạn theo document_id.
- `page` trong search/chunk-detail cho phép null vì nguồn DB không có trang PDF; không tạo số trang giả.
- Vẫn ghi/giữ `chunk_text`, chưa đổi schema, chưa xóa dữ liệu. Không có thay đổi nào ở Gemini/Evidence Gate hoặc citation UI trong bước này.

Kiểm chứng: 61 test source reader/API/reconstruction/ingest/manifest đạt. HTTP API chạy trong bộ nhớ với pool Supabase chỉ đọc: search + chunk details + vocab đều 200 cho mẫu hồ sơ công ty, chỉ số, tin, giá. Vector truy vấn trong phép thử này lấy từ vector thật đã lưu để cô lập kiểm chứng pgvector và bộ dựng; không phải phép đo chất lượng embedding câu hỏi. Chưa có chunk tài chính lưu nên không tuyên bố đã test API tài chính end-to-end.

Cần khởi động lại backend đang chạy để nạp code mới. Không chạy migration xóa cột cho đến khi xử lý lịch sử nguồn/corpus-v1 và tương thích các luồng upload cũ.

## Ngừng ghi text mới cho source chunks ngày 19/10/2026

Đã áp dụng `20261019000000_nullable_source_chunk_text.sql`: cột chunk_text cho phép NULL, ràng buộc yêu cầu locator v2 nếu text NULL. Không xóa cột hoặc đặt NULL các text cũ. `reset_and_rebuild.sql` được đồng bộ; không chạy reset trên DB thật.

`db_ingest.write_chunks` nay ghi NULL cho chunk mới từ nguồn DB, sau khi kiểm tra reconstruction metadata. Text vẫn tồn tại trong bộ nhớ lúc tạo embedding, không sao chép vào text_chunks. Rerun chunk cũ không đổi vẫn giữ text cũ; luồng PDF/JSON upload word-window-v1 tiếp tục ghi text vì chưa có nguồn để dựng lại. Manifest đọc qua bộ dựng nguồn nên vẫn tạo được khi text NULL; báo cáo retention tính dung lượng vector kể cả text NULL.

Đã qua 60 test liên quan. Migration so fingerprint toàn bộ 2.051 dòng trước/sau không đổi. Phép thử DB đặt tạm một text NULL: đọc nguồn khớp, bỏ locator bị ràng buộc từ chối, sau đó rollback. Kết thúc còn 2.051/2.051 text cũ; không có dữ liệu thử được giữ.

Đây chưa phải xóa text toàn DB. Cần nguồn cũ/cơ chế phiên bản cho chunk lịch sử trước khi bỏ các bản cũ; nếu nguồn thay đổi mà không có bản tương ứng thì reader trả lỗi, không thể khôi phục vector thành chữ. Không bảo đảm lịch sử chỉ bằng fingerprint. Các tiến trình backend/ingest của nhóm cần cập nhật code và restart trước khi dùng luồng không text.
