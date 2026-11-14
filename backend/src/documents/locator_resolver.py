"""WBS11: turn a chunk locator back into the source rows it came from, and check it.

A chunk locator (``text_chunks.locator_json``) holds ``source_table``, ``source_id``
and ``row_keys``. ``resolve_locator`` maps those to a read-only SQL query for one
source table; ``verify_chunk`` runs it and checks that every row exists and that
the chunk text really mentions what the row says. Nothing here writes to the database.

Row key grammar (see ``db_chunking``):

* financial_reports : ``<observation_id>``
* news_articles     : ``p<n>`` (paragraph n of the article ``source_id``)
* price_bars        : ``<price_id>`` | ``<SYMBOL>:<YYYY-MM-DD>`` | ``<SYMBOL>:<YYYY-MM>:summary``
* market_index_bars : ``<INDEX>:<YYYY-MM-DD>`` | ``<INDEX>:<YYYY-MM>:summary``
* companies         : ``<SYMBOL>:<column of companies>``
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

_DAY_KEY = re.compile(r"^(?P<code>.+):(?P<day>\d{4}-\d{2}-\d{2})$")
_MONTH_KEY = re.compile(r"^(?P<code>.+):(?P<month>\d{4}-\d{2}):summary$")
_PARAGRAPH_KEY = re.compile(r"^p\d+$")

COMPANY_COLUMNS = frozenset({"symbol", "company_name", "exchange", "industry_type", "sector", "is_active"})


class LocatorError(ValueError):
    """The locator cannot be resolved (unknown table or malformed key)."""


@dataclass(frozen=True)
class RowRef:
    """One lookup: run ``sql`` with ``params``; it must return ``expected`` rows."""
    table: str
    keys: tuple[str, ...]
    sql: str
    params: tuple[Any, ...]
    expected: int
    must_appear: tuple[str, ...] = ()  # strings the chunk text has to contain


@dataclass
class VerifyResult:
    ok: bool
    table: str = ""
    checked: int = 0
    problems: list[str] = field(default_factory=list)


def _as_dict(locator: Any) -> dict[str, Any]:
    if isinstance(locator, (str, bytes)):
        locator = json.loads(locator)
    if not isinstance(locator, Mapping):
        raise LocatorError("locator must be an object")
    return dict(locator)


def resolve_locator(locator: Any) -> list[RowRef]:
    """Return the lookups that find the source rows of a chunk (one per key kind)."""
    loc = _as_dict(locator)
    table = loc.get("source_table")
    source_id = str(loc.get("source_id") or "")
    keys = [str(k) for k in loc.get("row_keys") or []]
    if not table or not keys:
        raise LocatorError("locator has no source_table or row_keys")

    if table == "financial_reports":
        return [RowRef(
            table, tuple(keys),
            "SELECT o.observation_id::text AS key, m.code FROM public.observations o "
            "JOIN public.metrics m ON m.metric_id = o.metric_id "
            "WHERE o.report_id::text = $1 AND o.observation_id::text = ANY($2::text[])",
            (source_id, keys), len(keys),
        )]

    if table == "news_articles":
        bad = [k for k in keys if not _PARAGRAPH_KEY.match(k)]
        if bad:
            raise LocatorError(f"news row keys must look like p1, p2...: {bad}")
        return [RowRef(
            table, tuple(keys),
            "SELECT article_id::text AS key, url FROM public.news_articles WHERE article_id::text = $1",
            (source_id,), 1,
        )]

    if table == "companies":
        columns = []
        for key in keys:
            symbol, _, column = key.rpartition(":")
            if not symbol or column not in COMPANY_COLUMNS:
                raise LocatorError(f"company key must be <SYMBOL>:<column>: {key}")
            columns.append(column)
        return [RowRef(
            table, tuple(keys),
            "SELECT symbol, company_name, exchange, industry_type, sector, is_active "
            "FROM public.companies WHERE symbol = $1",
            (keys[0].rpartition(":")[0],), 1,
            must_appear=(),
        )]

    if table in ("price_bars", "market_index_bars"):
        return _bar_refs(table, keys)

    raise LocatorError(f"unsupported source_table: {table}")


def _bar_refs(table: str, keys: list[str]) -> list[RowRef]:
    prices = table == "price_bars"
    refs: list[RowRef] = []
    ids: list[str] = []
    for key in keys:
        month = _MONTH_KEY.match(key)
        day = _DAY_KEY.match(key)
        if month:
            code, value = month["code"], month["month"]
            if prices:
                sql = ("SELECT p.trade_date::text AS key FROM public.price_bars p "
                       "JOIN public.companies c ON c.company_id = p.company_id "
                       "WHERE c.symbol = $1 AND to_char(p.trade_date, 'YYYY-MM') = $2")
            else:
                sql = ("SELECT trade_date::text AS key FROM public.market_index_bars "
                       "WHERE index_symbol = $1 AND to_char(trade_date, 'YYYY-MM') = $2")
            refs.append(RowRef(table, (key,), sql, (code, value), -1, (value,)))  # -1: at least one row
        elif day:
            code, value = day["code"], day["day"]
            if prices:
                sql = ("SELECT p.trade_date::text AS key FROM public.price_bars p "
                       "JOIN public.companies c ON c.company_id = p.company_id "
                       "WHERE c.symbol = $1 AND p.trade_date::text = $2")
            else:
                sql = ("SELECT trade_date::text AS key FROM public.market_index_bars "
                       "WHERE index_symbol = $1 AND trade_date::text = $2")
            refs.append(RowRef(table, (key,), sql, (code, value), 1, (value,)))
        elif prices:
            ids.append(key)
        else:
            raise LocatorError(f"index row key must be <INDEX>:<date> or <INDEX>:<month>:summary: {key}")
    if ids:
        refs.append(RowRef(
            table, tuple(ids),
            "SELECT p.price_id::text AS key, p.trade_date::text AS day FROM public.price_bars p "
            "WHERE p.price_id::text = ANY($1::text[])",
            (ids,), len(ids),
        ))
    return refs


async def verify_chunk(conn: Any, locator: Any, chunk_text: str) -> VerifyResult:
    """Check that every row the locator points to exists and fits the chunk text."""
    try:
        refs = resolve_locator(locator)
    except (LocatorError, ValueError) as exc:
        return VerifyResult(False, problems=[str(exc)])
    result = VerifyResult(True, table=refs[0].table)
    loc = _as_dict(locator)

    for ref in refs:
        rows = await conn.fetch(ref.sql, *ref.params)
        result.checked += len(ref.keys)
        if ref.expected == -1:
            if not rows:
                result.problems.append(f"no rows for {ref.keys[0]}")
        elif len(rows) != ref.expected:
            result.problems.append(f"{ref.table}: expected {ref.expected} rows, found {len(rows)}")
        for needle in ref.must_appear:
            if needle not in chunk_text:
                result.problems.append(f"chunk text does not mention {needle}")

        if ref.table == "financial_reports":
            for row in rows:
                if f"({row['code']})" not in chunk_text:
                    result.problems.append(f"chunk text does not mention metric {row['code']}")
        elif ref.table == "price_bars":
            for row in rows:
                day = row.get("day") if hasattr(row, "get") else None
                if day and day not in chunk_text:
                    result.problems.append(f"chunk text does not mention trade date {day}")
        elif ref.table == "news_articles" and rows:
            if loc.get("url") and rows[0]["url"] != loc["url"]:
                result.problems.append("news url differs from the locator url")
        elif ref.table == "companies" and rows:
            row = rows[0]
            for key in ref.keys:
                column = key.rpartition(":")[2]
                value = row[column]
                if value is None:
                    result.problems.append(f"{key} is empty in the database")
                elif column != "is_active" and str(value) not in chunk_text:
                    result.problems.append(f"chunk text does not mention {column}={value}")

    result.ok = not result.problems
    return result
