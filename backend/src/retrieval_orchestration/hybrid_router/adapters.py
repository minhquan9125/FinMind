"""Deterministic mock adapters for the experimental hybrid router.

Nothing in this module calls a database or network.  Every returned item is
explicitly marked as synthetic fixture data so it cannot be confused with
LIVE evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol

from .schemas import RouterTask


AdapterStatus = Literal[
    "OK", "NO_DATA", "INSUFFICIENT_EVIDENCE", "SYSTEM_UNAVAILABLE"
]


@dataclass(frozen=True)
class AdapterResult:
    task_id: str
    adapter: Literal["GRAPH", "CONTENT"]
    status: AdapterStatus
    reason_code: str
    evidence: tuple[dict[str, Any], ...] = ()
    data: tuple[dict[str, Any], ...] = ()
    provenance: Literal["MOCK/FIXTURE", "LIVE/VECTOR", "LIVE/GRAPH"] = "MOCK/FIXTURE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RouterAdapter(Protocol):
    calls: list[dict[str, Any]]

    def execute(
        self, task: RouterTask, *, dependency: AdapterResult | None = None
    ) -> AdapterResult: ...


@dataclass
class _MockAdapterBase:
    calls: list[dict[str, Any]] = field(default_factory=list, init=False)

    def _record(
        self, task: RouterTask, dependency: AdapterResult | None
    ) -> None:
        self.calls.append(
            {
                "task_id": task.id,
                "operation": task.operation,
                "params": dict(task.params),
                "dependency_task_id": dependency.task_id if dependency else None,
                "provenance": "MOCK/FIXTURE",
            }
        )


class MockGraphAdapter(_MockAdapterBase):
    """Graph fixture with explicit G02/G04/G05 failure scenarios."""

    def execute(
        self, task: RouterTask, *, dependency: AdapterResult | None = None
    ) -> AdapterResult:
        if task.adapter != "GRAPH":
            raise ValueError("MockGraphAdapter only accepts GRAPH tasks")
        self._record(task, dependency)
        scenario = str(task.params.get("fixture_case", "G01")).upper()
        if scenario in {"G02", "B02"}:
            return AdapterResult(task.id, "GRAPH", "NO_DATA", "MOCK_GRAPH_NO_DATA")
        if scenario == "G04":
            return AdapterResult(
                task.id,
                "GRAPH",
                "INSUFFICIENT_EVIDENCE",
                "MOCK_SOURCE_ID_MISSING",
                data=({"company_id": "MOCK-SUB-01", "name": "Công ty con minh họa"},),
            )
        if scenario == "G05":
            return AdapterResult(
                task.id, "GRAPH", "SYSTEM_UNAVAILABLE", "MOCK_GRAPH_TIMEOUT"
            )
        if scenario == "G06":
            return AdapterResult(
                task.id,
                "GRAPH",
                "INSUFFICIENT_EVIDENCE",
                "MOCK_RELATION_OUTSIDE_EFFECTIVE_PERIOD",
            )
        company = (task.params.get("companies") or ["UNKNOWN"])[0]
        relation = {
            "parent_company": company,
            "company_id": f"MOCK-{company}-SUB-01",
            "name": f"Công ty con minh họa của {company}",
            "source_id": f"MOCK-SOURCE-{company}-REL-01",
        }
        return AdapterResult(
            task.id,
            "GRAPH",
            "OK",
            "MOCK_GRAPH_OK",
            evidence=(
                {
                    "source_id": relation["source_id"],
                    "source_verified": True,
                    "label": "MOCK/FIXTURE",
                },
            ),
            data=(relation,),
        )


class MockContentAdapter(_MockAdapterBase):
    """Content fixture with explicit V04/V05 failure scenarios."""

    def execute(
        self, task: RouterTask, *, dependency: AdapterResult | None = None
    ) -> AdapterResult:
        if task.adapter not in {"CONTENT", "VECTOR"}:
            raise ValueError("MockContentAdapter only accepts content tasks")
        self._record(task, dependency)
        scenario = str(task.params.get("fixture_case", "V01")).upper()
        if scenario == "V04":
            return AdapterResult(task.id, "CONTENT", "NO_DATA", "MOCK_CONTENT_NO_DATA")
        if scenario == "V05":
            return AdapterResult(
                task.id,
                "CONTENT",
                "INSUFFICIENT_EVIDENCE",
                "MOCK_SOURCE_ID_OR_HASH_MISSING",
                data=({"value": 100, "unit": "MOCK_UNIT"},),
            )
        if scenario == "B03":
            return AdapterResult(
                task.id,
                "CONTENT",
                "INSUFFICIENT_EVIDENCE",
                "MOCK_PARTIAL_COVERAGE",
                data=({"coverage": "PARTIAL", "missing_companies": ["MOCK-SUB-02"]},),
            )
        if scenario == "B04":
            return AdapterResult(
                task.id,
                "CONTENT",
                "INSUFFICIENT_EVIDENCE",
                "MOCK_DATASET_VERSION_MISMATCH",
            )
        if scenario == "B05":
            return AdapterResult(
                task.id, "CONTENT", "SYSTEM_UNAVAILABLE", "MOCK_CONTENT_TIMEOUT"
            )
        companies = list(task.params.get("companies") or [])
        if dependency is not None:
            companies = [str(row["company_id"]) for row in dependency.data]
        rows = tuple(
            {
                "company": company,
                "periods": list(task.params.get("periods") or []),
                "metric_code": task.params.get("metric_code"),
                "value": 100,
                "unit": "MOCK_UNIT",
            }
            for company in companies
        )
        evidence = tuple(
            {
                "source_id": f"MOCK-SOURCE-{index + 1}",
                "source_hash": f"MOCK-HASH-{index + 1}",
                "source_verified": True,
                "label": "MOCK/FIXTURE",
            }
            for index, _ in enumerate(rows)
        )
        return AdapterResult(
            task.id, "CONTENT", "OK", "MOCK_CONTENT_OK", evidence=evidence, data=rows
        )


class LiveContentAdapter:
    """Live content adapter: wraps HybridRetriever for real vector+BM25 retrieval.

    execute() is called from a worker thread (via asyncio.to_thread). It schedules
    the async search coroutine onto the main event loop via run_coroutine_threadsafe.
    """

    TIMEOUT_SECONDS = 30

    def __init__(
        self,
        search_fn,  # async callable: (question, company, period, top_k) -> dict
        event_loop,  # asyncio.AbstractEventLoop - main event loop
        *,
        top_k: int = 5,
    ) -> None:
        self._search_fn = search_fn
        self._loop = event_loop
        self._top_k = top_k
        self.calls: list[dict] = []

    def execute(
        self, task: RouterTask, *, dependency: AdapterResult | None = None
    ) -> AdapterResult:
        if task.adapter not in {"CONTENT", "VECTOR"}:
            raise ValueError("LiveContentAdapter only accepts content tasks")
        companies = list(task.params.get("companies") or [])
        if dependency is not None:
            companies = [str(row.get("company_id", row.get("company", ""))) for row in dependency.data]
        periods = list(task.params.get("periods") or [])
        company = companies[0] if len(companies) == 1 else None
        period = periods[0] if len(periods) == 1 else None
        # Normalize period: convert "2025-Q2" -> "2025-Q2" (OK), "2025" -> "2025" (OK)
        # HybridRetriever accepts YYYY and YYYY-Q[1-4]
        if period and period not in {
            "CURRENT", "LATEST_PUBLISHED_PERIOD", "LATEST_AVAILABLE_PERIOD",
            "CURRENT_YEAR", "PREVIOUS_YEAR", "CURRENT_QUARTER",
            "CURRENT_MONTH", "PREVIOUS_MONTH", "CURRENT_WEEK", "PREVIOUS_WEEK",
            "PREVIOUS_DAY",
        }:
            pass  # numeric period - usable
        else:
            period = None  # symbolic period - retriever can't filter by it
        question = task.params.get("question") or " ".join(filter(None, [
            task.params.get("metric_code"),
            company,
            period,
        ])) or "thong tin tai chinh"

        self.calls.append({
            "task_id": task.id,
            "operation": task.operation,
            "company": company,
            "period": period,
            "question": question,
        })

        try:
            import asyncio
            future = asyncio.run_coroutine_threadsafe(
                self._search_fn(question, company, period, self._top_k),
                self._loop,
            )
            result = future.result(timeout=self.TIMEOUT_SECONDS)
        except TimeoutError:
            return AdapterResult(
                task.id, "CONTENT", "SYSTEM_UNAVAILABLE", "CONTENT_TIMEOUT",
                provenance="LIVE/VECTOR",
            )
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code in {"CACHE_BUILD_REQUIRED", "CACHE_STALE", "INDEX_NOT_FOUND", "INDEX_NOT_ACTIVE", "CORPUS_NOT_READY"}:
                return AdapterResult(task.id, "CONTENT", "SYSTEM_UNAVAILABLE", f"RETRIEVER_{code}", provenance="LIVE/VECTOR")
            if code in {"SOURCE_UNAVAILABLE", "HASH_MISMATCH", "SOURCE_CHANGED"}:
                return AdapterResult(task.id, "CONTENT", "INSUFFICIENT_EVIDENCE", f"RETRIEVER_{code}", provenance="LIVE/VECTOR")
            return AdapterResult(task.id, "CONTENT", "SYSTEM_UNAVAILABLE", "CONTENT_ERROR", provenance="LIVE/VECTOR")

        hits = result.get("results") or []
        if not hits:
            return AdapterResult(task.id, "CONTENT", "NO_DATA", "CONTENT_NO_RESULTS", provenance="LIVE/VECTOR")

        data = tuple(
            {
                "chunk_id": hit.get("chunk_id"),
                "document_id": hit.get("document_id"),
                "title": hit.get("title"),
                "text": hit.get("text", "")[:500],  # truncate for safety
                "rrf_score": hit.get("rrf_score"),
                "company": hit.get("company") if "company" in (hit.get("locator") or {}) else company,
                "period": hit.get("period"),
            }
            for hit in hits
        )
        evidence = tuple(
            {
                "source_id": hit.get("chunk_id"),
                "content_hash": hit.get("content_hash"),
                "source_verified": True,
                "label": "LIVE/VECTOR",
                "index_version_id": result.get("index_version_id"),
            }
            for hit in hits
        )
        return AdapterResult(
            task.id, "CONTENT", "OK", "CONTENT_OK",
            evidence=evidence, data=data, provenance="LIVE/VECTOR",
        )


class LiveGraphAdapter:
    """Live graph adapter: wraps GraphStore for Neo4j financial observations.

    NOTE: Company relationship queries (find_relationships for subsidiaries,
    ownership) are NOT supported in the current Neo4j schema. Those return
    SYSTEM_UNAVAILABLE with reason GRAPH_RELATIONSHIPS_NOT_INDEXED.
    Only 'find_observations' for financial metrics is supported.
    """

    RELATIONSHIP_OPS = {
        "find_relationships", "resolve_event_entities", "expand_market_context",
        "find_subsidiaries",
    }
    TIMEOUT_SECONDS = 15

    def __init__(self, store) -> None:  # store: GraphStore
        self._store = store
        self.calls: list[dict] = []

    def execute(
        self, task: RouterTask, *, dependency: AdapterResult | None = None
    ) -> AdapterResult:
        if task.adapter != "GRAPH":
            raise ValueError("LiveGraphAdapter only accepts GRAPH tasks")

        self.calls.append({"task_id": task.id, "operation": task.operation})

        if task.operation in self.RELATIONSHIP_OPS:
            return AdapterResult(
                task.id, "GRAPH", "SYSTEM_UNAVAILABLE",
                "GRAPH_RELATIONSHIPS_NOT_INDEXED",
                provenance="LIVE/GRAPH",
            )

        # find_observations: read financial metrics from Neo4j
        companies = list(task.params.get("companies") or [])
        periods = list(task.params.get("periods") or [])
        metric_code = task.params.get("metric_code")
        if not companies or not periods:
            return AdapterResult(
                task.id, "GRAPH", "SYSTEM_UNAVAILABLE",
                "GRAPH_MISSING_SCOPE", provenance="LIVE/GRAPH",
            )

        symbol = companies[0]
        raw_period = periods[0]
        # Convert period format: "2025" -> "2025-YEAR", "2025-Q2" -> "2025-Q2"
        if len(raw_period) == 4 and raw_period.isdigit():
            period_label = f"{raw_period}-YEAR"
        elif raw_period.startswith("20") and "-Q" in raw_period:
            period_label = raw_period
        else:
            return AdapterResult(
                task.id, "GRAPH", "SYSTEM_UNAVAILABLE",
                "GRAPH_UNSUPPORTED_PERIOD_FORMAT", provenance="LIVE/GRAPH",
            )

        try:
            rows = self._store.get_observations(
                symbol=symbol,
                period_label=period_label,
                section="balance_sheet",
                code=metric_code,
                limit=50,
            )
        except Exception as exc:
            code = getattr(exc, "code", str(exc))
            return AdapterResult(
                task.id, "GRAPH", "SYSTEM_UNAVAILABLE",
                f"GRAPH_ERROR_{code}", provenance="LIVE/GRAPH",
            )

        if not rows:
            return AdapterResult(
                task.id, "GRAPH", "NO_DATA", "GRAPH_NO_OBSERVATIONS",
                provenance="LIVE/GRAPH",
            )

        data = tuple(
            {
                "symbol": symbol,
                "period": period_label,
                "code": row.get("code"),
                "value": row.get("value"),
                "basis": row.get("basis"),
                "dataset_id": row.get("dataset_id"),
                "dataset_version": row.get("dataset_version"),
            }
            for row in rows
        )
        evidence = tuple(
            {
                "source_id": f"{row.get('dataset_id')}:{row.get('code')}",
                "json_pointer": row.get("json_pointer"),
                "source_file": row.get("source_file"),
                "dataset_version": row.get("dataset_version"),
                "checksum": row.get("checksum"),
                "source_verified": True,
                "label": "LIVE/GRAPH",
            }
            for row in rows
        )
        return AdapterResult(
            task.id, "GRAPH", "OK", "GRAPH_OBSERVATIONS_OK",
            evidence=evidence, data=data, provenance="LIVE/GRAPH",
        )
