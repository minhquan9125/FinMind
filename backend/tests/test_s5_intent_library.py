"""Artifact integrity and split protection; fake encoder only in unit tests."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from src.retrieval_orchestration.intent_library import build_library, load_library

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / 'docs/sprint5/intent-dataset-v1'
SCHEMA = ROOT / 'docs/sprint5/intent-labels.v1.json'


class Encoder:
    model_name = 'UNIT-TEST-ENCODER'
    revision = 'a' * 40
    device = 'cpu'
    batch_size = 8

    def __init__(self):
        self.calls = []

    def embed_texts(self, texts):
        self.calls.append(list(texts))
        return np.tile([0.6, 0.8], (len(texts), 1)).tolist()


def build(tmp_path, encoder=None):
    return build_library(DATASET, SCHEMA, tmp_path / 'library', encoder or Encoder(),
                         library_version='test-artifact', expected_dimension=2)


def test_only_library_questions_are_encoded_and_rows_roundtrip(tmp_path):
    encoder = Encoder()
    artifact = build(tmp_path, encoder)
    rows = [json.loads(line) for line in (DATASET / 'library.jsonl').read_text(encoding='utf-8').splitlines()]
    assert encoder.calls == [[r['text'] for r in rows]]
    assert list(artifact.rows) == rows
    assert artifact.vectors.shape == (90, 2)
    assert artifact.vectors.dtype == np.float32
    assert artifact.manifest['model']['name'] == 'UNIT-TEST-ENCODER'
    assert artifact.manifest['row_ids'] == [r['id'] for r in rows]
    assert not (tmp_path / 'library/test.jsonl').exists()


@pytest.mark.parametrize('bad', ['dimension', 'count', 'nan', 'zero', 'unnormalized'])
def test_rejects_invalid_vectors_before_creating_artifact(tmp_path, bad):
    encoder = Encoder()
    def encode(texts):
        vectors = np.tile([0.6, 0.8], (len(texts), 1))
        if bad == 'dimension':
            return np.ones((len(texts), 3))
        if bad == 'count':
            return vectors[:-1]
        if bad == 'nan':
            vectors[0, 0] = np.nan
        elif bad == 'zero':
            vectors[0] = 0
        else:
            vectors[0] *= 2
        return vectors
    encoder.embed_texts = encode
    with pytest.raises(ValueError, match='VECTOR_'):
        build(tmp_path, encoder)
    assert not (tmp_path / 'library').exists()


def test_tampered_vector_file_is_rejected(tmp_path):
    build(tmp_path)
    path = tmp_path / 'library/vectors.npy'
    path.write_bytes(path.read_bytes() + b'tampered')
    with pytest.raises(ValueError, match='CHECKSUM'):
        load_library(path.parent)


def test_reordered_rows_are_rejected_even_with_updated_file_hash(tmp_path):
    build(tmp_path)
    directory = tmp_path / 'library'
    path = directory / 'library.jsonl'
    lines = path.read_bytes().splitlines(keepends=True)
    path.write_bytes(b''.join(reversed(lines)))
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    manifest['files']['library.jsonl'] = hashlib.sha256(path.read_bytes()).hexdigest()
    dataset_path = directory / 'dataset-manifest.json'
    dataset = json.loads(dataset_path.read_text(encoding='utf-8'))
    dataset['files']['library.jsonl']['sha256'] = manifest['files']['library.jsonl']
    dataset_path.write_text(json.dumps(dataset), encoding='utf-8')
    manifest['files']['dataset-manifest.json'] = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError, match='ROW_ORDER'):
        load_library(directory)


def test_expected_model_and_revision_must_match(tmp_path):
    build(tmp_path)
    with pytest.raises(ValueError, match='MODEL_MISMATCH'):
        load_library(tmp_path / 'library', expected_model='BAAI/bge-m3')
    with pytest.raises(ValueError, match='REVISION_MISMATCH'):
        load_library(tmp_path / 'library', expected_revision='b' * 40)


def test_existing_artifact_is_never_overwritten_or_reencoded(tmp_path):
    build(tmp_path)
    encoder = Encoder()
    with pytest.raises(FileExistsError):
        build(tmp_path, encoder)
    assert encoder.calls == []
