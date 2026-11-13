"""WBS12 graph adapter seam. Query and source readers are injected by WBS09.

This module does not open Neo4j/PostgreSQL or generate Cypher. Its small row
contract is provisional until WBS09 exposes a real retrieval function.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Callable

from .adapters import AdapterResult
from .schemas import RouterTask


class Sprint4GraphAdapter:
    """Turn a router GRAPH task into verified, approved graph evidence."""

    OPERATIONS = {"find_relationships", "resolve_event_entities"}

    def __init__(
        self,
        query_fn: Callable[[dict[str, Any]], list[dict[str, Any]]],
        read_source_fn: Callable[[str, str, str], dict[str, Any]],
        *,
        graph_version_id: str,
        corpus_version_id: str,
    ) -> None:
        self.query_fn = query_fn
        self.read_source_fn = read_source_fn
        self.graph_version_id = graph_version_id
        self.corpus_version_id = corpus_version_id
        self.calls: list[dict[str, Any]] = []

    @staticmethod
    def _result(task: RouterTask, status: str, reason: str) -> AdapterResult:
        return AdapterResult(task.id, "GRAPH", status, reason, provenance="LIVE/GRAPH")

    def execute(self, task: RouterTask, *, dependency: AdapterResult | None = None) -> AdapterResult:
        if task.adapter != "GRAPH":
            raise ValueError("Sprint4GraphAdapter only accepts GRAPH tasks")
        if task.operation not in self.OPERATIONS:
            return self._result(task, "SYSTEM_UNAVAILABLE", "GRAPH_OPERATION_UNSUPPORTED")
        companies = task.params.get("companies") or []
        periods = task.params.get("periods") or []
        if not self.graph_version_id or not self.corpus_version_id:
            return self._result(task, "SYSTEM_UNAVAILABLE", "GRAPH_VERSION_REQUIRED")
        if not companies and not task.params.get("entity_mentions"):
            return self._result(task, "INSUFFICIENT_EVIDENCE", "GRAPH_ENTITY_SCOPE_MISSING")
        request = {
            "operation": task.operation,
            "companies": list(companies),
            "periods": list(periods),
            "topic": task.params.get("topic"),
            "entity_mentions": list(task.params.get("entity_mentions") or []),
            "question": task.params.get("question"),
            "graph_version_id": self.graph_version_id,
            "corpus_version_id": self.corpus_version_id,
        }
        self.calls.append(request)
        try:
            rows = self.query_fn(request)
        except TimeoutError:
            return self._result(task, "SYSTEM_UNAVAILABLE", "GRAPH_TIMEOUT")
        except Exception:
            return self._result(task, "SYSTEM_UNAVAILABLE", "GRAPH_QUERY_FAILED")
        if not isinstance(rows, list):
            return self._result(task, "SYSTEM_UNAVAILABLE", "GRAPH_INVALID_RESPONSE")

        data: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                return self._result(task, "INSUFFICIENT_EVIDENCE", "GRAPH_INVALID_RELATION")
            if row.get("review_status") != "APPROVED":
                continue
            if (row.get("graph_version_id") != self.graph_version_id
                    or row.get("corpus_version_id") != self.corpus_version_id):
                return self._result(task, "INSUFFICIENT_EVIDENCE", "GRAPH_VERSION_MISMATCH")
            matched = row.get("matched_companies")
            if companies and (not isinstance(matched, list)
                              or not set(companies).intersection(matched)
                              or not set(matched).issubset(companies)):
                return self._result(task, "INSUFFICIENT_EVIDENCE", "GRAPH_COMPANY_SCOPE_MISMATCH")
            if periods == ["LATEST_AVAILABLE_PERIOD"] and not row.get("matched_period"):
                return self._result(task, "INSUFFICIENT_EVIDENCE", "GRAPH_PERIOD_SCOPE_MISMATCH")
            if periods and periods != ["LATEST_AVAILABLE_PERIOD"]:
                matched_period = row.get("matched_period")
                if matched_period not in periods:
                    return self._result(task, "INSUFFICIENT_EVIDENCE", "GRAPH_PERIOD_SCOPE_MISMATCH")
            sources = row.get("evidence")
            if (not row.get("relation_id") or not row.get("subject_id")
                    or not row.get("object_id") or not row.get("relation_type")
                    or not isinstance(sources, list) or not sources):
                return self._result(task, "INSUFFICIENT_EVIDENCE", "GRAPH_EVIDENCE_MISSING")
            relation_evidence = []
            for source in sources:
                if not isinstance(source, dict):
                    return self._result(task, "INSUFFICIENT_EVIDENCE", "GRAPH_EVIDENCE_MISSING")
                document_id = source.get("document_id")
                chunk_id = source.get("chunk_id")
                quote = source.get("quote")
                if not all(isinstance(x, str) and x for x in (document_id, chunk_id, quote)):
                    return self._result(task, "INSUFFICIENT_EVIDENCE", "GRAPH_EVIDENCE_MISSING")
                try:
                    replay = self.read_source_fn(document_id, chunk_id, self.corpus_version_id)
                except TimeoutError:
                    return self._result(task, "SYSTEM_UNAVAILABLE", "GRAPH_SOURCE_TIMEOUT")
                except Exception:
                    return self._result(task, "INSUFFICIENT_EVIDENCE", "GRAPH_SOURCE_UNAVAILABLE")
                if (not isinstance(replay, dict) or replay.get("document_id") != document_id
                        or replay.get("chunk_id") != chunk_id
                        or replay.get("corpus_version_id") != self.corpus_version_id
                        or not isinstance(replay.get("chunk_text"), str)
                        or quote not in replay["chunk_text"] or not replay.get("locator")
                        or replay.get("content_hash") != sha256(
                            replay["chunk_text"].encode("utf-8")).hexdigest()):
                    return self._result(task, "INSUFFICIENT_EVIDENCE", "GRAPH_SOURCE_MISMATCH")
                citation = {
                    "source_id": f"{row['relation_id']}:{document_id}:{chunk_id}",
                    "relation_id": row["relation_id"], "document_id": document_id,
                    "chunk_id": chunk_id, "quote": quote, "locator": replay["locator"],
                    "content_hash": replay.get("content_hash"),
                    "corpus_version_id": self.corpus_version_id,
                    "source_verified": True, "label": "LIVE/GRAPH",
                }
                relation_evidence.append(citation)
            data.append({key: row.get(key) for key in (
                "relation_id", "relation_type", "subject_id", "object_id", "path",
                "temporal", "matched_companies", "matched_period")})
            evidence.extend(relation_evidence)
        if not data:
            return self._result(task, "NO_DATA", "GRAPH_NO_APPROVED_RELATIONS")
        return AdapterResult(task.id, "GRAPH", "OK", "GRAPH_RELATIONS_OK",
                             evidence=tuple(evidence), data=tuple(data), provenance="LIVE/GRAPH")
