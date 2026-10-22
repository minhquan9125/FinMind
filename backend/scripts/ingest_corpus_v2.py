"""Resume embedding an immutable v2 snapshot into its own append-only DB index.

Defaults to validation only; --apply enables new index/doc/chunk inserts.
No source writes, no chunk_text, no updates/superseding of old documents/chunks.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from src.documents.corpus_manifest import sha256
from src.documents.chunk_reconstruction import reconstruct_document_chunk
from src.documents.db_source import fetch_locator_document

NS = uuid.UUID('b77dbd7f-5d89-479d-90a3-421e5f0981ea')


def validate_snapshot(data):
    manifest = data['manifest']
    if manifest['schema_version'] != 'finmind-source-corpus-v2' or sha256(manifest) != data['manifest_sha256']:
        raise ValueError('Invalid v2 snapshot hash/schema')
    documents, chunks = set(), set()
    for doc in manifest['documents']:
        if doc['document_id'] in documents:
            raise ValueError('Duplicate snapshot document')
        documents.add(doc['document_id'])
        body = {k: v for k, v in doc.items() if k != 'snapshot_sha256'}
        if sha256(body) != doc['snapshot_sha256']:
            raise ValueError('Invalid snapshot document hash')
        for chunk in doc['chunks']:
            if chunk['source_chunk_id'] in chunks:
                raise ValueError('Duplicate snapshot chunk')
            chunks.add(chunk['source_chunk_id'])
            if hashlib.sha256(chunk['text'].encode('utf-8')).hexdigest() != chunk['content_hash']:
                raise ValueError('Invalid snapshot chunk hash')
            meta = chunk['locator']['reconstruction']
            if meta['source_chunk_id'] != chunk['source_chunk_id'] or meta['content_hash'] != chunk['content_hash']:
                raise ValueError('Snapshot locator mismatch')
    if len(documents) != manifest['document_count'] or len(chunks) != manifest['chunk_count']:
        raise ValueError('Snapshot count mismatch')


def identities(digest, model, doc_id=None, source_chunk_id=None):
    index = uuid.uuid5(NS, f'corpus-v2:index:{digest}:{model}')
    document = uuid.uuid5(NS, f'corpus-v2:document:{digest}:{doc_id}') if doc_id else None
    chunk = uuid.uuid5(NS, f'corpus-v2:chunk:{index}:{source_chunk_id}') if source_chunk_id else None
    return index, document, chunk


async def preflight(conn, data):
    from src.documents import db_source
    async with conn.transaction(readonly=True, isolation='repeatable_read'):
        sources = {}
        for fetch in (db_source.fetch_company_documents, db_source.fetch_financial_documents,
                      db_source.fetch_price_documents, db_source.fetch_index_documents,
                      db_source.fetch_news_documents):
            for source in await fetch(conn):
                sources[(source.source_table, str(source.source_id))] = source
        for number, doc in enumerate(data['manifest']['documents'], 1):
            first = doc['chunks'][0]['locator']
            meta = first['reconstruction']
            source = sources.get((first['source_table'], first['source_id']))
            if source is None:
                raise ValueError(f'Source missing: {doc["document_id"]}')
            for chunk in doc['chunks']:
                reconstruct_document_chunk(source, chunk['locator'], chunk['content_hash'])
            if number % 100 == 0:
                print('PREFLIGHT', number, flush=True)


def preflight_snapshot(data, snapshot_path):
    from src.documents.source_snapshot import load_source_snapshot
    snapshot = load_source_snapshot(snapshot_path)
    checked = 0
    for doc in data['manifest']['documents']:
        for chunk in doc['chunks']:
            snapshot.resolve(chunk['locator'], chunk['content_hash'])
            checked += 1
    if checked != data['manifest']['chunk_count']:
        raise ValueError('Immutable snapshot chunk count mismatch')


async def run(args):
    import asyncpg
    from src.core.config import get_settings
    from src.documents.embeddings import EmbeddingService
    from src.documents.batch_embeddings import _validate_vector
    settings = get_settings()
    data = json.loads(args.manifest.read_text(encoding='utf-8'))
    validate_snapshot(data)
    index, _, _ = identities(data['manifest_sha256'], settings.embedding_model_ref)
    conn = await asyncpg.connect(settings.database_url, ssl='require', statement_cache_size=0, timeout=25)
    lock_acquired=False
    try:
        if args.source_snapshot:
            preflight_snapshot(data, args.source_snapshot)
        else:
            await preflight(conn, data)
        print('VALIDATED', data['manifest']['chunk_count'], 'INDEX', index, flush=True)
        if not args.apply:
            return
        lock_key = int.from_bytes(index.bytes[:8], 'big', signed=True)
        if not await conn.fetchval('SELECT pg_try_advisory_lock($1)', lock_key):
            raise ValueError('Another worker is already ingesting this corpus index')
        lock_acquired=True
        # BUILDING is intentionally not a benchmark-ready/ACTIVE corpus.
        await conn.execute('''INSERT INTO public.index_versions
            (index_version_id,chunker_version,chunk_size,chunk_overlap,embedding_model,built_at,status)
            VALUES($1,'db-corpus-v2',130,0,$2,now(),'BUILDING')
            ON CONFLICT(index_version_id) DO NOTHING''', index, settings.embedding_model_ref)
        existing = {str(r['chunk_id']): r['content_hash'].strip() for r in await conn.fetch(
            'SELECT chunk_id,content_hash FROM public.text_chunks WHERE index_version_id=$1', index)}
        # Reuse only exact-text, same-model, finite normalized vectors from older indexes.
        reusable = {}
        needed_hashes=sorted({c['content_hash'] for d in data['manifest']['documents'] for c in d['chunks']
            if str(identities(data['manifest_sha256'],settings.embedding_model_ref,
                              d['document_id'],c['source_chunk_id'])[2]) not in existing})
        for offset in range(0,0 if getattr(args,'skip_reuse_lookup',False) else len(needed_hashes),32):
            rows=await conn.fetch('''SELECT DISTINCT ON (t.content_hash) t.content_hash,t.embedding::text AS embedding
                FROM public.text_chunks t JOIN public.index_versions i USING(index_version_id)
                WHERE i.embedding_model=$1 AND vector_dims(t.embedding)=1024
                  AND t.content_hash=ANY($2::text[]) ORDER BY t.content_hash,t.chunk_id''',
                settings.embedding_model_ref,needed_hashes[offset:offset+32])
            for row in rows:
                reusable.setdefault(row['content_hash'].strip(),row['embedding'])
            print('REUSE_LOOKUP',min(offset+32,len(needed_hashes)),len(needed_hashes),flush=True)
        embedder = EmbeddingService(settings.embedding_model, revision=settings.embedding_model_revision,
                                    device=args.device or settings.embedding_device, batch_size=args.batch_size)
        completed, reused, embedded = 0, 0, 0
        start = time.monotonic()
        for doc in data['manifest']['documents']:
            _, document_id, _ = identities(data['manifest_sha256'], settings.embedding_model_ref, doc['document_id'])
            doc_hash = hashlib.sha256(f'{index}:{doc["snapshot_sha256"]}'.encode()).hexdigest()
            await conn.execute('''INSERT INTO public.documents
                (document_id,doc_type,file_type,title,external_id,language,sha256,parse_status,created_at,source_url)
                VALUES($1,$2,'DB',$3,$4,'vi',$5,'PARSED',now(),$6) ON CONFLICT(document_id) DO NOTHING''',
                document_id, doc['doc_type'], doc['title'][:500], str(doc['source_id'])[:100], doc_hash,
                doc['chunks'][0]['locator'].get('url'))
            pending = []
            for chunk in doc['chunks']:
                _, _, chunk_id = identities(data['manifest_sha256'], settings.embedding_model_ref,
                                             doc['document_id'], chunk['source_chunk_id'])
                if str(chunk_id) in existing:
                    if existing[str(chunk_id)] != chunk['content_hash']:
                        raise ValueError('Stored chunk collision')
                    completed += 1
                else:
                    pending.append((chunk_id, chunk))
            for offset in range(0, len(pending), args.batch_size):
                batch = pending[offset:offset+args.batch_size]
                need = [(key, c) for key, c in batch if c['content_hash'] not in reusable]
                if need:
                    vectors = embedder.embed_texts([c['text'] for _, c in need])
                    if len(vectors) != len(need):
                        raise ValueError('Embedding count mismatch')
                    for (_, chunk), vector in zip(need, vectors):
                        if _validate_vector(vector):
                            raise ValueError('Invalid embedding vector')
                        reusable[chunk['content_hash']] = json.dumps(vector)
                    embedded += len(need)
                async with conn.transaction():
                    for chunk_id, chunk in batch:
                        vector = reusable[chunk['content_hash']]
                        values = json.loads(vector)
                        if _validate_vector(values):
                            raise ValueError('Invalid reused embedding vector')
                        locator = chunk['locator']
                        reconstruction = locator['reconstruction']
                        await conn.execute('''INSERT INTO public.text_chunks
                            (chunk_id,document_id,index_version_id,chunk_index,section_label,token_count,
                             char_start,char_end,content_hash,embedding,locator_json,created_at)
                            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::vector,$11::jsonb,now())
                            ON CONFLICT(chunk_id) DO NOTHING''',
                            chunk_id, document_id, index, chunk['chunk_index'], locator['section'][:255],
                            chunk['token_count'], reconstruction['char_start'], reconstruction['char_end'],
                            chunk['content_hash'], vector, json.dumps(locator, ensure_ascii=False))
                reused += len(batch)-len(need)
                completed += len(batch)
                progress = {'index_version_id': str(index), 'manifest_sha256': data['manifest_sha256'],
                            'status': 'BUILDING', 'completed': completed,
                            'expected': data['manifest']['chunk_count'], 'newly_embedded': embedded,
                            'reused_exact_hash': reused, 'elapsed_seconds': round(time.monotonic()-start),
                            'device': args.device or settings.embedding_device, 'batch_size': args.batch_size}
                args.progress.parent.mkdir(parents=True, exist_ok=True)
                args.progress.write_text(json.dumps(progress, indent=2), encoding='utf-8')
                print(json.dumps(progress), flush=True)
        count = await conn.fetchval('SELECT count(*) FROM public.text_chunks WHERE index_version_id=$1', index)
        if count != data['manifest']['chunk_count']:
            raise ValueError('Incomplete corpus vector inventory')
        args.progress.write_text(json.dumps({
            'index_version_id': str(index), 'manifest_sha256': data['manifest_sha256'],
            'status': 'VECTORS_WRITTEN_PENDING_VERIFICATION', 'completed': count,
            'expected': count, 'newly_embedded': embedded, 'reused_exact_hash': reused,
            'benchmark_ready': False, 'corpus_registered': False,
            'device': args.device or settings.embedding_device, 'batch_size': args.batch_size,
        }, indent=2), encoding='utf-8')
        print('EMBEDDING_COMPLETE', count, index, flush=True)
    finally:
        if lock_acquired and not conn.is_closed():
            await conn.execute('SELECT pg_advisory_unlock($1)',lock_key)
        await conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT/'backend/.tmp/corpus-v2.content.manifest.json')
    parser.add_argument('--progress', type=Path, default=ROOT/'backend/.tmp/corpus-v2-ingest-progress.json')
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--device', choices=['cpu', 'cuda'], help='Explicit device; CUDA errors do not silently fall back to CPU')
    parser.add_argument('--source-snapshot', type=Path,
                        help='Use the immutable snapshot for preflight instead of mutable live sources')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--skip-reuse-lookup',action='store_true',
                        help='Embed remaining chunks directly; avoids slow lookup across older indexes')
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error('batch-size must be positive')
    asyncio.run(run(args))
