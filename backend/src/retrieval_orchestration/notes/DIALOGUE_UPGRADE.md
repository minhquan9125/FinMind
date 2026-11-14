# Nâng cấp hội thoại — hợp đồng hẹp

Only conversation.py and tests/test_dialogue_upgrade.py editable. Preserve current
public ChatSession(session_id=None,today:date=None), async ask(text)->11key envelope,
reset(), last_decision/last_result deepcopy properties, module render_response.
Core intent/contracts/orchestrator/fixtures unchanged, fixture-only stdlib.
Do not edit old tests or introduce new tickers/metric meanings, LLM/network/DB.

Current conversation source is provided. It wraps intent.analyze and orchestrate:
analyze(question,session,context=None) returns fullB1 dict with decision,slots,scope;
orchestrate(question,session,analyzer=callback) returns b1_decision STRING, status,
reason_code,scope,clarification,message,evidence_pack,etc. B1codes SEARCH,
ASK_CLARIFICATION,OUT_OF_SCOPE,UNSUPPORTED,SYSTEM_UNAVAILABLE. Same session and
confirmed/expired guards for explicit context. Four upstreammodules staged unchanged.
TICKERS10 VCB BID CTG MBB TCB FPT CMG ELC ITD ICT; METRICS4 totalassets/profitbefore/
profitafter/operatingcashflow. Missing generic profit must ask before/after tax.

Required upgrades, keep existing tests/semantics:
1. Combine clear short slot replies while pending: profit2025 → `BID, sau thuế`,
   `VCB năm 2024`, `sau thuế quý 2/2026` update ALL explicit slots and retain others.
2. Natural corrections `không, là VCB`, `ý tôi là năm 2024`, `còn VCB thì sao`,
   `đổi chỉ tiêu sang tổng tài sản` recognized with/without accents/casing. Only
   explicit correction/reference/clear slot reply may inherit; fresh question
   `Tổng tài sản FPT?` must ask period, not reuse oldyear. Do not infer arbitraryprose.
3. Multi conflicting choices (`BID hoặc VCB`, `trước thuế hay sau thuế`, 2different
   periods/entities) ask clarification, do not pick first or corrupt pending state.
   Unknown SSI in updates must be OOS, not silently reuse BID or addSSI toallowlist.
4. Explicit `năm nay`, `năm ngoái`/`năm trước`, `quý này`, `quý trước` resolve from
   injected session.today (default VietnamUTC+07), show resolved scope. Quarter
   rollover Jan2026 previousquarter=Q4/2025; no silent latest/date when absent.
   Keep invaliddate handling, exact day/quarter/YTD/full-year basis and entity.
5. Add context_summary()->str readable Vietnamese current active scope and next
   missing slot. No retrieval or mutation. After chatter summarize active query,
   after reset says no active query. /tomtat CLI will use this in next dependentjob.
6. Keep advice/news rejected, no fake financial numbers, no evidence bypass. Full
   compare/trend/BCTN unchanged, ambiguous abbreviated updates to complex scopes
   request full question rather than flattening to financial metric. Existing
   source-reference isolation remains. Preserve unrecognized chatter pending memory.
7. Compact coherent implementation (avoid copying whole original into helper files).
   Worker must return JSON only, exact allowlist. New tests actual upstream modules,
   no mock of entire system. No arbitrary commands/writes in this job.

Runtime preserved upstream4 modules verified by coordinator; manager exact candidate
hash applies to supplied files. Old tests normalize CRLF to LF before comparing
approved SHA; content verification remains. Baseline78PASS. New3RED scenarios are
the first3requirements above; don't just tailor strings to tests.
