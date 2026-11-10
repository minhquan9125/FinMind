import numpy as np
import pytest

from src.retrieval_orchestration.intent_library import IntentLibrary
from src.retrieval_orchestration.intent_matching import IntentMatcher, summarize_evaluation


class Encoder:
    model_name = 'TEST'
    revision = 'a' * 40

    def __init__(self, vector=(10, 0)):
        self.vector = vector
        self.calls = []

    def embed_query(self, text):
        self.calls.append(text)
        return self.vector

    def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [self.vector for _ in texts]


def library():
    rows = tuple(dict(id=ident, text=ident, intent_label=label,
                      component_intents=['NUMERIC', 'NEWS'] if label == 'MIXED' else [])
                 for ident, label in [('n2', 'NUMERIC'), ('n1', 'NUMERIC'),
                                      ('z', 'NEWS'), ('m', 'MIXED'), ('r', 'PERSON_ROLE')])
    return IntentLibrary(rows, np.asarray([[1, 0], [1, 0], [0, 1], [.8, .6], [-1, 0]], dtype=np.float32),
                         dict(model=dict(name='TEST', revision='a' * 40, dimension=2),
                              library_version='unit', dataset_version='unit-data', label_schema_version='unit-labels'))


def test_cosine_normalizes_query_groups_labels_and_keeps_best_example():
    encoder = Encoder()
    result = IntentMatcher(library(), encoder).match('Một câu hỏi', top_groups=9, top_examples=9)
    assert encoder.calls == ['Một câu hỏi']
    assert [g['intent_label'] for g in result['groups']] == ['NUMERIC', 'MIXED', 'NEWS', 'PERSON_ROLE']
    assert result['groups'][0]['score'] == pytest.approx(1)
    assert result['groups'][1]['score'] == pytest.approx(.8)
    assert result['groups'][-1]['score'] == pytest.approx(-1)
    assert result['groups'][0]['best_example']['id'] == 'n1'
    assert result['groups'][1]['best_example']['component_intents'] == ['NUMERIC', 'NEWS']
    assert len(result['examples']) == 5
    assert 'route' not in result and 'decision' not in result


def test_group_score_is_max_not_sum_or_number_of_variants():
    result = IntentMatcher(library(), Encoder((1, 1))).match('q')
    scores = {g['intent_label']: g['score'] for g in result['groups']}
    assert scores['NUMERIC'] == pytest.approx(scores['NEWS'])
    assert result['groups'][0]['intent_label'] == 'MIXED'


@pytest.mark.parametrize('attribute,value,error', [
    ('model_name', 'wrong', 'MODEL_MISMATCH'), ('revision', 'b' * 40, 'REVISION_MISMATCH')])
def test_wrong_encoder_is_rejected_before_any_call(attribute, value, error):
    encoder = Encoder()
    setattr(encoder, attribute, value)
    with pytest.raises(ValueError, match=error):
        IntentMatcher(library(), encoder)
    assert encoder.calls == []


@pytest.mark.parametrize('question', ['', '  ', None, 42])
def test_bad_question_stops_before_embedding(question):
    encoder = Encoder()
    with pytest.raises(ValueError, match='QUESTION'):
        IntentMatcher(library(), encoder).match(question)
    assert encoder.calls == []


@pytest.mark.parametrize('vector', [[0, 0], [np.nan, 1], [1, np.inf], [1, 2, 3]])
def test_bad_query_vectors_are_rejected(vector):
    with pytest.raises(ValueError, match='QUERY_VECTOR'):
        IntentMatcher(library(), Encoder(vector)).match('q')


@pytest.mark.parametrize('count', [0, -1, True, 1.5])
def test_invalid_top_k_stops_before_embedding(count):
    encoder = Encoder()
    with pytest.raises(ValueError, match='TOP_K'):
        IntentMatcher(library(), encoder).match('q', top_groups=count)
    assert encoder.calls == []


def test_batch_preserves_text_order_and_does_not_normalize_accents():
    encoder = Encoder()
    matcher = IntentMatcher(library(), encoder)
    questions = ['  Ai là TGĐ? ', 'ai la tgd?']
    results = matcher.match_many(questions)
    assert encoder.calls == [questions]
    assert [r['question'] for r in results] == questions
    assert matcher.match_many([]) == []
    with pytest.raises(ValueError, match='QUESTION'):
        matcher.match_many(['q', ''])
    assert len(encoder.calls) == 1


def test_evaluation_reports_wrong_cases_and_excludes_unlabeled_questions():
    cases = [dict(id='1', intent_label='NUMERIC', annotation_status='LABELED'),
             dict(id='2', intent_label='NEWS', annotation_status='LABELED'),
             dict(id='3', intent_label='NEWS', annotation_status='LABELED'),
             dict(id='4', intent_label=None, annotation_status='OUTSIDE_TAXONOMY')]
    rankings = [dict(groups=[dict(intent_label=label) for label in order]) for order in
                [['NUMERIC', 'NEWS'], ['NUMERIC', 'NEWS'], ['NEWS', 'NUMERIC'], ['NUMERIC', 'NEWS']]]
    summary = summarize_evaluation(cases, rankings, ['NUMERIC', 'NEWS'])
    assert summary['labeled_cases'] == 3
    assert summary['unlabeled_cases'] == 1
    assert summary['top1_accuracy'] == pytest.approx(2/3)
    assert summary['top3_recall'] == 1
    assert summary['macro_f1'] == pytest.approx(2/3)
    assert summary['wrong_case_ids'] == ['2']


@pytest.mark.parametrize('questions', [None, {'first': 'q'}, {'q1', 'q2'}, b'q', iter(['q'])])
def test_batch_rejects_unordered_or_non_sequence_input_before_embedding(questions):
    encoder = Encoder()
    with pytest.raises(ValueError, match='QUESTIONS_MUST_BE_A_SEQUENCE'):
        IntentMatcher(library(), encoder).match_many(questions)
    assert encoder.calls == []


def test_distinct_batch_vectors_keep_their_question_association():
    encoder = Encoder()
    encoder.embed_texts = lambda texts: [[10, 0], [0, 10]]
    result = IntentMatcher(library(), encoder).match_many(('number question', 'news question'))
    assert [r['groups'][0]['intent_label'] for r in result] == ['NUMERIC', 'NEWS']
    assert [r['question'] for r in result] == ['number question', 'news question']
