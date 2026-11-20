"""Read the Vietstock financial-statement (BCTC) catalog: titles, links, update times."""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone

from data_pipeline.annual_reports.vietstock_download_annual import allowed_file_url

log = logging.getLogger(__name__)

# Terms 9 (6T) and 12 (9T) are deliberately absent: skipped.
TERM_PERIOD = {1: "YEAR", 2: "Q1", 3: "Q2", 4: "Q3", 5: "Q4"}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def parse_title(title: str) -> dict:
    t = _fold(title or "")
    if "hop nhat" in t:
        scope = "CONSOLIDATED"
    elif "cong ty me" in t or "rieng" in t:
        scope = "SEPARATE"
    else:
        scope = "UNKNOWN"
    if "kiem toan" in t:
        audit = "AUDITED"
    elif "soat xet" in t:
        audit = "REVIEWED"
    else:
        audit = "NOT_STATED"
    return {"scope": scope, "audit_status": audit}


def _last_update(value: object) -> datetime | None:
    match = re.search(r"/Date\((-?\d+)", str(value or ""))
    if not match:
        return None
    return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc)


def catalog_entries(rows: list[dict], *, symbol: str, year: int, term_id: int) -> list[dict]:
    suffix = TERM_PERIOD.get(term_id)
    if suffix is None:
        return []
    best: dict[str, dict] = {}
    for row in rows:
        period_code = f"{year}-{suffix}"
        try:
            url = allowed_file_url(row.get("Url"))
        except ValueError as exc:
            log.warning("Dropped %s %s FileInfoID=%s: %s", symbol, period_code, row.get("FileInfoID"), exc)
            continue
        updated = _last_update(row.get("LastUpdate"))
        if updated is None:
            log.warning("%s %s FileInfoID=%s: missing or invalid LastUpdate %r; kept with last_update=None",
                        symbol, period_code, row.get("FileInfoID"), row.get("LastUpdate"))
        title = str(row.get("Title") or row.get("FullName") or "").strip()
        entry = {
            "symbol": symbol.upper(),
            "period_code": period_code,
            **parse_title(title),
            "title": title,
            "url": url,
            "external_id": str(row.get("FileInfoID") or url),
            "last_update": updated,
        }
        key = entry["scope"] if entry["scope"] != "UNKNOWN" else f"UNKNOWN:{entry['external_id']}"
        old = best.get(key)
        if old is None or (updated is not None and (old["last_update"] is None or updated > old["last_update"])):
            best[key] = entry
    return list(best.values())


def fetch_catalog(client, symbol: str, years: list[int]) -> list[dict]:
    # Binding constraint: requests at least 1 s apart.
    if getattr(client, "delay", 0) < 1.0:
        raise ValueError("Vietstock client delay must be >= 1.0 s")
    type_id = client.document_type("Báo cáo tài chính", "Financial Statement", exact=True)
    out: list[dict] = []
    for year in years:
        for term_id in TERM_PERIOD:
            rows = client.reports_for(symbol, year, document_type_id=type_id, term_id=term_id)
            out += catalog_entries(rows, symbol=symbol, year=year, term_id=term_id)
    return out
