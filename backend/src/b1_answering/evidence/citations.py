from copy import deepcopy
import re


class CitationError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _is_hex64(val: str) -> bool:
    return isinstance(val, str) and len(val) == 64 and bool(re.fullmatch(r"[0-9a-fA-F]{64}", val))


def prepare_evidence(pack: dict) -> dict[str, dict]:
    if not isinstance(pack, dict):
        raise CitationError("INVALID_EVIDENCE")
    if pack.get("conflicts"):
        raise CitationError("INVALID_EVIDENCE")
    if pack.get("schema_version") != "1.0":
        raise CitationError("INVALID_EVIDENCE")
    qid = pack.get("query_id")
    if not isinstance(qid, str) or not qid.strip():
        raise CitationError("INVALID_EVIDENCE")
    dv = pack.get("data_version")
    if not isinstance(dv, dict) or dv.get("kind") != "INDEX":
        raise CitationError("INVALID_EVIDENCE")
    dv_id = dv.get("id")
    if not isinstance(dv_id, str) or not dv_id.strip() or dv_id.strip() == "latest":
        raise CitationError("INVALID_EVIDENCE")

    items = pack.get("items")
    if not isinstance(items, list):
        raise CitationError("INVALID_EVIDENCE")
    if len(items) == 0:
        raise CitationError("NO_EVIDENCE")
    if len(items) > 30:
        raise CitationError("INVALID_EVIDENCE")

    out = {}
    for it in items:
        if not isinstance(it, dict):
            raise CitationError("INVALID_EVIDENCE")
        eid = it.get("evidence_id")
        sid = it.get("source_id")
        cid = it.get("chunk_id")
        pas = it.get("passage")
        sha = it.get("source_sha256")
        loc = it.get("locator")
        for s in (eid, sid, cid):
            if not isinstance(s, str) or not s.strip():
                raise CitationError("INVALID_EVIDENCE")
        if not isinstance(pas, str) or not pas.strip() or len(pas) > 12000:
            raise CitationError("INVALID_EVIDENCE")
        if not _is_hex64(sha):
            raise CitationError("INVALID_EVIDENCE")
        if not isinstance(loc, dict) or not loc:
            raise CitationError("INVALID_EVIDENCE")
        valid_loc = {}
        for k, v in loc.items():
            if k == "page_number":
                if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                    raise CitationError("INVALID_EVIDENCE")
                valid_loc[k] = v
            elif k == "table_id":
                if not isinstance(v, str) or not v.strip():
                    raise CitationError("INVALID_EVIDENCE")
                valid_loc[k] = v
            else:
                raise CitationError("INVALID_EVIDENCE")
        if eid in out:
            raise CitationError("INVALID_EVIDENCE")
        out[eid] = deepcopy(it)
    return out


def validate_draft(payload: dict, evidence: dict[str, dict]) -> dict:
    if not isinstance(payload, dict) or set(payload.keys()) != {"claims"}:
        raise CitationError("INVALID_CITATION")
    claims_in = payload.get("claims")
    if not isinstance(claims_in, list) or not (1 <= len(claims_in) <= 20):
        raise CitationError("INVALID_CITATION")

    validated_claims = []
    ordered_citations = []
    seen_cits = set()
    draft_parts = []

    for c in claims_in:
        if not isinstance(c, dict) or set(c.keys()) != {"text", "evidence_ids"}:
            raise CitationError("INVALID_CITATION")
        txt = c.get("text")
        eids = c.get("evidence_ids")
        if not isinstance(txt, str) or not (1 <= len(txt) <= 12000):
            raise CitationError("INVALID_CITATION")
        if not isinstance(eids, list) or len(eids) == 0:
            raise CitationError("INVALID_CITATION")
        if not all(isinstance(eid, str) and eid.strip() for eid in eids) or len(set(eids)) != len(eids):
            raise CitationError("INVALID_CITATION")
        for eid in eids:
            if not isinstance(eid, str) or not eid.strip() or eid not in evidence:
                raise CitationError("INVALID_CITATION")
            if txt not in evidence[eid]["passage"]:
                raise CitationError("UNSUPPORTED_CLAIM")
            if eid not in seen_cits:
                seen_cits.add(eid)
                ev = evidence[eid]
                ordered_citations.append({
                    "evidence_id": ev["evidence_id"],
                    "source_id": ev["source_id"],
                    "chunk_id": ev["chunk_id"],
                    "source_sha256": ev["source_sha256"],
                    "locator": deepcopy(ev["locator"]),
                })
        validated_claims.append({"text": txt, "evidence_ids": list(eids)})
        cit_tags = "".join(f"[{eid}]" for eid in eids)
        draft_parts.append(f"{txt} {cit_tags}")

    return {
        "status": "DRAFT_READY",
        "draft": "\n".join(draft_parts),
        "claims": validated_claims,
        "citations": ordered_citations,
    }


def resolve_citation(evidence_id: str, evidence: dict[str, dict]) -> dict:
    if not isinstance(evidence_id, str) or evidence_id not in evidence:
        raise CitationError("INVALID_CITATION")
    return deepcopy(evidence[evidence_id])
