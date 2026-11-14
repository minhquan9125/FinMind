"""WBS15 Graph Viewer API: read-only, READY graph versions only (docs/sprint4/WBS15-graph-viewer-api-contract.md)."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from starlette.concurrency import run_in_threadpool

from ...auth.authorization import READ_ROLES, require_roles
from ...core.db import get_pool
from ...graph.relation_retrieval import RELATION_TYPES
from ...graph.viewer import GraphViewerReader, NODE_TYPES, SOURCE_SCOPE, SOURCE_TYPES, VersionNotFound, VersionNotReady

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/graph", tags=["graph-viewer"], dependencies=[Depends(require_roles(*READ_ROLES))])


def _error(status, code, message):
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@lru_cache(maxsize=1)
def _reader() -> GraphViewerReader:
    from ...graph.graph_store import GraphStore
    store = GraphStore.from_environment()
    return GraphViewerReader(store.driver, database=store.database)


def get_graph_reader() -> GraphViewerReader:
    try:
        return _reader()
    except Exception as exc:
        logger.warning("Graph viewer: Neo4j unavailable: %s", exc)
        raise _error(503, "GRAPH_UNAVAILABLE", "Không kết nối được graph.") from exc


@lru_cache(maxsize=1)
def _tickers_by_entity() -> dict[str, str]:
    from .hybrid_router import _registry_tickers
    return {entity_id: ticker for ticker, entity_id in _registry_tickers().items()}


def get_ticker_map() -> dict[str, str]:
    return _tickers_by_entity()


async def _lookup_sources(chunk_ids: list[str]) -> dict[str, dict]:
    ids = []
    for chunk_id in chunk_ids:
        try:
            ids.append(uuid.UUID(chunk_id))
        except ValueError:
            continue  # PDF-fixture chunk IDs have no DB row; reported as DOCUMENT_NOT_FOUND
    if not ids:
        return {}
    rows = await get_pool().fetch(
        """SELECT t.chunk_id::text AS chunk_id, d.doc_type, d.title, d.source_url
           FROM text_chunks t JOIN documents d USING (document_id)
           WHERE t.chunk_id = ANY($1::uuid[])""", ids)
    return {row["chunk_id"]: dict(row) for row in rows}


def get_source_lookup():
    return _lookup_sources


def _call(fn, *args, **kwargs):
    """Map driver failures to the contract's error codes."""
    try:
        return fn(*args, **kwargs)
    except VersionNotFound as exc:
        raise _error(404, "GRAPH_VERSION_NOT_FOUND", "Không tìm thấy phiên graph.") from exc
    except VersionNotReady as exc:
        raise _error(409, "GRAPH_VERSION_NOT_READY", "Phiên graph chưa được công bố.") from exc
    except (ServiceUnavailable, SessionExpired) as exc:
        raise _error(503, "GRAPH_UNAVAILABLE", "Không kết nối được graph.") from exc
    except Neo4jError as exc:
        # Neo4j 5+: ClientError ...TransactionTimedOutClientConfiguration; older: TransientError ...TransactionTimedOut
        if "TimedOut" in (exc.code or ""):
            raise _error(504, "GRAPH_TIMEOUT", "Truy vấn graph quá thời gian.") from exc
        raise


def _version(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        # WBS08 test versions may use readable IDs; keep them but bound their size.
        if not value.strip() or len(value) > 100:
            raise _error(400, "INVALID_PARAMETER", "graph_version_id không hợp lệ.") from None
        return value


def _day(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise _error(400, "INVALID_PARAMETER", f"{name} phải có dạng YYYY-MM-DD.") from None


def _with_ticker(node: dict, tickers: dict[str, str]) -> dict:
    ticker = tickers.get(node["id"]) or node["attributes"].get("symbol")
    detail = ticker or node["attributes"].get("event_type")
    return {**node, "ticker": ticker, "detail": detail}


@router.get("/versions")
def list_versions(reader: GraphViewerReader = Depends(get_graph_reader)) -> dict:
    return {"versions": _call(reader.versions)}


@router.get("/entities")
def search_entities(
    graph_version_id: str,
    q: str = Query("", max_length=100),
    type: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    reader: GraphViewerReader = Depends(get_graph_reader),
    tickers: dict = Depends(get_ticker_map),
) -> dict:
    if type is not None and type not in NODE_TYPES:
        raise _error(400, "INVALID_PARAMETER", "type phải là Company, Person hoặc Event.")
    version = _version(graph_version_id)
    meta = _call(reader.ready_version, version)
    query = q.strip()
    # A ticker is not stored on Neo4j nodes; resolve it through the same registry as the router.
    by_ticker = {t: e for e, t in tickers.items()}
    resolved = query if meta.get("serving_scope") == SOURCE_SCOPE else by_ticker.get(query.upper(), query)
    items, truncated = _call(reader.entities, version, resolved, type, limit)
    return {"meta": meta,
            "items": [_with_ticker(item, tickers) for item in items], "truncated": truncated}


@router.get("/neighborhood")
def neighborhood(
    graph_version_id: str,
    entity_id: str = Query(..., min_length=1, max_length=200),
    hops: int = Query(2, ge=1, le=2),
    relation_type: list[str] = Query(default=[]),
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    reader: GraphViewerReader = Depends(get_graph_reader),
    tickers: dict = Depends(get_ticker_map),
) -> dict:
    if not set(relation_type) <= RELATION_TYPES | SOURCE_TYPES:
        raise _error(400, "INVALID_PARAMETER", "relation_type không hợp lệ.")
    start, end = _day(from_, "from"), _day(to, "to")
    if start and end and start > end:
        raise _error(400, "INVALID_PARAMETER", "from phải trước hoặc bằng to.")
    version = _version(graph_version_id)
    meta = _call(reader.ready_version, version)
    allowed = SOURCE_TYPES if meta.get("serving_scope") == SOURCE_SCOPE else RELATION_TYPES
    if not set(relation_type) <= allowed:
        raise _error(400, "INVALID_PARAMETER", "relation_type không thuộc contract của phiên graph.")
    root = _call(reader.nodes, version, [entity_id]).get(entity_id)
    if root is None:
        raise _error(404, "ENTITY_NOT_FOUND", "Thực thể không có trong phiên graph này.")
    edges, truncated = _call(reader.neighborhood, version, entity_id, hops=hops,
                             relation_types=relation_type or None, start=start, end=end, limit=limit)
    ids = {entity_id} | {i for e in edges for i in (e["subject_id"], e["object_id"])}
    nodes = _call(reader.nodes, version, ids)
    return {
        "meta": {**meta, "root_id": entity_id, "hops": hops,
                 "filters": {"relation_type": relation_type, "from": start, "to": end},
                 "limit": limit, "truncated": truncated},
        "nodes": [_with_ticker(nodes[i], tickers) for i in sorted(ids) if i in nodes],
        "edges": [{
            "id": e["relation_id"], "source": e["subject_id"], "target": e["object_id"],
            "type": e["relation_type"], "attributes": e["attributes"],
            "temporal": {k: e[k] for k in ("as_of", "valid_from", "valid_to")},
            "review": {"status": e.get("review_status", "APPROVED"), "reviewer": e["reviewer"], "reviewed_at": e["reviewed_at"]},
            "evidence_count": len(e["evidence"]),
            "evidence_preview": ({"document_id": e["evidence"][0]["document_id"],
                                  "page": e["evidence"][0]["locator"].get("page"),
                                  "quote": e["evidence"][0]["quote"]} if e["evidence"] else None),
        } for e in edges],
    }


def _open(source: dict | None, locator: dict) -> dict:
    if source is None:
        return {"status": "UNAVAILABLE", "kind": None, "url": None, "page": None, "reason": "DOCUMENT_NOT_FOUND"}
    news = source["doc_type"] == "NEWS"
    kind = "WEB_ARTICLE" if news else "PDF_PAGE"
    page = None if news else locator.get("page")  # News has no PDF page; never invent one
    if not source["source_url"]:
        return {"status": "UNAVAILABLE", "kind": kind, "url": None, "page": page, "reason": "SOURCE_URL_MISSING"}
    return {"status": "AVAILABLE", "kind": kind, "url": source["source_url"], "page": page, "reason": None}


@router.get("/relations/{relation_id}")
async def relation_detail(
    relation_id: str,
    graph_version_id: str,
    reader: GraphViewerReader = Depends(get_graph_reader),
    lookup=Depends(get_source_lookup),
) -> dict:
    version = _version(graph_version_id)
    meta = await run_in_threadpool(_call, reader.ready_version, version)
    found = await run_in_threadpool(_call, reader.relation, version, relation_id)
    if found is None:
        raise _error(404, "RELATION_NOT_FOUND", "Quan hệ không thuộc phiên graph này.")
    rel = found["relation"]
    nodes = await run_in_threadpool(_call, reader.nodes, version, [found["subject_id"], found["object_id"]])
    evidence = json.loads(rel["evidence_json"])
    try:
        sources = await lookup([e["chunk_id"] for e in evidence])
    except Exception as exc:
        logger.warning("Graph viewer: source lookup failed: %s", exc)
        sources = {}
    endpoint = lambda i: {k: nodes.get(i, {}).get(k) for k in ("type", "label")} | {"id": i}
    return {
        "meta": meta,
        "relation": {
            "id": rel["relation_id"], "type": rel["relation_type"],
            "source": endpoint(found["subject_id"]), "target": endpoint(found["object_id"]),
            "attributes": json.loads(rel["attributes_json"]),
            "temporal": {k: rel.get(k) for k in ("as_of", "valid_from", "valid_to")},
            "review": {"status": rel.get("review_status", "APPROVED"), "reviewer": rel.get("reviewer"), "reviewed_at": rel.get("reviewed_at")},
            "extraction": {k: rel.get(k) for k in ("relation_id", "source_batch_id", "corpus_id", "index_version_id")},
        },
        "evidence": [{
            **e,
            "title": (sources.get(e["chunk_id"]) or {}).get("title"),
            "doc_type": (sources.get(e["chunk_id"]) or {}).get("doc_type"),
            "open": _open(sources.get(e["chunk_id"]), e["locator"]),
        } for e in evidence],
    }
