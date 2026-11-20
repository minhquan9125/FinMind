# Hợp đồng triển khai fixture — coordinator

Phạm vi: chỉ folder này, Python3.11+ và stdlib; không network, DB, API/UI, package install, git commit, crawler hoặc chỉnh hai tài liệu gốc. Đây là bản triển khai thử fixture, không khẳng định nguồn/số liệu thật. Chưa có code cũ để giữ tương thích API. Tài liệu gốc được dùng làm yêu cầu, không coi các tuyên bố hiện trạng repo là đã xác minh.

## Package và kiểm thử

- Namespace package `retrieval_flow/`; modules dùng relative imports, không sửa sys.path toàn cục. Không cần __init__.py nếu chỉ namespace package.
- Test dùng unittest, import `retrieval_flow.contracts`, `.intent`, `.orchestrator` khi chạy từ folder này. Lệnh: `python -B -m unittest discover -s tests -p test_contracts.py -v` và tương tự cho intent/orchestrator; cuối cùng `python -B -m unittest discover -s tests -v`.
- Không subprocess/network/file writes trong code sản phẩm/test. Đọc fixture JSON cùng module được phép; test deep-copy data, không sửa fixture.


## Scoped task
 orchestrator.py + README.md

Public async `orchestrate(question, session_id, *, context=None, analyzer=analyze, retriever=None, reference_resolver=None, timeout_seconds=1.0) -> dict`. `FixtureRetriever` class: async `retrieve(scope, query_id, index_version) -> dict`, `calls` list counter, load fixtures. `FixtureReferenceResolver` class async `resolve(reference, session_id)->dict|None`, chỉ có store fixture gắn với phiên được constructor cung cấp; calls counter. Cho phép inject async fake adapter để test. Không retry mặc định. Deadline hữu hạn; dùng asyncio timeout/wait_for await trực tiếp coroutine, không background tasks/tồnđọng; cancellation caller phải propagate.

Envelope luôn cùngkeys: request_id, query_id, execution_mode(FIXTURE), b1_decision, status, reason_code, message, scope, clarification, evidence_pack, errors. Chỉ EVIDENCE_READY mới có evidence_pack đã kiểm tra; không có trường answer/số liệu tổng hợp. NO_DATA,INVALID_EVIDENCE_PACK,INSUFFICIENT_EVIDENCE,SYSTEM_UNAVAILABLE khác nhau. NhánhB1 nonSEARCH returnstatus giữdecision; không gọiretrieval. RESOLVE_REFERENCE chỉ gọireference resolver, trảREFERENCE_READY hoặcOUT_OF_SCOPE/NO_REFERENCED_EVIDENCE; khôngvector. Không trả rawexception/stacktrace/secret vào errors/message; logkhông cần.

SEARCH: tra mapping corpus_to_index đã chốt; corpus thiếu/sai ->SYSTEM_UNAVAILABLE khôngchoose latest; query_id unique gắn request; awaitretriever với deadline; timeout/systemerror SYSTEM_UNAVAILABLE reasonriêng. validate_pack rồi soexactquery_id/index expected; itemsrỗng->NO_DATA; check_evidence->INSUFFICIENT_EVIDENCE; pass->EVIDENCE_READY. Chặn malformed pack/rawJSON/nhầmscope, nguồn conflict hoặcentityambiguous; không leak pack khi fail.

FixtureRetriever chọn pack theo canonical scope: totalassets BID30/06 ->validmetric; compareBIDVCB31/12 ->validcompare; annualFPT2025 ->validannual; các scope khác chỉempty nếu known metadata đủ để kết luậnfixturekhôngcó, không fallbacknearest. Không trả nhầmBID khiđổiVCB. Demo README nêu rõ fixture, lệnh test và Python example đủ chạy từfolder; chưa nối API/app/vector thật.

## Tiêu chí chung

Workers triển khai, testing độc lập thiết kế test, Codex kiểm tra candidate rủi ro rồi chạy argv cố định, reviewer model thứba xem receipts, Codex duyệt trước tích hợp. No failed/partial acceptance. Các giới hạn NLP deterministic phải ghi rõ, không claim toàn bộ48ca đặc tả tự động pass khichưa test.
