# WBS10 BOTH evidence handoff to WBS14/WBS17

**2026-11-13 integration update:** The web chat persists an extractive BOTH
answer and its replayed citations in the conversation result. GRAPH-only
questions retain the existing web chat graph answer path. The separate
inspection panel described later in this historical handoff has been replaced
by branch status and trace shown with the saved answer. See
`docs/sprint4/WBS14-routed-answer-handoff.md` for the current contract and the
remaining live acceptance step.

`POST /api/hybrid-router/run` executes the routing plan in task order. A BOTH
content task depends on its Graph task. Only ticker aliases explicitly returned
as `resolved_companies` cross that boundary. The live factory already wires the
WBS11 graph relation adapter and WBS12 vector retriever; unavailable services
return branch-specific failure codes.

The response contains `branch_states`, `execution_trace`, `evidence`, and
`rejected_evidence`. `execution_trace.executed` records each adapter invocation;
an uninvoked dependent branch is `SKIPPED_DEPENDENCY`. A branch can retain its
evidence even if another branch has `NO_DATA`, `INSUFFICIENT_EVIDENCE`, or
`SYSTEM_UNAVAILABLE`. The top-level status still reports the failure.

Each merged evidence item retains `sources` with original source ID, task ID,
branch, provenance, and local rank. A shared `chunk_id` is deduplicated while
keeping both source records. Ranking uses reciprocal rank fusion with k=60 on
branch-local rank; raw vector and graph scores are never added. Evidence with
an explicit company or period outside the content task scope, an unverified
source, or a conflicting version for the same chunk is rejected and reported.
When the two branches cite the same chunk but expose no comparable version
field, their evidence stays separate and `alignment_warnings` records the
unverified cross-branch alignment. The overall status is then
`INSUFFICIENT_EVIDENCE`, rather than claiming a verified merge.
The response becomes `INSUFFICIENT_EVIDENCE` when filtering removes evidence
from an otherwise successful run.

WBS14 can consume the common evidence list for answer/citation construction and
must inspect `branch_states` before claiming BOTH coverage. WBS17 can audit
`index_version_id`, `document_id`, `chunk_id`, `content_hash`, and the retained
provenance against the frozen corpus. Graph version and vector index version are
different identifier types and are deliberately kept separate; a common corpus
release ID is needed before asserting release-level agreement between branches.
The current `LiveGraphAdapter` uses pinned graph relation retrieval but does not
read each cited source chunk back through the WBS11 resolver before setting
`source_verified`; that verification and release-level alignment remain open
for live acceptance.

Fixture acceptance: `backend/tests/test_both_evidence.py` covers both calls,
dependency skip, deduplication, provenance, scope and version rejection. Real
WBS11/WBS12 acceptance still requires a configured READY graph version, ACTIVE
vector index, frozen corpus, and authenticated `/run` invocation in an
environment with both data services available.

The `/research` web chat now inspects each submitted question with `/test` as
soon as it is sent, independently of conversation persistence. When the route is BOTH it calls `/run` using the
same bearer token and displays branch states, trace, evidence count and a full
JSON detail view. The web request sets `require_live=true`; a mock backend returns
503 and cannot supply synthetic evidence to this panel. The inspection is separate from the chat answer and is not
stored in conversation history. This makes BOTH execution visible in the web
UI; WBS14 still owns composing an answer from this merged evidence.

## Local live enablement audit (2026-11-09)

`backend/.env` now sets `HYBRID_ROUTER_MODE=live` and pins
`SPRINT4_GRAPH_VERSIONS=s4-bctn-b2550a0b-v4-20261102`. The backend must restart
to pick up these values. The latest TCP probe found PostgreSQL's local tunnel
on port 15433 listening, while Neo4j's local tunnel on port 17687 was still
closed. The SSH account documented for the VPS rejected this machine's
noninteractive credentials. A listening PostgreSQL port alone does not prove
that the configured frozen corpus or ACTIVE vector index is readable. No live BOTH result was
obtained. The web panel explicitly labels MOCK output and LIVE service failures.
Keep live acceptance open until the owner starts the required tunnels or supplies
reachable service endpoints, then verifies two executed live branches and source
readback against the pinned corpus and graph release.

## Local live run (2026-11-10)

The PostgreSQL and Neo4j tunnels answered read-only probes. Local `backend/.env`
now pins frozen corpus `b2550a0b-c423-5c50-9b15-6fb6af12e2c6`, active index
`ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d`, and READY graph version
`s4-bctn-b2550a0b-v4-20261102`. The router reads the graph version through
the same settings loader as the other `.env` values. The verified lexical cache
contains 44,930 chunks; it is shared with the research chat and remains subject
to the frozen corpus fingerprint and source hash checks.

Direct live call with `require_live=true` for “TCB với FPT năm 2024 bên nào khỏe
hơn?” returned `BOTH`, `LIVE`, `OK`, `LIVE_EXECUTION_OK`. Both execution trace
entries have `executed=true`: GRAPH `GRAPH_RELATIONS_OK` (16 source records),
VECTOR `CONTENT_OK` (10 source records). Consolidation returned 16 evidence
items with both `LIVE/GRAPH` and `LIVE/VECTOR` source provenance, zero rejected
items, and zero alignment warnings. Backend regression: 273 focused tests pass;
frontend chat API: 14 tests pass.

This is a successful live smoke test for this question and release, not a scored
WBS17 acceptance set. Graph evidence source readback and release-level alignment
remain open as described above. WBS14 still needs to compose an answer from the
merged evidence; the web BOTH panel is a separate inspection result. Restart the
backend after changing `.env` or this code. The cache is local to this machine.
