"""Safety and measurement checks for offline experiments, not production policy."""
import pytest
from src.retrieval_orchestration.intent_experiment import mask_tickers, policy_observation, transitions


def test_mask_only_registered_tickers_preserves_financial_abbreviations():
    assert mask_tickers('HĐQT MBB hỏi ROE, BCTN; mbb và ABCMBB.') == 'HĐQT doanh nghiệp hỏi ROE, BCTN; doanh nghiệp và ABCMBB.'


@pytest.mark.parametrize('score,gap,expected', [(.65,.08,'GRAPH'),(.649,.09,'NEED_FALLBACK'),(.8,.079,'NEED_FALLBACK')])
def test_unchanged_threshold_boundaries(score, gap, expected):
    assert policy_observation('PERSON_ROLE', score, gap) == expected


def test_wrong_high_confidence_label_is_not_rescued_by_policy():
    assert policy_observation('MIXED', .79, .18) == 'BOTH'


def test_transitions_reports_both_improvements_and_regressions():
    before = [dict(id='a', gold='NEWS', top1='NUMERIC'), dict(id='b', gold='NEWS', top1='NEWS')]
    after = [dict(id='a', gold='NEWS', top1='NEWS'), dict(id='b', gold='NEWS', top1='MIXED')]
    assert transitions(before, after) == dict(fixed=['a'], regressed=['b'])


def test_transitions_rejects_misaligned_cases():
    with pytest.raises(ValueError, match='CASE_ALIGNMENT'):
        transitions([dict(id='a', gold='NEWS', top1='NEWS')], [])
