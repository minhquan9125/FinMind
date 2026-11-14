# Approved unchanged runtime interfaces for the final job

This is a coordinator-verified interface excerpt of approved upstream candidates,
not a stub implementation. Tests run the actual pinned modules staged alongside
the candidate. Do not overwrite these dependencies; they are read-only. Test setup
MUST assert SHA256 of the three files below against these reviewed pins. This binds
the executed baseline to the already approved implementation instead of silently
mocking or changing it. On ordinary project integration these same files are present.

## Imports
from .contracts import load_fixtures, validate_pack, check_evidence
from .intent import analyze
Package is retrieval_flow, a namespace package. All code Python3.11+ stdlib-only.

## load_fixtures() -> dict
Reads an independent JSON copy from fixtures.json beside contracts.py, never writes.
Root: execution_mode FIXTURE, corpus_version fixture-corpus-v1, index_version
fixture-index-v1, corpus_to_index {fixture-corpus-v1:fixture-index-v1}, registry,
packs. packs keys valid_metric (BID TOTAL_ASSETS30/06/2026), valid_compare
(BID/VCB TOTAL_ASSETS31/12/2025), valid_annual (FPT2025topicquan_tri_rui_ro), empty.
Registry includes company,period_end,metric_code/topic,measure_basis,
reporting_entity,unit,source_type,source_id,source_sha256,locator,passage,
index_version,value_token per chunk_id; all synthetic and explicitly fixture.

## validate_pack(object) -> list[{code,path,message}]
No mutation, [] iff structurally valid. Exact WBS08 names schema_version1.0,
query_id nonblank, data_version.kindINDEX/id not latest, items[]. Each item has
unique evidence_id,chunk_id,source_id,source_sha25664hex,source_typeBCTC/BCTN,
locator(page_numberpositiveintnotbool or nonblanktable_id; both if present valid),
passage nonblank,score.typeCOSINE_SIMILARITY/valuefinite[-1,1]notbool/string.
One invalid item fails the whole pack. Never assume JSON validity proves provenance.

## check_evidence(pack,scope,registry) -> list[{code,path,message}]
Scope dict: companies:[ticker],periods:[ISOdate],metric_code:str|null,topic:str|null,
measure_basis POINT_IN_TIME/STANDALONE_QUARTER/YTD/FULL_YEAR/NOT_APPLICABLE,
reporting_entity UNKNOWN/CONSOLIDATED/PARENT,source_typeBCTC/BCTN, optionalunit.
Verifies index and source/hash/locator/passage binding, all scope fields, complete
company×period coverage, metadata present and no conflicting values. UNKNOWN can
use a single explicit evidence entity but cannot silently choose between entities.
[] only when all evidence matches and suffices. Empty pack yields coverage error
here, so orchestrator must detect structurally valid items=[] and return NO_DATA
before calling this gate. Nonempty gate errors -> INSUFFICIENT_EVIDENCE.

## analyze(question,session_id,context=None) -> dict (sync deterministic)
Decision exactly SEARCH,ASK_CLARIFICATION,OUT_OF_SCOPE,UNSUPPORTED,
SYSTEM_UNAVAILABLE,RESOLVE_REFERENCE. Contains request_id/session_id, intent,
slots, scope(canonical above), reason_code, clarification_question, missing_fields,
conflicts, corpus_version_id fixture-corpus-v1, original/normalizedquestion.
No answer or financial value. Confirmed unexpired context same session required
for explicit references. Reference question requires context.reference dict with
answer_id/evidence_id plus context.session_id matching and expiredFalse; reference
dict appears at b1['slots']['reference']. NonSEARCH must never invoke retrieval.
clarify(previous,reply,session_id) returns the same result shape for pending slots,
but orchestrator need not add its own pending-state persistence or UI.

## Fixture selection
You may choose only among predefined packs by exact matching through gate, except
empty fallback. Never alter periods/company/metric or fabricate a nearest result.
Set returned query_id to this request and verify pinned index. Do not change
registry. Hash/type/binding tests use copies or injected adapters for errors.

## Output and timeout
Follow ORCHESTRATION_BRIEF.md fixed public async APIs and envelope keys. Mark
execution_mode FIXTURE. EVIDENCE_READY is not a financial answer. For REFERENCE_READY
put the resolved fixture reference in scope['reference']; evidence_pack staysNone.
Resolver store keys(session_id,answer_id,evidence_id), no cross-session fallback.
Always validate a referenced record's declared IDs against the requested IDs.
Use a cooperative async adapter, wait_for and post-await monotonic deadline check;
propagate caller cancellation, no detached background tasks, no implicit retries.
Never expose rawexception text or invalid pack as successful evidence.

## Reviewed runtime SHA256 pins
```json
{
  "retrieval_flow/contracts.py": "10b580d1dbc6657d38540fc1f9f1506e975757d468c7db81708a71a5451b6910",
  "retrieval_flow/fixtures.json": "f4cc6896fe141834a9e002beb306362af624ed6fe4df9b0b98ab8ee1a3a1096d",
  "retrieval_flow/intent.py": "8d1f077bb22b5adcbdf09f2534a45fb979b760dc963cfd0b1de260dcde3d014e"
}
```
