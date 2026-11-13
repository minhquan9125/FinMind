"""Branch-aware evidence consolidation for hybrid retrieval."""

from __future__ import annotations

from typing import Any


def consolidate(decision: Any, results: tuple[Any, ...]) -> dict[str, Any]:
    """Rank by within-branch position, retaining every contributing source.

    Adapter scores have different meanings. Reciprocal rank fusion uses only
    ordinal positions, with no arithmetic on cosine, RRF or graph scores.
    """
    completed = {result.task_id: result for result in results}
    branches: dict[str, dict[str, Any]] = {}
    trace = []
    rejected = []
    alignment_warnings = []
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for task in decision.tasks:
        branch = "GRAPH" if task.adapter == "GRAPH" else "VECTOR"
        result = completed.get(task.id)
        if result is None:
            state = "SKIPPED_DEPENDENCY" if task.depends_on else "NOT_RUN"
            reason = "DEPENDENCY_NOT_OK" if task.depends_on else "EXECUTION_STOPPED"
            branches[branch] = {"status": state, "reason_code": reason, "evidence_count": 0}
            trace.append({"task_id": task.id, "branch": branch, "operation": task.operation,
                          "executed": False, "depends_on": task.depends_on})
            continue
        trace.append({"task_id": task.id, "branch": branch, "operation": task.operation,
                      "executed": True, "depends_on": task.depends_on,
                      "status": result.status, "reason_code": result.reason_code,
                      "provenance": result.provenance})
        branches[branch] = {"status": result.status, "reason_code": result.reason_code,
                            "evidence_count": len(result.evidence)}
        allowed_companies = set(task.params.get("resolved_companies") or task.params.get("companies") or [])
        allowed_periods = set(task.params.get("periods") or [])
        for rank, item in enumerate(result.evidence, 1):
            company = item.get("company") or item.get("symbol")
            period = item.get("period")
            if branch == "VECTOR" and ((company and allowed_companies and company not in allowed_companies)
                                       or (period and allowed_periods and period not in allowed_periods)):
                rejected.append({"task_id": task.id, "source_id": item.get("source_id"),
                                 "reason_code": "EVIDENCE_OUT_OF_SCOPE"})
                continue
            if not item.get("source_id") or not item.get("source_verified"):
                rejected.append({"task_id": task.id, "source_id": item.get("source_id"),
                                 "reason_code": "EVIDENCE_UNVERIFIED"})
                continue
            # A source chunk may be reached through both a graph edge and vector.
            key = (("chunk", str(item["chunk_id"])) if item.get("chunk_id")
                   else ("source", str(item["source_id"])))
            previous = merged.get(key)
            if previous:
                version_fields = ("document_version", "dataset_version", "source_sha256", "corpus_version_id")
                comparable = set()
                conflict = False
                for source in previous["sources"]:
                    for field in version_fields:
                        if source.get(field) and item.get(field):
                            comparable.add(field)
                            conflict |= source[field] != item[field]
                if conflict:
                    rejected.append({"task_id": task.id, "source_id": item["source_id"],
                                     "reason_code": "EVIDENCE_VERSION_MISMATCH"})
                    continue
                if not comparable and branch not in previous["branches"]:
                    # Same chunk ID alone cannot prove that two releases agree.
                    alignment_warnings.append({"chunk_id": item["chunk_id"],
                                               "reason_code": "CROSS_BRANCH_VERSION_UNVERIFIED"})
                    key = ("unverified_chunk", f"{item['chunk_id']}:{task.id}:{item['source_id']}")
            entry = merged.setdefault(key, {"evidence_id": ":".join(key), "branches": [],
                                            "provenance": [], "sources": [], "score": 0.0})
            entry["score"] += 1 / (60 + rank)
            if branch not in entry["branches"]:
                entry["branches"].append(branch)
            if result.provenance not in entry["provenance"]:
                entry["provenance"].append(result.provenance)
            entry["sources"].append({**item, "branch": branch, "provenance": result.provenance,
                                     "task_id": task.id,
                                     "rank_in_branch": rank})
        rejected_count = sum(row["task_id"] == task.id for row in rejected)
        if rejected_count:
            accepted_count = len(result.evidence) - rejected_count
            branches[branch] = {
                "status": "PARTIAL" if accepted_count else "INSUFFICIENT_EVIDENCE",
                "reason_code": "EVIDENCE_FILTERED",
                "evidence_count": accepted_count,
                "rejected_count": rejected_count,
                "adapter_status": result.status,
            }
    evidence = sorted(merged.values(), key=lambda row: (-row["score"], row["evidence_id"]))
    for position, row in enumerate(evidence, 1):
        row["rank"] = position
        row["rank_method"] = "RRF_BY_BRANCH_RANK_K60"
    return {"evidence": evidence, "branch_states": branches, "execution_trace": trace,
            "rejected_evidence": rejected, "alignment_warnings": alignment_warnings}
