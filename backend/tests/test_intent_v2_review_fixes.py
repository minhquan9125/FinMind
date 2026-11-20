"""Hưng's review findings on Nhân's v2 rules (14/11): each was a wrong label on a new question."""
import pytest

from src.retrieval_orchestration.intent_v2_classifier import IntentClassifier
from src.retrieval_orchestration.intent_v2_rules import explicit_intent, requests
from tests.test_s5_intent_v2_runtime import Encoder, artifact  # noqa: F401  (pytest fixture)


@pytest.mark.parametrize('question,label', [
    ('fpt định giá thế nào', 'ANALYSIS'),          # "định giá" is valuation, not the market price
    ('định giá cổ phiếu mbb hiện nay', 'ANALYSIS'),
    ('fpt đang đắt hay rẻ', 'ANALYSIS'),
    ('giá fpt hôm nay', 'PRICE'),                   # the plain price question is unchanged
    ('fpt có đáng đầu tư không', 'OUT_OF_SCOPE'),
    ('có nên đầu tư vào mbb', 'OUT_OF_SCOPE'),
    ('mbb bao giờ tăng lại', 'OUT_OF_SCOPE'),
    ('vcb có tăng trưởng tốt không', None),         # a judgement about results, not advice: rules stay silent
])
def test_valuation_and_investment_advice_wording(question, label):
    assert explicit_intent(question) == label


@pytest.mark.parametrize('question,parts', [
    ('doanh thu fpt 2025 và tin tức mới về fpt', ['doanh thu fpt 2025', 'tin tức mới về fpt']),
    ('giá fpt và phân tích fpt', ['giá fpt', 'phân tích fpt']),
    ('doanh thu và lợi nhuận fpt 2025', ['doanh thu và lợi nhuận fpt 2025']),   # one goal, two metrics
    ('Nhận định sức khỏe tài chính FPT dựa trên nợ và dòng tiền ba năm gần đây.',   # metrics are the evidence
     ['Nhận định sức khỏe tài chính FPT dựa trên nợ và dòng tiền ba năm gần đây']),
])
def test_and_splits_two_goals_of_different_types_only(question, parts):
    assert requests(question) == parts


def test_two_goal_question_becomes_mixed_with_both_components(artifact):  # noqa: F811
    result = IntentClassifier.load(artifact, Encoder()).classify('doanh thu fpt 2025 và tin tức mới về fpt')
    assert result['resolution']['intent_label'] == 'MIXED'
    assert result['resolution']['component_labels'] == ['NEWS', 'NUMERIC']


def test_a_guessed_conversation_without_followup_words_does_not_wait_for_context(artifact):  # noqa: F811
    result = IntentClassifier.load(artifact, Encoder('CONVERSATION')).classify('hôm nay ăn gì')
    assert result['resolution']['reason'] == 'CLASSIFIER_PROPOSAL'
    assert result['resolution']['status'] == 'PROPOSED'   # the fallback (Gemini) decides, not the session
