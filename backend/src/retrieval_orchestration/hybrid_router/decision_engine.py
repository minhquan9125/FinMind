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


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MODEL_PATH = ROOT / "models" / "router_classifier.joblib"
DEFAULT_MANIFEST_PATH = ROOT / "models" / "router_manifest.json"


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


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
    "truong gia binh": ("FPT",), "nguyen thanh nam": ("FPT",),
}

NON_COMPANY_CODES = {
    "BCTC", "BCTN", "CEO", "CFO", "CTCP", "HNX", "HOSE", "UPCOM", "TTCK", "VNI",
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

MACRO_KEYWORDS = (
    "lai suat", "ty gia", "lam phat", "gia dau", "thue", "chinh sach",
    "dau tu cong", "gdp", "tin dung", "cung tien",
)

COMPARISON_KEYWORDS = (
    "so sanh", "doi chieu", "so voi", "ben nao", "ma nao", "con nao",
    "ai hon", "khoe hon", "tot hon", "ngon hon", "nhieu hon", "it hon",
    "cao hon", "thap hon", "nang hon", "re hon", "dat len ban can",
    "so gang", "vuot", "kem hon", "nhieu nhat", "cao nhat", "nang nhat",
    "huong loi",
)

GRAPH_RELATION_KEYWORDS = (
    "cong ty con", "cong ty lien ket", "cong ty me", "don vi thanh vien",
    "he sinh thai", "so huu", "co dong", "ban lanh dao", "chu tich", "ceo",
    "tong giam doc", "giam doc", "sep lon", "nam quyen", "giu ghe",
    "cam nhieu co phieu", "doi thu", "cung nganh", "chung mam", "doi tac",
    "chuoi cung ung", "kiem soat", "dieu hanh", "lanh dao",
)

VECTOR_INFO_KEYWORDS = (
    "doanh thu", "loi nhuan", "lai", "lo", "lam an", "ket qua kinh doanh",
    "co tuc", "chia chac", "chia giay", "no", "bien loi nhuan", "bao cao",
    "ke hoach", "nhan dinh", "chia se", "du an", "tien do", "xa rong",
    "gom rong", "gia co phieu", "tang", "giam", "tin tuc", "so lieu",
)

EVENT_KEYWORDS = (
    "lien quan", "dinh dang", "an theo", "anh huong", "tac dong", "vu",
    "chay", "bi bat", "bat giu", "thanh tra", "bi phat", "xu phat", "khoi to", "tin don",
    "su kien", "bat tay", "hop tac", "dieu tra", "truy to", "tam giam",
)

STATIC_INFO_KEYWORDS = (
    "linh vuc", "nganh nghe", "nganh kinh doanh", "hoat dong trong", "tru so",
    "lich su", "co cau so huu", "danh sach cong ty con", "ban lanh dao",
)

VAGUE_TIME_KEYWORDS = ("dao nay", "dot vua roi", "dot nay", "hoi do", "may bua nay")

GRAPH_INTENT_TERMS = GRAPH_RELATION_KEYWORDS

CONTENT_INTENT_TERMS = VECTOR_INFO_KEYWORDS + (
    "tin tuc", "tin moi", "bao cao", "bctc", "bctn", "ket qua kinh doanh",
    "so lieu", "chi tieu", "gia co phieu", "gia cp", "gia ck", "thi gia",
    "chia se", "phat bieu", "noi gi", "ke hoach", "chien luoc", "dinh huong",
    "muc tieu", "cam ket", "quan diem",
    "co dong lon", "danh sach co dong", "tinh hinh", "dao nay", "khoi sac",
    "trien vong", "bien dong",
)

ANALYSIS_INTENT_TERMS = (
    "vi sao", "tai sao", "nguyen nhan", "do dau", "ly do", "tac dong",
    "anh huong", "he qua", "phan tich",
    "tinh hinh", "dao nay", "khoi sac", "trien vong", "bien dong",
)


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

        if " va gia " in f" {normalized} " and "moi nhat" in normalized:
            return self._clarify(
                question,
                RouterScope(),
                ("request_selection",),
                "UNSUPPORTED_MIXED_INTENTS",
                "Bạn muốn tra báo cáo tài chính hay giá thị trường trước?",
            )

        candidate_hits: list[tuple[int, str]] = []
        for alias, company_ids in self.company_registry.items():
            match = re.search(rf"\b{re.escape(_normalize(alias))}\b", normalized)
            if match:
                candidate_hits.extend((match.start(), company_id) for company_id in company_ids)
        # Tickers outside the small annotation fixture must still reach the
        # classifier.  The retrieval layer remains responsible for deciding
        # whether that company actually exists in the active corpus.
        for ticker_match in re.finditer(r"(?<![A-Za-z0-9])[A-Z][A-Z0-9]{2,4}(?![A-Za-z0-9])", question):
            ticker = ticker_match.group(0)
            if ticker not in NON_COMPANY_CODES:
                candidate_hits.append((ticker_match.start(), ticker))
        candidates = list(dict.fromkeys(company for _, company in sorted(candidate_hits)))
        detected_industry = next(
            (industry for phrase, industry in sorted(
                INDUSTRY_KEYWORDS.items(), key=lambda item: len(item[0]), reverse=True
            ) if re.search(rf"\b{re.escape(phrase)}\b", normalized)),
            None,
        )
        comparison = any(re.search(rf"\b{re.escape(term)}\b", normalized)
                         for term in COMPARISON_KEYWORDS)
        graph_relation = any(re.search(rf"\b{re.escape(term)}\b", normalized)
                             for term in GRAPH_RELATION_KEYWORDS)
        vector_info = any(re.search(rf"\b{re.escape(term)}\b", normalized)
                          for term in VECTOR_INFO_KEYWORDS)
        event_intent = any(re.search(rf"\b{re.escape(term)}\b", normalized)
                           for term in EVENT_KEYWORDS)
        macro_intent = any(re.search(rf"\b{re.escape(term)}\b", normalized)
                           for term in MACRO_KEYWORDS)
        static_info = any(re.search(rf"\b{re.escape(term)}\b", normalized)
                          for term in STATIC_INFO_KEYWORDS) or bool(re.search(
            r"\b(?:thuoc nganh|nganh gi|nganh nao|kinh doanh gi)\b", normalized
        ))
        entity_mentions: list[str] = []
        if event_intent:
            event_prefix = re.search(
                r"^(.{2,80}?)\s+(?:bi bat|bat giu|khoi to|dieu tra|truy to|tam giam)\b",
                normalized,
            )
            if event_prefix:
                mention = re.sub(r"^(?:ong|ba|anh|chi)\s+", "", event_prefix.group(1)).strip()
                if 2 <= len(mention.split()) <= 6:
                    entity_mentions.append(mention)
        if len(candidates) > 1 and not (comparison or event_intent):
            return self._clarify(question, RouterScope(), ("companies",), "AMBIGUOUS_COMPANY",
                                 "Tên công ty này có nhiều kết quả. Bạn muốn chọn công ty nào?")

        explicit_reference = bool(re.search(
            r"\b(?:con|cung ky|cong ty do|luc nay|no|con nay|ma nay|ben do|ong ay)\b",
            normalized,
        ))
        if context and explicit_reference and context.ambiguous_companies:
            return self._clarify(
                question,
                RouterScope(),
                ("companies",),
                "AMBIGUOUS_CONTEXT",
                "Có nhiều công ty phù hợp trong hội thoại. Bạn muốn chọn công ty nào?",
            )
        companies = candidates
        periods = self._periods(normalized)
        metric = self._metric(normalized)
        market_context = bool(re.search(
            r"\b(?:thi truong|thi truong chung khoan|chung khoan|ttck|tt|ck|vni|vn ?index|vnindex)\b",
            normalized,
        ))
        daily_market_digest = (
            market_context
            and bool(re.search(r"\b(?:hom nay|hien tai|bay gio|moi nhat|hn|hnay|nay)\b", normalized))
            and bool(re.search(
                r"\b(?:bien dong|co bien|co gi moi|co gi hot|co gi hay|tin moi|tin nong|"
                r"tin noi bat|diem tin|tong hop|do lua|rung lac|co song|day song|sap|"
                r"lao doc|bung no|co drama|co chuyen gi|co tin gi|nong gi|len xuong|"
                r"bat thuong|xanh|do|the nao)\b",
                normalized,
            ))
        )
        if (
            metric is None
            and periods
            and periods[0] in {
                "CURRENT", "LATEST_PUBLISHED_PERIOD", "CURRENT_MONTH",
                "PREVIOUS_MONTH", "CURRENT_WEEK", "PREVIOUS_WEEK",
            }
            and re.search(r"\bgia\b", normalized)
        ):
            metric = "STOCK_PRICE"
        if metric == "STOCK_PRICE" and not periods:
            periods = ["CURRENT"]
        if context and context.confirmed and explicit_reference:
            if not companies and len(context.companies) == 1:
                companies = list(context.companies)
            if not periods:
                periods = list(context.periods)
            if metric is None:
                metric = context.metric_code
            if detected_industry is None:
                detected_industry = context.detected_industry
            if not entity_mentions:
                entity_mentions = list(context.entity_mentions)

        multi_entity_both = len(companies) >= 2 and (comparison or event_intent)
        event_both = (
            event_intent and metric != "STOCK_PRICE" and bool(companies or entity_mentions)
        )
        multi_hop_both = bool(companies) and graph_relation and vector_info
        industry_both = (
            not companies and detected_industry is not None
            and (macro_intent or comparison)
        )
        topic = (
            "MARKET_DAILY_DIGEST" if daily_market_digest
            else "EVENT_IMPACT" if event_both
            else "INDUSTRY_ANALYSIS" if industry_both
            else "MULTI_HOP" if multi_hop_both
            else "OVERALL_COMPARISON" if multi_entity_both or (comparison and metric is None)
            else "COMPANY_PROFILE" if static_info and not graph_relation
            else "RELATIONSHIP_LOOKUP" if graph_relation
            else None
        )
        vague_time = any(re.search(rf"\b{re.escape(term)}\b", normalized)
                         for term in VAGUE_TIME_KEYWORDS)
        vague_financial_period = vague_time and not periods and len(companies) == 1 and metric is not None
        if not periods and topic != "COMPANY_PROFILE" and not vague_financial_period:
            periods = ["LATEST_AVAILABLE_PERIOD"]
        scope = RouterScope(
            companies=companies,
            periods=periods,
            metric_code=metric,
            topic=topic,
            detected_industry=detected_industry,
            entity_mentions=entity_mentions,
        )
        missing: list[str] = []
        if (not companies and detected_industry is None and not entity_mentions
                and topic != "MARKET_DAILY_DIGEST"):
            missing.append("companies")
        if vague_financial_period:
            missing.append("periods")
        if "loi nhuan" in normalized and metric is None:
            missing.append("metric_code")
        if missing:
            questions = {
                "companies": "Bạn muốn hỏi công ty nào?",
                "periods": "Bạn muốn hỏi kỳ báo cáo nào?",
                "metric_code": (
                    "Bạn muốn so sánh chỉ tiêu nào?"
                    if comparison else "Bạn muốn hỏi loại lợi nhuận nào?"
                ),
            }
            reason = "VAGUE_TIME" if vague_financial_period else "MISSING_SCOPE"
            return self._clarify(question, scope, tuple(missing), reason,
                                 " ".join(questions[item] for item in missing))
        return ResolvedInput(question, scope)

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
            "hom qua": "PREVIOUS_DAY",
            "thang nay": "CURRENT_MONTH",
            "thang truoc": "PREVIOUS_MONTH",
            "tuan nay": "CURRENT_WEEK",
            "tuan truoc": "PREVIOUS_WEEK",
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
        market_terms = r"\b(?:gia|gia cp|gia ck|thi gia|co phieu|ck)\b"
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
                if phrase == "loi nhuan sau thue":
                    return METRICS[phrase]
                if phrase == "loi nhuan":
                    return None
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

        normalized = _normalize(resolved.question)
        graph_intent = any(
            re.search(rf"\b{re.escape(term)}\b", normalized)
            for term in GRAPH_INTENT_TERMS
        )
        content_intent = (
            resolved.scope.metric_code is not None
            or resolved.scope.topic in {
                "COMPANY_PROFILE", "OVERALL_COMPARISON", "EVENT_IMPACT",
                "INDUSTRY_ANALYSIS", "MULTI_HOP", "MARKET_DAILY_DIGEST",
            }
            or bool(re.search(r"\bAI\b", resolved.question))
            or any(
                re.search(rf"\b{re.escape(term)}\b", normalized)
                for term in CONTENT_INTENT_TERMS
            )
        )
        analysis_intent = any(
            re.search(rf"\b{re.escape(term)}\b", normalized)
            for term in ANALYSIS_INTENT_TERMS
        )
        forced_both = resolved.scope.topic in {
            "OVERALL_COMPARISON", "EVENT_IMPACT", "INDUSTRY_ANALYSIS", "MULTI_HOP",
        }
        graph_score: float | None = None
        content_score: float | None = None
        if forced_both:
            route = "BOTH"
        else:
            graph_score, content_score = self.predictor.predict(resolved.question)
            labels = (int(graph_score >= self.threshold), int(content_score >= self.threshold))
            if resolved.scope.topic == "COMPANY_PROFILE":
                route = "VECTOR"
            elif resolved.scope.topic == "MARKET_DAILY_DIGEST":
                route = "VECTOR"
            elif analysis_intent and content_intent:
                route = "BOTH"
            elif graph_intent and content_intent:
                route = "BOTH"
            elif graph_intent:
                route = "GRAPH"
            elif content_intent:
                route = "VECTOR"
            else:
                route = {(0, 1): "VECTOR", (1, 0): "GRAPH", (1, 1): "BOTH"}.get(labels)
        if route is None:
            assert graph_score is not None and content_score is not None
            route = "GRAPH" if graph_score > content_score else "VECTOR"
        params = resolved.scope.model_dump(exclude_none=True)
        if fixture_case:
            params["fixture_case"] = fixture_case
        tasks: list[RouterTask]
        if route == "VECTOR":
            operation = (
                "find_company_profile" if resolved.scope.topic == "COMPANY_PROFILE"
                else "find_daily_market_digest" if resolved.scope.topic == "MARKET_DAILY_DIGEST"
                else "find_metric"
            )
            tasks = [RouterTask(id="v1", adapter="CONTENT", operation=operation, params=params)]
        elif route == "GRAPH":
            tasks = [RouterTask(id="g1", adapter="GRAPH", operation="find_relationships", params=params)]
        else:
            tasks = [
                RouterTask(
                    id="g1", adapter="GRAPH",
                    operation=(
                        "resolve_event_entities"
                        if resolved.scope.topic == "EVENT_IMPACT"
                        else "expand_market_context" if analysis_intent else "find_relationships"
                    ),
                    params=params,
                ),
                RouterTask(
                    id="v1", adapter="CONTENT",
                    operation=(
                        "compare_company_overview"
                        if resolved.scope.topic == "OVERALL_COMPARISON"
                        else "analyze_event_impact" if resolved.scope.topic == "EVENT_IMPACT"
                        else "analyze_market_drivers" if analysis_intent else "find_metric"
                    ),
                    params=params, depends_on="g1",
                ),
            ]
        return RouterOutput(
            decision="SEARCH", route=route, scope=resolved.scope, tasks=tasks,
            request_id=request_id, reason_code="CLASSIFIER_ROUTE",
            route_reason=(
                f"rule_override topic={resolved.scope.topic}"
                if forced_both else
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
