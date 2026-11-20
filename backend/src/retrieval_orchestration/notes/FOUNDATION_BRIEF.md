# Hợp đồng triển khai fixture — coordinator

Phạm vi: chỉ folder này, Python3.11+ và stdlib; không network, DB, API/UI, package install, git commit, crawler hoặc chỉnh hai tài liệu gốc. Đây là bản triển khai thử fixture, không khẳng định nguồn/số liệu thật. Chưa có code cũ để giữ tương thích API. Tài liệu gốc được dùng làm yêu cầu, không coi các tuyên bố hiện trạng repo là đã xác minh.

## Package và kiểm thử

- Namespace package `retrieval_flow/`; modules dùng relative imports, không sửa sys.path toàn cục. Không cần __init__.py nếu chỉ namespace package.
- Test dùng unittest, import `retrieval_flow.contracts`, `.intent`, `.orchestrator` khi chạy từ folder này. Lệnh: `python -B -m unittest discover -s tests -p test_contracts.py -v` và tương tự cho intent/orchestrator; cuối cùng `python -B -m unittest discover -s tests -v`.
- Không subprocess/network/file writes trong code sản phẩm/test. Đọc fixture JSON cùng module được phép; test deep-copy data, không sửa fixture.


## Scoped task
 contracts.py + fixtures.json

Public API cố định:

1. `load_fixtures() -> dict`: đọc JSON cố định, trả deep copy (không chia mutable giữa requests).
2. `validate_pack(pack: object) -> list[dict]`: danh sách lỗi có `code,path,message` tiếng Việt; rỗng là hợp lệ cấu trúc. Không mutate đầu vào, gom nhiều lỗi thay vì crash. Pack WBS08 schema1.0, query_id nonblank, data_version.kind INDEX/id pinned nonblank không latest, items list.
3. `check_evidence(pack: dict, scope: dict, registry: dict) -> list[dict]`: pack đã validate trước; đối chiếu metadata theo chunk/version và đủ companies×periods của câu hỏi. Kết quả rỗng chỉ khi đủ và đúng, không mặc định thông tin thiếu. Error codes ổn định (worker chọn và ghi docstring). Không loại bỏ item sai rồi dùng phần còn lại.

Item phải có evidence_id duy nhất, chunk_id/source_id nonblank, sha25664hex, source_type BCTC/BCTN, locator có page_number positive int loại bool hoặc table_id nonblank; field locator có mặt nhưng sai kiểu phải bị từ chối dù field khác hợp lệ. passage nonblank; score.type COSINE_SIMILARITY, score.value int/float finite -1..1 loại bool/string. Schema thiếu/sai kiểu: có error rõ, không ném exception ngoài dự kiến.

Scope canonical (dict): `companies` list tickers, `periods` list ISO dates (cuối kỳ hoặc ngày cụ thể), `metric_code` string|null, `topic` string|null, `measure_basis` string, `reporting_entity` UNKNOWN|CONSOLIDATED|PARENT, `source_type` BCTC|BCTN. Đơn vị lấy từ fixture profile rõ; nếu scope có `unit`, phải so khớp. UNKNOWN không có nghĩa hợp nhất; nếu nguồn không xác định entity/unit thì thiếu evidence. Nếu có nhiều entity cho cùng câu hỏi mà chưa chọn phải yêu cầu làm rõ, không chọn first.

Fixture JSON root: `execution_mode: FIXTURE`, `alias_version: fixture-alias-v1`, `corpus_version: fixture-corpus-v1`, `index_version: fixture-index-v1`, `corpus_to_index: {fixture-corpus-v1:fixture-index-v1}`, `registry` dict và `packs` dict. Registry keys là chunk_id; mỗi record gồm index_version, company, period_end, metric_code/topic, measure_basis, reporting_entity, unit, source_type, source_id, source_sha256, locator, passage, value_token. Đối chiếu passage/locator/hash/source với record, không chỉ tin chunk_id.

Tạo ít nhất records BID/VCB TOTAL_ASSETS tại30/06/2026 và31/12/2025 (4records), BID PROFIT_AFTER_TAX quý2/2026 riêng quý, FPT BCTN2025 chủ đề quản trị rủi ro. Tất cả ID/hash/passage/value_token rõ fixture; không chứa số tài chính được trình bày như thật. value_token là nhãn biểu tượng để test conflict, không phải đáp án số. Packs: `valid_metric` (BID30/06), `valid_compare` (BID/VCB31/12), `valid_annual`, `empty`; query_id fixture sẽ được adapter gắn lại request (metadata immutable còn lại).

check_evidence so record với scope từng item; không chấp nhận sai company/kỳ/metric/basis/entity/unit/source. Với cùng company/kỳ/metric/entity/basis/unit nhưng value_token khác, báo conflicting evidence; không dùng cosine chọn. So sánh/trend thiếu pair yêu cầu phải fail. Thiếu registry/record/scope metadata không được coi là match.

