"""Freeze a source-content candidate for corpus-v2, without writing Supabase.

This is NOT a registered/vector-ready benchmark corpus. It deliberately uses
a separate schema so freeze_corpus/register_manifest cannot mistake it for one.
"""
import argparse
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from src.documents import db_source
from src.documents.db_chunking import chunk_document
from src.documents.chunk_reconstruction import reconstruct_document_chunk
from src.documents.corpus_manifest import canonical, sha256


def freeze_documents(documents):
    result, seen_docs, seen_chunks = [], set(), set()
    counts = {}
    for doc in sorted(documents, key=lambda d: d.document_id):
        if doc.document_id in seen_docs:
            raise ValueError('Duplicate source document identity')
        seen_docs.add(doc.document_id)
        built = chunk_document(doc)
        if not built:
            continue
        expected = Counter(row.key for section in doc.sections for row in section.rows)
        actual = Counter(key for chunk in built for key in chunk.locator['row_keys'])
        if expected != actual:
            raise ValueError('Lost or repeated source rows')
        content = []
        for chunk in built:
            if chunk.chunk_id in seen_chunks:
                raise ValueError('Duplicate source chunk ID')
            seen_chunks.add(chunk.chunk_id)
            if reconstruct_document_chunk(doc, chunk.locator, chunk.content_hash).text != chunk.text:
                raise ValueError('Chunk reconstruction mismatch')
            content.append({'source_chunk_id': chunk.chunk_id, 'chunk_index': chunk.chunk_index,
                            'content_hash': chunk.content_hash, 'text': chunk.text,
                            'locator': chunk.locator, 'token_count': chunk.token_count})
        entry = {'document_id': doc.document_id, 'source_table': doc.source_table,
                 'source_id': doc.source_id, 'doc_type': doc.doc_type,
                 'title': doc.title, 'symbol': doc.symbol, 'chunks': content}
        entry['snapshot_sha256'] = sha256(entry)
        result.append(entry)
        stat = counts.setdefault(doc.doc_type, {'documents': 0, 'chunks': 0})
        stat['documents'] += 1
        stat['chunks'] += len(content)
    payload = {'schema_version': 'finmind-source-corpus-v2', 'version_label': 'corpus-v2',
               'document_count': len(result), 'chunk_count': len(seen_chunks),
               'summary': counts, 'documents': result}
    digest = sha256(payload)
    return {'status': 'CONTENT_FROZEN_AWAITING_VECTOR_INGEST',
            'benchmark_ready': False, 'database_registered': False,
            'database_writes': False, 'embedding_calls': False,
            'source_snapshot_id': str(uuid.uuid5(uuid.NAMESPACE_URL, 'finmind:source-corpus:'+digest)),
            'manifest_sha256': digest, 'manifest': payload}


async def run(args):
    import asyncpg
    from src.core.config import get_settings
    target = args.out
    # Never replace v1 or overwrite a different frozen candidate.
    if 'corpus-v1' in target.name:
        raise ValueError('Refusing to write corpus-v1')
    baseline = ROOT/'backend/.tmp/corpus-v1.manifest.json'
    before = hashlib.sha256(baseline.read_bytes()).hexdigest()
    conn = await asyncpg.connect(get_settings().database_url, ssl='require',
                                 statement_cache_size=0, timeout=25)
    try:
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            stamp = str(await conn.fetchval('SELECT transaction_timestamp()'))
            docs = []
            for name, fetch in [('companies', db_source.fetch_company_documents),
                                ('financial', db_source.fetch_financial_documents),
                                ('prices', db_source.fetch_price_documents),
                                ('indices', db_source.fetch_index_documents),
                                ('news', db_source.fetch_news_documents)]:
                batch = await fetch(conn)
                docs.extend(batch)
                print(json.dumps({'source': name, 'documents': len(batch)}), flush=True)
            # Inspect vector storage; this never certifies IDs of the new candidate.
            inventory = [dict(row) for row in await conn.fetch('''
                SELECT i.index_version_id::text,i.chunker_version,i.embedding_model,
                       count(t.chunk_id)::int AS total_chunks,
                       count(t.chunk_id) FILTER (WHERE t.superseded_at IS NULL)::int AS active_chunks
                FROM public.index_versions i LEFT JOIN public.text_chunks t USING(index_version_id)
                GROUP BY i.index_version_id,i.chunker_version,i.embedding_model
                ORDER BY i.index_version_id''')]
            result = freeze_documents(docs)
            result['provenance'] = {'database_snapshot': stamp,
                'source_scope': 'All current rows returned by the five production source readers; no local trial imports.',
                'original_corpus_v1_file_sha256': before,
                'vector_index_inventory_at_snapshot': inventory,
                'source_chunk_id_is_stored_vector_id': False,
                'excluded_local_trial_data': 'backend/.tmp/new-financial-flow; not imported into shared source tables'}
    finally:
        await conn.close()
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != before:
        raise ValueError('Corpus-v1 changed during preparation')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        old = json.loads(target.read_text(encoding='utf-8'))
        if old['manifest'] != result['manifest']:
            raise ValueError('Frozen output differs; choose a new path instead of overwriting')
    else:
        with target.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    print(json.dumps({'file': str(target), 'status': result['status'],
                      'manifest_sha256': result['manifest_sha256'],
                      'documents': result['manifest']['document_count'],
                      'chunks': result['manifest']['chunk_count'],
                      'summary': result['manifest']['summary'],
                      'vector_inventory': inventory}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'backend/.tmp/corpus-v2.content.manifest.json')
    asyncio.run(run(parser.parse_args()))
