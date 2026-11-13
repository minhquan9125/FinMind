# WBS14 routed answer and citation handoff

## Inputs and outputs

Authenticated `/research` chat remains the entry point. VECTOR questions keep
the existing B1 retrieval, Gemini policy, prompt, token budget and citations.
BOTH questions use the same live router as `/api/hybrid-router/run`, and the
router result is composed into the saved assistant message. GRAPH questions
use the existing web chat graph retriever and its B1 answer path. The separate
BOTH inspection request is no longer sent by the web chat, so a BOTH answer
and its branch trace describe the same retrieval.

The BOTH B2 answer is **extractive**: one exact source line or graph quote per cited
claim, with `[n]` citations. It does not infer a numerical comparison or a
relationship from missing results. Every cited chunk is replayed through the
existing PostgreSQL source reconstruction reader in the pinned FROZEN corpus
and ACTIVE index. Document/chunk IDs, content hash, quote, corpus identity and
available source hash are checked before citation. Source records retain branch,
provenance, graph/index version, locator and title. The answer and source pack
are persisted in the same Postgres conversation turn.

If either required branch fails, a requested company/period is absent, source
replay fails, or the consolidation reports a version warning, the assistant
returns `INSUFFICIENT_EVIDENCE`, names the missing branch or scope, and makes no
factual claim. `NO_DATA` does not mean a relation is absent or a number is zero.
This deliberately leaves unsupported synthesis unfinished. Graph quotes keep
their original wording, including role, time and proposed/unconfirmed status;
the renderer does not promote an event to completed status.

Asking “nguồn câu trả lời trước” reads the saved `router-v1` pack and citation
bindings, with no router or source query. The UI labels this saved reference.
The B2 manifest keeps `b3_evidence_gate=false` and
`b3_answer_verification=false`; no B3 component is activated.

## Verification

Fixture tests: `backend/tests/test_routed_answer.py` and
`backend/tests/test_routed_chat_integration.py` cover VECTOR, GRAPH, BOTH,
branch failures, missing comparison company, source mismatch, tampered saved
citations, source follow-up, and live router wiring. Backend regression and
frontend build/test results on 2026-11-11: `backend/tests` 2,384 passed,
18 skipped; `src/b1_answering/tests` 129 passed, 2 skipped; frontend chat tests
20 passed; Vite production build
passed. Full `backend` discovery still includes legacy tests importing the
missing `hoi` module, so the reported regression uses the maintained suites.

Live acceptance needs both PostgreSQL and Neo4j tunnels, an authenticated
session, the pinned FROZEN corpus and READY graph version. Submit a GRAPH,
VECTOR and BOTH question, inspect each saved assistant result's route,
`routing.branch_states`, `routing.execution_trace`, citations, and source
locators. Verify every cited chunk against its pinned source and check the
requested company/period coverage. A fixture pass does not replace this live
check. This implementation does not provide a generated comparative summary;
that requires a separately approved B2 generation policy and evaluation.
