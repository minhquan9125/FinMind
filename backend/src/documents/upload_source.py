"""Original upload sources in the existing ERD raw_payloads table."""
import base64
import hashlib
import json
import uuid

from .chunking import extract_pages, build_chunks
from .json_ingest import financial_json_to_pages, generic_json_to_pages
from .chunk_reconstruction import ReconstructionError


async def store_upload_source(conn, source_bytes, file_type, doc_type, symbol):
    digest = hashlib.sha256(source_bytes).hexdigest()
    payload_id = uuid.uuid5(uuid.NAMESPACE_URL, f'finmind:upload:{digest}:{file_type}:{doc_type}:{symbol}')
    payload = {'schema_version': 'upload-source-v1', 'file_type': file_type,
               'doc_type': doc_type, 'symbol': symbol,
               'original_base64': base64.b64encode(source_bytes).decode('ascii')}
    await conn.execute(
        'INSERT INTO public.raw_payloads(payload_id,source_uri,sha256,payload,stored_at) '
        'VALUES($1,$2,$3,$4::jsonb,now()) ON CONFLICT(payload_id) DO NOTHING',
        payload_id, f'upload:{digest}', digest, json.dumps(payload))
    return str(payload_id)


async def read_upload_chunks(conn, locator, cache):
    try:
        payload_id = uuid.UUID(locator['source_id'])
        words, overlap = locator['chunk_size'], locator['chunk_overlap']
        if (type(words) is not int or type(overlap) is not int
                or not 0 <= overlap < words <= 10000):
            raise ValueError('invalid chunk parameters')
        key = (payload_id, words, overlap)
        if key in cache:
            return cache[key]
        row = await conn.fetchrow('SELECT sha256,payload FROM public.raw_payloads WHERE payload_id=$1', payload_id)
        if row is None:
            raise ReconstructionError('SOURCE_MISSING', 'Upload source no longer available')
        payload = row['payload']
        payload = json.loads(payload) if isinstance(payload, str) else payload
        if payload['schema_version'] != 'upload-source-v1':
            raise ValueError('unsupported upload source')
        raw = base64.b64decode(payload['original_base64'], validate=True)
        if hashlib.sha256(raw).hexdigest() != row['sha256'].strip():
            raise ReconstructionError('HASH_MISMATCH', 'Upload source hash mismatch')
        if payload['file_type'] == 'PDF':
            pages = extract_pages(raw)
        elif payload['file_type'] == 'JSON':
            data = json.loads(raw)
            pages = (financial_json_to_pages(payload['symbol'], data)
                     if payload['doc_type'] == 'FINANCIAL_JSON' else generic_json_to_pages(data))
        else:
            raise ValueError('unsupported upload type')
        cache[key] = build_chunks(pages, words, words - overlap)
        return cache[key]
    except ReconstructionError:
        raise
    except (ValueError, KeyError, TypeError) as exc:
        raise ReconstructionError('INVALID_LOCATOR', 'Invalid upload source or locator') from exc
