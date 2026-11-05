"""Scope gate, classifier routing policy and mock execution for steps 9/10."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable, Protocol
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


def personnel_filters(text: str) -> dict:
    positions = (
        ("DEPUTY_BOARD_CHAIR", "pho chu tich"),
        ("AUDIT_CHAIR", "chu tich uy ban kiem toan"),
        ("BOARD_CHAIR", "chu tich"),
        ("DEPUTY_CEO", "pho tong giam doc"),
        ("CEO", "tong giam doc"), ("CEO", "ceo"),
        ("CFO", "giam doc tai chinh"),
        ("BOARD_MEMBER", "thanh vien hdqt"),
    )
    events = (
        ("RESIGNATION_REQUESTED", "REQUESTS_RESIGNATION", r"xin tu nhiem|don (?:xin )?tu nhiem"),
        ("DISMISSED", "DISMISSES", r"mien nhiem|bai nhiem"),
        ("RESIGNED", "RESIGNS", r"tu nhiem|tu chuc"),
        ("APPOINTED", "APPOINTS", r"bo nhiem|duoc bau"),
        ("NOMINATED", "NOMINATED", r"de cu|ung cu"),
    )
    result = {}
    for code, phrase in positions:
        if re.search(rf"\b{phrase}\b", text):
            result.update(position_code=code, relation_types=["HOLDS_ROLE"])
            break
    for stage, relation, pattern in events:
        if re.search(rf"\b(?:{pattern})\b", text):
            result.update(event_type=stage, relation_types=[relation])
            break
    # A name is a search mention, never an assertion that this person holds a role.
    person = re.fullmatch(r"(?:(?:ong|ba) )?([a-z]+(?: [a-z]+){1,5}) la ai", text)
    if person and not re.search(r"\b(?:chu tich|giam doc|ceo|cong ty|nhan su|co dong|thi truong|doi tac)\b", person[1]):
        result.update(person_name=person[1], relation_types=["HOLDS_ROLE"])
    return result


def reporting_filters(text: str, periods: list[str], metric: str | None) -> dict:
    result = {}
    if re.search(r"\bhop nhat\b", text):
        result["reporting_entity"] = "CONSOLIDATED"
    if re.search(r"\brieng le\b", text) or ((metric or contains(text, ("bctc", "bao cao tai chinh"))) and re.search(r"\bcong ty me\b", text)
                                             and not re.search(r"\bcong ty me (?:cua|la)\b", text)):
        result["reporting_entity"] = "PARENT"
    entities = []
    if re.search(r"\bhop nhat\b", text):
        entities.append("CONSOLIDATED")
    if result.get("reporting_entity") == "PARENT":
        entities.append("PARENT")
    result["reporting_entities"] = entities
    if len(entities) > 1:
        result["reporting_entity"] = None
    if re.search(r"\b(?:luy ke|ytd|6 thang|9 thang)\b", text):
        result["measure_basis"] = "YTD"
    elif metric in {"TOTAL_ASSETS", "TOTAL_EQUITY", "LONG_TERM_DEBT"}:
        result["measure_basis"] = "POINT_IN_TIME"
    elif re.search(r"\b(?:rieng quy|quy rieng)\b", text):
        result["measure_basis"] = "STANDALONE_QUARTER"
    elif metric and periods and all(re.fullmatch(r"\d{4}", p) for p in periods):
        result["measure_basis"] = "FULL_YEAR"
    # A quarter alone cannot establish standalone versus YTD without a source profile.
    return result


def explicit_quarters(text: str, reference_date: date | None = None) -> list[str]:
    matches = list(re.finditer(r"\b(?:quy\s*|q)([1-4])\b", text))
    result = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        prefix = re.search(r"\b((?:19|20)\d{2})\s*$", text[:match.start()])
        if (prefix and index and prefix.start() >= matches[index - 1].end()
                and not re.search(r"\bva\s+nam\s*$", text[:prefix.start()])):
            # A year following the preceding quarter is its suffix, not
            # an explicit year prefix for this quarter.
            prefix = None
        suffix = text[match.end():end]
        relative = re.match(r"\s+nam\s+(nay|ngoai)\b", suffix)
        if not relative:
            # A trailing year belongs to every quarter in its connector group.
            trailing = text[match.end():]
            anchor = re.search(r"\bnam\s+(nay|ngoai)\b|\b(?:19|20)\d{2}\b", trailing)
            if anchor:
                connectors = re.sub(r"\b(?:quy\s*|q)[1-4]\b|\bva\b", "", trailing[:anchor.start()])
                connectors = re.sub(r"\bnam\s*$", "", connectors)
                if not connectors.strip():
                    if anchor[1]:
                        relative = anchor
                    elif not prefix:
                        result.append(f"{anchor[0]}-Q{match[1]}")
                        continue
        if not relative:
            relative = re.search(r"\bnam\s+(nay|ngoai)\s*$", text[:match.start()])
        if relative:
            today = reference_date or datetime.now(timezone(timedelta(hours=7))).date()
            result.append(f"{today.year - int(relative[1] == 'ngoai')}-Q{match[1]}")
            continue
        year = re.search(r"\b(\d{4}|\d{2})\b", suffix)
        if year and re.search(r"\bva\s+nam\s+$", suffix[:year.start()]):
            year = None
        if prefix:
            year = prefix
        if not year:
            # Shared trailing year: 'quý 1 và quý 2 năm 2025'.
            year = re.search(r"\b((?:19|20)\d{2})\b", text[match.end():])
        if not year:
            preceding = re.findall(r"\b((?:19|20)\d{2})\b", text[:match.start()])
            value = preceding[-1] if preceding else None
        else:
            value = year[1]
        if value:
            value = "20" + value if len(value) == 2 else value
            result.append(f"{value}-Q{match[1]}")
        else:
            result.append(f"LATEST_YEAR-Q{match[1]}")
    return list(dict.fromkeys(result))


def calendar_periods(periods: list[str], today: date) -> list[str]:
    quarter = (today.month - 1) // 3
    resolved = []
    for period in periods:
        if period in {"PREVIOUS_YEAR", "CURRENT_YEAR"}:
            period = str(today.year - (period == "PREVIOUS_YEAR"))
        elif period in {"CURRENT_QUARTER", "PREVIOUS_QUARTER", "NEXT_QUARTER"}:
            offset = {"CURRENT_QUARTER": 0, "PREVIOUS_QUARTER": -1, "NEXT_QUARTER": 1}[period]
            year, q = divmod(today.year * 4 + quarter + offset, 4)
            period = f"{year}-Q{q + 1}"
        resolved.append(period)
    return resolved

PRICE_DATE_PATTERN = (r"\b(?:(?P<y>\d{4})\s+(?P<m>\d{1,2})\s+(?P<d>\d{1,2})|"
               r"(?P<day>\d{1,2})\s+(?:thang\s+)?(?P<month>\d{1,2})\s+(?:nam\s+)?(?P<year>\d{4})|"
               r"(?P<relative>hom nay|hom qua|ngay mai))\b")


def price_dates(normalized: str) -> list[str]:
    """Keep ordered full dates and relative days, rejecting incomplete dates."""
    pattern = PRICE_DATE_PATTERN
    remainder = re.sub(pattern, " ", normalized)
    if re.search(r"\b(?:ngay|thang)\s+\d+\b", remainder):
        raise ValueError("MISSING_PRICE_DATE")
    result = []
    for match in re.finditer(pattern, normalized):
        if match['relative']:
            value = {"hom nay": "CURRENT", "hom qua": "PREVIOUS_DAY", "ngay mai": "NEXT_DAY"}[match['relative']]
        else:
            fields = (match['y'], match['m'], match['d']) if match['y'] else (match['year'], match['month'], match['day'])
            value = date(*(int(part) for part in fields)).isoformat()
        if value not in result:
            result.append(value)
    return result


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
    topic: str | None = None
    source_type: str | None = None
    operation: str | None = None
    route_hint: str | None = None
    reporting_entity: str | None = None
    reporting_entities: tuple[str, ...] = ()
    targets: tuple[dict, ...] = ()
    measure_basis: str | None = None
    person_name: str | None = None
    position_code: str | None = None
    event_type: str | None = None
    relation_types: tuple[str, ...] = ()


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
    def __init__(self, company_registry: dict[str, tuple[str, ...]] | None = None,
                 *, reference_date: date | None = None) -> None:
        self.company_registry = company_registry or DEFAULT_COMPANIES
        self.reference_date = reference_date

    def resolve(self, question: str, context: SessionScope | None = None) -> ResolvedInput:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a nonempty string")
        normalized = _normalize(question)
        today = self.reference_date or datetime.now(timezone(timedelta(hours=7))).date()
        list_followup = bool(re.fullmatch(
            r"(?:co the )?(?:liet ke|ke|cho xem danh sach)(?: ra)?(?: khong| xem)?", normalized))
        if list_followup and context and context.confirmed and context.topic and context.operation and context.route_hint:
            if context.ambiguous_companies:
                return self._clarify(question, RouterScope(), ("companies",), "AMBIGUOUS_CONTEXT",
                                     "Bạn muốn liệt kê cho công ty nào?")
            scope = RouterScope(**{
                key: list(getattr(context, key)) if isinstance(getattr(context, key), tuple) else getattr(context, key)
                for key in RouterScope.model_fields if hasattr(context, key)
            })
            return ResolvedInput(question, scope, route_hint=context.route_hint)
        quarter_numbers = re.findall(r"\b(?:quy\s*|q)(\d+)\b", normalized)
        if any(int(q) not in range(1, 5) for q in quarter_numbers):
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
        # Keep local company/period bindings; never form a Cartesian product
        # when each company has its own explicit period clause.
        positions = []
        for company in companies:
            aliases = [a for a, ids in self.company_registry.items() if company in ids] + [company]
            hits = [m.start() for a in aliases for m in re.finditer(rf"\b{re.escape(_normalize(a))}\b", normalized)]
            if hits:
                start = min(hits)
                # A reporting qualifier immediately before a company belongs
                # to that company, not the preceding company's clause.
                qualifier = re.search(r"\b(?:(?:hop nhat|rieng le|luy ke|ytd|rieng quy|quy rieng)\s+)+(?:cua\s+)?$", normalized[:start])
                positions.append((company, qualifier.start() if qualifier else start))
        positions.sort(key=lambda item: item[1])
        bound_periods = {}
        bound_reporting = {}
        bound_clauses = {}
        for i, (company, start) in enumerate(positions):
            end = positions[i + 1][1] if i + 1 < len(positions) else len(normalized)
            local = self._periods(normalized[start:end], today)
            bound_clauses[company] = normalized[start:end]
            if local:
                bound_periods[company] = local
            bound_reporting[company] = reporting_filters(normalized[start:end], local, self._metric(normalized)).get("reporting_entities", [])
        detected_industry = next(
            (industry for phrase, industry in sorted(
                INDUSTRY_KEYWORDS.items(), key=lambda item: len(item[0]), reverse=True
            ) if re.search(rf"\b{re.escape(phrase)}\b", normalized)), None,
        )
        personnel = personnel_filters(normalized)
        entity_mentions: list[str] = []
        if personnel.get("person_name"):
            entity_mentions.append(personnel["person_name"])
        if contains(normalized, EVENT_TERMS):
            event_prefix = re.search(
                r"^(.{2,80}?)\s+(?:bi bat|bat giu|khoi to|dieu tra|truy to|tam giam)\b", normalized,
            )
            if event_prefix:
                mention = re.sub(r"^(?:ong|ba|anh|chi)\s+", "", event_prefix.group(1)).strip()
                if 2 <= len(mention.split()) <= 6:
                    entity_mentions.append(mention)

        periods = calendar_periods(self._periods(normalized, today), today)
        if contains(normalized, ("nam ngoai", "nam nay")):
            year = today.year - int(contains(normalized, ("nam ngoai",)))
            periods = [p.replace("LATEST_YEAR", str(year)) for p in periods]
        metric = self._metric(normalized)
        if (metric is None and re.search(r"\bgia\b", normalized)
                and (companies or (context and context.confirmed and context.companies))
                and (periods or re.search(r"\bngay\s+\d", normalized))):
            metric = "STOCK_PRICE"
        # A new global/conceptual question must never inherit yesterday's ticker.
        independent_scope = contains(normalized, MARKET_TERMS + KNOWLEDGE_TERMS)
        explicit_reference = bool(re.search(
            r"\b(?:con|vay|cung ky|cong ty do|luc nay|no|con nay|ma nay|ben do|ong ay|ma do)\b", normalized,
        ))
        bare_followup = bool(re.fullmatch(r"con\s+\w+(?:\s+\w+)?", normalized)) and bool(companies)
        if bare_followup and context and context.confirmed and context.topic and context.route_hint:
            scope = RouterScope(**{
                key: list(getattr(context, key)) if isinstance(getattr(context, key), tuple) else getattr(context, key)
                for key in RouterScope.model_fields if hasattr(context, key)
            })
            scope.companies = companies
            scope.targets = [{**t, "company": companies[0]} for t in scope.targets] if len(companies) == 1 else []
            return ResolvedInput(question, scope, route_hint=context.route_hint)
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
            years = {p[:4] for p in context.periods if re.fullmatch(r"\d{4}(?:-Q[1-4])?", p)}
            if len(years) == 1:
                periods = [p.replace("LATEST_YEAR", next(iter(years))) for p in periods]
        if (metric is None and re.search(r"\bgia\b", normalized) and companies
                and (periods or re.search(r"\bngay\s+\d", normalized))):
            metric = "STOCK_PRICE"
        if metric == "STOCK_PRICE":
            # Read exact trading dates before the generic year/quarter scope
            # reaches the daily price callback. Keep financial-report periods unchanged.
            try:
                explicit_dates = price_dates(normalized)
                if explicit_dates:
                    periods = explicit_dates
                price_positions = []
                prefix_dates = {}
                for company, start in positions:
                    prefix = re.search(r"(?:ngay\s+)?" + PRICE_DATE_PATTERN + r"\s+(?:cua\s+)?$", normalized[:start])
                    price_positions.append((company, prefix.start() if prefix else start))
                    prefix_dates[company] = bool(prefix)
                bound_clauses = {c: normalized[start:price_positions[i + 1][1] if i + 1 < len(price_positions) else len(normalized)]
                                 for i, (c, start) in enumerate(price_positions)}
                bound_periods = {c: local for c, clause in bound_clauses.items()
                                 if (local := price_dates(clause) or self._periods(clause, today))}
                if (len(companies) > 1 and set(bound_periods) == {companies[0]}
                        and prefix_dates.get(companies[0]) and bound_periods[companies[0]] == explicit_dates):
                    bound_periods = {}  # One leading date scopes the entire company list.
            except ValueError as exc:
                code = "MISSING_PRICE_DATE" if str(exc) == "MISSING_PRICE_DATE" else "INVALID_DATE"
                return self._clarify(question, RouterScope(companies=companies, metric_code=metric),
                                     ("periods",), code, "Bạn muốn hỏi giá vào ngày nào (ngày/tháng/năm hợp lệ)?")
            requested_periods = periods + [p for local in bound_periods.values() for p in local]
            if (any(re.fullmatch(r"\d{4}(?:-Q[1-4])?", p) for p in requested_periods)
                    or (not explicit_dates and re.search(r"\b(?:ngay|thang)\s+\d+\b", normalized))):
                return self._clarify(question, RouterScope(companies=companies, metric_code=metric),
                                     ("periods",), "MISSING_PRICE_DATE", "Bạn muốn hỏi giá vào ngày nào (ngày/tháng/năm)?")
            if not periods:
                periods = ["CURRENT"]
        intent_text = normalized
        if (metric or contains(normalized, ("bctc", "bao cao tai chinh"))) and re.search(r"\bcong ty me\b", normalized) and not re.search(r"\bcong ty me (?:cua|la)\b", normalized):
            intent_text = re.sub(r"\bcong ty me\b", " ", normalized)
        intent = resolve_intent(intent_text, companies, detected_industry, metric, entity_mentions)
        inherit_operation = (context and context.confirmed and explicit_reference and not independent_scope
                             and context.topic and context.route_hint
                             and (metric != "STOCK_PRICE" or context.metric_code == "STOCK_PRICE")
                             and not contains(normalized, GRAPH_TERMS + PROFILE_TERMS + CONTENT_TERMS
                                              + MARKET_ANALYSIS_TERMS + KNOWLEDGE_TERMS))
        if inherit_operation:
            from .intent_policy import RetrievalIntent
            intent = RetrievalIntent(context.route_hint, context.topic, not context.companies)
            personnel = {k: getattr(context, k) for k in ("person_name", "position_code", "event_type", "relation_types")}
        if personnel.get("person_name"):
            from .intent_policy import RetrievalIntent
            intent = RetrievalIntent("GRAPH", "PERSON_LOOKUP", True)
        if not periods and intent.topic not in {"COMPANY_PROFILE", "INVESTING_KNOWLEDGE", "PORTFOLIO_EDUCATION"}:
            periods = ["LATEST_AVAILABLE_PERIOD"]
        scope = RouterScope(companies=companies, periods=periods, metric_code=metric,
                            topic=intent.topic, detected_industry=detected_industry,
                            entity_mentions=entity_mentions, **personnel,
                            **reporting_filters(normalized, periods, metric))
        scope.source_type = ("BCTN" if contains(normalized, ("bctn", "bao cao thuong nien"))
                             else "PRICE" if metric == "STOCK_PRICE" else
                             "BCTN" if intent.route == "GRAPH" else "BCTC")
        if inherit_operation and context.source_type and metric != "STOCK_PRICE":
            scope.source_type = context.source_type
        if context and context.confirmed and explicit_reference and not independent_scope and metric != "STOCK_PRICE" and not contains(
                normalized, ("hop nhat", "rieng le", "cong ty me")):
            scope.reporting_entity = context.reporting_entity
            scope.reporting_entities = list(context.reporting_entities)
        if (context and context.confirmed and explicit_reference and not independent_scope
                and metric == context.metric_code and context.measure_basis in {"YTD", "STANDALONE_QUARTER"}
                and any("-Q" in p for p in periods)
                and not contains(normalized, ("luy ke", "ytd", "6 thang", "9 thang", "rieng quy", "quy rieng"))):
            scope.measure_basis = context.measure_basis
        if len(companies) > 1 and len(bound_periods) == len(companies):
            scope.targets = [{"company": c, "period": p} for c in companies
                             for p in calendar_periods(bound_periods[c], today)]
            if any(bound_reporting.values()):
                for target in scope.targets:
                    target["reporting_entities"] = bound_reporting[target["company"]]
        elif len(companies) > 1 and bound_periods and set(bound_periods) != {companies[-1]}:
            return self._clarify(question, scope, ("periods",), "AMBIGUOUS_COMPANY_PERIOD",
                                 "Bạn muốn dùng kỳ nào cho từng công ty?")
        if len(companies) > 1:
            if not scope.targets:
                scope.targets = [{"company": c, "period": p} for c in companies for p in periods or [None]]
            for target in scope.targets:
                if any(bound_reporting.values()):
                    target["reporting_entities"] = bound_reporting[target["company"]]
                local_filters = reporting_filters(bound_clauses.get(target["company"], ""),
                                                  [target["period"]] if target["period"] else [], metric)
                target["measure_basis"] = local_filters.get("measure_basis")
            if len({t["measure_basis"] for t in scope.targets}) > 1:
                scope.measure_basis = None
        if not companies and not detected_industry and not entity_mentions and not intent.company_optional:
            return self._clarify(question, scope, ("companies",), "MISSING_SCOPE", "Bạn muốn hỏi công ty nào?")
        return ResolvedInput(question, scope, route_hint=intent.route)

    @staticmethod
    def _periods(normalized: str, reference_date: date | None = None) -> list[str]:
        quarters = explicit_quarters(normalized, reference_date)
        if quarters:
            return quarters
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
            "ky moi nhat": "LATEST_AVAILABLE_PERIOD",
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
    # Inject a coverage-aware resolver; latest is never guessed from today's date.
    period_resolver: Callable[[RouterTask], list[str]] | None = None

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
        params["doc_type"] = {"BCTN": "ANNUAL_REPORT", "BCTC": "FINANCIAL_STATEMENT"}.get(resolved.scope.source_type)
        if fixture_case:
            params["fixture_case"] = fixture_case
        params["period_resolution_required"] = any(
            not re.fullmatch(r"\d{4}(?:-Q[1-4])?", period)
            for period in resolved.scope.periods
        )
        topic = resolved.scope.topic
        content_operations = {
            "MARKET_DAILY_DIGEST": "find_daily_market_digest",
            "MARKET_ANALYSIS": "analyze_market_drivers",
            "PRICE_ANALYSIS": "analyze_market_drivers",
            "INVESTING_KNOWLEDGE": "find_investing_knowledge",
            "PORTFOLIO_EDUCATION": "find_investing_knowledge",
            "SECTOR_RESEARCH": "find_sector_research",
        }
        if resolved.scope.metric_code == "STOCK_PRICE" and topic in {"FINANCIAL_RESEARCH", "FINANCIAL_COMPARISON"}:
            content_operations[topic] = "find_price"
        if route == "VECTOR":
            tasks = []
            targets = resolved.scope.targets or [
                {"company": c, "period": p}
                for c in resolved.scope.companies or [None]
                for p in resolved.scope.periods or [None]]
            for target in targets:
                entities = (target["reporting_entities"] or [None] if "reporting_entities" in target
                            else [target["reporting_entity"]] if "reporting_entity" in target
                            else resolved.scope.reporting_entities or [resolved.scope.reporting_entity])
                for entity in entities:
                    company, period = target.get("company"), target.get("period")
                    if content_operations.get(topic) == "find_price" and period in {"CURRENT", "PREVIOUS_DAY", "NEXT_DAY"}:
                        today = self.resolver.reference_date or datetime.now(timezone(timedelta(hours=7))).date()
                        period = (today + timedelta(days={"CURRENT": 0, "PREVIOUS_DAY": -1, "NEXT_DAY": 1}[period])).isoformat()
                    tasks.append(RouterTask(
                        id=f"v{len(tasks) + 1}", adapter="CONTENT",
                        operation=content_operations.get(topic, "find_metric"),
                        params={**params, "companies": [company] if company else [],
                                "periods": [period] if period else [], "reporting_entity": entity,
                                "measure_basis": target.get("measure_basis", resolved.scope.measure_basis),
                                "period_resolution_required": bool(period and not re.fullmatch(
                                    r"\d{4}(?:-\d{2}-\d{2})?" if content_operations.get(topic) == "find_price" else r"\d{4}(?:-Q[1-4])?", period))},
                    ))
        elif route == "GRAPH":
            tasks = [RouterTask(id="g1", adapter="GRAPH", operation="find_relationships", params=params)]
        else:
            company_policy = ("RELATED_COMPANIES" if contains(_normalize(question),
                              ("cong ty con", "cong ty lien ket", "don vi thanh vien"))
                              else "EXPLICIT_OR_RESOLVED")
            tasks = [
                RouterTask(id="g1", adapter="GRAPH", operation=(
                    "resolve_event_entities" if topic == "EVENT_IMPACT" else "find_relationships"
                ), params=params),
                RouterTask(id="v1", adapter="CONTENT", operation=(
                    "compare_company_overview" if topic == "OVERALL_COMPARISON"
                    else "analyze_event_impact" if topic == "EVENT_IMPACT" else "find_metric"
                ), params={**params, "company_scope_policy": company_policy,
                           "resolved_companies": []}, depends_on="g1"),
            ]
            tasks[0].params = {**tasks[0].params, "company_scope_policy": company_policy}
        if self.period_resolver:
            for task in tasks:
                if task.params.get("period_resolution_required"):
                    try:
                        concrete = self.period_resolver(task)
                        if not concrete or any(not isinstance(p, str) or not re.fullmatch(r"\d{4}(?:-Q[1-4])?", p) for p in concrete):
                            raise ValueError("No concrete coverage")
                        task.params.update(periods=concrete, period_resolution_required=False)
                    except Exception:
                        task.params["period_resolution_error"] = "PERIOD_RESOLUTION_REQUIRED"
            if all(not t.params.get("period_resolution_required") for t in tasks):
                resolved.scope.periods = list(dict.fromkeys(p for t in tasks for p in t.params.get("periods", [])))
        if route == "VECTOR":
            if (resolved.scope.metric_code == "STOCK_PRICE"
                    and any(re.fullmatch(r"\d{4}-\d{2}-\d{2}", p) for p in resolved.scope.periods)):
                resolved.scope.periods = list(dict.fromkeys(p for t in tasks for p in t.params.get("periods", [])))
            resolved.scope.targets = [{"company": c, "period": p, "reporting_entity": t.params.get("reporting_entity"),
                                       "measure_basis": t.params.get("measure_basis")}
                                      for t in tasks for c in t.params.get("companies") or [None]
                                      for p in t.params.get("periods") or [None]]
        resolved.scope.operation = tasks[0].operation
        resolved.scope.route_hint = route
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
            # Resolve symbolic periods before either LIVE adapter can drop a filter.
            from .adapters import MockGraphAdapter, MockContentAdapter
            adapter = self.graph_adapter if task.adapter == "GRAPH" else self.content_adapter
            if task.params.get("period_resolution_required") and not isinstance(adapter, (MockGraphAdapter, MockContentAdapter)):
                try:
                    periods = self.period_resolver(task) if self.period_resolver else []
                except Exception:
                    periods = []
                if not periods or any(not isinstance(p, str) or not re.fullmatch(r"\d{4}(?:-Q[1-4])?", p) for p in periods):
                    return ExecutionResult(decision, "SYSTEM_UNAVAILABLE", "PERIOD_RESOLUTION_REQUIRED",
                                           tuple(results), execution_mode="LIVE")
                task = task.model_copy(update={"params": {**task.params, "periods": periods,
                                                          "period_resolution_required": False}})
            if dependency is not None and dependency.provenance != "MOCK/FIXTURE":
                # Only adapter-declared ticker mappings may cross this seam.
                # Relation IDs, person IDs and path endpoints are never ticker guesses.
                declared = [c for row in dependency.data
                            if isinstance(row.get("resolved_companies"), list)
                            for c in row["resolved_companies"]
                            if isinstance(c, str) and re.fullmatch(r"[A-Z][A-Z0-9]{2,4}", c)]
                companies = list(dict.fromkeys(declared))
                if task.params.get("company_scope_policy") == "EXPLICIT_OR_RESOLVED":
                    companies = list(task.params.get("companies") or companies)
                if not companies:
                    return ExecutionResult(decision, "INSUFFICIENT_EVIDENCE", "GRAPH_COMPANY_MAPPING_REQUIRED",
                                           tuple(results), execution_mode="LIVE")
                task = task.model_copy(update={"params": {**task.params, "companies": companies,
                                                          "resolved_companies": companies}})
                # Legacy content adapters consume company_id from dependency.data.
                dependency = replace(dependency, data=tuple({"company_id": c} for c in companies))
            adapter = self.graph_adapter if task.adapter == "GRAPH" else self.content_adapter
            if task.adapter != "GRAPH" and not isinstance(adapter, MockContentAdapter):
                # Current content adapter accepts one exact company/period per call.
                partials = []
                for company in task.params.get("companies") or [None]:
                    for period in task.params.get("periods") or [None]:
                        single = task.model_copy(update={"params": {
                            **task.params, "companies": [company] if company else [],
                            "resolved_companies": [company] if company else [],
                            "periods": [period] if period else [],
                        }})
                        single_dependency = replace(dependency, data=({"company_id": company},)) if dependency else None
                        part = adapter.execute(single, dependency=single_dependency)
                        partials.append(part)
                        if part.status != "OK":
                            break
                    if partials[-1].status != "OK":
                        break
                failure = next((p for p in partials if p.status != "OK"), None)
                result = failure or replace(partials[0],
                    data=tuple(row for p in partials for row in p.data),
                    evidence=tuple(row for p in partials for row in p.evidence))
            else:
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
