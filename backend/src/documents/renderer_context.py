"""Read immutable financial rendering labels; values always come from sources."""
from dataclasses import replace
import json
import re
import uuid

from .chunk_reconstruction import ReconstructionError
from .corpus_manifest import sha256
from .db_chunking import SourceRow, SourceSection, NAMESPACE


def restore_metadata(doc, context):
    if (doc.document_id != context['document_id'] or doc.source_table != context['source_table']
            or str(doc.source_id) != context['source_id']
            or len(doc.sections) != len(context['sections'])):
        raise ReconstructionError('SOURCE_CHANGED', 'Archived context does not match source identity/sections')
    sections = []
    for saved, current in zip(context['sections'], doc.sections):
        if saved['section_index'] != len(sections) or saved['chunker_version'] != doc.meta.get('chunker_version', 'db-v1'):
            raise ReconstructionError('SOURCE_CHANGED', 'Archived section position/renderer differs')
        labels = {r['row_key']: r for r in saved['metric_labels']}
        if len(labels) != len(saved['metric_labels']) or set(labels) != {r.key for r in current.rows}:
            raise ReconstructionError('SOURCE_CHANGED', 'Source row membership changed')
        rows = []
        for row in current.rows:
            match = re.fullmatch(r'(.*) \(([^()]*)\): (.*)', row.text)
            old = labels[row.key]
            if not match or match.group(2) != old['code']:
                raise ReconstructionError('SOURCE_CHANGED', 'Metric code changed')
            rows.append(SourceRow(row.key, f"{old['label']} ({old['code']}): {match.group(3)}"))
        sections.append(SourceSection(current.label, saved['header'], rows))
    return replace(doc, sections=sections)


async def read_renderer_context(conn, index_id, doc):
    """Require a unique, checksum-verified context bound to this exact index/source."""
    index_id = str(uuid.UUID(str(index_id)))
    uri = f'finmind:renderer-context:{index_id}:{doc.document_id}'
    rows = await conn.fetch('SELECT payload_id,sha256,payload FROM public.raw_payloads WHERE source_uri=$1', uri)
    if len(rows) != 1:
        raise ReconstructionError('RENDERER_CONTEXT_MISSING', 'Expected one archived renderer context')
    try:
        row = rows[0]
        payload = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
        digest = sha256(payload)
        expected_id = uuid.uuid5(NAMESPACE, f'renderer-context:{index_id}:{doc.document_id}:{digest}')
        if (digest != row['sha256'].strip() or str(expected_id) != str(row['payload_id'])
                or payload['schema_version'] != 'financial-renderer-context-v1'
                or payload['index_version_id'] != index_id
                or not re.fullmatch('[a-f0-9]{64}', payload['corpus_manifest_sha256'])):
            raise ValueError('Archived context checksum or version mismatch')
        return restore_metadata(doc, payload)
    except ReconstructionError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ReconstructionError('INVALID_RENDERER_CONTEXT', 'Malformed or mismatched archived context') from exc
