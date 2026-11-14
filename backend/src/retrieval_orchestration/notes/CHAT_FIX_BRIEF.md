# Sửa hội thoại terminal theo phản hồi người dùng

Chỉ sửa hoi.py, retrieval_flow/conversation.py, tests/test_conversation.py.
Không sửa module intent/contracts/orchestrator, fixture hoặc tài liệu đầu vào.
Stdlib Python3.11+, không network/subprocess/filewrites trong sản phẩm/test.
Không LLM thật, không mở scope SSI hoặc bịa giá trị tài chính.

## Interface upstream đã đọc và kiểm chứng

retrieval_flow.intent: TICKERS tuple VCB BID CTG MBB TCB FPT CMG ELC ITD ICT.
METRICS dict TOTAL_ASSETS, PROFIT_BEFORE_TAX, PROFIT_AFTER_TAX,
CASH_FLOW_OPERATING -> tuple aliases không dấu (tong tai san, loi nhuan ...).
analyze(question, session_id, context=None) -> dict fields request_id/session_id,
original_question/normalized_question/intent/slots/decision/missing_fields/conflicts,
clarification_question/reason_code/corpus_version_id/scope.
slots.period: raw,year,quarter,start,end,granularity,measure_basis,origin.
scope: companies list, periods ISO list, metric_code,topic,measure_basis,
reporting_entity UNKNOWN|PARENT|CONSOLIDATED,source_type BCTC|BCTN.
Missing fields companies,period,metric.code,topic,period.measure_basis,reporting_entity.
Decisions SEARCH,ASK_CLARIFICATION,OUT_OF_SCOPE,UNSUPPORTED,RESOLVE_REFERENCE,
SYSTEM_UNAVAILABLE. Context strictly same session,confirmedTrue,expiredFalse,
explicit reference (cong ty nay,cung ky,con VCB), last_resolved_query stores full B1.
analyze understands explicit ISO-like d/m/yyyy, quy2/2026, nam2025, generic profit
ambiguous, no relative date, ten approved tickers caseinsensitive but unknown ticker
only detected uppercase and only after financial intent. Do not rely on that flaw.
clarify(previous,reply,session) exists but full metric reply resets company/period;
reconstructs year/ranges lossy. Do not blindly append conflicting year/company words.

async orchestrate(question,session_id,*,context=None,analyzer=analyze,retriever=None,
reference_resolver=None,timeout_seconds=1.0) -> fixed envelope11keys:
request_id,query_id,execution_mode FIXTURE,b1_decision,status,reason_code,message,
scope,clarification,evidence_pack,errors. A bound analyzer callback may return a
deepcopy of a precomputed decision so no upstream source changes needed.
Only SEARCH retrieves. EVIDENCE_READY validates pack, NO_DATA empty, INVALID_EVIDENCE_PACK,
INSUFFICIENT_EVIDENCE and SYSTEM_UNAVAILABLE distinguish other failures. No answer.
FixtureRetriever.retrieve exact matching packs: BID total assets30/06/2026,
BID/VCB total assets31/12/2025 comparison consolidated, FPT annual2025risk. All
other complete scopes NO_DATA. Source passages symbolic, no numerical answer.
FixtureReferenceResolver uses session+answer_id+evidence_id; no citations invented.
Actual approved modules/fixtures are staged read-only for runtime; verify pinned
SHA256 in tests before importing actual modules. Never replace them with stubs.

## Required public conversation API

class ChatSession(session_id=None, today=None): per-instance memory, no globals or disk;
today injectable datetime.date, default trusted local Vietnam UTC+07 date.
async ask(text:str)->dict returns normal envelope and updates latest explicit user
company/period/metric in pending conversation. Public last_decision stores full B1
decision for inspection. reset() clears all state. render_response(result:dict)->str
renders readable Vietnamese and short scope summary, never raw JSON by default.

## Behavior / acceptance / boundaries

- User transcript `lợi nhuân năm nay là bao nhiêu` (diacritic fold makes nhuan), then
  `BID`, then `sau thuế`: retain year and company; ask one missing field at a time,
  finally NO_DATA for fixture, not start over. Explicit `năm nay` uses injected date
  and shows resolved year; no silent latest default when no period supplied.
- Partial full metric phrase `lợi nhuận sau thuế` while pending must retain company/year.
  User corrections `đổi sang VCB`, `năm 2024`, `quý 2/2026` replace corresponding slot,
  do not concatenate conflicting old/new values. Preserve exact period/basis/entity.
- Only merge clear slot replies, corrections or explicit referents (`chủ đề trước`,
  `còn VCB`, `công ty này`). Fresh full question resets prior scope unless it refers
  back explicitly. Unrelated chatter does not become a metric query or erase pending.
- SSI/SSi/ssi is outside10ticker scope. `cho t xem lợi nhuận ssi` and standalone `SSi`
  during missing-company clarification report OUT_OF_SCOPE UNKNOWN_TICKER and nameSSI.
  Preserve pending other slots, allow correction to BID. Do not addSSI to supported list.
  Recognize unknown tickers in stock positions/standalone clarification, not arbitrary
  Vietnamese three-letter words (`nam`,`sau`,`cho`) as ticker. Unknown ticker must
  not silently reuse old company. Advice/news still rejected by upstream, not swallowed
  as slot replies. Same scope gates apply to BCTN/compare/trend; safely delegate these
  intact rather than flatten to financial metric.
- On referenced previous topic, recall only same ChatSession. New session/reset has
  no old slots. No financial answer or invented source. Evidence-ready text says
  `giả lập` and no real numeric financial answer. Default show useful message + captured
  company/period/metric in Vietnamese; ask only next missing field. No request IDs/hash
  or raw JSON except explicit `/json` command; `/json` shows last envelope, no retrieval.
- hoi.main() stays async, inputloop uses one ChatSession. `exit`/EOF/Ctrl+C graceful,
  `/moi` resets, `/json` debug. Blank input no state/retrieval. Header explains fixture.
  CLI runnable from project root with python -X utf8 backend/src/retrieval_orchestration/hoi.py.
- Tests actual modules, mock only terminal I/O/clock/adapters where needed; do not mock
  entire orchestrate for integration. Include multi-turn, overwrite, unrelated chatter,
  isolation/reset, unknown mixedcase, no JSON default and show JSON explicit, dates.

Red observed on unchanged CLI: tests/test_chat_regression.py all3fail (state lost,
rawJSON, lowercaseSSI misclassified). Fix these plus independent test suite.
No git commits per user. No requirement to pretend general NLP understanding; safely
ask when cannot parse. Keep implementation compact to fit worker context.
