"""Keep extractor formats distinct; never manufacture hashes, pages or identity."""
from __future__ import annotations
from copy import deepcopy
import hashlib

from .models import digest


def entity(raw, registry):
    row = registry.rows.get(raw.get("entity_id"), {})
    return dict(entity_id=raw.get("entity_id", ""), entity_type=raw.get("entity_type", row.get("entity_type", "Company")),
                canonical_name=raw.get("canonical_name"), aliases=raw.get("aliases", []),
                identity_key=raw.get("identity_key", row.get("identity_key")),
                resolution_status=raw.get("resolution_status", "unresolved"))


def source_ref(source, quote, *, document_version=None, content_hash=None, page=None):
    locator = deepcopy(source.locator)
    if page is not None:
        locator["page"] = page
    return dict(document_id=source.document_id, document_version=document_version or source.document_version,
                chunk_id=source.chunk_id, corpus_id=source.corpus_id, index_version_id=source.index_version_id,
                content_hash=content_hash or source.content_hash, source_sha256=source.source_sha256,
                locator=locator, quote=quote)


async def from_handoff(payload, reader, registry):
    """The compact 23-candidate handoff omits full locators; replay DB to bind them.

    Original document/version/hash/page claims remain comparisons, not replaced
    by current values when they disagree. Missing DB binding never gets a fake.
    """
    output = []
    for raw in payload["candidates"]:
        evidence, failures = [], []
        for ev in raw.get("evidence", []):
            try:
                actual = await reader.read_current(ev["chunk_id"], payload["corpus_id"])
                ref = source_ref(actual, ev["quote"], document_version=raw["document"]["document_version"],
                                 content_hash=ev["content_hash"], page=ev.get("page"))
                ref["document_id"] = ev["document_id"]
                ref["index_version_id"] = payload["index_version_id"]
                evidence.append(ref)
            except Exception as exc:
                failures.append(getattr(exc, "code", "ERR_SOURCE_UNAVAILABLE"))
        output.append(dict(candidate_id=raw["relation_id"], group="company", relation_type=raw["relation_type"],
            subject=entity(raw["subject"], registry), object=entity(raw["object"], registry),
            evidence=evidence, attributes=deepcopy(raw.get("attributes", {})), temporal=raw.get("temporal", {}),
            extractor_metadata={"format": payload["schema"], "raw_sha256": digest(raw), "input_errors": failures}))
    return output


def from_envelope(payload):
    """WBS01/03 2.1.0 adapter. Schema errors are not source verification."""
    from ..sprint4_runtime.contracts import validate_envelope
    errors = []
    try:
        validate_envelope(payload)
    except (ValueError, TypeError, KeyError):
        errors.append("ERR_CONTRACT_INVALID")
    documents = {d["document_id"]: d for d in payload.get("documents", [])}
    chunks = {(c["document_id"], c["chunk_id"]): c for c in payload.get("chunks", [])}
    entities = {e["entity_id"]: e for e in payload.get("entities", [])}
    output = []
    for raw in payload.get("relations", []):
        evidence = []
        for ev in raw.get("evidence", []):
            chunk = chunks.get((ev["document_id"], ev["chunk_id"]), {})
            doc = documents.get(ev["document_id"], {})
            evidence.append({**ev, "document_version": doc.get("document_version"),
                "corpus_id": payload.get("corpus_id"), "index_version_id": payload.get("dataset_version"),
                # PDF 2.0 locators have no hash field. This is only a claim
                # computed from the exchanged text; the source reader must
                # still independently reconstruct and compare it.
                "content_hash": chunk.get("locator", {}).get("content_hash") or hashlib.sha256(
                    chunk.get("text", "").encode("utf-8")).hexdigest(),
                "source_sha256": doc.get("source_sha256"), "locator": chunk.get("locator", {})})
        kind = raw["relation_type"]
        group = "person" if kind in ("HOLDS_ROLE", "APPOINTS", "DISMISSES") else "event" if kind == "INVOLVES" else "company"
        def endpoint(key):
            e = entities.get(raw.get(key), {})
            return {k: e.get(k) for k in ("entity_id", "entity_type", "canonical_name", "identity_key", "resolution_status")} | {"aliases": e.get("aliases", [])}
        output.append(dict(candidate_id=raw["relation_id"], group=group, relation_type=kind,
            subject=endpoint("subject_id"), object=endpoint("object_id"), evidence=evidence,
            attributes=raw.get("attributes", {}), temporal=raw.get("temporal", {}),
            assertion_status=raw.get("attributes", {}).get("assertion_status"),
            extractor_metadata={"format": "WBS01-2.1.0", "input_errors": errors, "raw_sha256": digest(raw)}))
    return output


def from_news_article(raw, registry):
    """WBS05/event_news 0.1. No corpus/locator is invented from article URL.

    The caller may subsequently attach independently replayed DB source refs.
    Subject tags, high confidence and dedup status never approve participation.
    """
    output = []
    for ev in raw.get("events", []):
        eid = f"event:{raw['article_id']}:{ev['local_event_id']}"
        for index, party in enumerate(ev.get("parties", [])):
            name = party.get("name_normalized") or party.get("name_raw") or "unknown"
            matches = [r for r in registry.rows.values() if name.casefold() in
                       {x.casefold() for x in [r["canonical_name"], *r.get("aliases", []), *r.get("ticker_aliases", [])]}]
            target = matches[0] if len(matches) == 1 else dict(entity_id="unresolved:"+name,
                entity_type="Company" if party.get("party_type") == "organization" else "Person",
                canonical_name=name, identity_key=None, aliases=[name])
            target = entity({**target, "resolution_status": "resolved" if len(matches) == 1 else "ambiguous"}, registry)
            output.append(dict(candidate_id=f"{eid}:party:{index}", group="event", relation_type="INVOLVES",
                subject=dict(entity_id=eid, entity_type="Event", canonical_name=ev.get("event_name"),
                    aliases=[], identity_key=None, resolution_status="unresolved"), object=target, evidence=[],
                temporal={"valid_from": ev.get("dates", {}).get("event_date_start")},
                attributes={"participant_role": party.get("role", "unspecified"), "event_type": ev.get("event_type"),
                    "event_status": ev.get("status"), "event_date_derived": ev.get("dates", {}).get("date_derived", False),
                    "needs_followup": ev.get("needs_followup", False)}, assertion_status=ev.get("status"),
                extractor_metadata={"format": "event_news-0.1", "article_id": raw["article_id"],
                    "original_quote": party.get("role_evidence"), "original_event": ev,
                    "raw_sha256": digest(ev), "input_errors": ["ERR_SOURCE_BINDING_MISSING"]}))
    return output
