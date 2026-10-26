"""Reconstruct exact text from Supabase sources. Not wired to search or migrations yet."""
import hashlib
import json
import re
from dataclasses import dataclass

from .db_chunking import CHUNKER_VERSION, FINANCIAL_RENDERER_VERSIONS
from .db_source import fetch_locator_document
from .source_signature import section_fingerprint


class ReconstructionError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ReconstructedChunk:
    text: str
    content_hash: str
    source_chunk_id: str
    document_id: str


def _metadata(locator):
    try:
        if isinstance(locator, str):
            locator = json.loads(locator)
        meta = locator['reconstruction']
        if meta['schema_version'] != 'source-locator-v2' or meta['chunker_version'] not in FINANCIAL_RENDERER_VERSIONS:
            raise ReconstructionError('UNSUPPORTED_VERSION', 'Unsupported locator/chunker version')
        if meta['chunker_version'] != CHUNKER_VERSION and locator['source_table'] != 'financial_reports':
            raise ReconstructionError('UNSUPPORTED_VERSION', 'Financial renderer requires a financial source')
        for key in ('max_words', 'section_index', 'row_start', 'row_end', 'char_start', 'char_end', 'chunk_index'):
            if type(meta[key]) is not int or meta[key] < 0:
                raise ValueError(key)
        if not 1 <= meta['max_words'] <= 10000:
            raise ValueError('max_words')
        for key in ('content_hash', 'source_view_sha256'):
            if not re.fullmatch('[a-f0-9]{64}', meta[key]):
                raise ValueError(key)
        if not isinstance(locator['source_id'], str) or not locator['source_id']:
            raise ValueError('source_id')
        if not isinstance(locator['row_keys'], list) or not locator['row_keys']:
            raise ValueError('row_keys')
        return locator, meta
    except ReconstructionError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ReconstructionError('INVALID_LOCATOR', 'Missing or malformed v2 reconstruction locator') from exc


def reconstruct_document_chunk(doc, locator, expected_hash):
    """Pure reconstruction. expected_hash must come from the trusted stored chunk row."""
    locator, meta = _metadata(locator)
    if not isinstance(expected_hash, str) or not re.fullmatch('[a-f0-9]{64}', expected_hash.strip()):
        raise ReconstructionError('INVALID_HASH', 'Missing trusted content_hash')
    expected_hash = expected_hash.strip()
    if meta['content_hash'] != expected_hash:
        raise ReconstructionError('HASH_MISMATCH', 'Locator differs from stored chunk hash')
    if (doc.source_table != locator['source_table'] or str(doc.source_id) != locator['source_id']
            or doc.document_id != meta['document_id']):
        raise ReconstructionError('SOURCE_MISMATCH', 'Locator refers to another source document')
    try:
        section = doc.sections[meta['section_index']]
    except IndexError as exc:
        raise ReconstructionError('SOURCE_CHANGED', 'Source section no longer exists') from exc
    if section_fingerprint(doc, meta['section_index']) != meta['source_view_sha256']:
        raise ReconstructionError('SOURCE_CHANGED', 'Source view differs from indexed fingerprint; historical source needed')
    start, end = meta['row_start'], meta['row_end']
    if not 0 <= start < end <= len(section.rows):
        raise ReconstructionError('INVALID_LOCATOR', 'Row range outside source section')
    selected = section.rows[start:end]
    if [row.key for row in selected] != locator['row_keys'] or section.label != locator['section']:
        raise ReconstructionError('SOURCE_MISMATCH', 'Source rows or section do not match locator')
    offset = sum(len(row.text) + 1 for row in section.rows[:start])
    body = '\n'.join(row.text for row in selected)
    if offset != meta['char_start'] or offset + len(body) != meta['char_end']:
        raise ReconstructionError('INVALID_LOCATOR', 'Character span does not match normalized source rows')
    text = f'{section.header}\n{body}' if section.header else body
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    if digest != expected_hash:
        raise ReconstructionError('HASH_MISMATCH', 'Reconstructed text differs from indexed chunk')
    # Confirm both position and source chunk identity with the same deterministic chunker.
    from .db_chunking import chunk_document
    chunks = chunk_document(doc, meta['max_words'])
    if meta['chunk_index'] >= len(chunks):
        raise ReconstructionError('INVALID_LOCATOR', 'Chunk index out of range')
    original = chunks[meta['chunk_index']]
    if original.chunk_id != meta['source_chunk_id'] or original.content_hash != digest:
        raise ReconstructionError('SOURCE_MISMATCH', 'Chunk identity/configuration differs')
    return ReconstructedChunk(text, digest, original.chunk_id, doc.document_id)


def preview_changed_document_chunk(doc, locator, expected_hash):
    """Show current source text for a matched locator, without claiming hash verification.

    Only the filtered-search diagnostic path calls this after strict reconstruction
    has already failed with SOURCE_CHANGED. Identity and row keys still must match.
    """
    locator, meta = _metadata(locator)
    if meta['content_hash'] != expected_hash.strip():
        raise ReconstructionError('HASH_MISMATCH', 'Locator differs from stored chunk hash')
    if (doc.source_table != locator['source_table'] or str(doc.source_id) != locator['source_id']
            or doc.document_id != meta['document_id']):
        raise ReconstructionError('SOURCE_MISMATCH', 'Locator refers to another source document')
    try:
        section = doc.sections[meta['section_index']]
    except IndexError as exc:
        raise ReconstructionError('SOURCE_CHANGED', 'Source section no longer exists') from exc
    start, end = meta['row_start'], meta['row_end']
    if not 0 <= start < end <= len(section.rows):
        raise ReconstructionError('INVALID_LOCATOR', 'Row range outside source section')
    selected = section.rows[start:end]
    if [row.key for row in selected] != locator['row_keys'] or section.label != locator['section']:
        raise ReconstructionError('SOURCE_MISMATCH', 'Source rows or section do not match locator')
    body = '\n'.join(row.text for row in selected)
    text = f'{section.header}\n{body}' if section.header else body
    return ReconstructedChunk(text, hashlib.sha256(text.encode('utf-8')).hexdigest(),
                              meta['source_chunk_id'], doc.document_id)


async def reconstruct_chunk(conn, locator, expected_hash):
    """Only reads source tables; never falls back to chunk_text or external files.

    Caller should own a READ ONLY REPEATABLE READ transaction for multi-query sources.
    """
    locator, meta = _metadata(locator)
    try:
        kwargs = ({'financial_renderer_version': meta['chunker_version']}
                  if locator['source_table'] == 'financial_reports' else {})
        doc = await fetch_locator_document(conn, locator['source_table'], locator['source_id'], meta['max_words'], **kwargs)
    except ValueError as exc:
        raise ReconstructionError('INVALID_LOCATOR', str(exc)) from exc
    if doc is None:
        raise ReconstructionError('SOURCE_MISSING', 'Source absent, expired or has no usable content')
    return reconstruct_document_chunk(doc, locator, expected_hash)
