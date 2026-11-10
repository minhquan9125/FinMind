"""Versioned intent vectors for Sprint 5. No routing or query classification here."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re

import numpy as np


@dataclass(frozen=True)
class IntentLibrary:
    rows: tuple[dict, ...]
    vectors: np.ndarray
    manifest: dict


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def _rows(raw, schema):
    rows = tuple(json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip())
    labels = {item['id'] for item in schema['labels']}
    ids = [r['id'] for r in rows]
    if not rows or len(ids) != len(set(ids)):
        raise ValueError('INVALID_ROW_IDS')
    for row in rows:
        if (row['split'] != 'LIBRARY' or row['annotation_status'] != 'LABELED'
                or row['intent_label'] not in labels or not row['text'].strip()
                or row['label_schema_version'] != schema['label_schema_version']):
            raise ValueError('INVALID_LIBRARY_ROW')
        components = row['component_intents']
        if row['intent_label'] == 'MIXED':
            if len(set(components)) < 2 or len(components) != len(set(components)) or not set(components) <= labels - {'MIXED'}:
                raise ValueError('INVALID_MIXED_COMPONENTS')
        elif components:
            raise ValueError('INVALID_COMPONENTS')
    return rows


def _vectors(values, count, dimension):
    values = np.asarray(values, dtype=np.float32)
    if values.shape != (count, dimension):
        raise ValueError(f'VECTOR_SHAPE: expected {(count, dimension)}, got {values.shape}')
    if not np.isfinite(values).all():
        raise ValueError('VECTOR_NONFINITE')
    norms = np.linalg.norm(values, axis=1)
    if not np.allclose(norms, 1, atol=1e-4, rtol=0):
        raise ValueError('VECTOR_NOT_UNIT_NORMALIZED')
    return values


def build_library(dataset_dir, schema_path, output_dir, embedder, *, library_version, expected_dimension=1024):
    """Encode only approved library.jsonl rows and persist exact row/vector order.

    Existing output directories are never overwritten. Encoder failures or invalid
    vectors leave no output directory. The manifest is written last, after files.
    """
    dataset_dir, schema_path, output_dir = map(Path, (dataset_dir, schema_path, output_dir))
    if output_dir.exists():
        raise FileExistsError(output_dir)
    dataset, schema = _json(dataset_dir / 'manifest.json'), _json(schema_path)
    if dataset['approval_status'] != 'APPROVED_FOR_WBS03_3' or schema['approval']['status'] != 'APPROVED':
        raise ValueError('INPUT_NOT_APPROVED')
    library_path = dataset_dir / 'library.jsonl'
    if (_sha(library_path) != dataset['files']['library.jsonl']['sha256']
            or _sha(schema_path) != dataset['label_schema_sha256']):
        raise ValueError('INPUT_CHECKSUM_MISMATCH')
    if not library_version.strip() or not embedder.model_name.strip() or not re.fullmatch(r'[0-9a-f]{40}', embedder.revision):
        raise ValueError('UNPINNED_MODEL_OR_VERSION')
    raw = library_path.read_bytes()
    rows = _rows(raw, schema)
    if len(rows) != dataset['files']['library.jsonl']['rows']:
        raise ValueError('INPUT_ROW_COUNT_MISMATCH')
    vectors = _vectors(embedder.embed_texts([r['text'] for r in rows]), len(rows), expected_dimension)
    # No input text normalization: preserve accents and abbreviations as reviewed.
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / 'library.jsonl').write_bytes(raw)
    (output_dir / 'label-schema.json').write_bytes(schema_path.read_bytes())
    (output_dir / 'dataset-manifest.json').write_bytes((dataset_dir / 'manifest.json').read_bytes())
    np.save(output_dir / 'vectors.npy', vectors, allow_pickle=False)
    versions = {}
    for package in ('numpy', 'torch', 'sentence-transformers', 'transformers', 'huggingface-hub'):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    manifest = dict(
        format_version=1, task_id='S5-WBS03.3', status='READY', library_version=library_version,
        dataset_version=dataset['dataset_version'], label_schema_version=schema['label_schema_version'],
        created_at=datetime.now(timezone.utc).isoformat(),
        model=dict(name=embedder.model_name, revision=embedder.revision,
                   dimension=expected_dimension, dtype='float32', normalization='L2',
                   input_preprocessing='NONE_EXACT_REVIEWED_TEXT',
                   device=str(embedder.device), batch_size=embedder.batch_size,
                   max_sequence_length=getattr(getattr(embedder, '_model', None), 'max_seq_length', None),
                   encoder_class=type(embedder).__module__ + '.' + type(embedder).__name__),
        environment=dict(python=platform.python_version(), packages=versions),
        row_count=len(rows), row_ids=[r['id'] for r in rows],
        test_rows_embedded=0,
        files={name: _sha(output_dir / name) for name in
               ('library.jsonl', 'label-schema.json', 'dataset-manifest.json', 'vectors.npy')},
    )
    _write_json(output_dir / 'manifest.json', manifest)
    return load_library(output_dir, expected_model=embedder.model_name, expected_revision=embedder.revision)


def load_library(directory, *, expected_model=None, expected_revision=None):
    """Read a self-contained artifact, checking hashes, model, shape and row order."""
    directory = Path(directory)
    manifest = _json(directory / 'manifest.json')
    if manifest['format_version'] != 1 or manifest['status'] != 'READY':
        raise ValueError('INVALID_ARTIFACT_STATUS_OR_FORMAT')
    names = {'library.jsonl', 'label-schema.json', 'dataset-manifest.json', 'vectors.npy'}
    if set(manifest['files']) != names:
        raise ValueError('INVALID_ARTIFACT_FILES')
    for name in names:
        if _sha(directory / name) != manifest['files'][name]:
            raise ValueError(f'ARTIFACT_CHECKSUM_MISMATCH: {name}')
    model = manifest['model']
    if expected_model is not None and model['name'] != expected_model:
        raise ValueError('MODEL_MISMATCH')
    if expected_revision is not None and model['revision'] != expected_revision:
        raise ValueError('REVISION_MISMATCH')
    if model['dtype'] != 'float32' or model['normalization'] != 'L2' or manifest['test_rows_embedded'] != 0:
        raise ValueError('INVALID_ENCODING_CONTRACT')
    schema, dataset = _json(directory / 'label-schema.json'), _json(directory / 'dataset-manifest.json')
    if (dataset['files']['library.jsonl']['sha256'] != manifest['files']['library.jsonl']
            or dataset['label_schema_sha256'] != manifest['files']['label-schema.json']
            or dataset['dataset_version'] != manifest['dataset_version']
            or schema['label_schema_version'] != manifest['label_schema_version']):
        raise ValueError('ARTIFACT_PROVENANCE_MISMATCH')
    rows = _rows((directory / 'library.jsonl').read_bytes(), schema)
    if [r['id'] for r in rows] != manifest['row_ids']:
        raise ValueError('ROW_ORDER_MISMATCH')
    vectors = np.load(directory / 'vectors.npy', allow_pickle=False)
    if vectors.dtype != np.float32 or len(rows) != manifest['row_count']:
        raise ValueError('VECTOR_DTYPE_OR_ROW_COUNT')
    vectors = _vectors(vectors, len(rows), model['dimension'])
    vectors.flags.writeable = False
    return IntentLibrary(rows, vectors, manifest)
