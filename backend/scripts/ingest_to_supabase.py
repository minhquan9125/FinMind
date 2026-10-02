"""Load normalized stock JSON into the financial tables described by the ERD.

The importer is deliberately dry-run by default. Pass ``--apply`` only after
the target PostgreSQL database has been migrated to the supplied ERD schema.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any
import uuid

import asyncpg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "normalized"
NAMESPACE = uuid.UUID("b77dbd7f-5d89-479d-90a3-421e5f0981ea")

if str(PROJECT_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from src.financial.mapping import META_KEYS, get_code, get_label_vi  # noqa: E402

SECTIONS = {
    "income_statement": "INCOME_STATEMENT",
    "balance_sheet": "BALANCE_SHEET",
    "cash_flow_statement": "CASH_FLOW",
    "ratios": "RATIO",
}

REQUIRED_COLUMNS = {
    "sources": {"source_id", "name", "source_type", "approval_status", "scope_note", "is_enabled"},
    "ingestion_jobs": {
        "job_id", "source_id", "trigger_type", "status", "schema_version",
        "started_at", "finished_at", "records_ok", "records_quarantined",
    },
    "raw_payloads": {"payload_id", "job_id", "source_uri", "sha256", "payload", "stored_at"},
    "companies": {"company_id", "symbol", "company_name", "industry_type", "sector", "exchange", "is_active"},
    "reporting_periods": {"period_id", "period_code", "fiscal_year", "quarter", "period_type", "start_date", "end_date"},
    "financial_reports": {
        "report_id", "company_id", "period_id", "document_id", "payload_id", "job_id",
        "statement_scope", "audit_status", "report_version", "restated_from_id", "published_at",
    },
    "metrics": {"metric_id", "code", "canonical_name", "section", "default_unit", "industry_scope", "mapping_status"},
    "observations": {"observation_id", "report_id", "metric_id", "value", "unit", "scale", "currency", "locator_json"},
    "price_bars": {"price_id", "company_id", "payload_id", "trade_date", "is_adjusted", "price_scale", "open", "high", "low", "close", "volume"},
}


def stable_id(kind: str, *parts: object) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, ":".join((kind, *(str(part) for part in parts))))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_period(label: str) -> tuple[int, int | None, str, date, date]:
    """Return fiscal year, quarter, type and calendar-period boundaries."""
    if len(label) == 7 and label[:4].isdigit() and label[4:6] == "-Q" and label[6] in "1234":
        year, quarter = int(label[:4]), int(label[-1])
        starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
        month, day = starts[quarter]
        start = date(year, month, day)
        end = date(year + (quarter == 4), 1 if quarter == 4 else month + 3, 1) - timedelta(days=1)
        return year, quarter, "QUARTER", start, end
    if len(label) == 4 and label.isdigit():
        year = int(label)
        return year, None, "YEAR", date(year, 1, 1), date(year, 12, 31)
    if label.endswith("-YEAR") and label[:4].isdigit():
        year = int(label[:4])
        return year, None, "YEAR", date(year, 1, 1), date(year, 12, 31)
    raise ValueError(f"Unsupported period_label {label!r}; expected YYYY-Q1..Q4 or YYYY-YEAR")


def normalize_payload(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: root JSON value must be an object")
    symbol = str(data.get("symbol") or path.stem).strip().upper()
    if not symbol or len(symbol) > 10:
        raise ValueError(f"{path.name}: missing or invalid stock symbol")
    if not isinstance(data.get("price_history"), list) or not isinstance(data.get("financial_data"), dict):
        raise ValueError(f"{path.name}: expected price_history[] and financial_data{{}} from data_pipeline")
    sources = data.get("sources") or {}
    if not isinstance(sources, dict):
        raise ValueError(f"{path.name}: sources must be an object")
    return {**data, "symbol": symbol, "sources": sources}


def source_info(data: dict[str, Any]) -> list[tuple[str, str, str, Any]]:
    sources = data["sources"]
    price_source = str(sources.get("prices") or "ENTRADE").strip()
    fundamentals_source = str(sources.get("fundamentals") or "VIETCAP_VCI").strip()
    return [
        (price_source, "MARKET_DATA", "Prices and daily OHLCV bars", data.get("price_history") or []),
        (fundamentals_source, "FINANCIAL_DATA", "Financial statements and ratios", data.get("financial_data") or {}),
    ]


def payload_identity(path: Path, data: dict[str, Any], source_name: str, section_payload: Any) -> tuple[uuid.UUID, uuid.UUID, str, str]:
    raw = canonical_json(section_payload).encode("utf-8")
    digest = sha256_bytes(raw)
    version = str(data.get("dataset_version") or "unknown")
    job_id = stable_id("job", data["symbol"], source_name, version, digest)
    payload_id = stable_id("payload", data["symbol"], source_name, version, digest)
    source_uri = f"{path.name}#{'price_history' if isinstance(section_payload, list) else 'financial_data'}"
    return job_id, payload_id, digest, source_uri


def financial_rows(data: dict[str, Any], company_id: uuid.UUID, payload_id: uuid.UUID, job_id: uuid.UUID) -> dict[str, list[tuple]]:
    """Build deterministic upsert rows for the supplied financial tables."""
    result: dict[str, list[tuple]] = {"periods": [], "reports": [], "metrics": [], "observations": []}
    financial_data = data.get("financial_data") or {}
    industry = str(data.get("industry") or "UNKNOWN").upper()
    version = str(data.get("dataset_version") or "unknown")
    periods_seen: set[str] = set()
    metrics_seen: dict[uuid.UUID, tuple] = {}
    reports_seen: set[uuid.UUID] = set()
    observations: dict[uuid.UUID, tuple] = {}

    for json_section, report_scope in SECTIONS.items():
        entries = financial_data.get(json_section) or []
        if not isinstance(entries, list):
            raise ValueError(f"{data['symbol']}: financial_data.{json_section} must be a list")
        for row in entries:
            if not isinstance(row, dict):
                continue
            period_code = str(row.get("period_label") or "").strip()
            if not period_code:
                continue
            year, quarter, period_type, start_date, end_date = parse_period(period_code)
            period_id = stable_id("period", period_code)
            if period_code not in periods_seen:
                result["periods"].append((period_id, period_code, year, quarter, period_type, start_date, end_date))
                periods_seen.add(period_code)

            report_id = stable_id("report", data["symbol"], period_code, report_scope)
            if report_id not in reports_seen:
                published_at = row.get("publicDate") or row.get("published_at")
                if isinstance(published_at, str) and published_at:
                    published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00")).date()
                elif isinstance(published_at, datetime):
                    published_at = published_at.date()
                else:
                    published_at = None
                result["reports"].append((
                    report_id, company_id, period_id, None, payload_id, job_id,
                    report_scope, "UNKNOWN", 1, None, published_at,
                ))
                reports_seen.add(report_id)

            for raw_key, value in row.items():
                if raw_key in META_KEYS or value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                code = get_code(raw_key, json_section, industry)
                canonical_name = get_label_vi(code)
                metric_id = stable_id("metric", industry, report_scope, code)
                unit = "SOURCE_NATIVE" if json_section == "ratios" else (
                    "VND_PER_SHARE" if code in {"BASIC_EARNINGS_PER_SHARE", "DILUTED_EARNINGS_PER_SHARE"} else "VND"
                )
                mapping_status = "MAPPED" if code != raw_key.upper() else "UNMAPPED"
                metrics_seen[metric_id] = (
                    metric_id, code, canonical_name, report_scope, unit, industry, mapping_status,
                )
                observation_id = stable_id("observation", report_id, metric_id)
                observation_unit = "SOURCE_NATIVE" if json_section == "ratios" else unit
                currency = "VND" if observation_unit in {"VND", "VND_PER_SHARE"} else None
                locator = json.dumps({
                    "source_field": raw_key,
                    "source_section": json_section,
                    "dataset_version": version,
                    "ratio_type": row.get("ratioType") if json_section == "ratios" else None,
                }, ensure_ascii=False, separators=(",", ":"))
                observations[observation_id] = (
                    observation_id, report_id, metric_id, value, observation_unit, 1, currency, locator,
                )

    result["metrics"] = list(metrics_seen.values())
    result["observations"] = list(observations.values())
    return result


def price_rows(data: dict[str, Any], company_id: uuid.UUID, payload_id: uuid.UUID) -> list[tuple]:
    output: dict[uuid.UUID, tuple] = {}
    for bar in data.get("price_history") or []:
        if not isinstance(bar, dict) or not bar.get("date"):
            continue
        trade_date = date.fromisoformat(str(bar["date"])[:10])
        price_id = stable_id("price", data["symbol"], trade_date, False)
        values = [bar.get(key) for key in ("open", "high", "low", "close")]
        output[price_id] = (
            price_id, company_id, payload_id, trade_date, False, 1000,
            *values, int(bar["volume"]) if bar.get("volume") is not None else None,
        )
    return list(output.values())


async def verify_schema(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        """SELECT table_name, column_name
           FROM information_schema.columns
           WHERE table_schema = 'public'"""
    )
    actual: dict[str, set[str]] = {}
    for row in rows:
        actual.setdefault(row["table_name"], set()).add(row["column_name"])
    missing = []
    for table, columns in REQUIRED_COLUMNS.items():
        absent = columns - actual.get(table, set())
        if absent:
            missing.append(f"{table}: {', '.join(sorted(absent))}")
    if missing:
        raise RuntimeError(
            "Target database does not match the supplied ERD; no data was written. Missing columns: "
            + "; ".join(missing)
        )


async def insert_source(conn: asyncpg.Connection, source_name: str, source_type: str, scope_note: str) -> uuid.UUID:
    source_id = stable_id("source", source_name)
    await conn.execute(
        """INSERT INTO public.sources
             (source_id, name, source_type, approval_status, scope_note, is_enabled)
           VALUES ($1, $2, $3, 'PENDING', $4, false)
           ON CONFLICT (source_id) DO NOTHING""",
        source_id, source_name, source_type, scope_note,
    )
    return source_id


async def store_job_and_payload(
    conn: asyncpg.Connection, path: Path, data: dict[str, Any], source_name: str,
    source_type: str, scope_note: str, section_payload: Any, record_count: int,
) -> tuple[uuid.UUID, uuid.UUID]:
    job_id, payload_id, digest, source_uri = payload_identity(path, data, source_name, section_payload)
    source_id = await insert_source(conn, source_name, source_type, scope_note)
    now = datetime.now(timezone.utc)
    await conn.execute(
        """INSERT INTO public.ingestion_jobs
             (job_id, source_id, trigger_type, status, schema_version, started_at, finished_at,
              records_ok, records_quarantined)
           VALUES ($1, $2, 'BATCH', 'SUCCEEDED', $3, $4, $4, $5, 0)
           ON CONFLICT (job_id) DO UPDATE SET
             status = EXCLUDED.status, finished_at = EXCLUDED.finished_at,
             records_ok = EXCLUDED.records_ok""",
        job_id, source_id, str(data.get("schema_version") or "1.0"), now, record_count,
    )
    await conn.execute(
        """INSERT INTO public.raw_payloads (payload_id, job_id, source_uri, sha256, payload, stored_at)
           VALUES ($1, $2, $3, $4, $5::jsonb, $6)
           ON CONFLICT (payload_id) DO UPDATE SET
             source_uri = EXCLUDED.source_uri, sha256 = EXCLUDED.sha256,
             payload = EXCLUDED.payload, stored_at = EXCLUDED.stored_at""",
        payload_id, job_id, source_uri, digest, canonical_json(section_payload), now,
    )
    return job_id, payload_id


async def upsert_company(conn: asyncpg.Connection, data: dict[str, Any]) -> uuid.UUID:
    symbol = data["symbol"]
    existing_id = await conn.fetchval(
        "SELECT company_id FROM public.companies WHERE symbol = $1 ORDER BY company_id LIMIT 1", symbol,
    )
    company_id = existing_id or stable_id("company", symbol)
    await conn.execute(
        """INSERT INTO public.companies
             (company_id, symbol, company_name, industry_type, sector, exchange, is_active)
           VALUES ($1, $2, $3, $4, $5, $6, true)
           ON CONFLICT (company_id) DO UPDATE SET
             company_name = EXCLUDED.company_name, industry_type = EXCLUDED.industry_type,
             sector = EXCLUDED.sector, exchange = EXCLUDED.exchange""",
        company_id, symbol, data.get("company_name") or symbol,
        str(data.get("industry") or "UNKNOWN").upper(),
        data.get("industry_name") or str(data.get("industry") or "UNKNOWN"),
        data.get("exchange"),
    )
    return company_id


async def upsert_rows(conn: asyncpg.Connection, rows: dict[str, list[tuple]]) -> None:
    statements = [
        ("periods", """INSERT INTO public.reporting_periods
             (period_id, period_code, fiscal_year, quarter, period_type, start_date, end_date)
           VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (period_id) DO UPDATE SET
             fiscal_year=EXCLUDED.fiscal_year, quarter=EXCLUDED.quarter, period_type=EXCLUDED.period_type,
             start_date=EXCLUDED.start_date, end_date=EXCLUDED.end_date"""),
        ("reports", """INSERT INTO public.financial_reports
             (report_id, company_id, period_id, document_id, payload_id, job_id, statement_scope,
              audit_status, report_version, restated_from_id, published_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) ON CONFLICT (report_id) DO UPDATE SET
             payload_id=EXCLUDED.payload_id, job_id=EXCLUDED.job_id, audit_status=EXCLUDED.audit_status,
             published_at=EXCLUDED.published_at"""),
        ("metrics", """INSERT INTO public.metrics
             (metric_id, code, canonical_name, section, default_unit, industry_scope, mapping_status)
           VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (metric_id) DO UPDATE SET
             canonical_name=EXCLUDED.canonical_name, default_unit=EXCLUDED.default_unit,
             mapping_status=EXCLUDED.mapping_status"""),
        ("observations", """INSERT INTO public.observations
             (observation_id, report_id, metric_id, value, unit, scale, currency, locator_json)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb) ON CONFLICT (observation_id) DO UPDATE SET
             value=EXCLUDED.value, unit=EXCLUDED.unit, scale=EXCLUDED.scale,
             currency=EXCLUDED.currency, locator_json=EXCLUDED.locator_json"""),
    ]
    for key, sql in statements:
        if rows.get(key):
            await conn.executemany(sql, rows[key])


async def apply_file(conn: asyncpg.Connection, path: Path, data: dict[str, Any]) -> dict[str, int]:
    symbol = data["symbol"]
    sources = source_info(data)
    counts: dict[str, int] = {}
    async with conn.transaction():
        company_id = await upsert_company(conn, data)
        price_source, price_type, price_scope, prices = sources[0]
        price_payload_id: uuid.UUID | None = None
        if prices:
            price_job_id, price_payload_id = await store_job_and_payload(
                conn, path, data, price_source, price_type, price_scope, prices, len(prices),
            )
            bars = price_rows(data, company_id, price_payload_id)
            await conn.executemany(
                """INSERT INTO public.price_bars
                     (price_id, company_id, payload_id, trade_date, is_adjusted, price_scale,
                      open, high, low, close, volume)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                   ON CONFLICT (price_id) DO UPDATE SET payload_id=EXCLUDED.payload_id,
                     open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                     close=EXCLUDED.close, volume=EXCLUDED.volume, price_scale=EXCLUDED.price_scale""",
                bars,
            ) if bars else None
            counts["price_bars"] = len(bars)
        else:
            counts["price_bars"] = 0

        finance_source, finance_type, finance_scope, financial_data = sources[1]
        financial_rows_count = sum(
            len(financial_data.get(section) or []) for section in SECTIONS
        )
        finance_job_id, finance_payload_id = await store_job_and_payload(
            conn, path, data, finance_source, finance_type, finance_scope,
            financial_data, financial_rows_count,
        )
        rows = financial_rows(data, company_id, finance_payload_id, finance_job_id)
        await upsert_rows(conn, rows)
        counts.update({
            "reporting_periods": len(rows["periods"]),
            "financial_reports": len(rows["reports"]),
            "metrics": len(rows["metrics"]),
            "observations": len(rows["observations"]),
        })
    return counts


def get_files(input_path: Path, symbols: list[str] | None) -> list[Path]:
    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = sorted(input_path.glob("*.json"))
    else:
        raise ValueError(f"Input does not exist: {input_path}")
    if symbols:
        selected = {symbol.upper() for symbol in symbols}
        files = [path for path in files if path.stem.upper() in selected]
        missing = selected - {path.stem.upper() for path in files}
        if missing:
            raise ValueError(f"No input JSON found for symbol(s): {', '.join(sorted(missing))}")
    if not files:
        raise ValueError(f"No JSON files found under {input_path}")
    return files


async def run(args: argparse.Namespace) -> int:
    paths = get_files(args.input, args.symbol)
    plans = []
    for path in paths:
        data = normalize_payload(path)
        company_id = stable_id("company", data["symbol"])
        rows = financial_rows(data, company_id, stable_id("payload", "preview"), stable_id("job", "preview"))
        counts = {
            "price_bars": len(price_rows(data, company_id, stable_id("payload", "preview"))),
            "reporting_periods": len(rows["periods"]),
            "financial_reports": len(rows["reports"]),
            "metrics": len(rows["metrics"]),
            "observations": len(rows["observations"]),
        }
        plans.append((path, data, counts))

    if not args.apply:
        for path, data, counts in plans:
            print(json.dumps({"symbol": data["symbol"], "file": path.name, "dry_run": True, "rows": counts}, ensure_ascii=False))
        print("Dry run only; no database connection or writes were made. Use --apply to load after deploying the ERD schema.")
        return 0

    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    load_dotenv(PROJECT_ROOT / ".env")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in backend/.env or project .env")
    ssl = "require" if "supabase.co" in database_url else None
    conn = await asyncpg.connect(database_url, ssl=ssl, statement_cache_size=0)
    try:
        await verify_schema(conn)
        for path, data, _ in plans:
            result = await apply_file(conn, path, data)
            print(json.dumps({"symbol": data["symbol"], "file": path.name, "applied": True, "rows": result}, ensure_ascii=False))
    finally:
        await conn.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Normalized JSON file or directory")
    parser.add_argument("--symbol", action="append", help="Limit import to a symbol; repeat to import several")
    parser.add_argument("--apply", action="store_true", help="Write rows to DATABASE_URL; default is dry-run")
    args = parser.parse_args(argv)
    try:
        return asyncio.run(run(args))
    except (ValueError, RuntimeError, asyncpg.PostgresError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
