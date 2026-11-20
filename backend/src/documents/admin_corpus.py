"""Read-only views of the corpus versions stored in PostgreSQL for the admin page.

Nothing here writes: switching or freezing a corpus stays in the ingestion/index jobs.
"""
from __future__ import annotations

import uuid

MAX_VERSIONS = 50


class CorpusActionError(ValueError):
    """Refused action; the message is a stable code the admin page maps to text."""


def servable(row):
    """Chat only reads FROZEN corpora whose index is ACTIVE and whose manifest is recorded."""
    return row.get('status') == 'FROZEN' and row.get('index_status') == 'ACTIVE' and bool(row.get('manifest_sha256'))


async def _row(conn, corpus_id):
    return await conn.fetchrow(
        '''SELECT cv.corpus_version_id::text AS corpus_version_id, cv.status, cv.manifest_sha256,
                  cv.index_version_id::text AS index_version_id, iv.status AS index_status
           FROM public.corpus_versions cv
           LEFT JOIN public.index_versions iv ON iv.index_version_id = cv.index_version_id
           WHERE cv.corpus_version_id = $1''', uuid.UUID(str(corpus_id)))


async def switch_serving(conn, queue, corpus_id, default_corpus, actor, publish=None):
    """Point Chat at an existing frozen corpus (e.g. roll back after a bad news update).

    `publish` (async callable corpus_id, index_id, actor -> bool) shares the choice with other machines."""
    row = await _row(conn, corpus_id)
    if row is None: raise CorpusActionError('CORPUS_NOT_FOUND')
    if not servable(row): raise CorpusActionError('CORPUS_NOT_SERVABLE')
    cid = row['corpus_version_id']
    if queue.serving_corpus(default_corpus) == cid: raise CorpusActionError('ALREADY_SERVING')
    previous = queue.serving_corpus(default_corpus)
    queue.publish_corpus(cid, row['index_version_id'])
    queue.audit(actor, 'SWITCH_CORPUS', f'{previous}->{cid}')
    shared = bool(await publish(cid, row['index_version_id'], actor)) if publish else False
    return {'corpus_version_id': cid, 'previous_corpus_id': previous, 'warmed': await _warm(conn, row), 'shared': shared}


async def _warm(conn, row):
    """Best effort: build the retrieval cache now so the first Chat question is not the slow one."""
    try:
        from pathlib import Path
        from .corpus_manifest import read_manifest
        from ..vector_retrieval.backend import cache_verified_manifest
        manifest = await read_manifest(conn, row['index_version_id'])
        if str(manifest.get('corpus_version_id')) != row['corpus_version_id']: return False
        cache = Path(__file__).resolve().parents[1] / 'vector_retrieval' / '.cache' / ('corpus-' + row['corpus_version_id'] + '.json')
        await cache_verified_manifest(conn, manifest, cache)
        return True
    except Exception:
        return False


async def set_archived(writer, queue, corpus_id, archived, default_corpus, actor):
    """FROZEN <-> ARCHIVED. An archived corpus can no longer be served; the serving one is protected."""
    row = await _row(writer, corpus_id)
    if row is None: raise CorpusActionError('CORPUS_NOT_FOUND')
    cid, wanted, needed = row['corpus_version_id'], ('ARCHIVED' if archived else 'FROZEN'), ('FROZEN' if archived else 'ARCHIVED')
    if archived and cid in (queue.serving_corpus(default_corpus), str(default_corpus)):
        raise CorpusActionError('CORPUS_IN_USE')
    if row['status'] != needed: raise CorpusActionError('CORPUS_STATE_CHANGED')
    done = await writer.execute('UPDATE public.corpus_versions SET status=$2 WHERE corpus_version_id=$1 AND status=$3',
                                uuid.UUID(cid), wanted, needed)
    if done != 'UPDATE 1': raise CorpusActionError('CORPUS_STATE_CHANGED')
    queue.audit(actor, 'ARCHIVE_CORPUS' if archived else 'RESTORE_CORPUS', cid)
    return {'corpus_version_id': cid, 'status': wanted}


async def list_versions(conn, serving_corpus_id):
    rows = await conn.fetch(
        '''SELECT cv.corpus_version_id::text AS corpus_version_id, cv.version_label, cv.description,
                  cv.status, cv.frozen_at, cv.manifest_sha256, cv.index_version_id::text AS index_version_id,
                  iv.status AS index_status, iv.embedding_model, iv.built_at,
                  (SELECT count(*) FROM public.corpus_documents cd
                    WHERE cd.corpus_version_id = cv.corpus_version_id) AS documents
           FROM public.corpus_versions cv
           LEFT JOIN public.index_versions iv ON iv.index_version_id = cv.index_version_id
           ORDER BY coalesce(cv.frozen_at, iv.built_at) DESC NULLS LAST
           LIMIT $1''', MAX_VERSIONS)
    ids = [uuid.UUID(r['corpus_version_id']) for r in rows]
    by_type = {}
    if ids:
        for r in await conn.fetch(
                '''SELECT cd.corpus_version_id::text AS corpus_version_id, d.doc_type, count(*) AS n
                   FROM public.corpus_documents cd JOIN public.documents d ON d.document_id = cd.document_id
                   WHERE cd.corpus_version_id = ANY($1::uuid[]) GROUP BY 1, 2''', ids):
            by_type.setdefault(r['corpus_version_id'], {})[r['doc_type']] = r['n']
    items = []
    for r in rows:
        item = dict(r)
        item['serving'] = bool(serving_corpus_id) and item['corpus_version_id'] == str(serving_corpus_id)
        item['servable'] = servable(item)
        item['by_type'] = by_type.get(item['corpus_version_id'], {})
        items.append(item)
    return {'items': items, 'serving_corpus_id': str(serving_corpus_id) if serving_corpus_id else None}


async def list_documents(conn, corpus_id, *, offset=0, limit=30, doc_type=None):
    cid = uuid.UUID(str(corpus_id))
    if not await conn.fetchval('SELECT 1 FROM public.corpus_versions WHERE corpus_version_id = $1', cid):
        return None
    where, params = 'cd.corpus_version_id = $1', [cid]
    if doc_type:
        params.append(doc_type)
        where += f' AND d.doc_type = ${len(params)}'
    total = await conn.fetchval(
        f'SELECT count(*) FROM public.corpus_documents cd JOIN public.documents d ON d.document_id = cd.document_id WHERE {where}',
        *params)
    rows = await conn.fetch(
        f'''SELECT d.document_id::text AS document_id, d.title, d.doc_type, c.symbol,
                   cd.document_hash, (cd.document_hash = d.sha256) AS hash_matches
            FROM public.corpus_documents cd
            JOIN public.documents d ON d.document_id = cd.document_id
            LEFT JOIN public.companies c ON c.company_id = d.company_id
            WHERE {where} ORDER BY d.doc_type, c.symbol NULLS LAST, d.title
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}''', *params, limit, offset)
    types = [r['doc_type'] for r in await conn.fetch(
        '''SELECT DISTINCT d.doc_type FROM public.corpus_documents cd
           JOIN public.documents d ON d.document_id = cd.document_id
           WHERE cd.corpus_version_id = $1 ORDER BY 1''', cid)]
    return {'items': [dict(r) for r in rows], 'total': total, 'offset': offset, 'limit': limit, 'doc_types': types}
