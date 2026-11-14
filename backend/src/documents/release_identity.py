"""Explicit, fail-closed identities for release aliases versus source documents."""
import uuid
from .chunk_reconstruction import ReconstructionError

def release_document_id(index_version_id, source_document_id):
    index=str(uuid.UUID(str(index_version_id)))
    source=str(uuid.UUID(str(source_document_id)))
    return str(uuid.uuid5(uuid.NAMESPACE_URL,f'finmind:release-document:{index}:{source}'))

def validate_document_binding(stored_document_id, index_version_id, locator):
    """Validate identity only; caller must also pin membership and replay hashes."""
    try:
        stored=str(uuid.UUID(str(stored_document_id)))
        index=str(uuid.UUID(str(index_version_id)))
        source=str(uuid.UUID(str(locator['reconstruction']['document_id'])))
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        raise ReconstructionError('INVALID_DOCUMENT_BINDING','Missing or malformed document identity') from exc
    if stored==source:
        mode='DIRECT_SOURCE_ID'
    elif stored==release_document_id(index,source):
        mode='RELEASE_DOCUMENT_ALIAS_V1'
    else:
        raise ReconstructionError('DOCUMENT_ID_MISMATCH','Stored document is neither source nor its release alias')
    return dict(stored_document_id=stored,source_document_id=source,index_version_id=index,mode=mode)
