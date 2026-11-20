"""Read only the frozen annual-report chunks and verify pinned source text."""

import json
import uuid

from ..documents.corpus_manifest import sha256
from ..documents.annual_source_reader import resolve_annual_member_row
from ..documents.shared_source import read_envelope, read_release_root


async def read_verified_bctn_chunks(conn, corpus_version_id, limit=None, document_id=None):
    """Return source-verified rows; the caller must open a READ ONLY transaction.

    The corpus membership and current index are fixed by the supplied corpus
    version. No OCR, chunking, embeddings, or database writes occur here.
    """
    corpus_id = uuid.UUID(str(corpus_version_id))
    selected_document = uuid.UUID(str(document_id)) if document_id is not None else None
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError('limit must be a positive integer')
    if await conn.fetchval('SHOW transaction_read_only') != 'on':
        raise ValueError('BCTN source reader requires a READ ONLY transaction')
    corpus = await conn.fetchrow('''
        SELECT corpus_version_id::text, index_version_id::text, status
        FROM public.corpus_versions WHERE corpus_version_id=$1
    ''', corpus_id)
    if corpus is None or corpus['status'] not in ('FROZEN', 'ACTIVE'):
        raise ValueError('Corpus missing or not frozen/active')
    index_id = corpus['index_version_id']
    cache = {}
    release = await read_release_root(conn, index_id, cache)
    if release['corpus_version_id'] != str(corpus_id):
        raise ValueError('Source release and corpus differ')
    rows = await conn.fetch('''
        SELECT d.document_id::text, d.title, d.source_url, d.doc_type, d.company_id::text,
               company.symbol AS issuer_symbol, company.company_name AS issuer_company_name,
               d.sha256 AS database_document_sha256, d.external_id,
               cd.document_hash,
               t.chunk_id::text, t.index_version_id::text, t.chunk_index, t.page_number,
               t.char_start, t.char_end, t.content_hash, t.locator_json
        FROM public.text_chunks AS t
        JOIN public.documents AS d ON d.document_id=t.document_id
        JOIN public.companies AS company ON company.company_id=d.company_id
        JOIN public.corpus_documents AS cd ON cd.document_id=d.document_id
        JOIN public.corpus_versions AS cv ON cv.corpus_version_id=cd.corpus_version_id
        WHERE cv.corpus_version_id=$1 AND d.doc_type='ANNUAL_REPORT'
          AND t.index_version_id=cv.index_version_id AND t.superseded_at IS NULL
          AND ($2::uuid IS NULL OR d.document_id=$2)
        ORDER BY d.document_id,t.chunk_index,t.chunk_id
        LIMIT $3
    ''', corpus_id, selected_document, limit)
    members = {(m['source_table'], m['source_id']): m for m in release['sources']}
    verified_versions = {}
    output = []
    for raw in rows:
        row = dict(raw)
        if row['document_hash'] is None or row['document_hash'].strip() != row['database_document_sha256'].strip():
            raise ValueError('Corpus document hash mismatch')
        locator = row['locator_json']
        if isinstance(locator, str):
            locator = json.loads(locator)
        if not isinstance(locator, dict):
            raise ValueError('Missing source locator')
        meta = locator.get('reconstruction')
        if not isinstance(meta, dict) or meta.get('schema_version') != 'source-locator-v2':
            raise ValueError('Unsupported BCTN source locator')
        if locator.get('symbol') != row['issuer_symbol']:
            raise ValueError('BCTN issuer differs from source locator')
        member = members.get((locator.get('source_table'), locator.get('source_id')))
        if member is None or member.get('source_table') != 'annual_reports':
            raise ValueError('Annual report not in pinned source release')
        binding = {'source_uri': member['source_uri'], 'source_sha256': member['sha256']}
        if member['source_uri'] not in verified_versions:
            snapshot = await read_envelope(conn, member['source_uri'], member)
            version = sha256(snapshot)
            if version != member['sha256']:
                raise ValueError('Snapshot version differs from source binding')
            verified_versions[member['source_uri']] = version
            cache[('shared-document', member['payload_id'])] = snapshot
        verified = await resolve_annual_member_row(conn, row, corpus_id, cache)
        row['text'] = verified['chunk_text']
        row['source_document_id'] = verified['source_document_id']
        row['document_id_binding'] = verified['document_id_binding']
        row['locator_json'] = locator
        row['source_binding'] = binding
        row['document_version'] = verified_versions[member['source_uri']]
        row['index_version_id'] = index_id
        output.append(row)
    return output
