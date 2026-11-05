"""Replay Sprint 4 graph citations from the pinned PostgreSQL corpus."""

from __future__ import annotations

from hashlib import sha256

from ...graph_review.models import SourceProblem


async def verify_relation_paths(paths, reader):
    """Return citations only when every edge source still matches its pinned chunk.

    ``reader`` is a PostgresSourceReader inside a read-only transaction. Keeping
    this separate from Neo4j retrieval also makes the verification easy to test.
    """
    citations = []
    for path in paths:
        version = path.get("graph_version_id")
        if not version or not isinstance(path.get("relations"), list):
            raise SourceProblem("GRAPH_INVALID_PATH")
        for edge in path["relations"]:
            corpus_id = edge.get("corpus_id")
            index_id = edge.get("index_version_id")
            sources = edge.get("evidence")
            if not all((edge.get("relation_id"), corpus_id, index_id, sources)):
                raise SourceProblem("GRAPH_EVIDENCE_MISSING")
            for source in sources:
                if not isinstance(source, dict) or not all(
                    source.get(field) for field in
                    ("document_id", "chunk_id", "document_version", "locator", "quote")
                ):
                    raise SourceProblem("GRAPH_EVIDENCE_MISSING")
                actual = await reader.read_current(source["chunk_id"], corpus_id)
                if (actual.verification_mode != "LIVE" or not actual.active
                        or actual.document_id != source["document_id"]
                        or actual.chunk_id != source["chunk_id"]
                        or actual.document_version != source["document_version"]
                        or actual.corpus_id != corpus_id
                        or actual.index_version_id != index_id
                        or actual.locator != source["locator"]
                        or actual.content_hash != sha256(actual.text.encode("utf-8")).hexdigest()
                        or source["quote"] not in actual.text):
                    raise SourceProblem("GRAPH_SOURCE_MISMATCH")
                citations.append({
                    "relation_id": edge["relation_id"],
                    "document_id": actual.document_id,
                    "chunk_id": actual.chunk_id,
                    "document_version": actual.document_version,
                    "corpus_version_id": corpus_id,
                    "index_version_id": index_id,
                    "graph_version_id": version,
                    "locator": actual.locator,
                    "quote": source["quote"],
                    "content_hash": actual.content_hash,
                    "source_verified": True,
                    "label": "LIVE/GRAPH",
                })
    return tuple(citations)
