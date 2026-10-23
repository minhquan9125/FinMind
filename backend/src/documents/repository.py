"""Database access for ERD-backed documents, chunks, and index versions."""

import uuid
import json
import hashlib
from datetime import datetime, timezone

import asyncpg
from .chunk_reconstruction import (
    ReconstructionError, reconstruct_document_chunk, preview_changed_document_chunk,
)
from .db_source import fetch_locator_document

# This frozen release stores immutable source bindings in raw_payloads. Older
# indices still use their existing reconstruction path.
V4_SHARED_INDEX_ID = 'e3725b7d-1a39-5196-b000-3496dbab388f'


def index_for_document(document, chunk_words, overlap, model):
    """DB source chunks use db-v1; legacy uploads retain word-window-v1."""
    if document.get('file_type') == 'DB':
        from .db_ingest import index_version_id_for as source_index
        return source_index(chunk_words, model)
    return index_version_id_for(chunk_words, overlap, model)


async def resolve_result_rows(conn, rows, *, preview_source_changed=False):
    """Rebuild result text exclusively from verified sources."""
    resolved, sources = [], {}
    for record in rows:
        row = dict(record)
        try:
            locator = row.get('locator_json') or {}
            locator = json.loads(locator) if isinstance(locator, str) else locator
            if not isinstance(locator, dict):
                raise ValueError('locator_json is not an object')
        except (TypeError, ValueError) as exc:
            raise ReconstructionError('INVALID_LOCATOR', 'Invalid stored locator') from exc
        row['locator_json'] = locator
        if 'reconstruction' in locator:
            # Validate metadata before using max_words in a source query.
            from .chunk_reconstruction import _metadata
            _, meta = _metadata(locator)
            if (row.get('chunker_version') == 'db-corpus-v2'
                    and str(row.get('index_version_id')) == V4_SHARED_INDEX_ID):
                from .shared_source import resolve_shared_source
                row['text'] = await resolve_shared_source(
                    conn, V4_SHARED_INDEX_ID, locator, row['content_hash'], sources,
                )
                resolved.append(row)
                continue
            renderer = meta['chunker_version'] if locator['source_table'] == 'financial_reports' else 'db-v1'
            key = (locator['source_table'], locator['source_id'], meta['max_words'], renderer)
            if key not in sources:
                sources[key] = await fetch_locator_document(
                    conn, *key[:3], financial_renderer_version=renderer,
                )
            source = sources[key]
            if source is None:
                raise ReconstructionError('SOURCE_MISSING', 'Source no longer available')
            try:
                result = reconstruct_document_chunk(source, locator, row['content_hash'].strip())
            except ReconstructionError as exc:
                if not preview_source_changed or exc.code != 'SOURCE_CHANGED':
                    raise
                result = preview_changed_document_chunk(source, locator, row['content_hash'].strip())
                row['source_verified'] = False
                row['source_warning'] = 'SOURCE_CHANGED'
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
                'SELECT t.chunk_index,t.page_number AS page,t.content_hash,t.locator_json,t.index_version_id::text,'
                't.token_count,i.chunker_version FROM text_chunks t JOIN index_versions i USING(index_version_id) '
                'WHERE t.document_id=$1 AND t.index_version_id=$2 AND t.superseded_at IS NULL '
                'ORDER BY t.chunk_index', uuid.UUID(document_id), uuid.UUID(index_version_id))
            return await resolve_result_rows(conn, rows)


async def vector_search(pool, document_id, index_version_id, query_embedding, top_k):
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            rows = await conn.fetch(
                'SELECT t.chunk_index,t.page_number AS page,t.content_hash,t.locator_json,t.index_version_id::text,i.chunker_version,'
                '1-(t.embedding <=> $3::vector) AS score FROM text_chunks t JOIN index_versions i USING(index_version_id) '
                'WHERE t.document_id=$1 AND t.index_version_id=$2 AND t.superseded_at IS NULL '
                'ORDER BY t.embedding <=> $3::vector LIMIT $4',
                uuid.UUID(document_id), uuid.UUID(index_version_id), query_embedding, top_k)
            return await resolve_result_rows(conn, rows)


async def get_corpus_index(pool, corpus_version_id):
    """Return the index and statuses pinned by a corpus, without changing data."""
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            row = await conn.fetchrow(
                '''SELECT cv.corpus_version_id::text, cv.index_version_id::text,
                          cv.status AS corpus_status, iv.status AS index_status,
                          iv.embedding_model
                   FROM public.corpus_versions cv
                   JOIN public.index_versions iv USING(index_version_id)
                   WHERE cv.corpus_version_id=$1::uuid''',
                uuid.UUID(str(corpus_version_id)),
            )
            return dict(row) if row else None


async def vector_search_filtered(
    pool,
    index_version_id,
    query_embedding,
    top_k,
    company_symbol=None,
    period=None,
    doc_type=None,
    corpus_version_id=None,
    preview_source_changed=False,
    on_ranked=None,
):
    """Search active chunks in one embedding version, applying source filters first.

    ``period`` matches a reporting-period code, news publication date, or the
    month/period label in a source locator.  This keeps the query usable across
    the existing financial, news, price, company, and market-index sources.
    """
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            rows = await conn.fetch(
                '''
                SELECT t.chunk_id::text, t.document_id::text, t.chunk_index,
                       t.content_hash, t.locator_json, t.index_version_id::text, i.chunker_version,
                       d.title, d.doc_type,
                       coalesce(c.symbol, t.locator_json->>'symbol') AS company_symbol,
                       coalesce(p.period_code, t.locator_json->>'period_code',
                                t.locator_json->>'published_at',
                                t.locator_json->>'section') AS period,
                       1-(t.embedding <=> $5::vector) AS score
                FROM public.text_chunks t
                JOIN public.index_versions i USING(index_version_id)
                JOIN public.documents d USING(document_id)
                LEFT JOIN public.companies c USING(company_id)
                LEFT JOIN public.reporting_periods p USING(period_id)
                WHERE t.index_version_id=$1
                  AND t.superseded_at IS NULL
                  AND ($2::text IS NULL OR upper(coalesce(c.symbol,
                       t.locator_json->>'symbol', t.locator_json->>'source_id'))=upper($2)
                       OR (t.locator_json->>'source_table'='news_articles' AND EXISTS (
                           SELECT 1 FROM public.news_articles n
                           WHERE n.article_id::text=t.locator_json->>'source_id'
                             AND upper($2)=ANY(n.symbols))))
                  AND ($3::text IS NULL OR coalesce(p.period_code,
                       t.locator_json->>'period_code',
                       t.locator_json->>'published_at', t.locator_json->>'section',
                       d.title) ILIKE '%' || $3 || '%')
                  AND ($4::text IS NULL OR upper(d.doc_type)=upper($4))
                  AND ($7::uuid IS NULL OR EXISTS (
                      SELECT 1 FROM public.corpus_documents cd
                      WHERE cd.corpus_version_id=$7::uuid
                        AND cd.document_id=t.document_id
                        AND cd.document_hash=d.sha256))
                ORDER BY t.embedding <=> $5::vector
                LIMIT $6
                ''',
                uuid.UUID(index_version_id), company_symbol, period, doc_type,
                query_embedding, top_k,
                uuid.UUID(str(corpus_version_id)) if corpus_version_id else None,
            )
            if on_ranked is not None:
                on_ranked([{"chunk_id": row["chunk_id"], "score": row["score"]}
                           for row in rows])
            return await resolve_result_rows(
                conn, rows, preview_source_changed=preview_source_changed,
            )
