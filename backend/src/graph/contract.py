"""Boundary validation for normalized schema 1.0; no crawler modifications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re


GRAPH_VERSION = "1.0"
SECTIONS = {
    "ratios": "total_ratio_periods",
    "income_statement": "total_income_periods",
    "balance_sheet": "total_balance_sheet_periods",
    "cash_flow_statement": "total_cash_flow_periods",
}
REPORT_METADATA = frozenset({
    "period_label", "period_type", "year", "quarter", "yearReport", "lengthReport",
    "organCode", "ticker", "createDate", "updateDate", "publicDate",
    "ratioTTMId", "ratioYearId", "ratioType",
})
VIETNAM_TZ = timezone(timedelta(hours=7))


class ContractError(ValueError):
    """Normalized input does not satisfy the Knowledge Graph contract."""


@dataclass(frozen=True)
class GraphDataset:
    """Validated projection; JSON properties preserve the original payload."""

    company: dict
    dataset: dict
    periods: tuple[dict, ...]
    reports: tuple[dict, ...]
    metrics: tuple[dict, ...]
    observations: tuple[dict, ...]
    prices: tuple[dict, ...]

    def counts(self) -> dict[str, int]:
        return {name: len(getattr(self, name)) for name in
                ("periods", "reports", "metrics", "observations", "prices")}


def canonical_json(value) -> str:
    try:
        serialized = json.dumps(value, sort_keys=True, ensure_ascii=False,
                                separators=(",", ":"), allow_nan=False)
        serialized.encode("utf-8")
        return serialized
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ContractError("Input must contain finite, serializable JSON values") from exc


def require(condition, message):
    if not condition:
        raise ContractError(message)


def _object(value, path):
    require(isinstance(value, dict), f"{path} must be an object")
    require(all(isinstance(key, str) for key in value), f"{path} keys must be strings")
    return value


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _count(value, path):
    require(_integer(value) and value >= 0, f"{path} must be a nonnegative integer")
    return value


def _validate_json(value, depth=0):
    require(depth <= 128, "JSON nesting exceeds 128 levels")
    if type(value) is dict:
        _object(value, "JSON object")
        for item in value.values():
            _validate_json(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _validate_json(item, depth + 1)
    else:
        require(type(value) in (str, int, float, bool, type(None)), "Invalid JSON value type")
        require(type(value) is not float or math.isfinite(value), "Nonfinite JSON number")


def period_from_row(row, section):
    """Return canonical period metadata while keeping provider row untouched."""
    require(all(key in row for key in ("period_label", "period_type", "year", "quarter")),
            f"{section}: missing canonical period metadata")
    label = row.get("period_label")
    require(isinstance(label, str), f"{section}: period_label must be a string")
    match = re.fullmatch(r"([1-9][0-9]{3})-(Q([1-4])|YEAR)", label or "")
    require(match is not None, f"{section}: invalid period_label")
    year = int(match[1])
    quarter = int(match[3]) if match[3] else None
    period_type = "QUARTER" if quarter else "YEAR"
    require(row.get("period_type") == period_type, f"{section}: inconsistent period_type")
    input_year = row.get("year")
    require((_integer(input_year) and input_year == year) or
            (isinstance(input_year, str) and input_year == str(year)),
            f"{section}: inconsistent year")
    input_quarter = row.get("quarter")
    if quarter:
        require(_integer(input_quarter) and input_quarter == quarter,
                f"{section}: inconsistent quarter")
    else:
        require(input_quarter is None or
                (section == "ratios" and _integer(input_quarter) and input_quarter == 5),
                f"{section}: invalid annual quarter")
    if "yearReport" in row:
        require(_integer(row["yearReport"]) and row["yearReport"] == year,
                f"{section}: inconsistent yearReport")
    if "lengthReport" in row:
        require(_integer(row["lengthReport"]) and row["lengthReport"] == (quarter or 5),
                f"{section}: inconsistent lengthReport")
    return {"id": label, "year": year, "quarter": quarter, "period_type": period_type}


def validate_dataset(payload):
    """Validate a whole snapshot before any database interaction."""
    _object(payload, "dataset")
    _validate_json(payload)
    canonical_json(payload)
    require(payload.get("schema_version") == "1.0", "Unsupported normalized schema_version")
    symbol = payload.get("symbol")
    require(isinstance(symbol, str) and re.fullmatch(r"[A-Z][A-Z0-9]{0,15}", symbol),
            "symbol must be an uppercase stock code")
    version = payload.get("dataset_version")
    require(isinstance(version, str) and re.fullmatch(r"[0-9]{8}T[0-9]{6}Z", version),
            "Invalid dataset_version")
    try:
        generated_at = datetime.fromisoformat(payload["generated_at"].replace("Z", "+00:00"))
        version_at = datetime.strptime(version, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (KeyError, AttributeError, TypeError, ValueError):
        raise ContractError("Invalid generated_at or dataset_version") from None
    require(generated_at.utcoffset() == timedelta(0) and
            generated_at.replace(microsecond=0) == version_at,
            "generated_at must be UTC and match dataset_version")
    sources = _object(payload.get("sources"), "sources")
    for key in ("prices", "fundamentals"):
        source = sources.get(key)
        require(isinstance(source, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", source),
                f"sources.{key} must be a provider code")

    prices = payload.get("price_history")
    require(isinstance(prices, list) and prices, "price_history must be nonempty")
    previous = ""
    for price in prices:
        _object(price, "price_history row")
        trading_date = price.get("date")
        try:
            parsed_date = date.fromisoformat(trading_date)
        except (TypeError, ValueError):
            raise ContractError("Invalid trading date") from None
        require(parsed_date.isoformat() == trading_date and trading_date > previous,
                "Trading dates must be ISO, unique and increasing")
        previous = trading_date
        values = [price.get(field) for field in ("open", "high", "low", "close")]
        require(all((type(v) is float or (type(v) is int and 0 < v < 2**63))
                    and math.isfinite(v) and v > 0 for v in values), "Invalid OHLC value")
        opening, high, low, closing = values
        require(low <= min(opening, closing) <= max(opening, closing) <= high,
                "Invalid OHLC bounds")
        volume = price.get("volume")
        require("volume" in price and (volume is None or
                (_integer(volume) and 0 <= volume < 2**63)), "Invalid volume")
        timestamp = price.get("source_timestamp")
        require(_integer(timestamp) and 0 <= timestamp < 2**63, "Invalid source_timestamp")
        try:
            timestamp_date = datetime.fromtimestamp(timestamp, VIETNAM_TZ).date().isoformat()
        except (ValueError, OSError, OverflowError):
            raise ContractError("Invalid source_timestamp") from None
        require(timestamp_date == trading_date, "Timestamp does not match Vietnam trading date")

    meta = _object(payload.get("meta"), "meta")
    require(_count(meta.get("total_price_sessions"), "total_price_sessions") == len(prices),
            "Price count mismatch")
    require(meta.get("price_start_date") == prices[0]["date"] and
            meta.get("price_end_date") == prices[-1]["date"], "Price bounds mismatch")
    financial = _object(payload.get("financial_data"), "financial_data")
    require(set(financial) == set(SECTIONS), "Unsupported or missing financial sections")
    for section, count_key in SECTIONS.items():
        rows = financial[section]
        require(isinstance(rows, list) and rows, f"{section} must be nonempty")
        require(_count(meta.get(count_key), count_key) == len(rows), f"{section} count mismatch")
        seen = set()
        for row in rows:
            _object(row, section)
            period = period_from_row(row, section)
            require(period["id"] not in seen, f"{section}: duplicate period")
            seen.add(period["id"])
            for key in ("organCode", "ticker"):
                require(key not in row or row[key] == symbol, f"{section}: {key} mismatch")
            require("ratioType" not in row or
                    (isinstance(row["ratioType"], str) and row["ratioType"]),
                    f"{section}: invalid ratioType")
    quality = _object(payload.get("quality"), "quality")
    issues = quality.get("issues")
    require(isinstance(issues, list), "quality.issues must be a list")
    for issue in issues:
        _object(issue, "quality issue")
        require(issue.get("severity") in ("ERROR", "WARNING", "INFO") and
                isinstance(issue.get("code"), str) and bool(issue["code"]) and
                isinstance(issue.get("message"), str), "Invalid quality issue")
    require(quality.get("status") == ("PASS_WITH_WARNINGS" if issues else "PASS"),
            "Invalid quality status")
    published = _count(quality.get("published_price_records"), "published_price_records")
    rejected = _count(quality.get("rejected_price_records"), "rejected_price_records")
    raw = _count(quality.get("raw_price_records"), "raw_price_records")
    require(published == len(prices) and raw == published + rejected, "Quality count mismatch")


def load_dataset(path: str | Path) -> dict:
    """Read strict JSON; disallow duplicate keys and oversized files (32 MiB)."""
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ContractError("Nonfinite JSON value")

    with Path(path).open("rb") as stream:
        content = stream.read(32 * 1024 * 1024 + 1)
    require(len(content) <= 32 * 1024 * 1024, "Dataset exceeds 32 MiB")
    try:
        payload = json.loads(content, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ContractError("Invalid dataset JSON") from exc
    validate_dataset(payload)
    return payload
