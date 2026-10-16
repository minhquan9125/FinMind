# Hợp đồng triển khai fixture — coordinator

Phạm vi: chỉ folder này, Python3.11+ và stdlib; không network, DB, API/UI, package install, git commit, crawler hoặc chỉnh hai tài liệu gốc. Đây là bản triển khai thử fixture, không khẳng định nguồn/số liệu thật. Chưa có code cũ để giữ tương thích API. Tài liệu gốc được dùng làm yêu cầu, không coi các tuyên bố hiện trạng repo là đã xác minh.

## Package và kiểm thử

- Namespace package `retrieval_flow/`; modules dùng relative imports, không sửa sys.path toàn cục. Không cần __init__.py nếu chỉ namespace package.
- Test dùng unittest, import `retrieval_flow.contracts`, `.intent`, `.orchestrator` khi chạy từ folder này. Lệnh: `python -B -m unittest discover -s tests -p test_contracts.py -v` và tương tự cho intent/orchestrator; cuối cùng `python -B -m unittest discover -s tests -v`.
- Không subprocess/network/file writes trong code sản phẩm/test. Đọc fixture JSON cùng module được phép; test deep-copy data, không sửa fixture.

## Job nền tảng: contracts.py + fixtures.json

Public API cố định:

1. `load_fixtures() -> dict`: đọc JSON cố định, trả deep copy (không chia mutable giữa requests).
2. `validate_pack(pack: object) -> list[dict]`: danh sách lỗi có `code,path,message` tiếng Việt; rỗng là hợp lệ cấu trúc. Không mutate đầu vào, gom nhiều lỗi thay vì crash. Pack WBS08 schema1.0, query_id nonblank, data_version.kind INDEX/id pinned nonblank không latest, items list.
3. `check_evidence(pack: dict, scope: dict, registry: dict) -> list[dict]`: pack đã validate trước; đối chiếu metadata theo chunk/version và đủ companies×periods của câu hỏi. Kết quả rỗng chỉ khi đủ và đúng, không mặc định thông tin thiếu. Error codes ổn định (worker chọn và ghi docstring). Không loại bỏ item sai rồi dùng phần còn lại.

Item phải có evidence_id duy nhất, chunk_id/source_id nonblank, sha25664hex, source_type BCTC/BCTN, locator có page_number positive int loại bool hoặc table_id nonblank; field locator có mặt nhưng sai kiểu phải bị từ chối dù field khác hợp lệ. passage nonblank; score.type COSINE_SIMILARITY, score.value int/float finite -1..1 loại bool/string. Schema thiếu/sai kiểu: có error rõ, không ném exception ngoài dự kiến.

Scope canonical (dict): `companies` list tickers, `periods` list ISO dates (cuối kỳ hoặc ngày cụ thể), `metric_code` string|null, `topic` string|null, `measure_basis` string, `reporting_entity` UNKNOWN|CONSOLIDATED|PARENT, `source_type` BCTC|BCTN. Đơn vị lấy từ fixture profile rõ; nếu scope có `unit`, phải so khớp. UNKNOWN không có nghĩa hợp nhất; nếu nguồn không xác định entity/unit thì thiếu evidence. Nếu có nhiều entity cho cùng câu hỏi mà chưa chọn phải yêu cầu làm rõ, không chọn first.

Fixture JSON root: `execution_mode: FIXTURE`, `alias_version: fixture-alias-v1`, `corpus_version: fixture-corpus-v1`, `index_version: fixture-index-v1`, `corpus_to_index: {fixture-corpus-v1:fixture-index-v1}`, `registry` dict và `packs` dict. Registry keys là chunk_id; mỗi record gồm index_version, company, period_end, metric_code/topic, measure_basis, reporting_entity, unit, source_type, source_id, source_sha256, locator, passage, value_token. Đối chiếu passage/locator/hash/source với record, không chỉ tin chunk_id.

Tạo ít nhất records BID/VCB TOTAL_ASSETS tại30/06/2026 và31/12/2025 (4records), BID PROFIT_AFTER_TAX quý2/2026 riêng quý, FPT BCTN2025 chủ đề quản trị rủi ro. Tất cả ID/hash/passage/value_token rõ fixture; không chứa số tài chính được trình bày như thật. value_token là nhãn biểu tượng để test conflict, không phải đáp án số. Packs: `valid_metric` (BID30/06), `valid_compare` (BID/VCB31/12), `valid_annual`, `empty`; query_id fixture sẽ được adapter gắn lại request (metadata immutable còn lại).

check_evidence so record với scope từng item; không chấp nhận sai company/kỳ/metric/basis/entity/unit/source. Với cùng company/kỳ/metric/entity/basis/unit nhưng value_token khác, báo conflicting evidence; không dùng cosine chọn. So sánh/trend thiếu pair yêu cầu phải fail. Thiếu registry/record/scope metadata không được coi là match.

## Job B1: intent.py

Public `analyze(question: str, session_id: str, context: dict|None=None) -> dict`, và `clarify(previous: dict, reply: str, session_id: str) -> dict`. Pure deterministic, không shared global mutable/persistence. Output có WBS03 fields request_id/original_question/normalized_question/intent/slots/decision/missing_fields/conflicts/clarification_question/reason_code/corpus_version_id, cộng `session_id` và `scope` canonical ở trên. UUID request_id được sinh thật; quyết định/slots không phụ thuộc randomness.

Ưu tiên an toàn và no guessing: 10mã VCB BID CTG MBB TCB FPT CMG ELC ITD ICT; aliases fixture có nhãn/version. Recognize total assets/tổng tài sản, profit before/after tax/lợi nhuận trước/sau thuế, cash flow operating/lưu chuyển tiền thuần từ hoạt động kinh doanh; lợi nhuận/doanh thu/dòng tiền chung phải hỏi; không map theo substring gần nghĩa. Câu không hiểu/trống hỏi rõ, độ dài >4000 từ chối rõ không truy xuất. Unknown ticker rõ ràng ->OUT_OF_SCOPE, prose ABC không rõ ý ->UNCLEAR/ASK_CLARIFICATION.

Hỗ trợ ngày d/m/yyyy hoặc d-m-yyyy có validation, quýQn/yyyy/quarter, năm/yyyy; POINT_IN_TIME với total assets tại cuối quý/năm, FULL_YEAR dòng chảy, STANDALONE_QUARTER chỉ fixtureVietcap; YTD6thángđầu phải riêng, latest/gầnđây hỏi kỳ; không dùng ngày hệ thống. Chỉ lấy thời gian được viết hoặc session hợp lệ. Compare phải >=2companies cùngkỳ/basis/entity; trend>=2periods, metric rõ; annual topic rõ năm. Multiintent độc lập hỏi tách. News thuần OUT_OF_SCOPE; financialmetric 'theo tin tức' hỏi SOURCE_CONFLICT trước, không lén đổi nguồn; advice UNSUPPORTED.

Context chỉ dùng khi có explicitreference (công ty này/cùng kỳ/còn VCB), đúng context.session_id, context.confirmed is True và context.expired is False, một scope xác nhận không mơ hồ. Không tự dùng selected_company khi câu không ám chỉ. Reference request dùng context.reference có IDs đúngsession; decisionRESOLVE_REFERENCE, khôngsearch; thiếuID OUT_OF_SCOPE/NO_REFERENCED_EVIDENCE. Registry unavailable context flag phải SYSTEM_UNAVAILABLE, không giả thành hỏi người dùng.

clarify chỉ nhận previous ASK_CLARIFICATION cùngsession; reply chỉ bổ sung slot đang thiếu/ambiguous, originCLARIFICATION; giữ BID/quý; không sửa previous. Reply đổi rõ company/period/topic ->phân tích lại với thông tin user mới thắng, không lẫn phiên. Unsupported input phải fail closed và có trạng thái hữu ích, không crash.

## Job orchestration: orchestrator.py + README.md

Public async `orchestrate(question, session_id, *, context=None, analyzer=analyze, retriever=None, reference_resolver=None, timeout_seconds=1.0) -> dict`. `FixtureRetriever` class: async `retrieve(scope, query_id, index_version) -> dict`, `calls` list counter, load fixtures. `FixtureReferenceResolver` class async `resolve(reference, session_id)->dict|None`, chỉ có store fixture gắn với phiên được constructor cung cấp; calls counter. Cho phép inject async fake adapter để test. Không retry mặc định. Deadline hữu hạn; dùng asyncio timeout/wait_for await trực tiếp coroutine, không background tasks/tồnđọng; cancellation caller phải propagate.

Envelope luôn cùngkeys: request_id, query_id, execution_mode(FIXTURE), b1_decision, status, reason_code, message, scope, clarification, evidence_pack, errors. Chỉ EVIDENCE_READY mới có evidence_pack đã kiểm tra; không có trường answer/số liệu tổng hợp. NO_DATA,INVALID_EVIDENCE_PACK,INSUFFICIENT_EVIDENCE,SYSTEM_UNAVAILABLE khác nhau. NhánhB1 nonSEARCH returnstatus giữdecision; không gọiretrieval. RESOLVE_REFERENCE chỉ gọireference resolver, trảREFERENCE_READY hoặcOUT_OF_SCOPE/NO_REFERENCED_EVIDENCE; khôngvector. Không trả rawexception/stacktrace/secret vào errors/message; logkhông cần.

SEARCH: tra mapping corpus_to_index đã chốt; corpus thiếu/sai ->SYSTEM_UNAVAILABLE khôngchoose latest; query_id unique gắn request; awaitretriever với deadline; timeout/systemerror SYSTEM_UNAVAILABLE reasonriêng. validate_pack rồi soexactquery_id/index expected; itemsrỗng->NO_DATA; check_evidence->INSUFFICIENT_EVIDENCE; pass->EVIDENCE_READY. Chặn malformed pack/rawJSON/nhầmscope, nguồn conflict hoặcentityambiguous; không leak pack khi fail.

FixtureRetriever chọn pack theo canonical scope: totalassets BID30/06 ->validmetric; compareBIDVCB31/12 ->validcompare; annualFPT2025 ->validannual; các scope khác chỉempty nếu known metadata đủ để kết luậnfixturekhôngcó, không fallbacknearest. Không trả nhầmBID khiđổiVCB. Demo README nêu rõ fixture, lệnh test và Python example đủ chạy từfolder; chưa nối API/app/vector thật.

## Tiêu chí chung

Workers triển khai, testing độc lập thiết kế test, Codex kiểm tra candidate rủi ro rồi chạy argv cố định, reviewer model thứba xem receipts, Codex duyệt trước tích hợp. No failed/partial acceptance. Các giới hạn NLP deterministic phải ghi rõ, không claim toàn bộ48ca đặc tả tự động pass khichưa test.
