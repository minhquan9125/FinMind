"""Pinned annual-report reader supporting direct and release-alias identities."""
import json,uuid
from .chunk_reconstruction import ReconstructionError,_metadata
from .release_identity import validate_document_binding
from .shared_source import resolve_shared_source

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
    binding=validate_document_binding(row['document_id'],row['index_version_id'],loc)
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
