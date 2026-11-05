"""Registry revisions preserve old files and make identity merges explicit."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.scripts.build_registry_revision import apply_changes


def row(ident, name, ticker=None):
    return {'entity_id': ident, 'entity_type': 'Company', 'canonical_name': name,
            'aliases': [name] + ([ticker] if ticker else []),
            'ticker_aliases': [ticker] if ticker else [],
            'identity_key': 'name:' + name, 'verified': True}


def changes():
    return {'add_aliases': [], 'remove_aliases': [], 'add_entities': [],
            'merge_entities': [{'source_id': 'old', 'target_id': 'keep'}],
            'merged_ids': {'old': 'keep'}}


def test_merge_moves_canonical_aliases_and_ticker_without_mutating_base():
    base = [row('keep', 'Công ty Alpha'), row('old', 'Công ty Alpha (Telecom)', 'FOX')]
    before = deepcopy(base)
    result = apply_changes(base, changes())
    assert base == before
    assert len(result) == 1 and result[0]['entity_id'] == 'keep'
    assert result[0]['canonical_name'] == 'Công ty Alpha'
    assert result[0]['identity_key'] == base[0]['identity_key']
    assert 'Công ty Alpha (Telecom)' in result[0]['aliases']
    assert 'FOX' in result[0]['aliases'] and result[0]['ticker_aliases'] == ['FOX']


@pytest.mark.parametrize('update', [
    {'merged_ids': {'old': 'other'}},
    {'merge_entities': [{'source_id': 'keep', 'target_id': 'keep'}]},
    {'merge_entities': [{'source_id': 'missing', 'target_id': 'keep'}]},
    {'merge_entities': [{'source_id': 'old', 'target_id': 'keep'},
                        {'source_id': 'keep', 'target_id': 'old'}]},
])
def test_invalid_mapping_is_rejected(update):
    proposal = changes() | update
    with pytest.raises(ValueError):
        apply_changes([row('keep', 'Công ty Alpha'), row('old', 'Công ty Beta')], proposal)


def test_new_alias_collision_is_rejected():
    proposal = changes()
    proposal['add_aliases'] = [{'entity_id': 'keep', 'aliases': ['Công ty Gamma']}]
    with pytest.raises(ValueError, match='Alias'):
        apply_changes([row('keep', 'Công ty Alpha'), row('old', 'Công ty Beta'),
                       row('third', 'Công ty Gamma')], proposal)


def test_unverified_identity_is_not_promoted_by_merge():
    base = [row('keep', 'Công ty Alpha'), row('old', 'Công ty Beta')]
    base[1]['verified'] = False
    with pytest.raises(ValueError, match='verified'):
        apply_changes(base, changes())


def test_proposed_r3_is_reproducible_and_keeps_fox_on_one_identity():
    folder = Path(__file__).resolve().parents[1] / 'src/sprint4_runtime'
    proposal = json.loads((folder / 'company.registry.20261105.r3.changes.json').read_text('utf-8'))
    base = json.loads((folder / proposal['base']).read_text('utf-8'))
    result = apply_changes(base, proposal)
    assert result == json.loads((folder / proposal['result']).read_text('utf-8'))
    assert len(result) == len(base) - 1
    assert proposal['application_load_allowed'] is False
    assert not any(r['entity_id'] == 'CMP-7159a1a0f4ea52a1ffd3' for r in result)
    owners = [r['entity_id'] for r in result if 'FOX' in r.get('ticker_aliases', [])]
    assert owners == ['CMP-7097a7e10282f47ca683']
