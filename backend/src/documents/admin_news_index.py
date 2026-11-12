"""Approved News -> chunk/vector -> shared DB corpus, automatically published by one job."""
import asyncio
import json
import uuid
import tempfile
from pathlib import Path
from dataclasses import replace
from datetime import datetime

from .admin_ingestion import canonical, sha
from .db_chunking import news_documents, chunk_document, CHUNKER_VERSION
from .db_ingest import embed_all, upsert_document, write_chunks
from .job_recovery import job_worker
from .chunk_reconstruction import ReconstructionError, reconstruct_document_chunk


def source_document(payload, payload_id):
    article = dict(payload['article'], article_id=str(payload_id))
    published = article.get('published_at')
    if published:
        article['published_at'] = datetime.fromisoformat(published.replace('Z', '+00:00'))
    doc = news_documents([article])[0]
    return replace(doc, source_table='raw_payloads')


def prepare(record):
    if record['status'] != 'APPROVED': raise ValueError('ARTICLE_NOT_APPROVED')
    body = {'schema_version': 'admin-news-snapshot-v1', 'article': record['payload'],
            'approved_digest': record['digest'], 'reviews': record['reviews']}
    checksum = sha(body); payload_id = uuid.uuid5(uuid.NAMESPACE_URL, 'admin-news:' + checksum)
    doc = source_document(body, payload_id); chunks = chunk_document(doc)
    if not chunks: raise ValueError('EMPTY_CHUNKS')
    for chunk in chunks:
        chunk.locator['admin_news_snapshot'] = {'payload_id': str(payload_id), 'sha256': checksum}
    return body, payload_id, checksum, doc, chunks


async def resolve_snapshot(conn, locator, expected_hash):
    try:
        binding = locator['admin_news_snapshot']
        if locator['source_table'] != 'raw_payloads' or locator['source_id'] != binding['payload_id']:
            raise ValueError('Wrong source')
        row = await conn.fetchrow('SELECT payload,sha256 FROM public.raw_payloads WHERE payload_id=$1',
                                  uuid.UUID(binding['payload_id']))
        if row is None: raise ReconstructionError('SOURCE_MISSING', 'Snapshot missing')
        payload = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
        if (payload.get('schema_version') != 'admin-news-snapshot-v1'
                or row['sha256'].strip() != binding['sha256'] or sha(payload) != binding['sha256']):
            raise ReconstructionError('HASH_MISMATCH', 'Snapshot changed')
        doc = source_document(payload, binding['payload_id'])
        return reconstruct_document_chunk(doc, locator, expected_hash).text
    except ReconstructionError: raise
    except (KeyError, ValueError, TypeError, IndexError):
        raise ReconstructionError('INVALID_LOCATOR', 'Invalid admin News snapshot') from None


async def connect_writer(settings):
    if not settings.admin_ingest_database_url:
        raise ValueError('ADMIN_INGEST_DATABASE_URL_REQUIRED')
    import asyncpg
    from ..core.db import _init_connection
    conn = await asyncpg.connect(settings.admin_ingest_database_url.get_secret_value(), timeout=15,
                                 statement_cache_size=0, command_timeout=90)
    try: await _init_connection(conn)
    except BaseException:
        await conn.close(); raise
    return conn


async def build(queue, ident, settings, embedder=None, *, publish=False):
    import numpy as np
    from .embeddings import get_embedding_service
    from .corpus_manifest import read_manifest
    from .news_batch_runner import write_json
    job = queue.get_job(ident)
    prepared = [prepare(queue.article(aid)) for aid in job['details']['article_ids']]
    queue.update_job(ident, 'RUNNING', phase='CHUNKING', chunks=sum(len(p[-1]) for p in prepared))
    # Check writer access before spending time on embeddings.
    conn = await connect_writer(settings)
    try:
        queue.update_job(ident, 'RUNNING', phase='EMBEDDING', completed_documents=0, total_documents=len(prepared))
        service = embedder or get_embedding_service()
        # Bound vector RAM to one article, even when selecting hundreds of articles.
        # All embeddings still finish before the atomic DB transaction begins.
        with tempfile.TemporaryDirectory(prefix='vectors-' + ident + '-', dir=queue.root) as work:
            for position, item in enumerate(prepared, 1):
                embedded = await asyncio.to_thread(embed_all, service, item[-1])
                np.save(Path(work) / f'{position}.npy', np.asarray(embedded, dtype=np.float32), allow_pickle=False)
                queue.update_job(ident, 'RUNNING', phase='EMBEDDING', completed_documents=position, total_documents=len(prepared))
            index_id = uuid.UUID(ident)
            queue.update_job(ident, 'RUNNING', phase='WRITING_INDEX')
            async with conn.transaction():
                await conn.execute('''INSERT INTO public.index_versions
                    (index_version_id,chunker_version,chunk_size,chunk_overlap,embedding_model,built_at,status)
                    VALUES($1,$2,130,0,$3,now(),'BUILDING')''', index_id, CHUNKER_VERSION, settings.embedding_model_ref)
                for position, (payload, pid, checksum, doc, chunks) in enumerate(prepared, 1):
                    embedded = np.load(Path(work) / f'{position}.npy', allow_pickle=False).tolist()
                    await conn.execute('''INSERT INTO public.raw_payloads(payload_id,source_uri,sha256,payload,stored_at)
                        VALUES($1,$2,$3,$4::jsonb,now()) ON CONFLICT(payload_id) DO NOTHING''',
                        pid, payload['article']['url'], checksum, canonical(payload))
                    await upsert_document(conn, doc, chunks)
                    await write_chunks(conn, doc, chunks, embedded, str(index_id))
                base = getattr(settings,'research_corpus_version_id',None)
                if base:
                    from .admin_shared_index import merge_shared
                    base = queue.serving_corpus(base)
                    extras = [j['id'] for j in queue.jobs() if j['kind']=='INDEX' and j['status']=='ACTIVE']
                    manifest = await merge_shared(conn,str(index_id),base,settings,extra_indices=extras)
                else:
                    manifest = await read_manifest(conn, str(index_id))
        write_json(queue.root / (ident + '.manifest.json'), manifest)
        queue.update_job(ident, 'RUNNING' if publish else 'INDEXED',
                         phase='PUBLISHING' if publish else 'READY_TO_ACTIVATE',auto_publish=publish,index_version_id=ident,
                         corpus_version_id=manifest['corpus_version_id'], manifest_sha256=manifest['manifest_sha256'],
                         shared_base_corpus=base, shared_chunk_count=manifest.get('manifest',{}).get('chunk_count'))
        if not publish: queue.indexed(ident)
    finally: await conn.close()


async def activate(queue, ident, settings):
    from .corpus_manifest import read_manifest, register_manifest
    job = queue.get_job(ident)
    if not (job['status']=='INDEXED' or (job['status']=='RUNNING' and job['details'].get('phase')=='PUBLISHING')):
        raise ValueError('INDEX_NOT_READY')
    base = job['details'].get('shared_base_corpus')
    if base and queue.serving_corpus(settings.research_corpus_version_id) not in (base,job['details'].get('corpus_version_id')):
        raise ValueError('SHARED_BASE_CHANGED_REBUILD_REQUIRED')
    conn = await connect_writer(settings)
    try:
        async with conn.transaction():
            status = await conn.fetchval('SELECT status FROM public.index_versions WHERE index_version_id=$1 FOR UPDATE', uuid.UUID(ident))
            if status not in ('BUILDING','ACTIVE'): raise ValueError('INDEX_STATE_CHANGED')
            manifest = await read_manifest(conn, ident)
            if manifest['manifest_sha256'] != job['details']['manifest_sha256']:
                raise ValueError('INDEX_CHANGED_SINCE_BUILD')
            if not base and getattr(settings,'research_corpus_version_id',None):
                from .admin_shared_index import merge_shared
                base = queue.serving_corpus(settings.research_corpus_version_id)
                manifest = await merge_shared(conn,ident,base,settings)
            await register_manifest(conn, manifest, 'admin-' + ident[:20])
            await conn.execute("UPDATE public.index_versions SET status='ACTIVE' WHERE index_version_id=$1", uuid.UUID(ident))
            if base:
                from ..vector_retrieval.backend import cache_verified_manifest
                cache=Path(__file__).resolve().parents[1]/'vector_retrieval'/'.cache'/('corpus-'+manifest['corpus_version_id']+'.json')
                queue.update_job(ident,'RUNNING',phase='PREPARING_SEARCH')
                await cache_verified_manifest(conn,manifest,cache)
        queue.finish_index(ident,dict(phase='PUBLISHED_NEW_VERSION',
                           corpus_version_id=manifest.get('corpus_version_id',job['details'].get('corpus_version_id')),
                           manifest_sha256=manifest['manifest_sha256'],shared_base_corpus=base,
                           shared_chunk_count=manifest.get('manifest',{}).get('chunk_count')),
                           corpus_id=manifest.get('corpus_version_id') if base else None,
                           default_corpus=getattr(settings,'research_corpus_version_id',None),expected_base=base)
        if base:
            # Tell the other machines which corpus is now served; never fails the activation.
            from .shared_serving import best_effort_publish
            await best_effort_publish(conn, manifest.get('corpus_version_id'), ident, str(job.get('actor') or 'admin'))
    finally: await conn.close()


@job_worker
def index_job(queue, ident, settings):
    async def run():
        job=queue.get_job(ident)
        if job['details'].get('manifest_sha256'):
            queue.update_job(ident,'RUNNING',phase='PUBLISHING',auto_publish=True)
        else:
            await build(queue,ident,settings,publish=True)
        await activate(queue,ident,settings)
    try: asyncio.run(run())
    except Exception as exc:
        code = 'ADMIN_INGEST_DATABASE_URL_REQUIRED' if str(exc) == 'ADMIN_INGEST_DATABASE_URL_REQUIRED' else type(exc).__name__
        if queue.get_job(ident)['status'] != 'INTERRUPTED':
            queue.update_job(ident, 'FAILED', error=code)
