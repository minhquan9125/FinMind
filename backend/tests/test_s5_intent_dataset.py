"""Protect the intent dataset against invalid labels and evaluation leakage."""
import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('s5_dataset', ROOT / 'backend/scripts/validate_s5_intent_dataset.py')
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def row(identifier, text, split='LIBRARY', label='NUMERIC', family=None):
    return dict(id=identifier, text=text, split=split, intent_label=label,
                family_id=family or identifier, component_intents=[], source_types=[],
                annotation_status='LABELED', scope_status='RESOLVED',
                annotation_note='fixture', operation='lookup', linguistic_form='ACCENTED',
                label_schema_version='s5-intent-labels-v1-draft2')


def test_rejects_accent_and_punctuation_variant_leaking_to_test():
    rows = [row('l', 'Giá đóng cửa BID bao nhiêu?'),
            row('t', 'gia dong cua bid bao nhieu!', 'TEST')]
    assert any('TEXT_LEAKAGE' in e for e in validator.validate_rows(rows))


def test_rejects_distinct_paraphrases_with_same_family_in_both_splits():
    rows = [row('l', 'Tài sản cuối kỳ của BID?', family='same-goal'),
            row('t', 'BID có tổng tài sản là bao nhiêu?', 'TEST', family='same-goal')]
    assert any('FAMILY_LEAKAGE' in e for e in validator.validate_rows(rows))


@pytest.mark.parametrize('components', [[], ['NEWS'], ['NEWS', 'NEWS'], ['NEWS', 'MIXED'], ['NEWS', 'BAD']])
def test_mixed_requires_distinct_base_components(components):
    item = row('m', 'Tóm tắt tin và đọc số liệu.', label='MIXED')
    item['component_intents'] = components
    assert any('MIXED_COMPONENTS' in e for e in validator.validate_rows([item]))


def test_unknown_requires_null_label_and_stays_out_of_embedding_library():
    item = row('x', 'Mình đang nói về ai vậy?')
    item.update(intent_label=None, annotation_status='NEEDS_CONTEXT', scope_status='NEEDS_CONTEXT')
    assert any('LIBRARY_UNLABELED' in e for e in validator.validate_rows([item]))
    item['split'] = 'TEST'
    assert validator.validate_rows([item]) == []
    item['intent_label'] = 'MIXED'
    assert any('STATUS_LABEL' in e for e in validator.validate_rows([item]))


def test_allows_known_intent_with_partial_scope():
    item = row('t', 'Dòng tiền năm 2024 bao nhiêu?', 'TEST')
    item['scope_status'] = 'PARTIAL'
    assert validator.validate_rows([item]) == []


def test_rejects_bad_sources_ids_and_schema_version():
    item = row('t', 'Một câu hỏi.', 'TEST')
    item.update(source_types=['GRAPH'], label_schema_version='wrong')
    errors = validator.validate_rows([item, copy.deepcopy(item)])
    assert any('SOURCE_TYPES' in e for e in errors)
    assert any('SCHEMA_VERSION' in e for e in errors)
    assert any('DUPLICATE_ID' in e for e in errors)


def test_dataset_matches_pinned_schema_and_declared_coverage():
    errors, summary = validator.validate_dataset(ROOT / 'docs/sprint5/intent-dataset-v1')
    assert errors == []
    assert summary['library_rows'] == 84
    assert summary['test_rows'] == 54
    assert summary['test_unlabeled_rows'] == 9


def test_pinned_files_use_lf_so_git_checkout_preserves_checksums():
    paths = [ROOT / 'docs/sprint5/intent-labels.v1.json']
    paths.extend((ROOT / 'docs/sprint5/intent-dataset-v1').glob('*.json*'))
    for path in paths:
        assert b'\r\n' not in path.read_bytes(), f'{path.name}: CRLF would change on checkout'
