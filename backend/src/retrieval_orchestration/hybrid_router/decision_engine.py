"""Scope gate, classifier routing policy and mock execution for steps 9/10."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Protocol
import unicodedata

from .adapters import AdapterResult, MockContentAdapter, MockGraphAdapter
from .schemas import RouterOutput, RouterScope, RouterTask
from ..input_normalization import normalize_user_text
from .intent_policy import (
    contains, resolve_intent, EVENT_TERMS, MARKET_TERMS, KNOWLEDGE_TERMS,
    GRAPH_TERMS, PROFILE_TERMS, CONTENT_TERMS, MARKET_ANALYSIS_TERMS,
)


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MODEL_PATH = ROOT / "models" / "router_classifier.joblib"
DEFAULT_MANIFEST_PATH = ROOT / "models" / "router_manifest.json"


def _normalize(text: str) -> str:
    text = normalize_user_text(text)
    text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())
    aliases = {"bn": "bao nhieu", "cp": "co phieu", "ko": "khong",
               "kh": "khong", "nhtas": "nhat", "ln": "loi nhuan"}
    return " ".join(aliases.get(token, token) for token in text.split())


class LabelPredictor(Protocol):
    model_version: str

    def predict(self, question: str) -> tuple[float, float]: ...


class ArtifactPredictor:
    """Lazily load the trusted local classifier and the shared embedding service."""

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        manifest_path: Path = DEFAULT_MANIFEST_PATH,
    ) -> None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.threshold = float(manifest["classifier"]["threshold"])
        self.model_version = str(manifest["artifact_version"])
        self._model_path = model_path
        self._model: Any = None

    def warmup(self) -> None:
        """Load the small classifier artifact before the first request."""
        if self._model is None:
            import joblib

            self._model = joblib.load(self._model_path)

    def predict(self, question: str) -> tuple[float, float]:
        self.warmup()
        from src.documents.embeddings import get_embedding_service

        vector = get_embedding_service().embed_texts([question])
        scores = self._model.predict_proba(vector)[0]
        return float(scores[0]), float(scores[1])


@dataclass(frozen=True)
class SessionScope:
    companies: tuple[str, ...] = ()
    periods: tuple[str, ...] = ()
    metric_code: str | None = None
    detected_industry: str | None = None
    entity_mentions: tuple[str, ...] = ()
    confirmed: bool = True
    ambiguous_companies: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedInput:
    question: str
    scope: RouterScope
    missing_fields: tuple[str, ...] = ()
    reason_code: str | None = None
    clarification_question: str | None = None
    route_hint: str | None = None


DEFAULT_COMPANIES = {
    "fpt": ("FPT",), "fpt corp": ("FPT",),
    "vcb": ("VCB",), "vietcombank": ("VCB",),
    "mbb": ("MBB",), "mb bank": ("MBB",), "mbbank": ("MBB",),
    "bid": ("BID",), "bidv": ("BID",),
    "ctg": ("CTG",), "vietinbank": ("CTG",),
    "tcb": ("TCB",), "techcombank": ("TCB",),
    "cmg": ("CMG",), "cmc": ("CMG",), "elc": ("ELC",), "ssi": ("SSI",),
    "hpg": ("HPG",), "hoa phat": ("HPG",),
    "mwg": ("MWG",), "the gioi di dong": ("MWG",), "bach hoa xanh": ("MWG",),
    "vnm": ("VNM",), "vinamilk": ("VNM",),
    "gas": ("GAS",), "pv gas": ("GAS",),
    "acb": ("ACB",), "vpb": ("VPB",), "vpbank": ("VPB",),
    "hdb": ("HDB",), "hdbank": ("HDB",), "stb": ("STB",),
    "sacombank": ("STB",), "msn": ("MSN",), "masan": ("MSN",),
    "vic": ("VIC",), "vingroup": ("VIC",),
    "ctr": ("CTR",), "nlg": ("NLG",), "itd": ("ITD",), "ict": ("ICT",),
    "vhm": ("VHM",), "vre": ("VRE",), "vnd": ("VND",), "vci": ("VCI",),
    "fts": ("FTS",), "shb": ("SHB",), "tpb": ("TPB",), "lpb": ("LPB",),
    "dgc": ("DGC",), "dgw": ("DGW",), "pnj": ("PNJ",), "pow": ("POW",),
    "pvd": ("PVD",), "pvs": ("PVS",), "bsr": ("BSR",), "sab": ("SAB",),
    "gvr": ("GVR",), "kdh": ("KDH",), "dxg": ("DXG",), "nvl": ("NVL",),
    "truong gia binh": ("FPT",), "nguyen thanh nam": ("FPT",),
}

NON_COMPANY_CODES = {
    "BCTC", "BCTN", "CEO", "CFO", "CTCP", "HNX", "HOSE", "UPCOM", "TTCK", "VNI",
    "DCA", "ETF", "EPS", "ROE", "ROA", "RSI", "MACD", "GDP", "LNST", "LNTT",
    "VCSH", "VNINDEX", "VN", "INDEX", "FOMO", "FUD", "ATO", "ATC",
}

METRICS = {
    "gia co phieu": "STOCK_PRICE",
    "gia cp": "STOCK_PRICE",
    "gia ck": "STOCK_PRICE",
    "gia chung khoan": "STOCK_PRICE",
    "thi gia": "STOCK_PRICE",
    "tong tai san": "TOTAL_ASSETS",
    "tong ts": "TOTAL_ASSETS",
    "tai san": "TOTAL_ASSETS",
    "doanh thu thuan": "NET_REVENUE",
    "dtt": "NET_REVENUE",
    "doanh thu": "REVENUE",
    "dt": "REVENUE",
    "loi nhuan sau thue": "PROFIT_AFTER_TAX",
    "loi nhuan truoc thue": "PROFIT_BEFORE_TAX",
    "lntt": "PROFIT_BEFORE_TAX",
    "loi nhuan": "PROFIT",
    "lnst": "PROFIT_AFTER_TAX",
    "von chu so huu": "TOTAL_EQUITY",
    "vcsh": "TOTAL_EQUITY",
    "no dai han": "LONG_TERM_DEBT",
    "dong tien kinh doanh": "CASH_FLOW_OPERATING",
}

INDUSTRY_KEYWORDS = {
    "ngan hang": "BANKING", "bank": "BANKING",
    "thep": "STEEL", "bat dong san": "REAL_ESTATE", "bds": "REAL_ESTATE",
    "chung khoan": "SECURITIES", "dau khi": "OIL_GAS", "ban le": "RETAIL",
    "cong nghe": "TECHNOLOGY", "vien thong": "TELECOM",
    "thuy san": "SEAFOOD", "dien": "POWER",
}

TICKER_STOP_WORDS = set(" ".join(
    EVENT_TERMS + MARKET_TERMS + KNOWLEDGE_TERMS + GRAPH_TERMS + PROFILE_TERMS
    + CONTENT_TERMS + MARKET_ANALYSIS_TERMS + tuple(INDUSTRY_KEYWORDS)
).split()) | {"nay", "nao", "cua", "thi", "the", "khong", "hom", "bao", "nhieu",
             "hien", "moi", "dang", "tuan", "thang", "nam", "viet", "trong", "nhom",
             "check", "thu", "coi", "cho", "giup", "toi", "nguoi", "mua", "ban"}


class ScopeResolver:
    def __init__(self, company_registry: dict[str, tuple[str, ...]] | None = None) -> None:
        self.company_registry = company_registry or DEFAULT_COMPANIES

    def resolve(self, question: str, context: SessionScope | None = None) -> ResolvedInput:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a nonempty string")
        normalized = _normalize(question)
        invalid_quarter = re.search(
            r"\b(?:quy\s*|q)(\d+)(?:\s+nam)?\s+(\d{2}|\d{4})\b", normalized
        )
        if invalid_quarter and int(invalid_quarter.group(1)) not in range(1, 5):
            return self._clarify(question, RouterScope(), ("periods",), "INVALID_QUARTER",
                                 "Quý chỉ có giá trị từ 1 đến 4. Bạn muốn hỏi quý nào?")

        candidate_hits: list[tuple[int, str]] = []
        for alias, company_ids in self.company_registry.items():
            match = re.search(rf"\b{re.escape(_normalize(alias))}\b", normalized)
            if match:
                if len(company_ids) > 1:
                    return self._clarify(question, RouterScope(), ("companies",),
                                         "AMBIGUOUS_COMPANY", "Tên này chỉ nhiều công ty. Bạn muốn hỏi công ty nào?")
                candidate_hits.extend((match.start(), company_id) for company_id in company_ids)
        for ticker_match in re.finditer(r"(?<![A-Za-z0-9])[A-Z][A-Z0-9]{2,4}(?![A-Za-z0-9])", question):
            ticker = ticker_match.group(0)
            if (ticker not in NON_COMPANY_CODES and len(ticker) == 3
                    and ticker.lower() not in TICKER_STOP_WORDS
                    and _normalize(ticker) == ticker.lower()):
                candidate_hits.append((ticker_match.start(), ticker))
        # Unknown lower-case symbols are accepted only in explicit ticker syntax.
        for match in re.finditer(r"\b(?:ma|co phieu)\s+([a-z]{3})\b", normalized):
            token = match.group(1)
            if token not in TICKER_STOP_WORDS and token.upper() not in NON_COMPANY_CODES:
                candidate_hits.append((match.start(1), token.upper()))
        companies = list(dict.fromkeys(company for _, company in sorted(candidate_hits)))
        detected_industry = next(
            (industry for phrase, industry in sorted(
                INDUSTRY_KEYWORDS.items(), key=lambda item: len(item[0]), reverse=True
            ) if re.search(rf"\b{re.escape(phrase)}\b", normalized)), None,
        )
        entity_mentions: list[str] = []
        if contains(normalized, EVENT_TERMS):
            event_prefix = re.search(
                r"^(.{2,80}?)\s+(?:bi bat|bat giu|khoi to|dieu tra|truy to|tam giam)\b", normalized,
            )
            if event_prefix:
                mention = re.sub(r"^(?:ong|ba|anh|chi)\s+", "", event_prefix.group(1)).strip()
                if 2 <= len(mention.split()) <= 6:
                    entity_mentions.append(mention)

        periods = self._periods(normalized)
        metric = self._metric(normalized)
        # A new global/conceptual question must never inherit yesterday's ticker.
        independent_scope = contains(normalized, MARKET_TERMS + KNOWLEDGE_TERMS)
        explicit_reference = bool(re.search(
            r"\b(?:con|cung ky|cong ty do|luc nay|no|con nay|ma nay|ben do|ong ay|ma do)\b", normalized,
        ))
        implicit_reference = not companies and not independent_scope and (
            metric is not None or contains(normalized, ("gia", "loi nhuan", "co tuc", "lai", "lo"))
        )
        if context and context.confirmed and not independent_scope and (explicit_reference or implicit_reference):
            if context.ambiguous_companies or (not companies and len(context.companies) > 1):
                return self._clarify(question, RouterScope(), ("companies",), "AMBIGUOUS_CONTEXT",
                                     "Có nhiều công ty trong câu trước. Bạn muốn hỏi công ty nào?")
            if not companies and len(context.companies) == 1:
                companies = list(context.companies)
            if explicit_reference:
                if not periods:
                    periods = list(context.periods)
                new_operation = contains(normalized, GRAPH_TERMS + PROFILE_TERMS + CONTENT_TERMS
                                         + MARKET_ANALYSIS_TERMS + KNOWLEDGE_TERMS)
                if metric is None and not new_operation:
                    metric = context.metric_code
                detected_industry = detected_industry or context.detected_industry
                entity_mentions = entity_mentions or list(context.entity_mentions)
        if metric is None and re.search(r"\bgia\b", normalized) and periods and companies:
            metric = "STOCK_PRICE"
        if metric == "STOCK_PRICE" and not periods:
            periods = ["CURRENT"]
        intent = resolve_intent(normalized, companies, detected_industry, metric, entity_mentions)
        if not periods and intent.topic not in {"COMPANY_PROFILE", "INVESTING_KNOWLEDGE", "PORTFOLIO_EDUCATION"}:
            periods = ["LATEST_AVAILABLE_PERIOD"]
        scope = RouterScope(companies=companies, periods=periods, metric_code=metric,
                            topic=intent.topic, detected_industry=detected_industry,
                            entity_mentions=entity_mentions)
        if not companies and not detected_industry and not entity_mentions and not intent.company_optional:
            return self._clarify(question, scope, ("companies",), "MISSING_SCOPE", "Bạn muốn hỏi công ty nào?")
        return ResolvedInput(question, scope, route_hint=intent.route)

    @staticmethod
    def _periods(normalized: str) -> list[str]:
        quarter = re.search(r"\b(?:quy\s*|q)([1-4])(?:\s+nam)?\s+(\d{4})\b", normalized)
        if quarter:
            return [f"{quarter.group(2)}-Q{quarter.group(1)}"]
        short_quarter = re.search(r"\b(?:quy\s*|q)([1-4])\s+(\d{2})\b", normalized)
        if short_quarter:
            return [f"20{short_quarter.group(2)}-Q{short_quarter.group(1)}"]
        years = re.findall(r"\b(?:19|20)\d{2}\b", normalized)
        if years:
            return list(dict.fromkeys(years))
        relative = {
            "nam nay": "CURRENT_YEAR",
            "nam ngoai": "PREVIOUS_YEAR",
            "quy nay": "CURRENT_QUARTER",
            "quy truoc": "PREVIOUS_QUARTER",
            "quy sau": "NEXT_QUARTER",
            "hom qua": "PREVIOUS_DAY",
            "thang nay": "CURRENT_MONTH",
            "thang truoc": "PREVIOUS_MONTH",
            "thang sau": "NEXT_MONTH",
            "tuan nay": "CURRENT_WEEK",
            "tuan truoc": "PREVIOUS_WEEK",
            "tuan sau": "NEXT_WEEK",
            "tuan toi": "NEXT_WEEK",
            "ngay mai": "NEXT_DAY",
            "gan day": "CURRENT",
            "ngay hom nay": "CURRENT",
            "hom nay": "CURRENT",
            "hien tai": "CURRENT",
            "hien gio": "CURRENT",
            "bay gio": "CURRENT",
            "moi nhat": "LATEST_PUBLISHED_PERIOD",
            "ky bao cao gan nhat": "LATEST_AVAILABLE_PERIOD",
            "ky gan nhat": "LATEST_AVAILABLE_PERIOD",
            "ky vua cong bo": "LATEST_PUBLISHED_PERIOD",
        }
        for phrase, token in relative.items():
            if phrase in normalized:
                return [token]
        quarter_without_year = re.search(r"\b(?:quy\s*|q)([1-4])\b", normalized)
        if quarter_without_year:
            return [f"LATEST_YEAR-Q{quarter_without_year.group(1)}"]
        market_terms = r"\b(?:gia|gia cp|gia ck|thi gia|co phieu|ck|tt|thi truong|vni|vnindex)\b"
        if re.search(market_terms, normalized):
            if re.search(r"\b(?:hn|hnay|homnay|ht|htai|bg|bgio)\b", normalized):
                return ["CURRENT"]
            if re.search(r"\b(?:mn|latest)\b", normalized):
                return ["LATEST_PUBLISHED_PERIOD"]
        return []

    @staticmethod
    def _metric(normalized: str) -> str | None:
        for phrase in sorted(METRICS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(phrase)}\b", normalized):
                return METRICS[phrase]
        return None

    @staticmethod
    def _clarify(
        question: str,
        scope: RouterScope,
        missing: tuple[str, ...],
        reason: str,
        clarification: str,
    ) -> ResolvedInput:
        return ResolvedInput(question, scope, missing, reason, clarification)


@dataclass(frozen=True)
class ExecutionResult:
    decision: RouterOutput
    status: str
    reason_code: str
    adapter_results: tuple[AdapterResult, ...] = ()
    execution_mode: str = "MOCK"


@dataclass(frozen=True)
class ShadowResult:
    request_id: str
    live_decision: str
    live_route: str | None
    predicted_decision: str
    predicted_route: str | None
    baseline_route: str | None
    reason_code: str | None
    model_version: str | None
    execution_mode: str = "SHADOW"
    adapter_calls: int = 0


@dataclass
class DecisionEngine:
    predictor: LabelPredictor
    threshold: float = 0.65
    resolver: ScopeResolver = field(default_factory=ScopeResolver)
    graph_adapter: Any = field(default_factory=MockGraphAdapter)
    content_adapter: Any = field(default_factory=MockContentAdapter)

    def decide(
        self,
        question: str,
        *,
        context: SessionScope | None = None,
        request_id: str | None = None,
        fixture_case: str | None = None,
    ) -> RouterOutput:
        resolved = self.resolver.resolve(question, context)
        if resolved.missing_fields:
            return RouterOutput(
                decision="ASK_CLARIFICATION", route="CLARIFY", scope=resolved.scope,
                missing_fields=list(resolved.missing_fields), tasks=[],
                clarification_question=resolved.clarification_question,
                request_id=request_id, reason_code=resolved.reason_code,
                route_reason="Scope gate stopped execution before classifier",
                execution_mode="MOCK",
            )

        graph_score: float | None = None
        content_score: float | None = None
        route = resolved.route_hint
        if route is None:
            graph_score, content_score = self.predictor.predict(resolved.question)
            labels = (int(graph_score >= self.threshold), int(content_score >= self.threshold))
            route = {(0, 1): "VECTOR", (1, 0): "GRAPH", (1, 1): "BOTH"}.get(labels)
            if route is None:
                route = "GRAPH" if graph_score > content_score else "VECTOR"
        # Preserve the actual question: a generic stock/metric fallback loses the
        # meaning of forecasts, knowledge requests and explanations downstream.
        params = {**resolved.scope.model_dump(exclude_none=True), "question": question,
                  "retrieval_question": normalize_user_text(question)}
        if fixture_case:
            params["fixture_case"] = fixture_case
        topic = resolved.scope.topic
        content_operations = {
            "MARKET_DAILY_DIGEST": "find_daily_market_digest",
            "MARKET_ANALYSIS": "analyze_market_drivers",
            "PRICE_ANALYSIS": "analyze_market_drivers",
            "INVESTING_KNOWLEDGE": "find_investing_knowledge",
            "PORTFOLIO_EDUCATION": "find_investing_knowledge",
            "SECTOR_RESEARCH": "find_sector_research",
        }
        if route == "VECTOR":
            tasks = [RouterTask(id="v1", adapter="CONTENT",
                                operation=content_operations.get(topic, "find_metric"), params=params)]
        elif route == "GRAPH":
            tasks = [RouterTask(id="g1", adapter="GRAPH", operation="find_relationships", params=params)]
        else:
            tasks = [
                RouterTask(id="g1", adapter="GRAPH", operation=(
                    "resolve_event_entities" if topic == "EVENT_IMPACT" else "find_relationships"
                ), params=params),
                RouterTask(id="v1", adapter="CONTENT", operation=(
                    "compare_company_overview" if topic == "OVERALL_COMPARISON"
                    else "analyze_event_impact" if topic == "EVENT_IMPACT" else "find_metric"
                ), params=params, depends_on="g1"),
            ]
        return RouterOutput(
            decision="SEARCH", route=route, scope=resolved.scope, tasks=tasks,
            request_id=request_id, reason_code="INTENT_POLICY" if resolved.route_hint else "CLASSIFIER_ROUTE",
            route_reason=(
                f"rule_override topic={resolved.scope.topic}"
                if resolved.route_hint else
                f"scores graph={graph_score:.6f}, content={content_score:.6f}, threshold={self.threshold:.6f}"
            ),
            model_version=self.predictor.model_version, execution_mode="MOCK",
        )

    def run(self, question: str, **kwargs: Any) -> ExecutionResult:
        decision = self.decide(question, **kwargs)
        if decision.decision != "SEARCH":
            return ExecutionResult(decision, "ASK_CLARIFICATION", decision.reason_code or "CLARIFY")
        results: list[AdapterResult] = []
        by_id: dict[str, AdapterResult] = {}
        for task in decision.tasks:
            dependency = by_id.get(task.depends_on) if task.depends_on else None
            if dependency is not None and dependency.status != "OK":
                break
            adapter = self.graph_adapter if task.adapter == "GRAPH" else self.content_adapter
            result = adapter.execute(task, dependency=dependency)
            results.append(result)
            by_id[task.id] = result
            if result.status != "OK":
                break
        status = next((item.status for item in results if item.status != "OK"), "OK")
        reason = next((item.reason_code for item in results if item.status != "OK"), "MOCK_EXECUTION_OK")
        # Determine execution mode from adapter types
        from .adapters import MockGraphAdapter as _MockG, MockContentAdapter as _MockC
        live_adapters = not (isinstance(self.graph_adapter, _MockG) and isinstance(self.content_adapter, _MockC))
        mode = "LIVE" if live_adapters else "MOCK"
        return ExecutionResult(decision, status, reason, tuple(results), execution_mode=mode)

    def shadow(
        self,
        question: str,
        *,
        request_id: str,
        live_decision: str,
        live_route: str | None,
        context: SessionScope | None = None,
    ) -> ShadowResult:
        """Predict beside LIVE without executing or changing its decision."""
        from .baseline_rule import classify_by_keywords

        graph_before = len(self.graph_adapter.calls)
        content_before = len(self.content_adapter.calls)
        prediction = self.decide(question, context=context, request_id=request_id)
        baseline = classify_by_keywords(question)
        calls = (len(self.graph_adapter.calls) - graph_before) + (
            len(self.content_adapter.calls) - content_before
        )
        return ShadowResult(
            request_id=request_id,
            live_decision=live_decision,
            live_route=live_route,
            predicted_decision=prediction.decision,
            predicted_route=None if prediction.route == "CLARIFY" else prediction.route,
            baseline_route=baseline.route,
            reason_code=prediction.reason_code,
            model_version=prediction.model_version,
            adapter_calls=calls,
        )
