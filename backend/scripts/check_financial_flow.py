"""Replay real financial inputs and read Supabase without database writes."""
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/scripts'),
               str(ROOT/'data_pipeline/FinancialCleaner')]
from cleaner.files import clean_file
from import_clean_financials import read_input, SECTION, stable_id
from src.documents.db_chunking import financial_documents, chunk_document
from src.documents.chunk_reconstruction import reconstruct_document_chunk
from src.documents.db_source import FINANCIAL_SQL

OUT = ROOT/'backend/.tmp/financial-flow-check'


def check_documents(rows):
    docs = financial_documents(rows)
    chunks = 0
    long_chunks = 0
    all_ids = set()
    for doc in docs:
        built = chunk_document(doc)
        expected = Counter(r.key for section in doc.sections for r in section.rows)
        actual = Counter(key for chunk in built for key in chunk.locator['row_keys'])
        if expected != actual:
            raise ValueError('Observation coverage mismatch')
        for chunk in built:
            if chunk.chunk_id in all_ids:
                raise ValueError('Duplicate chunk ID')
            all_ids.add(chunk.chunk_id)
            if reconstruct_document_chunk(doc, chunk.locator, chunk.content_hash).text != chunk.text:
                raise ValueError('Reconstruction mismatch')
            long_chunks += chunk.token_count > 130
        chunks += len(built)
    return {'reports': len(docs), 'observations': len(rows), 'chunks': chunks,
            'over_130_words': long_chunks, 'coverage_and_roundtrip': 'PASS'}


def local_replay():
    results = []
    for source in sorted((ROOT/'data/normalized').glob('*.json')):
        if source.stem not in {'FPT','CMG','ICT','ITD','ELC','VCB','BID','CTG','MBB','TCB'}:
            continue
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        # The real file adapter permits outputs only inside FinancialCleaner.
        output, _ = clean_file(source, ROOT/'data_pipeline/FinancialCleaner/.tmp/flow-check')
        item = read_input(output)
        rows = []
        for period, section, metric, value in item['values']:
            report_id = stable_id('clean-report', item['symbol'], period, item['digest'])
            metric_id = stable_id('metric', item['data']['ngành'], SECTION[section], metric['mã_chuẩn'])
            rows.append({'report_id': str(report_id), 'symbol': item['symbol'],
                         'company_name': item['data']['tên_doanh_nghiệp'], 'period_code': period,
                         'statement_scope': 'UNKNOWN', 'section': SECTION[section],
                         'code': metric['mã_chuẩn'], 'canonical_name': metric['tên_chỉ_tiêu'],
                         'observation_id': str(stable_id('observation', report_id, metric_id)),
                         'value': value, 'unit': 'SOURCE_NATIVE'})
        result = {'symbol': item['symbol'], **check_documents(rows)}
        if before != hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError('Normalized source changed')
        results.append(result)
        print(json.dumps({'local': result}), flush=True)
    if len(results) != 10:
        raise ValueError(f'Expected ten source companies, got {len(results)}')
    return results


async def database_check():
    import asyncpg
    from src.core.config import get_settings
    conn = await asyncpg.connect(get_settings().database_url, ssl='require', statement_cache_size=0, timeout=25)
    try:
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            stamp = str(await conn.fetchval('SELECT transaction_timestamp()'))
            rows = [dict(row) for row in await conn.fetch(FINANCIAL_SQL, None)]
            result = check_documents(rows)
            result.update(snapshot=stamp, readonly=True,
                          symbols=sorted({row['symbol'] for row in rows}))
            print(json.dumps({'database': result}), flush=True)
            return result
    finally:
        await conn.close()


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'database_writes': False, 'embedding_calls': False}
    collector = ROOT/'data_pipeline/financial_data/collect_financial_data.py'
    try:
        compile(collector.read_text(encoding='utf-8-sig'), str(collector), 'exec')
        report['collector_syntax'] = 'PASS (network collection not exercised)'
    except SyntaxError as exc:
        report['collector_error'] = {'type': type(exc).__name__, 'line': exc.lineno, 'message': exc.msg}
    try:
        report['local_replay'] = local_replay()
    except Exception as exc:
        report['local_error'] = {'type': type(exc).__name__, 'message': str(exc)}
        print(json.dumps({'local_error': report['local_error']}, ensure_ascii=False), flush=True)
    try:
        report['database'] = asyncio.run(database_check())
    except Exception as exc:
        # Do not include connection details/credentials in output.
        report['database_error'] = {'type': type(exc).__name__}
        print(json.dumps({'database_error': report['database_error']}), flush=True)
    (OUT/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if any(key.endswith('_error') for key in report):
        sys.exit(1)
