# S3-WBS08 — Cấu trúc gói bằng chứng cho luồng B1

**Phụ trách:** Thái Quốc Hưng · **Sprint 3, tuần 1** · **Ước lượng ticket:** 3 giờ

**Trạng thái:** Bản đề xuất để team đối chiếu. Chưa ký duyệt contract chunk/retrieval và chưa hoàn tất cổng kiểm thử/review độc lập ECC. Các mẫu bên dưới là dữ liệu giả lập, không phải dữ liệu tài chính đã xác minh.

## 1. Task này giải quyết việc gì?

Khi hệ thống tìm được một đoạn tài liệu, chỉ chuyển mỗi câu chữ sang phần trả lời là chưa đủ. Phần trả lời cần biết đoạn đó lấy từ tài liệu nào, ở trang/bảng nào và thuộc lần nạp dữ liệu nào. **Evidence pack là phong bì chứa đoạn nội dung cùng thông tin để kiểm tra lại nguồn.**

Ví dụ: người dùng hỏi về hoạt động quản trị trong BCTN; phần tìm kiếm trả về đoạn liên quan. Evidence pack giữ nguyên đoạn này, mã tài liệu, vị trí trang, phiên bản index và điểm tương đồng. Phần trả lời có thể đọc đoạn và phần citation có thể mở đúng vị trí nguồn.

Theo đặc tả S3-WBS03 hiện tại, B1 là bước hiểu câu hỏi trước tìm kiếm; B1 không tạo bằng chứng. Cụm “B1 đọc gói mẫu” trong ticket được hiểu là **luồng xử lý câu hỏi B1 có một consumer đọc được output bằng chứng**. Consumer thử nghiệm chưa chứng minh intent gate, retrieval và sinh câu trả lời đã được nối hoàn chỉnh.

## 2. Đầu ra phải bàn giao

| Đầu ra | Người dùng tiếp |
|---|---|
| Quy ước trường, kiểu dữ liệu, trường bắt buộc và lỗi | Nhân lập trình retrieval; Hưng lập trình consumer |
| Gói mẫu hợp lệ và mẫu thiếu metadata | Nhóm B1, nhóm UI/citation, QA |
| Quy tắc đối chiếu mã chunk và phiên bản | Vũ xác nhận với schema chunk đang triển khai |
| Kết quả chạy kiểm tra có thể lặp lại | QA và người review task |

Không cần chờ vector search thật mới kiểm tra việc đọc gói: đưa JSON mẫu vào cùng một parser mà consumer sẽ dùng về sau.

## 3. Cấu trúc đề xuất v1

Một pack ứng với một lần truy xuất của một câu hỏi và một phiên bản dữ liệu đã chọn. `items` chứa 0 hoặc nhiều bằng chứng.

| Trường | Bắt buộc | Quy tắc và ý nghĩa dễ hiểu |
|---|---|---|
| `schema_version` | Có | Chuỗi `1.0`; phiên bản cấu trúc JSON. Không phải phiên bản dữ liệu. |
| `query_id` | Có | Mã lần hỏi/truy xuất; chuỗi không rỗng. Không dùng câu hỏi làm ID. |
| `data_version.kind` | Có | `INDEX` ở baseline hiện tại. `CORPUS` chỉ mở khi có resolver/manifest tương ứng. |
| `data_version.id` | Có | ID phiên index được pin; không ghi `latest`, ngày hôm nay hay phiên tự đoán. |
| `items` | Có | Mảng. Mảng rỗng nghĩa là không tìm được bằng chứng trong phạm vi truy xuất này. |
| `items[].evidence_id` | Có | Mã bằng chứng duy nhất trong pack để câu trả lời/citation tham chiếu. Quy tắc sinh/lưu cần thống nhất với retrieval. |
| `items[].chunk_id` | Có | Mã đoạn do tầng chunk cung cấp; không tự tạo từ thứ tự kết quả, không thay bằng `chunk_index`. |
| `items[].source_id` | Có | Mã tài liệu nguồn để resolver truy lại. Đề xuất dùng `doc:<document_id>` cho tài liệu; cần team xác nhận namespace. Không dùng tên provider thay ID tài liệu. |
| `items[].source_sha256` | Có | 64 ký tự hex của file nguồn; giúp phát hiện tài liệu đã thay đổi. Không sinh hash giả để bù dữ liệu thiếu. |
| `items[].source_type` | Có | `BCTC` hoặc `BCTN` theo baseline B1 hiện tại. News chưa bật trong đặc tả B1 đã đối chiếu. |
| `items[].locator` | Có | Có `page_number` nguyên dương hoặc `table_id` không rỗng; có thể có cả hai. Locator phải tìm lại được trong nguồn. |
| `items[].passage` | Có | Nội dung đoạn trích không rỗng; giữ câu chữ nguồn. Không đưa nội dung AI viết vào đây dưới danh nghĩa trích nguồn. |
| `items[].score.type` | Có | `COSINE_SIMILARITY` cho vector hiện tại. Điểm kiểu khác phải có định nghĩa riêng trước khi sử dụng. |
| `items[].score.value` | Có | Số hữu hạn từ -1 đến 1 với cosine similarity. `true/false`, `NaN`, `Infinity` và chuỗi số bị từ chối. |
| `items[].locator.section_label` | Không | Tên mục giúp người đọc tìm nhanh; không thay locator trang/bảng. |

ID là chuỗi opaque: consumer không tự phân tích hoặc đổi ID sang định dạng khác. Quy tắc ID cụ thể do tầng sở hữu xác nhận. Một pack không trộn các index version. Nếu cần nhiều corpus/index, retrieval phải nhóm pack hoặc chốt contract mở rộng trước.

**Quy ước trang:** `page_number` đếm trang vật lý của PDF từ 1. Nếu số trang in trên tài liệu khác số PDF, thêm `printed_page_label` để hiển thị; số này không thay `page_number`. `table_id` phải ổn định trong tài liệu và có resolver xác định bảng, không phải tên bảng tùy ý. Nguồn JSON không có trang có thể dùng bảng/record locator đã thống nhất; không tự gán trang 1.

**Điểm phù hợp:** `0.82` không có nghĩa “82% đáp án đúng”. Nó chỉ hỗ trợ xếp hạng độ tương đồng với câu hỏi. Không dùng điểm để thay kiểm tra công ty, kỳ, đơn vị, loại báo cáo hoặc sự đầy đủ của bằng chứng.

## 4. Gói mẫu hợp lệ

Các ID/hash bên dưới cố ý là fixture, chỉ dùng kiểm tra cấu trúc. Không đưa chúng vào kho dữ liệu thật hoặc hiển thị như nguồn thật.

```json
{
  "schema_version": "1.0",
  "query_id": "fixture-query-001",
  "data_version": {"kind": "INDEX", "id": "fixture-index-v1"},
  "items": [
    {
      "evidence_id": "fixture-evidence-001",
      "chunk_id": "fixture-chunk-001",
      "source_id": "doc:fixture-document-001",
      "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "source_type": "BCTN",
      "locator": {"page_number": 14, "section_label": "Quản trị doanh nghiệp"},
      "passage": "Đoạn giả lập: doanh nghiệp mô tả quy trình giám sát và quản trị rủi ro trong báo cáo thường niên.",
      "score": {"type": "COSINE_SIMILARITY", "value": 0.82}
    }
  ]
}
```

Consumer mong đợi: đọc được 1 item; lấy đúng passage; trả lại evidence ID, source ID, trang 14 và index fixture-index-v1 để tầng citation sử dụng. **Không sinh đáp án tài chính từ fixture này.**

Mẫu thứ hai: thay locator bằng `{"table_id":"fixture-table-003"}`. Consumer chấp nhận vị trí bảng; việc mở được bảng cần resolver thật. Mẫu thứ ba: `items: []`, giữ query/version hợp lệ; consumer trả `NO_DATA`, không tạo citation hay câu trả lời có dữ kiện.

## 5. Phản hồi khi thiếu hoặc sai thông tin

Parser nên gom các lỗi có thể kiểm tra được và trả danh sách; từng lỗi có `code`, `path`, `message`. Không âm thầm điền metadata thiếu bằng giá trị mặc định.

```json
{
  "status": "INVALID_EVIDENCE_PACK",
  "errors": [
    {"code": "MISSING_LOCATOR", "path": "items[0].locator", "message": "Bằng chứng thiếu vị trí trang hoặc bảng."},
    {"code": "MISSING_DATA_VERSION", "path": "data_version.id", "message": "Gói bằng chứng thiếu phiên bản dữ liệu."}
  ]
}
```

| Ca | Kết quả cần có |
|---|---|
| Xóa `source_id` hoặc để chuỗi trắng | `MISSING_SOURCE_ID`, chỉ rõ item bị lỗi |
| Xóa locator hoặc chỉ có section_label | `MISSING_LOCATOR`; tên mục chưa đủ vị trí |
| Trang bằng 0, âm, 1.5 hoặc true | `INVALID_LOCATOR`; không sửa thành trang 1 |
| Xóa phiên bản hoặc dùng `latest` | `MISSING_DATA_VERSION`/`INVALID_DATA_VERSION` |
| Xóa passage hoặc passage chỉ có dấu cách | `EMPTY_PASSAGE` |
| Score là chuỗi, bool, NaN/Inf hoặc ngoài miền cosine | `INVALID_SCORE` |
| Hai item trùng evidence_id | `DUPLICATE_EVIDENCE_ID` |
| schema_version chưa hỗ trợ | `UNSUPPORTED_SCHEMA_VERSION` |
| Source hash sai định dạng | `INVALID_SOURCE_HASH` |
| ID không resolve được/không thuộc phiên bản pin | Lỗi resolver `EVIDENCE_NOT_FOUND`/`VERSION_MISMATCH`; không được coi parser hợp lệ là resolver đã thành công |

Baseline đề xuất: một item thiếu metadata bắt buộc khiến cả pack bị từ chối ở consumer. Chưa cho phép tự bỏ item lỗi rồi dùng phần còn lại; nếu muốn trả kết quả một phần cần contract riêng và trace rõ.

Lỗi metadata là lỗi dữ liệu/hệ thống, không yêu cầu người dùng đổi câu hỏi. `NO_DATA` chỉ nói retrieval không tìm được evidence trong phạm vi đó; không khẳng định công ty không có dữ liệu hoặc chỉ tiêu bằng 0.

## 6. Đối chiếu với repo hiện tại

| Cần trong pack | Trường/nguồn hiện có | Việc còn phải nối |
|---|---|---|
| passage | `SearchResultOut.text` / `text_chunks.chunk_text` | Mapping trực tiếp, giữ nguyên nội dung |
| page_number | `SearchResultOut.page` / `text_chunks.page_number` | Xác nhận PDF index và quy ước trang 1-based |
| cosine score | `vector_search`: `1 - cosine_distance` | Gắn type `COSINE_SIMILARITY` |
| chunk_id | `text_chunks.chunk_id` | Search response hiện chưa trả; Vũ xác nhận tính ổn định |
| data_version | `text_chunks.index_version_id`, tham số repository | API search chưa trả; Nhân giữ/pin phiên trong retrieval contract |
| source_id | `documents.document_id` | Chốt namespace và trả tham chiếu từ retrieval; không lấy chunk_index thay thế |
| source_sha256 | `documents.sha256` | Nối nguồn tài liệu, không dùng content_hash của chunk thay hash file |
| evidence_id | Có trong ERD evidence/retrieval_results | Chưa chứng minh đường API hiện tại tạo/lưu ID này |
| table_id | Locator trong thiết kế ERD | Chưa chứng minh extractor và resolver bảng đã triển khai |

`insert_chunks` tạo UUID mới cho lần insert và giữ ID hiện có khi conflict update; điều đó chưa chứng minh ID giữ nguyên sau khi xóa/tạo lại hoặc rebuild. Task này không tự thay quy tắc chunk ID.

## 7. Phân việc và phụ thuộc để không phải chờ nhau

| Người | Có thể làm ngay | Cần xác nhận để nối thật |
|---|---|---|
| Hưng | Viết contract, fixture, parser/consumer và kiểm tra lỗi | Tên trường ID/version của Vũ và Nhân |
| Vũ — chunk | Đối chiếu trường chunk_id, document_id, locator và version | Quy tắc ID ổn định, locator đúng nguồn |
| Nhân — retrieval | Trả pack fixture theo cùng contract; pin version | Mapping từ query/result thật, evidence ID và resolver |
| UI/citation | Dùng fixture để dựng đoạn trích, tên nguồn và vị trí | URL/resolver thật; không link fixture như nguồn thật |
| QA | Viết ca valid/missing/invalid/NO_DATA | Chạy lại ca tích hợp khi retrieval thật sẵn sàng |

Hưng không cần chờ vector search xong để kiểm tra parser. Tuy nhiên không đánh dấu “tích hợp retrieval thật hoàn tất” khi chỉ đọc được fixture.

## 8. Kiểm tra chấp nhận và điều kiện đóng task

1. Team xác nhận schema v1 và naming ID/version/locator trong ticket hoặc biên bản.
2. Consumer thực sự đọc mẫu trang, mẫu bảng và mẫu NO_DATA; kết quả được ghi bằng test/receipt.
3. Consumer báo đúng code/path khi thiếu source, locator và phiên bản; kiểm tra cả kiểu dữ liệu sai, score không hữu hạn và ID trùng.
4. Không có giả định rằng schema hợp lệ đồng nghĩa nguồn thật tồn tại; resolver/integration test được ghi riêng.
5. Có người kiểm thử và người review độc lập theo workflow dự án; chỉ bản qua các cổng được tích hợp.

Đối với task chốt contract, có thể hoàn tất phần thiết kế và thử fixture trước retrieval thật nếu ticket chấp nhận ranh giới đó. Việc nối retrieval thật và kiểm tra citation đúng tài liệu vẫn cần task triển khai tương ứng.

## 9. Nội dung cập nhật Jira sau khi có kết quả kiểm tra

“Đã thống nhất evidence pack v1 gồm nội dung đoạn, mã evidence/chunk/source, vị trí trang hoặc bảng, phiên index pin và cosine score có định nghĩa. Đã thử consumer với fixture hợp lệ và các lỗi metadata bắt buộc. Mapping với chunk/retrieval: [ghi phiên bản xác nhận của Vũ/Nhân]. Bằng chứng kiểm thử/review: [đính kèm receipt]. Tích hợp retrieval thật: [ghi chính xác đã/chưa].”

Các phần trong ngoặc vuông chỉ điền sau khi có bằng chứng; không dùng mẫu comment này để tuyên bố task đã Done trước kiểm chứng.
