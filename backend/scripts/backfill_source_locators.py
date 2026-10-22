"""Add reconstruction metadata to matching current DB chunks; never re-embed or change text.

Default is read-only. --apply updates locator_json only and fails the batch if a
current chunk cannot be reconstructed exactly. Superseded chunks remain untouched.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.documents import db_source
from src.documents.db_chunking import CHUNKER_VERSION, chunk_document
from src.documents.db_ingest import stored_chunk_id
from src.documents.chunk_reconstruction import reconstruct_document_chunk


def locator_update(row, doc, chunks):
    if row['chunker_version'] != CHUNKER_VERSION or doc is None:
        raise ValueError('Unsupported chunker or missing source')
    chunk = chunks.get(row['chunk_index'])
    if 'chunk_text' in row and chunk is not None and chunk.text != row['chunk_text']:
        raise ValueError('Source differs from supplied reference text')
    if (chunk is None or chunk.content_hash != row['content_hash'].strip()
            or stored_chunk_id(row['index_version_id'], chunk) != row['chunk_id']):
        raise ValueError('Source differs from stored text/hash/chunk ID')
    locator = row['locator_json']
    locator = json.loads(locator) if isinstance(locator, str) else dict(locator or {})
    for key in ('source_table', 'source_id', 'section', 'row_keys'):
        if locator.get(key) != chunk.locator[key]:
            raise ValueError('Legacy source locator differs: ' + key)
    new = {**locator, 'reconstruction': chunk.locator['reconstruction']}
    if reconstruct_document_chunk(doc, new, row['content_hash'].strip()).text != chunk.text:
        raise ValueError('Reconstructed content differs')
    return locator, new


async def run(apply=False):
    import asyncpg
    from src.core.config import get_settings
    conn = await asyncpg.connect(get_settings().database_url, ssl='require', statement_cache_size=0, timeout=25)
    try:
        async with conn.transaction(readonly=not apply, isolation='repeatable_read'):
            if apply:
                await conn.execute("SET LOCAL lock_timeout='10s'")
                await conn.execute('SELECT pg_advisory_xact_lock(167218)')
                await conn.execute('LOCK TABLE public.text_chunks IN SHARE ROW EXCLUSIVE MODE')
                await conn.execute('LOCK TABLE public.documents, public.companies, public.news_articles, public.price_bars, public.price_indicators, public.market_index_bars IN SHARE MODE')
            rows = await conn.fetch('SELECT t.chunk_id::text,t.document_id::text,t.index_version_id::text,t.chunk_index,t.content_hash,t.locator_json,i.chunker_version,i.chunk_size,d.doc_type FROM public.text_chunks t JOIN public.index_versions i USING(index_version_id) JOIN public.documents d USING(document_id) WHERE t.superseded_at IS NULL')
            fetchers = {'COMPANY_PROFILE': db_source.fetch_company_documents, 'NEWS': db_source.fetch_news_documents,
                        'PRICE_HISTORY': db_source.fetch_price_documents, 'MARKET_INDEX': db_source.fetch_index_documents}
            docs = {}
            for typ in {r['doc_type'] for r in rows}:
                if typ not in fetchers:
                    raise ValueError('Unsupported current document type: ' + typ)
                docs[typ] = {d.document_id: d for d in await fetchers[typ](conn)}
            updates, cache = [], {}
            for row in rows:
                doc = docs[row['doc_type']].get(row['document_id'])
                key = (row['document_id'], row['chunk_size'])
                if key not in cache:
                    cache[key] = {ch.chunk_index: ch for ch in chunk_document(doc, row['chunk_size'])} if doc else {}
                old, new = locator_update(row, doc, cache[key])
                if old != new:
                    import uuid
                    updates.append((uuid.UUID(row['chunk_id']), json.dumps(new, ensure_ascii=False)))
            print('VERIFIED_CURRENT', len(rows), 'LOCATOR_UPDATES', len(updates), flush=True)
            if not apply:
                print('READ_ONLY_NO_UPDATES')
                return
            fingerprint = "SELECT chunk_id,md5((to_jsonb(t)-'locator_json')::text) AS fingerprint FROM public.text_chunks t ORDER BY chunk_id"
            before = await conn.fetch(fingerprint)
            await conn.executemany('UPDATE public.text_chunks SET locator_json=$2::jsonb WHERE chunk_id=$1 AND superseded_at IS NULL', updates)
            if await conn.fetch(fingerprint) != before:
                raise ValueError('Non-locator fields changed')
            verified = await conn.fetchval("SELECT count(*) FROM public.text_chunks WHERE superseded_at IS NULL AND locator_json->'reconstruction'->>'schema_version'='source-locator-v2'")
            if verified != len(rows):
                raise ValueError('Incomplete backfill')
        print('COMMITTED_LOCATORS_ONLY', verified)
    finally:
        await conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    asyncio.run(run(parser.parse_args().apply))
