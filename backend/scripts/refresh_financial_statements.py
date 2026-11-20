"""BCTC refresh: Vietcap statement numbers plus Vietstock financial-statement PDFs, append-only.

  python -m backend.scripts.refresh_financial_statements                  # dry run: capture, download, decide
  python -m backend.scripts.refresh_financial_statements --apply          # write new periods, documents, verifications
  python -m backend.scripts.refresh_financial_statements --symbols FPT,BID

Per symbol: capture Vietcap, read the Vietstock catalog, download the in-scope PDFs (consolidated
first; the separate file only when the consolidated one does not verify), decide, then write in one
transaction. Network work happens before that transaction opens. A symbol that fails is rolled back
and reported; the others still run. More than MAX_NEW_VERSIONS restatements for one symbol in one
run rolls that symbol back (TOO_MANY_RESTATEMENTS). Nothing is ever updated or deleted.
The dry run still downloads PDFs to the cache but never opens a write transaction.
Each run writes outputs/financial-refresh/<time>/report.json, with the Vietcap captures beside it.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
from zipfile import BadZipFile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pypdf

from backend.src.core.config import get_settings
from backend.src.financial import exact_json, statement_pdf
from backend.src.financial import verification_store as store
from backend.src.financial.verification import decide, quarter_basis, same_conclusion
from backend.src.market_data.activity import VN
from data_pipeline.annual_reports.vietstock_download_annual import VietstockAnnualClient, extract_zip_pdfs, safe_component
from data_pipeline.financial_data.financial_capture import SECTIONS, capture_financial, financial_records
from data_pipeline.financial_data.vietstock_statements import fetch_catalog

SYMBOLS = ('VCB', 'BID', 'CTG', 'MBB', 'TCB', 'FPT', 'CMG', 'ELC', 'ITD', 'ICT')
ANNUAL_YEARS = (2024, 2025)
QUARTER_FROM = '2025-Q1'
MAX_NEW_VERSIONS = 4
PDF_MAGIC = b'%PDF'
VERIFY_SECTIONS = ('INCOME_STATEMENT', 'BALANCE_SHEET')
VERIFY_CODES = ('NET_REVENUE', 'TOTAL_OPERATING_INCOME', 'PROFIT_AFTER_TAX', 'TOTAL_ASSETS', 'OWNERS_EQUITY')
# Income-statement flow metrics only: period-end balances do not add up over quarters.
FLOW_CODES = {'BANK': ('TOTAL_OPERATING_INCOME', 'PROFIT_AFTER_TAX'), 'TECH': ('NET_REVENUE', 'PROFIT_AFTER_TAX')}
SCOPE_ORDER = {'CONSOLIDATED': 0, 'SEPARATE': 1}
COUNTS = ('new_reports', 'new_versions', 'verifications_added', 'verified', 'partial', 'mismatch')
LATEST = """SELECT DISTINCT ON (r.statement_scope) r.statement_scope, r.report_id, r.payload_id
            FROM financial_reports r JOIN reporting_periods p USING (period_id)
            WHERE r.company_id=$1 AND p.period_code=$2 AND r.statement_scope = ANY($3::text[])
            ORDER BY r.statement_scope, r.report_version DESC"""


class TooManyRestatements(Exception):
    pass


def in_scope(period_code: str) -> bool:
    return period_code in {f'{y}-YEAR' for y in ANNUAL_YEARS} or '-Q' in period_code and period_code >= QUARTER_FROM


def _prior(period_code: str) -> str:
    return f'{int(period_code[:4]) - 1}{period_code[4:]}'


def capture(fetch_vietcap, symbol: str, profile: dict, folder: Path) -> tuple[list, dict]:
    """Vietcap records for every provider field (None values dropped) and each section's raw response."""
    manifest = fetch_vietcap([symbol], folder, {symbol: profile})
    company = manifest['companies'][symbol]
    if company.get('status') != 'complete':
        raise RuntimeError(f"Vietcap capture {company.get('status')}: {company.get('failure_class') or manifest.get('status')}")
    run_dir = Path(manifest['run_dir'])
    normalized = exact_json.loads((run_dir / company['normalized_path']).read_text(encoding='utf-8'))
    by_json = {v: k for k, v in SECTIONS.items()}
    decoded = {by_json[k]: rows for k, rows in normalized['financial_data'].items()}
    records = [r for r in financial_records(symbol, profile, decoded, dataset_version=manifest['dataset_version'],
                                            receipts=company['sections']) if r['value'] is not None]
    raw = {s: (r['url'], (run_dir / r['path']).read_bytes().decode('utf-8-sig')) for s, r in company['sections'].items()}
    return records, raw


def report_inputs(records: list, industry: str) -> dict:
    """decide() report dicts per period, from the captured values (IS + BS)."""
    values: dict[str, dict] = {}
    for r in records:
        if r['section'] in VERIFY_SECTIONS and r['code'] in VERIFY_CODES:
            values.setdefault(r['period_code'], {})[r['code']] = Decimal(r['value'])
    out = {}
    for period, current in values.items():
        basis = None
        if '-Q' in period:
            flow = lambda p: {k: v for k, v in values.get(p, {}).items() if k in FLOW_CODES[industry]}
            basis = quarter_basis(flow(f'{period[:4]}-YEAR'), {q: flow(f'{period[:4]}-Q{q}') for q in (1, 2, 3, 4)
                                                                 if f'{period[:4]}-Q{q}' in values})
        out[period] = dict(period_code=period, industry=industry, values=current,
                           prior_values=values.get(_prior(period)), quarter_basis=basis)
    return out


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _page_count(data: bytes):
    try:
        return len(pypdf.PdfReader(BytesIO(data)).pages)
    except Exception:  # unreadable PDFs are still recorded, without a page count
        return None


def _cached(path: Path):
    """(sha256, mtime) of a cached PDF, None when absent or not a PDF. Blocking: run in a thread."""
    if not path.exists():
        return None
    data = path.read_bytes()
    if not data.startswith(PDF_MAGIC):
        return None
    return _sha(data), datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)


def _pages(path: Path, data: bytes):
    """read_pages result cached next to the PDF by sha256: OCR of a scan takes minutes and the job reruns daily.
    A NoTextLayer/PdfUnreadable outcome about the file is cached too, so a broken file is not re-read every run;
    OcrUnavailable (tools missing, OCR crash or timeout) is about this machine and is never cached."""
    sha = _sha(data)
    cache = path.with_name(path.stem + '.pages.json')
    errors = {'NoTextLayer': statement_pdf.NoTextLayer, 'PdfUnreadable': statement_pdf.PdfUnreadable}
    try:
        stored = json.loads(cache.read_text(encoding='utf-8'))
        if stored.get('sha256') == sha:
            error = stored.get('error')
            if error is None:
                return stored['pages']
            if error['type'] in errors:
                return errors[error['type']](error['message'])
    except (OSError, ValueError, KeyError, AttributeError, TypeError):
        pass  # missing or damaged cache: read the PDF again
    try:
        pages = statement_pdf.read_pages(data)
        stored = dict(sha256=sha, pages=pages)
    except statement_pdf.OcrUnavailable as exc:
        return exc
    except (statement_pdf.NoTextLayer, statement_pdf.PdfUnreadable) as exc:
        pages = exc
        stored = dict(sha256=sha, error=dict(type=type(exc).__name__, message=str(exc)))
    try:
        temporary = cache.with_name(cache.name + '.tmp')
        temporary.write_text(json.dumps(stored, ensure_ascii=False), encoding='utf-8')
        temporary.replace(cache)
    except OSError:
        pass  # the pages are already read; a cache that cannot be written only costs a re-read next run
    return pages


def _load(path: Path):
    """Read and parse the cached file; None (file removed) when it is not a PDF. Blocking: run in a thread."""
    data = path.read_bytes()
    if data.startswith(b'PK\x03\x04'):
        with tempfile.TemporaryDirectory(dir=path.parent) as folder:
            try:
                pdfs = extract_zip_pdfs(path, Path(folder))
            except (BadZipFile, ValueError):  # ValueError: expands beyond the extractor's size cap
                pdfs = []
            if len(pdfs) == 1:
                extracted = Path(folder) / Path(pdfs[0]).name
                data = extracted.read_bytes()
                extracted.replace(path)
    if not data.startswith(PDF_MAGIC):
        path.unlink()  # a login or error page is never cached or recorded as a statement
        return None
    return dict(sha256=_sha(data), file_size=len(data), page_count=_page_count(data), pages=_pages(path, data))


async def fetch_pdf(conn, entry: dict, download) -> dict | None:
    """Cached PDF, re-downloaded when absent, not a PDF, its sha256 differs from the stored document, or the
    catalog's LastUpdate is newer than both the stored document and the cached file. None: not a PDF."""
    path = (ROOT / 'data/references/vietstock/financial_statements/files' / entry['symbol'] / entry['period_code']
            / f"{safe_component(entry['external_id'], 'file')}.pdf")
    cached = await asyncio.to_thread(_cached, path)
    stale = cached is None
    if not stale:
        rows = await conn.fetch('SELECT sha256,published_at FROM documents WHERE external_id=$1', entry['external_id'])
        published = [r['published_at'] for r in rows if r['published_at'] is not None]
        updated = entry.get('last_update')
        cached_sha, cached_at = cached
        # The file mtime stops a loop when the source bumps LastUpdate but serves the same bytes.
        replaced = updated is not None and bool(published) and updated > max(published) and updated > cached_at
        stale = replaced or bool(rows) and cached_sha not in {r['sha256'] for r in rows}
    if stale:
        await asyncio.to_thread(download, entry['url'], path)
    loaded = await asyncio.to_thread(_load, path)
    return None if loaded is None else dict(entry=entry, **loaded)


async def choose(conn, inputs: dict, candidates: list, download, skipped: list) -> tuple[list, tuple | None]:
    """Consolidated first; the next file only when the previous does not verify or is not a PDF. Returns
    the PDFs fetched and (pdf, conclusion): the first VERIFIED, else the one with the most metrics found."""
    fetched, best = [], None
    for entry in sorted(candidates, key=lambda e: SCOPE_ORDER.get(e['scope'], 2)):
        pdf = await fetch_pdf(conn, entry, download)
        if pdf is None:
            skipped.append(dict(period_code=entry['period_code'], external_id=entry['external_id'],
                                reason='DOWNLOAD_NOT_PDF'))
            continue
        fetched.append(pdf)
        document = dict(scope=entry['scope'], audit_status=entry['audit_status'], title=entry['title'],
                        url=entry['url'], document_id=None)
        conclusion = await asyncio.to_thread(decide, inputs, {'document': document, 'pages': pdf['pages'],
                                                              'fiscal_end': None})
        # No file verifies yet: keep the one with the most metrics found (consolidated wins ties).
        if (best is None or conclusion['status'] == 'VERIFIED'
                or len(conclusion.get('evidence') or ()) > len(best[1].get('evidence') or ())):
            best = (pdf, conclusion)
        if conclusion['status'] == 'VERIFIED':
            break
    return fetched, best


async def known_records(conn, records: list) -> tuple[list, list]:
    """Records whose (code, section, industry) exists in metrics, and the sorted unknown keys. A new provider
    field is reported and quarantined instead of failing the whole symbol."""
    keys = {store.metric_key(r) for r in records}
    known = {tuple(r) for r in await conn.fetch('SELECT code,section,industry_scope FROM metrics '
                                                'WHERE code = ANY($1::text[])', list({k[0] for k in keys}))}
    return [r for r in records if store.metric_key(r) in known], sorted(keys - known)


async def plan_reports(conn, company_id, records: list) -> tuple[dict, set]:
    """Read-only twin of append_reports: counts and the (period, section) groups that change.
    `records` must contain known metrics only (see known_records)."""
    counts, fresh, groups = dict(new_reports=0, new_versions=0), set(), {}
    for r in records:
        groups.setdefault((r['period_code'], r['section']), {})[r['code']] = Decimal(r['value'])
    for (period, section), new in groups.items():
        latest = await conn.fetchval(
            'SELECT r.report_id FROM financial_reports r JOIN reporting_periods p USING (period_id) '
            'WHERE r.company_id=$1 AND p.period_code=$2 AND r.statement_scope=$3 ORDER BY r.report_version DESC LIMIT 1',
            company_id, period, section)
        if latest is None:
            counts['new_reports'] += 1
        else:
            old = {r['code']: r['value'] for r in await conn.fetch(
                'SELECT m.code,o.value FROM observations o JOIN metrics m USING (metric_id) WHERE o.report_id=$1',
                latest)}
            if not store.values_differ(old, new):
                continue
            counts['new_versions'] += 1
        fresh.add((period, section))
    return counts, fresh


async def refresh_symbol(conn, symbol: str, apply: bool, item: dict, *, years, folder, fetch_vietcap, client,
                         download) -> int:
    """One symbol; fills `item` and returns the number of documents added (or, dry run, that would be)."""
    company = await conn.fetchrow('SELECT company_id,industry_type,sector FROM companies WHERE symbol=$1', symbol)
    if company is None or company['industry_type'] not in FLOW_CODES:
        raise ValueError(f'{symbol}: unknown company or unsupported industry')
    profile = {'industry': company['industry_type'], 'industry_name': company['sector']}
    records, raw = await asyncio.to_thread(capture, fetch_vietcap, symbol, profile, folder)
    inputs = await asyncio.to_thread(report_inputs, records, company['industry_type'])
    entries = await asyncio.to_thread(fetch_catalog, client, symbol, list(years))
    periods: dict[str, list] = {}
    for entry in entries:
        if in_scope(entry['period_code']) and entry['period_code'] in inputs:
            periods.setdefault(entry['period_code'], []).append(entry)
    pdfs, choices = [], {}
    for period, candidates in sorted(periods.items()):
        fetched, best = await choose(conn, inputs[period], candidates, download, item['skipped'])
        pdfs += fetched
        if best is not None:
            choices[period] = best

    if not apply:
        return await _store(conn, company['company_id'], records, raw, pdfs, choices, item, None)
    async with conn.transaction():
        return await _store(conn, company['company_id'], records, raw, pdfs, choices, item, symbol)


async def _store(conn, company_id, records, raw, pdfs, choices, item, write_symbol) -> int:
    """Apply when write_symbol is set; otherwise count what would be written, reading only."""
    apply = write_symbol is not None
    records, unknown = await known_records(conn, records)
    item['unknown_metrics'] = [list(k) for k in unknown[:20]]
    counts, fresh = await plan_reports(conn, company_id, records)
    if apply:
        vietcap = await store.ensure_source(conn, 'VIETCAP_VCI', source_type='FINANCIAL_DATA',
                                            base_url='https://iq.vietcap.com.vn')
        vietstock = await store.ensure_source(conn, 'Vietstock BCTC', source_type='FINANCIAL_DOCUMENT',
                                              base_url='https://finance.vietstock.vn')
        numbers_job, documents_job = await store.start_job(conn, vietcap), await store.start_job(conn, vietstock)
        changed = {section for _, section in fresh}
        for section in SECTIONS:
            recs = [r for r in records if r['section'] == section]
            # The raw response carries serverDateTime, so it is new on every call: store it only when it
            # backs a new report or version, otherwise raw_payloads would grow with orphans every run.
            if not recs or section not in changed:
                continue
            uri, text = raw[section]
            payload_id = await store.store_payload(conn, numbers_job, source_uri=uri, payload_text=text)
            result = await store.append_reports(conn, recs, job_id=numbers_job, payload_id=payload_id)
            item['new_reports'] += result['new_reports']
            item['new_versions'] += result['new_versions']
        if unknown and not await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM quarantine_records WHERE reason_code='UNKNOWN_METRIC' "
                "AND reasons @> $1::jsonb)", json.dumps({'metrics': item['unknown_metrics']})):
            await store.quarantine(conn, numbers_job, payload_id=None, reason_code='UNKNOWN_METRIC',
                                   reasons={'metrics': item['unknown_metrics']})
    else:
        item.update(counts)
    if item['new_versions'] > MAX_NEW_VERSIONS:
        raise TooManyRestatements()

    added_docs, doc_ids = 0, {}
    for pdf in pdfs:
        if pdf['sha256'] in doc_ids:
            continue
        found = await conn.fetchval('SELECT document_id FROM documents WHERE sha256=$1', pdf['sha256'])
        added_docs += found is None
        if apply:
            period_id = await conn.fetchval('SELECT period_id FROM reporting_periods WHERE period_code=$1',
                                            pdf['entry']['period_code'])
            found = await store.ensure_document(conn, pdf['entry'], company_id=company_id, period_id=period_id,
                                                job_id=documents_job, sha256=pdf['sha256'],
                                                page_count=pdf['page_count'], file_size=pdf['file_size'])
        doc_ids[pdf['sha256']] = found

    quarantined = 0
    for period, (pdf, conclusion) in choices.items():
        conclusion = {**conclusion, 'document_id': doc_ids[pdf['sha256']]}
        rows = {r['statement_scope']: r for r in await conn.fetch(LATEST, company_id, period, list(VERIFY_SECTIONS))}
        for section in VERIFY_SECTIONS:
            row = rows.get(section)
            if apply:
                if row is None:
                    continue
                added = await store.append_verification(conn, row['report_id'], documents_job, conclusion) is not None
            elif (period, section) in fresh:
                added = True  # a new report or version starts without a verification
            elif row is None:
                continue
            else:
                current = await store.current_verification(conn, row['report_id'])
                added = not (current and same_conclusion({k: current.get(k) for k in conclusion}, conclusion))
            item[conclusion['status'].lower()] += 1
            item['verifications_added'] += added
            if added and conclusion['status'] == 'MISMATCH':
                quarantined += 1
                if apply:
                    await store.quarantine(conn, documents_job, payload_id=row['payload_id'],
                                           reason_code='VERIFICATION_MISMATCH',
                                           reasons={'reason_codes': conclusion['reason_codes'],
                                                    'report_id': row['report_id'],
                                                    'document_id': conclusion['document_id']})
    if apply:
        await store.finish_job(conn, numbers_job, ok=len(records), quarantined=0, status='SUCCEEDED')
        await store.finish_job(conn, documents_job, ok=item['verifications_added'], quarantined=quarantined,
                               status='SUCCEEDED')
    return added_docs


def _write_report(path: Path, report: dict):
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


async def run(apply: bool, *, now: datetime, symbols=SYMBOLS, fetch_vietcap=None, vietstock=None, download=None,
              connect=None, on_report=None) -> int:
    """0 when every symbol finished, 1 when any failed. fetch_vietcap(symbols, output_root, profiles),
    vietstock (catalog client), download(url, target) and connect() are replaceable for tests."""
    fetch_vietcap = fetch_vietcap or capture_financial
    client = vietstock or VietstockAnnualClient(delay=1.0)
    download = download or client.download
    if connect is None:
        import asyncpg
        connect = lambda: asyncpg.connect(get_settings().database_url, timeout=10, command_timeout=60,
                                          statement_cache_size=0)
    years = sorted({*ANNUAL_YEARS, *range(int(QUARTER_FROM[:4]), now.year + 1)})
    folder = ROOT / 'outputs/financial-refresh' / datetime.now(VN).strftime('%Y%m%d-%H%M%S-%f')
    await asyncio.to_thread(folder.mkdir, parents=True)
    report = {'started_at': now.isoformat(), 'apply': apply, 'symbols': {}, 'documents_added': 0}
    conn = None
    try:
        for symbol in symbols:
            item = report['symbols'][symbol] = dict(status='ok', **dict.fromkeys(COUNTS, 0), skipped=[], error=None,
                                                    unknown_metrics=[])
            try:
                if conn is None or conn.is_closed():  # a dropped connection is replaced once per symbol
                    conn = await connect()
                    if not apply:  # the dry run is read-only at the session level, not just by code path
                        await conn.execute('SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY')
                report['documents_added'] += await refresh_symbol(
                    conn, symbol, apply, item, years=years, folder=folder, fetch_vietcap=fetch_vietcap,
                    client=client, download=download)
            except Exception as exc:  # one symbol's failure never stops the others; never a DSN in the report
                item['status'] = 'failed'
                item['error'] = ('TOO_MANY_RESTATEMENTS' if isinstance(exc, TooManyRestatements)
                                 else f'{type(exc).__name__}: {exc}'[:500])
    finally:
        if conn is not None:
            await conn.close()
        if vietstock is None:  # only the client this run created
            await asyncio.to_thread(client.session.close)
        await asyncio.to_thread(_write_report, folder / 'report.json', report)
        if on_report is not None:
            on_report(report)

    for symbol, item in report['symbols'].items():
        line = (f"{symbol}: {item['status']}, bao cao moi {item['new_reports']}, phien ban moi {item['new_versions']}, "
                f"xac minh them {item['verifications_added']} (dung {item['verified']}, thieu {item['partial']}, "
                f"lech {item['mismatch']})")
        if item['skipped']:
            line += f", bo qua {len(item['skipped'])} tep khong phai PDF"
        if item['error']:
            line += ' LOI: ' + item['error']
        print(line.encode('ascii', 'backslashreplace').decode())  # the backend console may not encode Vietnamese
    print(f"Tai lieu moi: {report['documents_added']}." + ('' if apply else ' Chay thu: chua ghi gi. Them --apply de ghi.'))
    print(f"Bien ban: {folder / 'report.json'}")
    return 1 if any(item['status'] == 'failed' for item in report['symbols'].values()) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='write to the database (default: dry run)')
    parser.add_argument('--symbols', help='comma-separated subset, default: ' + ','.join(SYMBOLS))
    args = parser.parse_args(argv)
    symbols = SYMBOLS
    if args.symbols:
        symbols = tuple(s.strip().upper() for s in args.symbols.split(',') if s.strip())
        if not symbols or any(s not in SYMBOLS for s in symbols):
            parser.error('--symbols must be a subset of ' + ','.join(SYMBOLS))
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors='replace')
    return asyncio.run(run(args.apply, now=datetime.now(VN), symbols=symbols))


if __name__ == '__main__':
    raise SystemExit(main())
