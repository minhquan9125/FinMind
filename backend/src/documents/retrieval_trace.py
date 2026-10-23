"""Small, local JSONL trace for filtered vector retrieval.

Only the fields selected here are written. Questions, chunk text, locators,
connection strings and exception messages are intentionally excluded.
"""

import json
import logging
import math
import re
import uuid
from pathlib import Path


TRACE_FILE = Path(__file__).resolve().parents[2] / ".tmp" / "retrieval-traces.jsonl"
LOGGER = logging.getLogger("uvicorn.error")
SAFE_SCOPE = re.compile(r"^[A-Za-z0-9_.:-]{1,40}$")
SAFE_CODE = re.compile(r"^[A-Z0-9_]{1,60}$")


def _scope_value(value):
    if value is None:
        return None
    return value if SAFE_SCOPE.fullmatch(value) else "[redacted]"


def _uuid_value(value):
    try:
        return str(uuid.UUID(str(value))) if value else None
    except (TypeError, ValueError):
        return None


def write_retrieval_trace(data):
    """Write one bounded, sanitized trace; a file error must not break search."""
    rows = data.get("rows")
    ranked_hits = data.get("ranked_hits")
    completed = data["status"] in {"success", "empty"}
    hits = []
    if ranked_hits is not None:
        for row in ranked_hits:
            score = float(row["score"])
            hits.append({"chunk_id": _uuid_value(row["chunk_id"]),
                         "score": round(score, 6) if math.isfinite(score) else None})
    code = data.get("error_code")
    event = {
        "event": "vector_retrieval",
        "trace_id": data["trace_id"],
        "timestamp": data["timestamp"],
        "status": data["status"],
        "index_version_id": _uuid_value(data.get("index_version_id")),
        "corpus_version_id": _uuid_value(data.get("corpus_version_id")),
        "filters": {name: _scope_value(data.get(name))
                    for name in ("company_symbol", "period", "doc_type")},
        "top_k": data["top_k"],
        "preview_source_changed": data["preview_source_changed"],
        "embedding_ms": data.get("embedding_ms"),
        "retrieval_ms": data.get("retrieval_ms"),
        "total_ms": data["total_ms"],
        "hit_count": len(ranked_hits) if ranked_hits is not None else None,
        "returned_hit_count": len(rows or []) if completed else None,
        "hits": hits,
        "unverified_hit_count": sum(not row.get("source_verified", True) for row in rows or [])
                                if completed else None,
        "error_code": code if code and SAFE_CODE.fullmatch(code) else None,
    }
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    LOGGER.info("retrieval_trace %s", line)
    try:
        TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_FILE.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
    except OSError:
        LOGGER.warning("retrieval_trace_file_unavailable")
