"""WBS16: deterministic snapshots of an ingested index, independent of live sources."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

NAMESPACE = uuid.UUID('1672a3e5-5517-4912-a7c1-a17e78c65736')


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def build_manifest(index: dict, rows: list[dict]) -> dict:
    if not rows:
        raise ValueError('Cannot freeze an empty corpus')
    documents = {}
    seen = set()
    positions = set()
    for row in rows:
        document_id, chunk_id = str(row['document_id']), str(row['chunk_id'])
        position = (document_id, row['chunk_index'])
        if chunk_id in seen or position in positions:
            raise ValueError('Duplicate chunk ID or position')
        seen.add(chunk_id)
        positions.add(position)
        locator = row['locator_json']
        if isinstance(locator, str):
            locator = json.loads(locator)
        if not isinstance(locator, dict) or not all(locator.get(k) for k in ('source_table', 'source_id', 'row_keys')):
            raise ValueError(f'Missing locator: {chunk_id}')
        text_hash = hashlib.sha256(row['chunk_text'].encode('utf-8')).hexdigest()
        if text_hash != row['content_hash'].strip() or row['dimensions'] != 1024:
            raise ValueError(f'Invalid content hash or vector dimension: {chunk_id}')
        doc = documents.setdefault(document_id, {
            'document_id': document_id, 'document_hash': row['document_hash'].strip(),
            'doc_type': row['doc_type'], 'title': row['title'],
            'source_id': row['external_id'], 'source_url': row['source_url'], 'chunks': [],
        })
        doc['chunks'].append({'chunk_id': chunk_id, 'chunk_index': row['chunk_index'],
                              'content_hash': text_hash, 'text': row['chunk_text'], 'locator': locator})
    for doc in documents.values():
        doc['chunks'].sort(key=lambda c: c['chunk_index'])
    payload = {'schema_version': 'finmind-corpus-v1', 'index': index,
               'document_count': len(documents), 'chunk_count': len(rows),
               'documents': [documents[k] for k in sorted(documents)]}
    digest = sha256(payload)
    return {'corpus_version_id': str(uuid.uuid5(NAMESPACE, digest)),
            'manifest_sha256': digest, 'manifest': payload}


async def read_manifest(conn, index_id: str) -> dict:
    index = await conn.fetchrow(
        'SELECT index_version_id::text, chunker_version, chunk_size, chunk_overlap, embedding_model '
        'FROM public.index_versions WHERE index_version_id=$1', uuid.UUID(index_id))
    if index is None:
        raise ValueError('Index version does not exist')
    rows = await conn.fetch(
        'SELECT d.document_id::text, d.sha256 AS document_hash, d.doc_type, d.title, '
        'd.external_id, d.source_url, t.chunk_id::text, t.chunk_index, t.chunk_text, '
        't.content_hash, t.locator_json, vector_dims(t.embedding) AS dimensions '
        'FROM public.text_chunks t JOIN public.documents d USING(document_id) '
        'WHERE t.index_version_id=$1 AND t.superseded_at IS NULL', uuid.UUID(index_id))
    return build_manifest(dict(index), [dict(row) for row in rows])


async def register_manifest(conn, manifest: dict, label: str) -> bool:
    """Caller owns transaction. Existing versions are immutable; reruns are no-ops."""
    if not label or len(label) > 30:
        raise ValueError('Version label must contain 1 to 30 characters')
    version_id = uuid.UUID(manifest['corpus_version_id'])
    digest = manifest['manifest_sha256']
    if sha256(manifest['manifest']) != digest or uuid.uuid5(NAMESPACE, digest) != version_id:
        raise ValueError('Manifest digest or ID mismatch')
    # Serialize registrations even though the original schema has no unique label constraint.
    await conn.execute('SELECT pg_advisory_xact_lock(167216)')
    existing = await conn.fetch(
        'SELECT corpus_version_id, version_label, manifest_sha256 FROM public.corpus_versions '
        'WHERE version_label=$1 OR corpus_version_id=$2', label, version_id)
    if existing:
        if len(existing) != 1 or str(existing[0]['corpus_version_id']) != str(version_id) or existing[0]['manifest_sha256'].strip() != digest or existing[0]['version_label'] != label:
            raise ValueError('Version label or corpus ID already registered; use a new label for changed content')
        members = await conn.fetch('SELECT document_id::text, document_hash FROM public.corpus_documents WHERE corpus_version_id=$1', version_id)
        expected = {d['document_id']: d['document_hash'] for d in manifest['manifest']['documents']}
        if {r['document_id']: r['document_hash'].strip() for r in members} != expected:
            raise ValueError('Stored corpus membership differs from manifest')
        return False
    await conn.execute(
        'INSERT INTO public.corpus_versions (corpus_version_id,version_label,description,index_version_id,frozen_at,manifest_sha256,status) '
        "VALUES($1,$2,$3,$4,now(),$5,'FROZEN')", version_id, label,
        'WBS16; chunk membership and locator snapshots in manifest JSON; sha256 covers canonical manifest payload.',
        uuid.UUID(manifest['manifest']['index']['index_version_id']), digest)
    await conn.executemany(
        'INSERT INTO public.corpus_documents(corpus_version_id,document_id,document_hash) VALUES($1,$2,$3)',
        [(version_id, uuid.UUID(d['document_id']), d['document_hash']) for d in manifest['manifest']['documents']])
    return True
