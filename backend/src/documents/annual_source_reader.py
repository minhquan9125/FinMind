"""Pinned annual-report reader supporting direct and release-alias identities."""
import json,uuid
from .chunk_reconstruction import ReconstructionError,_metadata
from .release_identity import validate_document_binding
from .shared_source import resolve_shared_source


async def _annual_binding(conn, row, loc, corpus_version_id, cache):
    try:
        return validate_document_binding(row['document_id'], row['index_version_id'], loc)
    except ReconstructionError as exc:
        if exc.code != 'DOCUMENT_ID_MISMATCH':
            raise
    # admin_shared_index.merge_shared preserves the source release's document
    # aliases, while deriving a fresh chunk ID from the copied parent's ID.
    # Accept only that explicit protocol, with a registered immutable root and
    # an exact frozen parent; an arbitrary old alias is never enough.
    from .shared_source import read_release_root
    root = await read_release_root(conn, row['index_version_id'], cache)
    origin = root.get('source_index_version_id')
    if (root.get('corpus_version_id') != str(corpus_version_id) or not origin
            or origin == row['index_version_id']):
        raise ReconstructionError('DOCUMENT_ID_MISMATCH', 'No registered source-release lineage')
    binding = validate_document_binding(row['document_id'], origin, loc)
    if binding['mode'] != 'RELEASE_DOCUMENT_ALIAS_V1':
        raise ReconstructionError('DOCUMENT_ID_MISMATCH', 'Invalid inherited document alias')
    parents = await conn.fetch('''SELECT DISTINCT p.index_version_id::text AS index_version_id
        FROM text_chunks p JOIN documents d USING(document_id)
        JOIN index_versions i ON i.index_version_id=p.index_version_id
        JOIN corpus_versions cv ON cv.index_version_id=p.index_version_id
        JOIN corpus_documents cd ON cd.corpus_version_id=cv.corpus_version_id
          AND cd.document_id=d.document_id AND cd.document_hash=d.sha256
        WHERE p.document_id=$1::uuid AND p.content_hash=$2 AND p.locator_json=$3::jsonb
          AND p.index_version_id<>$4::uuid AND p.superseded_at IS NULL
          AND i.status='ACTIVE' AND cv.status='FROZEN'
          AND md5('shared:' || $4::uuid::text || ':' || p.chunk_id::text)::uuid=$5::uuid
        LIMIT 2''', uuid.UUID(row['document_id']), row['content_hash'].strip(), json.dumps(loc),
        uuid.UUID(row['index_version_id']), uuid.UUID(row['chunk_id']))
    if len(parents) != 1:
        raise ReconstructionError('CHUNK_ID_MISMATCH', 'No unique frozen parent for shared chunk identity')
    parent = await read_release_root(conn, parents[0]['index_version_id'], cache)
    if parent.get('source_index_version_id', parents[0]['index_version_id']) != origin:
        raise ReconstructionError('DOCUMENT_ID_MISMATCH', 'Parent source release differs')
    return {**binding, 'mode':'SHARED_RELEASE_SOURCE_ALIAS_V1',
            'index_version_id':row['index_version_id'], 'source_index_version_id':origin,
            'parent_index_version_id':parents[0]['index_version_id']}

async def read_annual_chunk(conn,chunk_id,corpus_version_id,cache=None):
    """Caller supplies an authorized corpus ID; this function writes nothing.

    Return the stored ID as document_id and the separate source identity without
    rewriting the locator. Keep this read within a repeatable-read transaction
    when batching. Corpus freezing, index selection and source replay are all
    checked; an alias equality alone never establishes source authenticity.
    """
    row=await conn.fetchrow('''SELECT t.chunk_id::text,t.document_id::text,t.index_version_id::text,
        t.content_hash,t.page_number,t.locator_json,d.source_url,d.title
        FROM text_chunks t JOIN documents d USING(document_id)
        JOIN index_versions i USING(index_version_id)
        JOIN corpus_versions cv USING(index_version_id)
        JOIN corpus_documents cd ON cd.corpus_version_id=cv.corpus_version_id
          AND cd.document_id=d.document_id AND cd.document_hash=d.sha256
        WHERE t.chunk_id=$1 AND cv.corpus_version_id=$2 AND d.doc_type='ANNUAL_REPORT'
          AND t.superseded_at IS NULL AND cv.status='FROZEN' AND i.status='ACTIVE' ''',
        uuid.UUID(str(chunk_id)),uuid.UUID(str(corpus_version_id)))
    if row is None:
        raise ReconstructionError('CHUNK_NOT_IN_CORPUS','Active annual chunk is absent from requested frozen corpus')
    return await resolve_annual_member_row(conn,row,corpus_version_id,cache)

async def resolve_annual_member_row(conn,row,corpus_version_id,cache=None):
    """Replay a row already selected by the same trusted membership query.

    Internal bulk-reader primitive; do not expose this with caller-supplied rows.
    Use read_annual_chunk for untrusted chunk IDs.
    """
    loc=json.loads(row['locator_json']) if isinstance(row['locator_json'],str) else row['locator_json']
    cache = cache if cache is not None else {}
    binding=await _annual_binding(conn,row,loc,corpus_version_id,cache)
    _,meta=_metadata(loc)
    if binding['mode']=='RELEASE_DOCUMENT_ALIAS_V1':
        expected=str(uuid.uuid5(uuid.NAMESPACE_URL,f'finmind:release-chunk:{row["index_version_id"]}:{meta["source_chunk_id"]}'))
        if row['chunk_id']!=expected:
            raise ReconstructionError('CHUNK_ID_MISMATCH','Chunk ID does not belong to its pinned release')
    page=loc.get('pdf_page')
    if type(page) is not int or page<1 or page!=row['page_number']:
        raise ReconstructionError('PAGE_MISMATCH','Stored PDF page differs from source locator')
    text=await resolve_shared_source(conn,row['index_version_id'],loc,row['content_hash'],cache if cache is not None else {})
    return dict(chunk_id=row['chunk_id'],document_id=row['document_id'],
        source_document_id=binding['source_document_id'],document_id_binding=binding,
        corpus_version_id=str(corpus_version_id),index_version_id=row['index_version_id'],
        chunk_text=text,content_hash=row['content_hash'].strip(),pdf_page=page,
        locator=loc,source_url=row['source_url'],title=row['title'],
        position={k:meta[k] for k in ('section_index','row_start','row_end','char_start','char_end')})
