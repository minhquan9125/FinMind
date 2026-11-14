# Hợp đồng triển khai fixture — coordinator

Phạm vi: chỉ folder này, Python3.11+ và stdlib; không network, DB, API/UI, package install, git commit, crawler hoặc chỉnh hai tài liệu gốc. Đây là bản triển khai thử fixture, không khẳng định nguồn/số liệu thật. Chưa có code cũ để giữ tương thích API. Tài liệu gốc được dùng làm yêu cầu, không coi các tuyên bố hiện trạng repo là đã xác minh.

## Package và kiểm thử

- Namespace package `retrieval_flow/`; modules dùng relative imports, không sửa sys.path toàn cục. Không cần __init__.py nếu chỉ namespace package.
- Test dùng unittest, import `retrieval_flow.contracts`, `.intent`, `.orchestrator` khi chạy từ folder này. Lệnh: `python -B -m unittest discover -s tests -p test_contracts.py -v` và tương tự cho intent/orchestrator; cuối cùng `python -B -m unittest discover -s tests -v`.
- Không subprocess/network/file writes trong code sản phẩm/test. Đọc fixture JSON cùng module được phép; test deep-copy data, không sửa fixture.


## Scoped task
 intent.py

Public `analyze(question: str, session_id: str, context: dict|None=None) -> dict`, và `clarify(previous: dict, reply: str, session_id: str) -> dict`. Pure deterministic, không shared global mutable/persistence. Output có WBS03 fields request_id/original_question/normalized_question/intent/slots/decision/missing_fields/conflicts/clarification_question/reason_code/corpus_version_id, cộng `session_id` và `scope` canonical ở trên. UUID request_id được sinh thật; quyết định/slots không phụ thuộc randomness.

Ưu tiên an toàn và no guessing: 10mã VCB BID CTG MBB TCB FPT CMG ELC ITD ICT; aliases fixture có nhãn/version. Recognize total assets/tổng tài sản, profit before/after tax/lợi nhuận trước/sau thuế, cash flow operating/lưu chuyển tiền thuần từ hoạt động kinh doanh; lợi nhuận/doanh thu/dòng tiền chung phải hỏi; không map theo substring gần nghĩa. Câu không hiểu/trống hỏi rõ, độ dài >4000 từ chối rõ không truy xuất. Unknown ticker rõ ràng ->OUT_OF_SCOPE, prose ABC không rõ ý ->UNCLEAR/ASK_CLARIFICATION.

Hỗ trợ ngày d/m/yyyy hoặc d-m-yyyy có validation, quýQn/yyyy/quarter, năm/yyyy; POINT_IN_TIME với total assets tại cuối quý/năm, FULL_YEAR dòng chảy, STANDALONE_QUARTER chỉ fixtureVietcap; YTD6thángđầu phải riêng, latest/gầnđây hỏi kỳ; không dùng ngày hệ thống. Chỉ lấy thời gian được viết hoặc session hợp lệ. Compare phải >=2companies cùngkỳ/basis/entity; trend>=2periods, metric rõ; annual topic rõ năm. Multiintent độc lập hỏi tách. News thuần OUT_OF_SCOPE; financialmetric 'theo tin tức' hỏi SOURCE_CONFLICT trước, không lén đổi nguồn; advice UNSUPPORTED.

Context chỉ dùng khi có explicitreference (công ty này/cùng kỳ/còn VCB), đúng context.session_id, context.confirmed is True và context.expired is False, một scope xác nhận không mơ hồ. Không tự dùng selected_company khi câu không ám chỉ. Reference request dùng context.reference có IDs đúngsession; decisionRESOLVE_REFERENCE, khôngsearch; thiếuID OUT_OF_SCOPE/NO_REFERENCED_EVIDENCE. Registry unavailable context flag phải SYSTEM_UNAVAILABLE, không giả thành hỏi người dùng.

clarify chỉ nhận previous ASK_CLARIFICATION cùngsession; reply chỉ bổ sung slot đang thiếu/ambiguous, originCLARIFICATION; giữ BID/quý; không sửa previous. Reply đổi rõ company/period/topic ->phân tích lại với thông tin user mới thắng, không lẫn phiên. Unsupported input phải fail closed và có trạng thái hữu ích, không crash.

