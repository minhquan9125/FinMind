"""The public v2 classifier uses one loaded artifact and explicit score metadata."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from src.retrieval_orchestration.intent_v2_classifier import IntentClassifier, classify_intent

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / 'docs/sprint5/intent-labels.v2.json').read_text(encoding='utf-8'))
LABELS = sorted(x['id'] for x in SCHEMA['labels'])


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


@pytest.fixture
def artifact(tmp_path):
    directory = tmp_path / 'artifact'
    library = directory / 'library'
    library.mkdir(parents=True)
    rows = [dict(id=label, text='Example ' + label, intent_label=label,
                 component_intents=['NEWS', 'NUMERIC'] if label == 'MIXED' else [],
                 family_id=label, split='LIBRARY', annotation_status='LABELED',
                 label_schema_version=SCHEMA['label_schema_version']) for label in LABELS]
    (library / 'library.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    write(library / 'label-schema.json', SCHEMA)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    dataset = dict(dataset_version='unit-v2', label_schema_sha256=sha(library / 'label-schema.json'),
                   files={'library.jsonl': {'sha256': sha(library / 'library.jsonl')}})
    write(library / 'dataset-manifest.json', dataset)
    np.save(library / 'vectors.npy', np.eye(11, dtype=np.float32), allow_pickle=False)
    write(library / 'manifest.json', dict(format_version=1, status='READY', row_count=11,
        row_ids=LABELS, library_version='unit-v2', dataset_version='unit-v2',
        label_schema_version=SCHEMA['label_schema_version'], test_rows_embedded=0,
        model=dict(name='TEST', revision='a' * 40, dimension=11, dtype='float32', normalization='L2'),
        files={n: sha(library / n) for n in ['library.jsonl','label-schema.json','dataset-manifest.json','vectors.npy']}))
    np.savez(directory / 'classifier.npz', coefficients=np.eye(11) * 3, intercepts=np.zeros(11))
    write(directory / 'fit.json', {'test_encoder_only': True})
    write(directory / 'manifest.json', dict(format_version='intent-classifier-v2', status='READY_FOR_REVIEW',
        labels=LABELS, classifier_version='unit-v2',
        files={n: sha(directory / n) for n in ['library/manifest.json', 'classifier.npz', 'fit.json']}))
    return directory


class Encoder:
    model_name, revision = 'TEST', 'a' * 40

    def __init__(self, label='NUMERIC'):
        self.label, self.calls = label, []

    def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [np.eye(11)[LABELS.index(self.label)].tolist() for _ in texts]


@pytest.mark.parametrize('label', LABELS)
def test_real_ranking_math_roundtrips_every_label_with_a_fake_encoder(artifact, label):
    encoder = Encoder(label)
    result = IntentClassifier.load(artifact, encoder).classify('Một yêu cầu chưa có luật cụ thể')
    assert result['base_ranking']['groups'][0]['intent_label'] == label
    assert result['base_ranking']['ranking_policy'] == 'intent-linear-v2'
    assert result['base_ranking']['score_type'] == 'CLASSIFIER_PROBABILITY_UNCALIBRATED'
    assert len(result['base_ranking']['groups']) == 3
    assert result['resolution']['confidence'] is None
    assert result['resolution']['runtime_enabled'] is False
    assert 'route' not in result and 'decision' not in result


def test_rule_override_preserves_raw_classifier_scores(artifact):
    result = IntentClassifier.load(artifact, Encoder('NEWS')).classify('Giá FPT hôm nay bao nhiêu?')
    assert result['base_ranking']['groups'][0]['intent_label'] == 'NEWS'
    assert result['resolution']['intent_label'] == 'PRICE'
    assert result['resolution']['reason'] == 'EXPLICIT_REQUEST_TYPE'
    assert result['reference_ranking']['score_type'] == 'COSINE_SIMILARITY_NOT_PROBABILITY'


def test_compound_goals_include_a_restricted_component(artifact):
    result = IntentClassifier.load(artifact, Encoder()).classify('Doanh thu FPT năm 2024 bao nhiêu rồi khuyên tôi có nên mua FPT?')
    assert result['resolution']['intent_label'] == 'MIXED'
    assert set(result['resolution']['component_labels']) == {'NUMERIC', 'OUT_OF_SCOPE'}
    assert result['resolution']['contains_restricted_component'] is True


def test_followup_has_a_label_but_needs_verified_context(artifact):
    classifier = IntentClassifier.load(artifact, Encoder())
    result = classifier.classify('Còn SSI thì sao?')
    assert result['resolution']['intent_label'] == 'CONVERSATION'
    assert result['resolution']['status'] == 'NEEDS_CONTEXT'
    assert classifier.classify('Còn SSI thì sao?', context={'verified': True})['resolution']['status'] == 'PROPOSED'


@pytest.mark.parametrize('question', ['', ' ', None, 7])
def test_invalid_question_stops_before_embedding(artifact, question):
    encoder = Encoder()
    classifier = IntentClassifier.load(artifact, encoder)
    with pytest.raises(ValueError, match='QUESTION'):
        classifier.classify(question)
    assert not encoder.calls


def test_checksum_failure_and_wrong_revision_are_rejected(artifact):
    encoder = Encoder()
    encoder.revision = 'b' * 40
    with pytest.raises(ValueError, match='REVISION_MISMATCH'):
        IntentClassifier.load(artifact, encoder)
    encoder.revision = 'a' * 40
    with (artifact / 'classifier.npz').open('ab') as handle:
        handle.write(b'tampered')
    with pytest.raises(ValueError, match='CHECKSUM'):
        IntentClassifier.load(artifact, encoder)


def test_public_function_caches_artifact_and_does_not_read_files_per_request(artifact, monkeypatch):
    encoder = Encoder()
    first = classify_intent('Giá FPT hôm nay bao nhiêu?', embedder=encoder, artifact_path=artifact)
    def fail_read(*args, **kwargs):
        raise AssertionError('Artifact must already be in memory')
    monkeypatch.setattr(Path, 'read_bytes', fail_read)
    monkeypatch.setattr(Path, 'read_text', fail_read)
    second = classify_intent('Doanh thu FPT năm 2024 bao nhiêu?', embedder=encoder, artifact_path=artifact)
    assert first['resolution']['intent_label'] == 'PRICE'
    assert second['resolution']['intent_label'] == 'NUMERIC'
    assert len(encoder.calls) == 2


@pytest.mark.parametrize('vectors', [[[0.] * 11], [[float('nan')] * 11], [[1.] * 10], []])
def test_invalid_encoder_vectors_are_rejected(artifact, vectors):
    encoder = Encoder()
    classifier = IntentClassifier.load(artifact, encoder)
    encoder.embed_texts = lambda texts: vectors
    with pytest.raises(ValueError, match='VECTOR'):
        classifier.classify('Doanh thu FPT bao nhiêu?')


def test_mismatched_model_name_is_rejected(artifact):
    encoder = Encoder()
    encoder.model_name = 'WRONG'
    with pytest.raises(ValueError, match='MODEL_MISMATCH'):
        IntentClassifier.load(artifact, encoder)


@pytest.mark.parametrize('shape', [(7, 11), (11, 10)])
def test_checksummed_but_wrong_parameter_shape_is_rejected(artifact, shape):
    np.savez(artifact / 'classifier.npz', coefficients=np.zeros(shape), intercepts=np.zeros(11))
    manifest = json.loads((artifact / 'manifest.json').read_text(encoding='utf-8'))
    manifest['files']['classifier.npz'] = hashlib.sha256((artifact / 'classifier.npz').read_bytes()).hexdigest()
    write(artifact / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='INVALID_CLASSIFIER_PARAMETERS'):
        IntentClassifier.load(artifact, Encoder())


def test_partial_compound_request_requires_review_instead_of_hiding_unknown_goal(artifact):
    result = IntentClassifier.load(artifact, Encoder('NUMERIC')).classify(
        'Doanh thu FPT bao nhiêu rồi làm điều đó giúp tôi?')
    assert result['resolution']['status'] == 'UNRESOLVED'
    assert result['resolution']['unresolved_requests']


def test_contract_has_question_and_explicit_evidence_without_invented_scores(artifact):
    question = 'Doanh thu FPT bao nhiêu?'
    result = IntentClassifier.load(artifact, Encoder('NEWS')).classify(question)
    resolution = result['resolution']
    assert resolution['question'] == question
    assert resolution['explicit_evidence'] == [dict(text=question, intent_label='NUMERIC')]
    assert 'score' not in resolution
    assert resolution['score_type'] == 'DECISION_EVIDENCE_NO_CONFIDENCE'


def test_session_creation_does_not_require_previous_context(artifact):
    result = IntentClassifier.load(artifact, Encoder('CONVERSATION')).classify('Tạo phiên nghiên cứu mới.')
    assert result['resolution']['status'] == 'PROPOSED'


# Gold comes from frozen library families, not from the classifier's prediction.
REVIEW_FAMILIES = {
    'L2-NUMERIC-016': ('NUMERIC', []),
    'L2-ANALYSIS-014': ('ANALYSIS', []),
    'L2-NEWS-007': ('NEWS', []),
    'L2-NEWS-020': ('NEWS', []),
    'L2-PERSON_ROLE-008': ('PERSON_ROLE', []),
    'L2-PERSON_ROLE-012': ('PERSON_ROLE', []),
    'L2-MIXED-006': ('MIXED', ['NEWS', 'NUMERIC']),
    'L2-NEWS-006': ('NEWS', []),
    'L2-MIXED-019': ('MIXED', ['OUT_OF_SCOPE', 'PRICE']),
}
REVIEW_ROWS = [json.loads(line) for line in (ROOT / 'docs/sprint5/intent-v2/library.jsonl')
               .read_text(encoding='utf-8').splitlines() if json.loads(line)['family_id'] in REVIEW_FAMILIES]


@pytest.mark.parametrize('row', REVIEW_ROWS, ids=lambda row: row['id'])
def test_review_families_do_not_override_correct_classifier_with_wrong_goal(artifact, row):
    expected, components = REVIEW_FAMILIES[row['family_id']]
    assert row['intent_label'] == expected
    result = IntentClassifier.load(artifact, Encoder(expected)).classify(row['text'])
    assert result['base_ranking']['groups'][0]['intent_label'] == expected
    assert result['resolution']['intent_label'] == expected
    assert result['resolution']['component_labels'] == components
    assert result['resolution']['status'] == 'PROPOSED'


@pytest.mark.parametrize('question', [
    'Xin chào, tôi có nên mua FPT không?',
    'Chào bạn, hãy khuyên tôi nên bán hay giữ SSI.',
    'Cảm ơn bạn, hãy dự đoán giá HPG vào tuần sau.',
])
def test_salutation_cannot_remove_restricted_request(artifact, question):
    result = IntentClassifier.load(artifact, Encoder('OUT_OF_SCOPE')).classify(question)
    assert result['resolution']['intent_label'] == 'OUT_OF_SCOPE'
    assert result['resolution']['contains_restricted_component'] is True


@pytest.mark.parametrize('question', ['Xin chào, còn SSI thì sao?', 'Cảm ơn bạn, số 2 nhé.'])
def test_salutation_does_not_supply_followup_context(artifact, question):
    classifier = IntentClassifier.load(artifact, Encoder('CONVERSATION'))
    result = classifier.classify(question)
    assert result['resolution']['intent_label'] == 'CONVERSATION'
    assert result['resolution']['status'] == 'NEEDS_CONTEXT'
    assert classifier.classify(question, context={'verified': True})['resolution']['status'] == 'PROPOSED'


@pytest.mark.parametrize('question', ['Xin chào!', 'Chào bạn.', 'Cảm ơn bạn!',
    'Chào bạn, rất vui được trò chuyện.', 'Cảm ơn phần giải đáp vừa rồi nhé.'])
def test_only_a_greeting_is_standalone_conversation(artifact, question):
    result = IntentClassifier.load(artifact, Encoder('CONVERSATION')).classify(question)
    assert result['resolution']['intent_label'] == 'CONVERSATION'
    assert result['resolution']['status'] == 'PROPOSED'


def test_quoted_advice_and_user_advice_keep_both_component_goals(artifact):
    question = 'Tóm tắt bài báo khuyến nghị mua FPT rồi khuyên tôi có nên mua FPT không?'
    result = IntentClassifier.load(artifact, Encoder('MIXED')).classify(question)
    assert result['resolution']['intent_label'] == 'MIXED'
    assert result['resolution']['component_labels'] == ['NEWS', 'OUT_OF_SCOPE']
    assert result['resolution']['contains_restricted_component'] is True


def test_a_separately_delimited_thanks_and_news_request_preserve_both_speech_acts(artifact):
    result = IntentClassifier.load(artifact, Encoder('MIXED')).classify('Cảm ơn bạn; hãy tìm bài tin mới nhất về ACB.')
    assert result['resolution']['intent_label'] == 'MIXED'
    assert result['resolution']['component_labels'] == ['CONVERSATION', 'NEWS']
    assert result['resolution']['status'] == 'PROPOSED'
