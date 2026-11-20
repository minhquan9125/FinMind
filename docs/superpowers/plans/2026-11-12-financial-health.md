# Financial Health Implementation Plan

> For agentic workers: follow ECC manager stages; native exception only if unavailable routes are recorded. No price/shared source edits while Claude works.

**Goal:** đánh giá BCTC theo kỳ và vị thế từng chỉ tiêu cùng ngành, với căn cứ và trạng thái thiếu dữ liệu.
**Architecture:** pure Decimal company signals → peer comparisons → read-only snapshot adapter/report. Reuse financial.exact_json; no schema/API/UI dependency.
**Tech stack:** existing Python3/backend unittest/Decimal/json/asyncpg audit only.
**Spec:** docs/sprint5/financial-health/CONTRACT.md.

## Constraints / observed risks

VPS audit12Nov readonly:10companies cóBCTC,24mã giá mới chưa cóBCTC;1752selectedfacts từ2024. Hầu hết tới2026Q2,TCB tớiQ3. Financial report.statement_scope hiện chứa section, không chứng minh consolidated. Ratios SOURCE_NATIVE; source VIETCAP_VCI PENDING. FPT2026 đổi cách hợp nhất, CMC/ITD có fiscal year khác năm dương lịch. Vì thế UNKNOWN phải chặn so sánh, không certify nguồn hoặc tự sửa dữ liệu.

## FIN01 — Company signals
- [x] QA tests theo contract, quan sát RED trước production implementation.
- [x] Candidate financial/health.py, backend/tests/test_financial_health.py; metadata gates + Decimal math + BANK/TECH rules.
- [x] Fixed unittest runner; independent review + exact hash gate trước integration.

## FIN02 — Peer comparisons (depends FIN01)
- [x] Candidate financial/peers.py + test_financial_peers.py.
- [x] Median ngoài self, cùng kỳ/ngành/signature; minimum3; direction + provisional.
- [x] QA/review/run receipt như FIN01.

## FIN03 — Adapter and actual report (depends FIN01,FIN02)
- [x] Candidate financial/health_store.py, scripts/report_financial_health.py + tests/test_financial_health_store.py (3files; no old importer changes).
- [x] Exact DBrow adapter, unknown preserved; CLI snapshot→JSON/Markdown.
- [x] Run actual1752row snapshot, inspect limits; report no unsupported conclusion.

## Final integration
- [x] Integrate only7new code/test paths after review and source guards; audit/report files separate.
- [x] Combined tests + compile + source preservation guards; no market regressions unless shared paths change (they must not).
- [x] Financial checkpoint for Claude; do not edit shared price checkpoint while Claude may update it.

## Execution outcome12Nov

FIN01/02/03 and7file integration completed after nativeQA/review gates under recorded coordinator exception.52newtests/102combinedfinancialtests+65subtestsPASS; Q2/latest real10companyreports/sourceimmutability/Decimal evidence PASS. Reviewcorrected whitespace/provenance, exactfiscal labelconvention, domainbounds, partialpeercoverage andlegacyannualperiod. Source facts remain insufficient for actualdevelopment/stronger-company conclusions until reviewed metadata/restated comparatives arrive; not accepted as a completed financial ranking.

Broadercleaner16tests includes1oldfingerprinttestfail10subcases, isolatedreproducedwithouthealthimports andsourcehashbefore/afterunchanged. Nofixture/sourcebaseline rewrite. Separate financial-feature-verification.json labels corepass andlegacyfalse, preservesfullsuitefalse. Finalcheckpoint CHECKPOINT-BCTC-2026-11-12.md; reportpaths there. No market/shared edits orVPSwrites. Canonicalworkflowqueued/noAPIinference; native2helpers/5turns/usageunknown, shared24call7200s unchanged.

Shared workflow s5-financial-health-20261112 budget24helper calls/7200seconds, max2repair rounds per job; usage unknown stays unknown. Old price/live workflows and quarantined leases untouched. Skill discovery searched financial/accounting: suggestions were fundraising/competitive landscape and not relevant; no hidden skill enabled. Guidance: coding-standards, tdd-workflow, agentic-engineering. Domain references IAS34(IFRS)/bank FSIs(IMF); project data not assumed IFRS-compliant merely from methodology reference.
