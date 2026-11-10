"""Artifact integrity and split protection; fake encoder only in unit tests."""
import hashlib
import json
from pathlib import Path
import shutil

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


def input_snapshot(tmp_path):
    dataset = tmp_path / 'inputs'
    dataset.mkdir()
    for name in ('library.jsonl', 'manifest.json'):
        shutil.copyfile(DATASET / name, dataset / name)
    schema = tmp_path / 'schema.json'
    shutil.copyfile(SCHEMA, schema)
    return dataset, schema


def test_input_snapshot_is_preserved_if_source_changes_during_embedding(tmp_path):
    dataset, schema = input_snapshot(tmp_path)
    original_manifest = (dataset / 'manifest.json').read_bytes()
    original_schema = schema.read_bytes()
    encoder = Encoder()
    encode = encoder.embed_texts
    def mutate_after_read(texts):
        manifest = json.loads(original_manifest)
        manifest['dataset_version'] = 'changed-during-encoding'
        (dataset / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        schema.write_text('{}', encoding='utf-8')
        return encode(texts)
    encoder.embed_texts = mutate_after_read
    artifact = build_library(dataset, schema, tmp_path / 'result', encoder,
                             library_version='snapshot-test', expected_dimension=2)
    assert artifact.manifest['dataset_version'] == json.loads(original_manifest)['dataset_version']
    assert (tmp_path / 'result/dataset-manifest.json').read_bytes() == original_manifest
    assert (tmp_path / 'result/label-schema.json').read_bytes() == original_schema


@pytest.mark.parametrize('unapproved', ['dataset', 'schema'])
def test_unapproved_input_stops_before_encoder_and_output(tmp_path, unapproved):
    dataset, schema = input_snapshot(tmp_path)
    path = dataset / 'manifest.json' if unapproved == 'dataset' else schema
    value = json.loads(path.read_text(encoding='utf-8'))
    if unapproved == 'dataset':
        value['approval_status'] = 'PENDING'
    else:
        value['approval']['status'] = 'PENDING'
    path.write_text(json.dumps(value), encoding='utf-8')
    encoder = Encoder()
    with pytest.raises(ValueError, match='INPUT_NOT_APPROVED'):
        build_library(dataset, schema, tmp_path / 'result', encoder,
                      library_version='test', expected_dimension=2)
    assert encoder.calls == []
    assert not (tmp_path / 'result').exists()


def test_changed_library_checksum_stops_before_encoder(tmp_path):
    dataset, schema = input_snapshot(tmp_path)
    path = dataset / 'library.jsonl'
    path.write_bytes(path.read_bytes() + b'\n')
    encoder = Encoder()
    with pytest.raises(ValueError, match='INPUT_CHECKSUM_MISMATCH'):
        build_library(dataset, schema, tmp_path / 'result', encoder,
                      library_version='test', expected_dimension=2)
    assert encoder.calls == []
