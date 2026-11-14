"""Evaluation must count unresolved cases and lost restricted components honestly."""
import importlib
from pathlib import Path

import pytest


@pytest.fixture
def summarize(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    return importlib.import_module('evaluate_s5_intent_v2').summarize_resolution


def case(ident, label, components=None):
    return dict(id=ident, intent_label=label, component_intents=components or [])


def prediction(label, *, status='PROPOSED', components=None, restricted=False):
    return dict(intent_label=label, status=status, component_labels=components or [],
                contains_restricted_component=restricted)


def test_unresolved_is_kept_in_denominator_even_with_correct_top_label(summarize):
    metrics = summarize([case('a', 'NUMERIC'), case('b', 'NUMERIC')],
                        [prediction('NUMERIC'), prediction('NUMERIC', status='UNRESOLVED')])
    assert metrics['label_correct_count'] == 2
    assert metrics['complete_classification_correct_count'] == 1
    assert metrics['complete_classification_accuracy'] == 0.5
    assert metrics['unresolved_ids'] == ['b']


def test_mixed_label_alone_cannot_hide_a_lost_restricted_component(summarize):
    metrics = summarize([case('a', 'MIXED', ['NEWS', 'OUT_OF_SCOPE'])],
                        [prediction('MIXED', components=['NEWS'])])
    assert metrics['label_correct_count'] == 1
    assert metrics['complete_classification_correct_count'] == 0
    assert metrics['component_mismatch_ids'] == ['a']
    assert metrics['lost_restricted_component_ids'] == ['a']


def test_a_followup_can_have_correct_classification_while_waiting_for_context(summarize):
    metrics = summarize([case('a', 'CONVERSATION')],
                        [prediction('CONVERSATION', status='NEEDS_CONTEXT')])
    assert metrics['complete_classification_correct_count'] == 1
    assert metrics['needs_context_ids'] == ['a']
    assert metrics['not_proposed_ids'] == ['a']
    assert metrics['routing_not_executed'] is True


def test_missing_prediction_does_not_silently_shrink_the_evaluation(summarize):
    with pytest.raises(ValueError, match='ALIGNMENT'):
        summarize([case('a', 'NUMERIC')], [])


def test_annotated_greeting_status_is_checked_separately_from_its_label(summarize):
    row = dict(case('a', 'CONVERSATION'), expected_status='PROPOSED')
    metrics = summarize([row], [prediction('CONVERSATION', status='NEEDS_CONTEXT')])
    assert metrics['label_correct_count'] == 1
    assert metrics['complete_classification_correct_count'] == 0
    assert metrics['status_mismatch_ids'] == ['a']
