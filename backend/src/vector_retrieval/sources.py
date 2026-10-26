"""Read explicitly pinned historical source text; DB chunk identity stays authoritative."""
import hashlib
import json
import re
from pathlib import Path

MAX_BYTES = 128 * 1024 * 1024


class SnapshotError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _reject_constant(value):
    raise ValueError('Non-finite JSON value')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


class SnapshotResolver:
    def __init__(self, path, expected_sha256):
        if not isinstance(expected_sha256, str) or not re.fullmatch('[a-f0-9]{64}', expected_sha256):
            raise SnapshotError('SNAPSHOT_INVALID_HASH')
        self._digest = expected_sha256
        try:
            with Path(path).open('rb') as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise SnapshotError('SNAPSHOT_TOO_LARGE')
            envelope = json.loads(raw.decode('utf-8'), parse_constant=_reject_constant,
                                  object_pairs_hook=_unique_object)
            self._chunks = self._validate(envelope)
        except SnapshotError:
            raise
        except OSError:
            raise SnapshotError('SNAPSHOT_UNAVAILABLE') from None
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise SnapshotError('SNAPSHOT_INVALID') from None

    @property
    def provenance(self):
        return dict(mode='FROZEN_SNAPSHOT', manifest_sha256=self._digest)

    def _validate(self, envelope):
        if not isinstance(envelope, dict) or not isinstance(envelope.get('manifest'), dict):
            raise SnapshotError('SNAPSHOT_INVALID')
        payload = envelope['manifest']
        if envelope.get('manifest_sha256') != self._digest or _sha(_canonical(payload)) != self._digest:
            raise SnapshotError('SNAPSHOT_HASH_MISMATCH')
        docs = payload.get('documents')
        if (payload.get('schema_version') != 'finmind-source-corpus-v2'
                or not isinstance(docs, list) or type(payload.get('document_count')) is not int
                or payload['document_count'] != len(docs) or type(payload.get('chunk_count')) is not int):
            raise SnapshotError('SNAPSHOT_INVALID')
        chunks = {}
        for doc in docs:
            if not isinstance(doc, dict) or not isinstance(doc.get('chunks'), list):
                raise SnapshotError('SNAPSHOT_INVALID')
            for chunk in doc['chunks']:
                if not isinstance(chunk, dict):
                    raise SnapshotError('SNAPSHOT_INVALID')
                cid, locator = chunk.get('source_chunk_id'), chunk.get('locator')
                text, digest = chunk.get('text'), chunk.get('content_hash')
                if (not isinstance(cid, str) or not cid or cid in chunks
                        or not isinstance(locator, dict) or not isinstance(locator.get('reconstruction'), dict)
                        or locator['reconstruction'].get('source_chunk_id') != cid
                        or not isinstance(text, str) or digest != _sha(text.encode('utf-8'))
                        or type(chunk.get('chunk_index')) is not int or chunk['chunk_index'] < 0):
                    raise SnapshotError('SNAPSHOT_INVALID')
                chunks[cid] = chunk
        if payload['chunk_count'] != len(chunks):
            raise SnapshotError('SNAPSHOT_INVALID')
        return chunks

    async def __call__(self, conn, rows):
        resolved = []
        for record in rows:
            try:
                row = dict(record)
                locator = row['locator_json']
                if isinstance(locator, str):
                    locator = json.loads(locator, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
                cid = locator['reconstruction']['source_chunk_id']
                candidate = self._chunks[cid]
                if (locator != candidate['locator'] or row['content_hash'].strip() != candidate['content_hash']
                        or type(row['chunk_index']) is not int or row['chunk_index'] != candidate['chunk_index']
                        or _sha(candidate['text'].encode('utf-8')) != row['content_hash'].strip()):
                    raise SnapshotError('SNAPSHOT_CHUNK_MISMATCH')
                row.update(locator_json=locator, text=candidate['text'], source_provenance=self.provenance)
                resolved.append(row)
            except SnapshotError:
                raise
            except (ValueError, TypeError, KeyError, AttributeError):
                raise SnapshotError('SNAPSHOT_CHUNK_MISMATCH') from None
        return resolved
