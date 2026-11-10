"""Guard frozen evaluation provenance against concurrent artifact replacement."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('s5_evaluation', ROOT / 'backend/scripts/evaluate_s5_intent_matching.py')
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


def inputs(tmp_path):
    artifact = tmp_path / 'artifact'
    shutil.copytree(ROOT / 'outputs/s5_wbs033_20261110/intent-library-v1', artifact)
    return artifact, ROOT / 'docs/sprint5/intent-dataset-v1/test.jsonl'


def change_version(directory):
    path = directory / 'manifest.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['library_version'] = 'changed-during-evaluation'
    path.write_text(json.dumps(data), encoding='utf-8')


def test_library_replacement_after_capture_aborts_evaluation(tmp_path):
    directory, test_path = inputs(tmp_path)
    frozen = evaluation.capture_evaluation_inputs(directory, test_path)
    change_version(directory)
    with pytest.raises(ValueError, match='LIBRARY_CHANGED_DURING_EVALUATION'):
        evaluation.assert_library_unchanged(directory, frozen['library_manifest_sha256'])


def test_snapshot_digest_is_bound_to_the_actually_loaded_library(tmp_path, monkeypatch):
    directory, test_path = inputs(tmp_path)
    original_loader = evaluation.load_library
    def swap_before_load(path):
        change_version(path)
        return original_loader(path)
    monkeypatch.setattr(evaluation, 'load_library', swap_before_load)
    with pytest.raises(ValueError, match='LIBRARY_CHANGED_DURING_CAPTURE'):
        evaluation.capture_evaluation_inputs(directory, test_path)
