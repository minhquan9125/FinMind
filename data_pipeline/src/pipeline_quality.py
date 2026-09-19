"""Validation and normalization rules for crawler output."""

from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
PRICE_FIELDS = ("t", "o", "h", "l", "c", "v")


class PayloadValidationError(ValueError):
    """Raised when a provider payload cannot be normalized safely."""


def sanitize_json_value(value):
    """Convert non-finite floats to null without rounding valid values."""
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {key: sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    return value


def format_period(year_value, length_or_quarter):
    try:
        year = int(year_value)
    except (TypeError, ValueError):
        raise PayloadValidationError(f"Invalid reporting year: {year_value!r}") from None

    try:
        quarter = int(length_or_quarter) if length_or_quarter is not None else 5
    except (TypeError, ValueError):
        quarter = 5

    if quarter in (1, 2, 3, 4):
        return f"{year}-Q{quarter}", "QUARTER", year, quarter
    return f"{year}-YEAR", "YEAR", year, None


def sort_period_key(item):
    year = item.get("year", 0) or 0
    quarter = item.get("quarter")
    return int(year) * 10 + (int(quarter) if quarter is not None else 5)


def _issue(code, message, record_key=None, severity="ERROR"):
    issue = {"code": code, "severity": severity, "message": message}
    if record_key is not None:
        issue["record_key"] = str(record_key)
    return issue


def _trading_date(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp), tz=VIETNAM_TZ).date().isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        raise PayloadValidationError(f"Invalid price timestamp: {timestamp!r}") from None


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_price_history(prices):
    """Return all quality issues found in a normalized price series."""
    issues = []
    seen_dates = set()
    previous_date = None

    for price in prices:
        trading_date = price.get("date")
        if trading_date in seen_dates:
            issues.append(_issue("DUPLICATE_TRADING_DATE", "Duplicate daily price bar", trading_date))
        seen_dates.add(trading_date)
        if previous_date is not None and trading_date <= previous_date:
            issues.append(_issue("PRICE_DATE_ORDER", "Trading dates are not strictly increasing", trading_date))
        previous_date = trading_date

        open_price = price.get("open")
        high_price = price.get("high")
        low_price = price.get("low")
        close_price = price.get("close")
        values = (open_price, high_price, low_price, close_price)
        if not all(_is_number(value) and value > 0 for value in values):
            issues.append(_issue("INVALID_PRICE", "OHLC prices must be finite positive numbers", trading_date))
        elif high_price < max(open_price, close_price) or low_price > min(open_price, close_price):
            issues.append(_issue("INVALID_OHLC", "High/low does not contain open and close", trading_date))

        volume = price.get("volume")
        if volume is not None and (not _is_number(volume) or volume < 0 or int(volume) != volume):
            issues.append(_issue("INVALID_VOLUME", "Volume must be a non-negative integer or null", trading_date))

    return issues


def normalize_price_payload(raw_payload):
    """Normalize daily OHLCV, resolving duplicates and quarantining invalid bars."""
    if not isinstance(raw_payload, dict):
        raise PayloadValidationError("Price payload must be an object")
    arrays = {field: raw_payload.get(field) for field in PRICE_FIELDS}
    if not all(isinstance(value, list) for value in arrays.values()):
        raise PayloadValidationError("Price payload must contain t/o/h/l/c/v arrays")
    lengths = {len(value) for value in arrays.values()}
    if len(lengths) != 1:
        raise PayloadValidationError("Price arrays must have the same length")
    if not arrays["t"]:
        raise PayloadValidationError("Price payload is empty")

    by_date = {}
    issues = []
    for index, timestamp in enumerate(arrays["t"]):
        trading_date = _trading_date(timestamp)
        candidate = {
            "date": trading_date,
            "open": sanitize_json_value(arrays["o"][index]),
            "high": sanitize_json_value(arrays["h"][index]),
            "low": sanitize_json_value(arrays["l"][index]),
            "close": sanitize_json_value(arrays["c"][index]),
            "volume": sanitize_json_value(arrays["v"][index]),
            "source_timestamp": int(timestamp),
        }
        previous = by_date.get(trading_date)
        if previous is not None:
            issues.append(
                _issue(
                    "DUPLICATE_TRADING_DATE",
                    "Kept the bar with the latest provider timestamp",
                    trading_date,
                    severity="WARNING",
                )
            )
            if candidate["source_timestamp"] <= previous["source_timestamp"]:
                continue
        by_date[trading_date] = candidate

    valid_prices = []
    for candidate in sorted(by_date.values(), key=lambda item: item["date"]):
        candidate_issues = validate_price_history([candidate])
        if candidate_issues:
            issues.extend(candidate_issues)
        else:
            if candidate["volume"] is not None:
                candidate["volume"] = int(candidate["volume"])
            valid_prices.append(candidate)

    if not valid_prices:
        raise PayloadValidationError("No valid price bars remain after validation")
    return valid_prices, issues


def normalize_financial_rows(rows, *, ratio=False):
    """Add a stable natural period key while preserving provider fields."""
    if not isinstance(rows, list):
        raise PayloadValidationError("Financial rows must be a list")
    normalized = []
    seen_periods = set()
    for row in rows:
        if not isinstance(row, dict):
            raise PayloadValidationError("Each financial row must be an object")
        year = row.get("year") or row.get("yearReport") if ratio else row.get("yearReport")
        quarter = row.get("quarter") if ratio else row.get("lengthReport")
        label, period_type, year_number, quarter_number = format_period(year, quarter)
        if label in seen_periods:
            raise PayloadValidationError(f"Duplicate financial period: {label}")
        seen_periods.add(label)
        item = {
            "period_label": label,
            "period_type": period_type,
            "year": year_number,
            "quarter": quarter_number,
        }
        item.update(sanitize_json_value(row))
        normalized.append(item)
    normalized.sort(key=sort_period_key, reverse=True)
    return normalized


def atomic_write_json(path, payload):
    """Write strict JSON via a sibling temporary file and atomic replace."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
