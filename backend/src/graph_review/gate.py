"""Short-lived, server-side approval snapshots for WBS08 writes and reads."""
from dataclasses import dataclass
from time import monotonic

from .adapters import from_envelope
from .models import digest
from .repository import approved_records


def core(candidate):
    # from_envelope always emits assertion_status (often None) while from_handoff
    # omits it; Candidate defaults it to None, so absent and None are the same claim.
    return {k: v for k, v in candidate.items() if k != "extractor_metadata"
            and not (k == "assertion_status" and v is None)}


@dataclass(frozen=True)
class ApprovalGate:
    graph_version_id: str
    allowed_relation_ids: frozenset[str]
    input_hash: str | None
    expires_at: float

    def validate(self, graph_id):
        if str(graph_id) != self.graph_version_id or monotonic() >= self.expires_at:
            raise PermissionError("WBS06 approval snapshot expired or belongs to another graph")

    def authorize(self, prepared):
        self.validate(prepared["graph_version_id"])
        if self.input_hash is None or prepared["input_hash"] != self.input_hash:
            raise PermissionError("WBS06 approval is not bound to this envelope")
        ids = {r["properties"]["relation_id"] for r in prepared["relations"]}
        if not ids <= self.allowed_relation_ids:
            raise PermissionError("WBS06: unapproved or stale relations cannot enter Neo4j")


async def build_gate(store, engine, graph_id, payload=None):
    records = await approved_records(store, engine, graph_id)
    allowed = {r["candidate"]["candidate_id"]: r["candidate"] for r in records}
    if payload is not None:
        for c in from_envelope(payload):
            relation = next(r for r in payload["relations"] if r["relation_id"] == c["candidate_id"])
            if relation["review"]["status"] == "APPROVED":
                if c["candidate_id"] not in allowed or digest(core(c)) != digest(core(allowed[c["candidate_id"]])):
                    raise PermissionError("WBS06: exported relation differs from reviewed evidence")
    return ApprovalGate(str(graph_id), frozenset(allowed), digest(payload) if payload else None, monotonic()+60)
