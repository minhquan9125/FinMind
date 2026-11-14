"""Deterministic Vietnamese fixture grammar, not a general language model.

Only the explicitly listed metric/topic patterns are supported. Unknown or
ambiguous language asks for clarification; no financial values are generated.
"""
from __future__ import annotations

import calendar
import copy
from datetime import date
import re
import unicodedata
import uuid

TICKERS = ("VCB", "BID", "CTG", "MBB", "TCB", "FPT", "CMG", "ELC", "ITD", "ICT")
METRICS = {
    "TOTAL_ASSETS": ("tong tai san", "total assets"),
    "PROFIT_BEFORE_TAX": ("loi nhuan truoc thue", "profit before tax"),
    "PROFIT_AFTER_TAX": ("loi nhuan sau thue", "profit after tax"),
    "CASH_FLOW_OPERATING": ("luu chuyen tien thuan tu hoat dong kinh doanh", "cash flow from operating activities"),
}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.replace("đ", "d").replace("Đ", "D"))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).lower().split())


def _has(text: str, phrase: str) -> bool:
    return bool(re.search(r"\b" + re.escape(phrase) + r"\b", text))


def _period(text: str, metric: str | None) -> tuple[dict | None, str | None]:
    """Return a period object and a reason; never use the current date."""
    day_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", text)
    quarter = re.search(r"\b(?:quy|q)\s*([0-9]+)\s*[/ -]?\s*(\d{4})\b", text)
    years = list(dict.fromkeys(re.findall(r"\b(?:19|20|21)\d{2}\b", text)))
    point = metric == "TOTAL_ASSETS"
    try:
        if day_match:
            day, month, year = map(int, day_match.groups())
            end = date(year, month, day)
            result = {"raw": day_match.group(0), "year": year, "quarter": (month-1)//3+1,
                      "start": end.isoformat(), "end": end.isoformat(), "granularity": "DAY",
                      "measure_basis": "POINT_IN_TIME" if point else None, "origin": "USER"}
        elif quarter:
            q, year = map(int, quarter.groups())
            if not 1 <= q <= 4:
                raise ValueError("quarter")
            end = date(year, q*3, calendar.monthrange(year, q*3)[1])
            ytd = "luy ke" in text or "6 thang dau" in text
            start = end if point else date(year, 1 if ytd else q*3-2, 1)
            result = {"raw": quarter.group(0), "year": year, "quarter": q,
                      "start": start.isoformat(), "end": end.isoformat(), "granularity": "QUARTER",
                      "measure_basis": "POINT_IN_TIME" if point else "YTD" if ytd else "STANDALONE_QUARTER", "origin": "USER"}
        elif years:
            first, last = int(years[0]), int(years[-1])
            if first > last or last-first > 10:
                return None, "CONFLICTING_PERIODS"
            half = bool(re.search(r"\b(?:6 thang dau|6 thang dau nam|luy ke 6 thang|nua dau)\b", text))
            end = date(last, 6 if half else 12, 30 if half else 31)
            result = {"raw": "–".join(years), "year": last, "quarter": 2 if half else None,
                      "start": date(first, 12, 31).isoformat() if point and first != last else end.isoformat() if point else date(first, 1, 1).isoformat(),
                      "end": end.isoformat(), "granularity": "RANGE" if first != last or half else "YEAR",
                      "measure_basis": "POINT_IN_TIME" if point else "YTD" if half else "FULL_YEAR", "origin": "USER"}
        else:
            return None, None
    except (ValueError, OverflowError):
        return None, "INVALID_DATE"
    return result, None


def analyze(question: str, session_id: str, context: dict | None = None) -> dict:
    """Analyze supported fixture patterns; missing information never triggers search."""
    original = question if isinstance(question, str) else ""
    norm = _fold(original)
    context = context if isinstance(context, dict) else {}
    result = {"request_id": str(uuid.uuid4()), "session_id": session_id,
              "original_question": original, "normalized_question": " ".join(original.split()),
              "intent": "UNCLEAR", "slots": {"companies": [], "period": None,
              "metric": {"raw": original, "code": None, "mapping_version": "fixture-alias-v1"},
              "topic": None, "source_scope": [], "reporting_entity": "UNKNOWN", "reference": None},
              "decision": "ASK_CLARIFICATION", "missing_fields": [], "conflicts": [],
              "clarification_question": None, "reason_code": "UNRECOGNIZED_INTENT",
              "corpus_version_id": "fixture-corpus-v1", "scope": {}}
    def finish(decision: str, reason: str, message: str | None = None) -> dict:
        result.update(decision=decision, reason_code=reason, clarification_question=message)
        return result
    if not isinstance(session_id, str) or not session_id.strip():
        return finish("SYSTEM_UNAVAILABLE", "DEPENDENCY_UNAVAILABLE", "Không xác định được phiên hiện tại.")
    if not norm or len(original) > 40000 or len(original.split()) > 4000:
        return finish("ASK_CLARIFICATION", "UNRECOGNIZED_INTENT", "Vui lòng nhập câu hỏi rõ và ngắn hơn.")
    if context.get("registry_unavailable") is True:
        return finish("SYSTEM_UNAVAILABLE", "DEPENDENCY_UNAVAILABLE", "Chưa thể xác nhận phạm vi; vui lòng thử lại.")
    if re.search(r"\b(?:nen mua|nen ban|gia muc tieu|tu van dau tu|should i buy|should i sell)\b", norm):
        return finish("UNSUPPORTED", "UNSUPPORTED_ADVICE", "Chức năng này không cung cấp tư vấn mua bán.")
    reference_question = bool(re.search(r"\b(?:nguon|trang nao|citation|source of)\b", norm))
    if reference_question and re.search(r"\b(?:vua|tren|cau tra loi|so do|citation|source of)\b", norm):
        result["intent"] = "SOURCE_OR_CITATION"
        ref = context.get("reference")
        if (context.get("session_id") == session_id and context.get("expired") is False
                and isinstance(ref, dict) and all(isinstance(ref.get(k), str) and ref[k].strip()
                                                for k in ("answer_id", "evidence_id"))):
            result["slots"]["reference"] = copy.deepcopy(ref)
            return finish("RESOLVE_REFERENCE", "REFERENCE_AVAILABLE")
        return finish("OUT_OF_SCOPE", "NO_REFERENCED_EVIDENCE", "Chưa xác minh được bằng chứng tham chiếu trong phiên này.")
    codes = [code for code, aliases in METRICS.items() if any(_has(norm, a) for a in aliases)]
    generic = next((word for word in ("loi nhuan", "doanh thu", "dong tien") if _has(norm, word)), None)
    annual = _has(norm, "bctn") or _has(norm, "bao cao thuong nien")
    news = bool(re.search(r"^(?:tin|news)\b|\btin tuc\b", norm))
    if news and (codes or generic) and "theo tin" in norm:
        result["conflicts"] = ["source_scope"]
        return finish("ASK_CLARIFICATION", "SOURCE_CONFLICT", "Bạn có muốn dùng BCTC cho chỉ tiêu này không? Tin tức chưa được bật.")
    if news:
        result["intent"] = "NEWS_TOPIC"
        return finish("OUT_OF_SCOPE", "SOURCE_NOT_APPROVED", "Loại nguồn tin tức chưa được bật.")
    compare = _has(norm, "so sanh") or _has(norm, "compare")
    trend = _has(norm, "xu huong") or _has(norm, "trend")
    extra_generic = bool(codes and any(_has(norm, word) and not any(_has(alias, word) for alias in METRICS[codes[0]])
                                      for word in ("loi nhuan", "doanh thu", "dong tien")))
    if len(codes) > 1 or extra_generic or ";" in norm or "ngoai ra" in norm or (annual and (codes or generic)):
        return finish("ASK_CLARIFICATION", "MULTI_INTENT_SPLIT_REQUIRED", "Vui lòng tách các yêu cầu thành từng câu hỏi.")
    metric = codes[0] if codes else None
    companies = [ticker for ticker in TICKERS if _has(norm, ticker.lower())]
    explicit_context = bool(re.search(r"\b(?:cong ty nay|cung ky|con (?:vcb|bid|ctg|mbb|tcb|fpt|cmg|elc|itd|ict))\b", norm))
    recognizable = bool(metric or generic or annual or compare or trend or explicit_context)
    if not recognizable:
        return finish("ASK_CLARIFICATION", "UNRECOGNIZED_INTENT", "Bạn muốn hỏi chỉ tiêu hoặc chủ đề nào?")
    unknown = [v for v in re.findall(r"\b[A-Z]{3}\b", original) if v not in TICKERS and v not in ("YTD",)]
    if unknown:
        return finish("OUT_OF_SCOPE", "UNKNOWN_TICKER", "Mã công ty nằm ngoài danh sách fixture được hỗ trợ.")
    if len(companies) > 1 and not compare:
        return finish("ASK_CLARIFICATION", "MULTI_INTENT_SPLIT_REQUIRED", "Vui lòng tách câu hỏi hoặc nêu yêu cầu so sánh rõ ràng.")
    period, period_error = _period(norm, metric)
    if period_error:
        result["missing_fields"] = ["period"]
        return finish("ASK_CLARIFICATION", period_error, "Vui lòng sửa ngày hoặc chọn phạm vi kỳ nhất quán.")
    context_valid = (context.get("session_id") == session_id and context.get("confirmed") is True
                     and context.get("expired") is False)
    inherited_company = inherited_metric = inherited_period = False
    old = context.get("last_resolved_query", {}) if context_valid else {}
    old = old if isinstance(old, dict) else {}
    old_scope = old.get("scope", context.get("scope", {})) if context_valid else {}
    old_scope = old_scope if isinstance(old_scope, dict) else {}
    if explicit_context and context_valid:
        candidates = old_scope.get("companies") or ([context["selected_company"]] if isinstance(context.get("selected_company"), str) else [])
        if not companies and len(candidates) == 1 and candidates[0] in TICKERS:
            companies = list(candidates)
            inherited_company = True
        if not metric and not generic and isinstance(old_scope.get("metric_code"), str) and old_scope["metric_code"] in METRICS:
            metric = old_scope["metric_code"]
            inherited_metric = True
        prior_period = old.get("slots", {}).get("period") if isinstance(old.get("slots"), dict) else None
        if period is None and isinstance(prior_period, dict) and all(k in prior_period for k in ("start", "end", "granularity", "measure_basis", "year", "quarter")):
            try:
                valid_dates = date.fromisoformat(prior_period["start"]) <= date.fromisoformat(prior_period["end"])
            except (ValueError, TypeError):
                valid_dates = False
            if valid_dates:
                period = copy.deepcopy(prior_period)
                inherited_period = True
    topic = "quan_tri_rui_ro" if "quan tri rui ro" in norm else "chuyen_doi_so" if "chuyen doi so" in norm else None
    entity = "CONSOLIDATED" if "hop nhat" in norm else "PARENT" if "rieng" in norm or "cong ty me" in norm else "UNKNOWN"
    result["intent"] = "COMPANY_COMPARE" if compare else "FINANCIAL_TREND" if trend else "ANNUAL_REPORT_TOPIC" if annual else "FINANCIAL_METRIC"
    source = "BCTN" if annual else "BCTC"
    if annual and period:
        period["measure_basis"] = "NOT_APPLICABLE"
    if period and inherited_metric and metric == "TOTAL_ASSETS":
        period["measure_basis"] = "POINT_IN_TIME"
    if period and inherited_period:
        period["origin"] = "SESSION_CONTEXT"
    result["slots"].update(companies=[{"raw": ticker, "ticker": ticker, "origin": "SESSION_CONTEXT" if inherited_company else "USER"} for ticker in companies],
                           period=period, metric={"raw": original, "code": metric, "mapping_version": "fixture-alias-v1",
                                                  "origin": "SESSION_CONTEXT" if inherited_metric else "USER"},
                           topic=topic, source_scope=[source], reporting_entity=entity)
    periods = []
    if period:
        if trend and period["granularity"] == "RANGE":
            periods = [f"{year}-12-31" for year in range(int(period["start"][:4]), int(period["end"][:4])+1)]
        else:
            periods = [period["end"]]
    result["scope"] = {"companies": companies, "periods": periods, "metric_code": metric, "topic": topic,
                       "measure_basis": period["measure_basis"] if period else None,
                       "reporting_entity": entity, "source_type": source}
    missing = result["missing_fields"]
    if not companies or (compare and len(companies) < 2):
        missing.append("companies")
    if not period:
        missing.append("period")
    if (annual and not topic) or (not annual and not metric):
        missing.append("topic" if annual else "metric.code")
    if period and period["measure_basis"] is None:
        missing.append("period.measure_basis")
    if compare and entity == "UNKNOWN":
        missing.append("reporting_entity")
    if trend and len(periods) < 2:
        if "period" not in missing:
            missing.append("period")
    if compare and len(set(re.findall(r"\b(?:19|20|21)\d{2}\b", norm))) > 1:
        result["conflicts"] = ["period"]
        return finish("ASK_CLARIFICATION", "CONFLICTING_PERIODS", "Bạn muốn so sánh cùng kỳ nào?")
    if missing:
        reason = ("MISSING_COMPANY" if "companies" in missing else "AMBIGUOUS_METRIC" if generic and not metric
                  else "MISSING_PERIOD" if "period" in missing else "MISSING_METRIC" if "metric.code" in missing or "topic" in missing
                  else "AMBIGUOUS_BASIS" if "period.measure_basis" in missing else "AMBIGUOUS_ENTITY")
        questions = []
        if "companies" in missing:
            questions.append("Bạn muốn xem công ty nào" if not compare else "Bạn muốn so sánh những công ty nào")
        if "metric.code" in missing:
            questions.append("lợi nhuận trước thuế hay sau thuế" if generic == "loi nhuan" else "chỉ tiêu cụ thể nào")
        if "topic" in missing:
            questions.append("chủ đề BCTN nào")
        if "period" in missing:
            questions.append("trong kỳ hoặc khoảng kỳ cụ thể nào")
        if "period.measure_basis" in missing:
            questions.append("khoảng tính số liệu nào cho chỉ tiêu dòng chảy")
        if "reporting_entity" in missing:
            questions.append("báo cáo hợp nhất hay riêng")
        return finish("ASK_CLARIFICATION", reason, "; ".join(questions) + "?")
    return finish("SEARCH", "SCOPE_COMPLETE")


def clarify(previous: dict, reply: str, session_id: str) -> dict:
    """Complete pending slots only in the same session, never mutate prior state."""
    if (not isinstance(previous, dict) or previous.get("decision") != "ASK_CLARIFICATION"
            or previous.get("session_id") != session_id or previous.get("expired") is True or not isinstance(reply, str)):
        return analyze("", session_id)
    normalized = _fold(reply)
    if previous.get("reason_code") == "SOURCE_CONFLICT" and normalized in ("bctc", "co", "dong y", "bao cao tai chinh"):
        question = _fold(previous.get("original_question", "")).replace("theo tin tuc", "")
        return analyze(question, session_id)
    new_codes = [k for k, values in METRICS.items() if any(_has(normalized, a) for a in values)]
    if new_codes or "bctn" in normalized or "tin tuc" in normalized or "nen mua" in normalized:
        return analyze(reply, session_id)
    if any(t not in TICKERS and t != "YTD" for t in re.findall(r"\b[A-Z]{3}\b", reply)):
        return analyze(previous.get("original_question", "") + " " + reply, session_id)
    scope = copy.deepcopy(previous.get("scope", {}))
    if not isinstance(scope, dict) or not scope:
        return analyze(reply, session_id)
    codes = new_codes or ([scope["metric_code"]] if scope.get("metric_code") else [])
    if "metric.code" in previous.get("missing_fields", []) and normalized in ("sau thue", "truoc thue"):
        codes = ["PROFIT_AFTER_TAX" if normalized == "sau thue" else "PROFIT_BEFORE_TAX"]
    companies = [t for t in TICKERS if _has(normalized, t.lower())] or scope.get("companies", [])
    old_period = previous.get("slots", {}).get("period")
    new_period, error = _period(normalized, codes[0] if codes else None)
    if error:
        result = copy.deepcopy(previous)
        result.update(request_id=str(uuid.uuid4()), reason_code=error,
                      clarification_question="Vui lòng sửa ngày hoặc kỳ vừa bổ sung.")
        return result
    period = new_period or old_period
    metric_words = METRICS[codes[0]][0] if codes else "loi nhuan"
    period_words = ""
    if period:
        if period["granularity"] == "QUARTER":
            period_words = f"quy {period['quarter']}/{period['year']}"
        elif period["measure_basis"] == "YTD":
            period_words = f"6 thang dau {period['year']}"
        elif period["granularity"] == "DAY":
            year, month, day = period["end"].split("-")
            period_words = f"{day}/{month}/{year}"
        else:
            period_words = f"nam {period['year']}"
    question = " ".join([metric_words, *companies, period_words])
    if scope.get("reporting_entity") == "CONSOLIDATED" or "hop nhat" in normalized:
        question += " hop nhat"
    elif scope.get("reporting_entity") == "PARENT" or "rieng" in normalized:
        question += " rieng"
    result = analyze(question, session_id)
    result["original_question"] = previous.get("original_question", "") + "\n" + reply
    result["normalized_question"] = " ".join(result["original_question"].split())
    for field in ("metric", "period"):
        value = result["slots"].get(field)
        if isinstance(value, dict):
            value["origin"] = "CLARIFICATION" if (field == "metric" and codes and not scope.get("metric_code")) or (field == "period" and new_period) else previous.get("slots", {}).get(field, {}).get("origin", "USER")
            if value["origin"] == "CLARIFICATION":
                value["raw"] = reply
    for company in result["slots"]["companies"]:
        if _has(normalized, company["ticker"].lower()):
            company["origin"] = "CLARIFICATION"
    return result
