"""Protect schema v2 and train/development separation."""
import copy
import json
from pathlib import Path

import pytest

from src.retrieval_orchestration.intent_v2_dataset import validate_rows, validate_dataset

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / 'docs/sprint5/intent-labels.v2.json').read_text(encoding='utf-8'))


def row(text='Doanh thu FPT bao nhiêu?', split='LIBRARY', **updates):
    return dict(id='L1', text=text, intent_label='NUMERIC', component_intents=[],
                family_id='family1', subtype='lookup', split=split,
                linguistic_form='ACCENTED') | updates


def test_cross_split_normalized_text_and_family_leakage_are_rejected():
    original = row()
    leaked = row('doanh thu fpt bao nhieu!', 'DEVELOPMENT', id='D1')
    with pytest.raises(ValueError, match='LEAKAGE'):
        validate_rows([original, leaked], SCHEMA)


def test_variants_remain_in_one_family_and_split():
    assert validate_rows([row(), row('doanh thu fpt bao nhieu?', id='L2', linguistic_form='UNACCENTED')], SCHEMA) is None


@pytest.mark.parametrize('components', [[], ['NEWS'], ['NEWS', 'NEWS'], ['NEWS', 'MIXED'], ['BAD', 'NEWS']])
def test_mixed_requires_distinct_valid_component_intents(components):
    with pytest.raises(ValueError, match='COMPONENT'):
        validate_rows([row(intent_label='MIXED', subtype='cross_source', component_intents=components)], SCHEMA)


@pytest.mark.parametrize('updates', [dict(intent_label='BAD'), dict(text=''), dict(subtype='BAD'), dict(split='TEST_SECRET'), dict(component_intents=['NEWS'])])
def test_invalid_annotations_are_rejected(updates):
    with pytest.raises(ValueError):
        validate_rows([row(**updates)], SCHEMA)


def test_v2_input_is_not_misrepresented_as_team_approved():
    assert SCHEMA['approval']['status'] == 'OWNER_AUTHORIZED_PENDING_TEAM_REVIEW'
    assert len(SCHEMA['labels']) == 11
    assert {x['id'] for x in SCHEMA['labels']} >= {'PRICE', 'ANALYSIS', 'OUT_OF_SCOPE', 'CONVERSATION'}


def test_complete_dataset_is_separate_and_has_twenty_seed_families_per_label():
    summary = validate_dataset(ROOT / 'docs/sprint5/intent-v2', ROOT / 'docs/sprint5/intent-labels.v2.json')
    assert summary['library_seed_families'] == 220
    assert summary['development_rows'] == 110
    assert summary['blind_acceptance_available'] is False
    assert min(summary['families_per_label'].values()) >= 20
