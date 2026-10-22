"""Database access for ERD-backed documents, chunks, and index versions."""

import uuid
import json
import hashlib
from datetime import datetime, timezone

import asyncpg
from .chunk_reconstruction import ReconstructionError, reconstruct_document_chunk
from .db_source import fetch_locator_document


def index_for_document(document, chunk_words, overlap, model):
    """DB source chunks use db-v1; legacy uploads retain word-window-v1."""
    if document.get('file_type') == 'DB':
        from .db_ingest import index_version_id_for as source_index
        return source_index(chunk_words, model)
    return index_version_id_for(chunk_words, overlap, model)


async def index_for_read(pool, document, settings):
    """Use the configured corpus for DB document detail reads as well as search."""
    if document.get('file_type')=='DB' and settings.default_corpus_version_id:
        from .corpus_scope import load_scope,CorpusScopeError
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True,isolation='repeatable_read'):
                scope=await load_scope(conn,settings.default_corpus_version_id,model=settings.embedding_model_ref,
                                       expected_hash=settings.default_corpus_manifest_sha256)
                member=await conn.fetchval('SELECT 1 FROM public.corpus_documents WHERE corpus_version_id=$1 AND document_id=$2',
                    uuid.UUID(scope.corpus_version_id),uuid.UUID(str(document['id'])))
                if not member:raise CorpusScopeError('DOCUMENT_OUTSIDE_CORPUS','Document is outside configured corpus')
                return scope.index_version_id
    return index_for_document(document,settings.chunk_words,settings.chunk_words-settings.chunk_stride,settings.embedding_model_ref)


async def resolve_result_rows(conn, rows):
    """Rebuild result text exclusively from verified sources."""
    resolved, sources = [], {}
    from .core_snapshot import configured_source_snapshot
    from ..core.config import get_settings
    source_backend=get_settings().source_read_backend
    if source_backend not in ('local','supabase'):
        raise ReconstructionError('INVALID_SOURCE_BACKEND','Unknown source read backend')
    snapshot = configured_source_snapshot() if source_backend=='local' else None
    for record in rows:
        row = dict(record)
        try:
            locator = row.get('locator_json') or {}
            locator = json.loads(locator) if isinstance(locator, str) else locator
            if not isinstance(locator, dict):
                raise ValueError('locator_json is not an object')
        except (TypeError, ValueError) as exc:
            raise ReconstructionError('INVALID_LOCATOR', 'Invalid stored locator') from exc
        if 'reconstruction' in locator:
            # Validate metadata before using max_words in a source query.
            from .chunk_reconstruction import _metadata
            _, meta = _metadata(locator)
            if source_backend=='supabase' and row.get('chunker_version')=='db-corpus-v2':
                from .shared_source import resolve_shared_source
                if not row.get('index_version_id'):
                    raise ReconstructionError('INVALID_LOCATOR','Shared source requires index identity')
                row['text']=await resolve_shared_source(conn,row['index_version_id'],locator,row['content_hash'],sources)
                resolved.append(row)
                continue
            archived = row.get('chunker_version') == 'db-corpus-v2' and locator['source_table'] == 'financial_reports'
            index_id = row.get('index_version_id') if archived else None
            if archived and not index_id:
                raise ReconstructionError('INVALID_LOCATOR', 'Archived financial source requires index identity')
            if snapshot is not None:
                row['text'] = snapshot.resolve(locator, row['content_hash'])
                resolved.append(row)
                continue
            key = (locator['source_table'], locator['source_id'], meta['max_words'], meta['chunker_version'], str(index_id))
            if key not in sources:
                kwargs = ({'financial_renderer_version': meta['chunker_version']}
                          if locator['source_table'] == 'financial_reports' else {})
                sources[key] = await fetch_locator_document(conn, *key[:3], **kwargs)
                if archived and sources[key] is not None:
                    from .renderer_context import read_renderer_context
                    sources[key] = await read_renderer_context(conn, index_id, sources[key])
            source = sources[key]
            if source is None:
                raise ReconstructionError('SOURCE_MISSING', 'Source no longer available')
            result = reconstruct_document_chunk(source, locator, row['content_hash'].strip())
            row['text'] = result.text
        elif locator.get('schema_version') == 'upload-source-v1' and locator.get('source_table') == 'raw_payloads':
            from .upload_source import read_upload_chunks
            chunks = await read_upload_chunks(conn, locator, sources)
            position = row['chunk_index']
            if type(position) is not int or position < 0 or position >= len(chunks):
                raise ReconstructionError('INVALID_LOCATOR', 'Upload chunk position is invalid')
            chunk = chunks[position]
            if (hashlib.sha256(chunk.text.encode('utf-8')).hexdigest() != row['content_hash'].strip()
                    or chunk.page != row['page']):
                raise ReconstructionError('HASH_MISMATCH', 'Upload chunk differs from its source')
            row['text'] = chunk.text
        else:
            raise ReconstructionError('INVALID_LOCATOR', 'Chunk requires a source locator')
        resolved.append(row)
    return resolved


def index_version_id_for(chunk_size, chunk_overlap, embedding_model):
    version_key = f"word-window-v1:{chunk_size}:{chunk_overlap}:{embedding_model}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"finmind:index:{version_key}"))


async def ensure_index_version(pool, chunk_size, chunk_overlap, embedding_model):
    version_id = uuid.UUID(index_version_id_for(chunk_size, chunk_overlap, embedding_model))
    await pool.execute(
        'INSERT INTO index_versions(index_version_id,chunker_version,chunk_size,chunk_overlap,'
        "embedding_model,built_at,status) VALUES($1,'word-window-v1',$2,$3,$4,$5,'ACTIVE') "
        'ON CONFLICT(index_version_id) DO NOTHING', version_id, chunk_size, chunk_overlap,
        embedding_model, datetime.now(timezone.utc))
    return str(version_id)


async def create_document(pool, filename, page_count, file_type, file_size, sha256, doc_type='USER_UPLOAD'):
    document_id = uuid.uuid5(uuid.NAMESPACE_URL, f'finmind:document:{sha256}')
    result = await pool.fetchval(
        'INSERT INTO documents(document_id,doc_type,file_type,title,page_count,file_size,sha256,parse_status,created_at) '
        "VALUES($1,$2,$3,$4,$5,$6,$7,'PARSED',$8) ON CONFLICT(sha256) DO UPDATE "
        'SET parse_status=EXCLUDED.parse_status RETURNING document_id',
        document_id, doc_type, file_type.upper(), filename, page_count, file_size, sha256, datetime.now(timezone.utc))
    return str(result)


async def insert_chunks(pool, document_id, index_version_id, rows):
    await pool.executemany(
        'INSERT INTO text_chunks(chunk_id,document_id,index_version_id,chunk_index,page_number,locator_json,'
        'token_count,char_start,char_end,content_hash,embedding,created_at) '
        'VALUES($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10,$11,$12) '
        'ON CONFLICT(index_version_id,document_id,chunk_index) WHERE superseded_at IS NULL DO UPDATE '
        'SET page_number=EXCLUDED.page_number,locator_json=EXCLUDED.locator_json,'
        'token_count=EXCLUDED.token_count,char_start=EXCLUDED.char_start,char_end=EXCLUDED.char_end,'
        'content_hash=EXCLUDED.content_hash,embedding=EXCLUDED.embedding,created_at=EXCLUDED.created_at',
        [(uuid.uuid4(), uuid.UUID(document_id), uuid.UUID(index_version_id), row['chunk_index'], row['page'],
          json.dumps(row['locator_json']), row['token_count'], row['char_start'], row['char_end'],
          row['content_hash'], row['embedding'], datetime.now(timezone.utc)) for row in rows])


async def get_document(pool, document_id):
    return await pool.fetchrow(
        'SELECT document_id AS id,title AS filename,page_count,file_type FROM documents WHERE document_id=$1',
        uuid.UUID(document_id))


async def get_chunks(pool, document_id, index_version_id):
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            rows = await conn.fetch(
                'SELECT t.index_version_id,t.chunk_index,t.page_number AS page,t.content_hash,t.locator_json,'
                't.token_count,i.chunker_version FROM text_chunks t JOIN index_versions i USING(index_version_id) '
                'WHERE t.document_id=$1 AND t.index_version_id=$2 AND t.superseded_at IS NULL '
                'ORDER BY t.chunk_index', uuid.UUID(document_id), uuid.UUID(index_version_id))
            return await resolve_result_rows(conn, rows)


async def vector_search(pool, document_id, index_version_id, query_embedding, top_k):
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            rows = await conn.fetch(
                'SELECT t.index_version_id,t.chunk_index,t.page_number AS page,t.content_hash,t.locator_json,i.chunker_version,'
                '1-(t.embedding <=> $3::vector) AS score FROM text_chunks t JOIN index_versions i USING(index_version_id) '
                'WHERE t.document_id=$1 AND t.index_version_id=$2 AND t.superseded_at IS NULL '
                'ORDER BY t.embedding <=> $3::vector LIMIT $4',
                uuid.UUID(document_id), uuid.UUID(index_version_id), query_embedding, top_k)
            return await resolve_result_rows(conn, rows)


async def corpus_vector_search(pool, corpus_id, query_embedding, top_k, *, model,
                               document_id=None, expected_hash=None,symbols=None,period_codes=None,metric_codes=None):
    """Search exactly one registered corpus; no BUILDING/legacy fallback."""
    from .corpus_scope import load_scope, CorpusScopeError
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True,isolation='repeatable_read'):
            scope=await load_scope(conn,corpus_id,model=model,expected_hash=expected_hash)
            mismatched=await conn.fetchval('''SELECT count(*) FROM public.corpus_documents cd
                LEFT JOIN public.documents d USING(document_id) WHERE cd.corpus_version_id=$1
                AND (d.document_id IS NULL OR d.sha256 IS DISTINCT FROM cd.document_hash)''',uuid.UUID(scope.corpus_version_id))
            if mismatched:raise CorpusScopeError('CORPUS_DOCUMENT_CHANGED','Corpus document identity/hash changed')
            if document_id:
                member=await conn.fetchval('''SELECT 1 FROM public.corpus_documents
                    WHERE corpus_version_id=$1 AND document_id=$2''',
                    uuid.UUID(scope.corpus_version_id),uuid.UUID(document_id))
                if not member:raise CorpusScopeError('DOCUMENT_OUTSIDE_CORPUS','Document is not in requested corpus')
            metric_rows=None
            if metric_codes is not None:
                selected=await conn.fetch('''SELECT o.observation_id::text
                    FROM public.corpus_facts cf JOIN public.observations o USING(observation_id)
                    JOIN public.metrics m USING(metric_id)
                    JOIN public.financial_reports fr ON fr.report_id=o.report_id
                    JOIN public.reporting_periods rp USING(period_id)
                    JOIN public.companies c ON c.company_id=fr.company_id
                    WHERE cf.corpus_version_id=$1 AND c.symbol=ANY($2::text[])
                      AND rp.period_code=ANY($3::text[]) AND m.code=ANY($4::text[])''',
                    uuid.UUID(scope.corpus_version_id),symbols,period_codes,metric_codes)
                metric_rows=[r['observation_id'] for r in selected]
            rows=await conn.fetch('''SELECT t.chunk_id::text,t.document_id::text,t.index_version_id,
                t.chunk_index,t.page_number AS page,t.content_hash,t.locator_json,i.chunker_version,
                1-(t.embedding <=> $3::vector) AS score
                FROM public.corpus_documents cd JOIN public.documents d USING(document_id)
                JOIN public.text_chunks t ON t.document_id=d.document_id
                JOIN public.index_versions i ON i.index_version_id=t.index_version_id
                WHERE cd.corpus_version_id=$1 AND t.index_version_id=$2
                  AND t.superseded_at IS NULL AND d.sha256=cd.document_hash
                  AND ($4::uuid IS NULL OR t.document_id=$4)
                  AND ($6::text[] IS NULL OR EXISTS (
                    SELECT 1 FROM public.financial_reports fr
                    JOIN public.reporting_periods rp ON rp.period_id=fr.period_id
                    JOIN public.companies c ON c.company_id=fr.company_id
                    WHERE fr.report_id::text=t.locator_json->>'source_id'
                      AND t.locator_json->>'source_table'='financial_reports'
                      AND c.symbol=ANY($6::text[]) AND rp.period_code=ANY($7::text[])))
                  AND ($8::text[] IS NULL OR (t.locator_json->'row_keys') ?| $8::text[])
                ORDER BY t.embedding <=> $3::vector,t.chunk_id LIMIT $5''',
                uuid.UUID(scope.corpus_version_id),uuid.UUID(scope.index_version_id),query_embedding,
                uuid.UUID(document_id) if document_id else None,top_k,symbols,period_codes,metric_rows)
            return scope,await resolve_result_rows(conn,rows)
