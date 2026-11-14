import copy
import pytest

from src.b1_answering.evidence.market_contract import feed_pack
from src.b1_answering.evidence.citations import prepare_evidence, CitationError
from src.b1_answering.evidence.grounded import validate_grounded
from src.b1_answering.evidence.news_binding import bind_article_quotes


def example():
    pack = feed_pack([{'kind': 'NEWS', 'provider': 'fireant', 'symbol': 'FPT',
        'title': 'FPT triển khai công viên công nghệ', 'description': '',
        'content': 'UBND phường Phú Diễn đề nghị liên hệ trước ngày 30/10/2026. Dự án do FPT đầu tư.',
        'url': 'https://fireant.vn/bai-viet/tin/123', 'published_at': '2026-10-23T09:00:00+07:00',
        'observed_at': '2026-10-23T10:00:00+07:00'}])
    evidence = prepare_evidence(pack)
    eid = next(iter(evidence))
    payload = {'claims': [{'text': 'UBND phường Phú Diễn đề nghị liên hệ trước ngày 30/10/2026 về dự án FPT.',
        'evidence_ids': [eid], 'support_quotes': [{'evidence_id': eid, 'quote': evidence[eid]['title']}]}]}
    return payload, evidence, {'source_type': 'NEWS'}


def test_body_sentence_repairs_title_quote_without_rewriting_the_claim():
    payload, evidence, scope = example()
    saved = copy.deepcopy(payload)
    with pytest.raises(CitationError): validate_grounded(payload, evidence, scope)
    rebound, changes = bind_article_quotes(payload, evidence, scope)
    assert validate_grounded(rebound, evidence, scope)['status'] == 'DRAFT_READY'
    assert rebound['claims'][0]['text'] == payload['claims'][0]['text']
    assert changes[0]['original_quote'] != changes[0]['bound_quote']
    assert payload == saved


@pytest.mark.parametrize('case', ['invented_number', 'nonexistent_quote', 'wrong_source', 'financial'])
def test_rebinding_cannot_justify_unsupported_or_untrusted_claims(case):
    payload, evidence, scope = example()
    if case == 'invented_number': payload['claims'][0]['text'] += ' với 999 dự án.'
    elif case == 'nonexistent_quote': payload['claims'][0]['support_quotes'][0]['quote'] = 'fake quote'
    elif case == 'wrong_source': next(iter(evidence.values())).pop('verification_basis')
    else: scope['source_type'] = 'BCTC'
    assert bind_article_quotes(payload, evidence, scope) is None


def test_two_exact_spans_can_support_facts_far_apart_in_same_article():
    payload, evidence, scope = example()
    item = next(iter(evidence.values()))
    snapshot = copy.deepcopy(item['snapshot'])
    snapshot['content'] = 'FPT có 101 dự án. '+('Phần bối cảnh chung được công bố. '*25)+'FPT có 202 nhân viên.'
    evidence = prepare_evidence(feed_pack([snapshot]))
    eid = next(iter(evidence))
    payload = {'claims': [{'text': 'FPT có 101 dự án và 202 nhân viên.', 'evidence_ids': [eid],
        'support_quotes': [{'evidence_id': eid, 'quote': snapshot['title']}]}]}
    rebound, _ = bind_article_quotes(payload, evidence, scope)
    quotes = rebound['claims'][0]['support_quotes']
    assert len(quotes) == 2
    assert all(len(q['quote']) <= 300 and q['quote'] in evidence[eid]['passage'] for q in quotes)
    assert validate_grounded(rebound, evidence, scope)['status'] == 'DRAFT_READY'


def test_oversized_real_quote_is_shortened_without_accepting_invented_quotes():
    payload, evidence, scope = example()
    snapshot = copy.deepcopy(next(iter(evidence.values()))['snapshot'])
    snapshot['content'] += ' Phần bối cảnh bổ sung trong bài.'*15
    evidence = prepare_evidence(feed_pack([snapshot]))
    eid, item = next(iter(evidence.items()))
    payload['claims'][0]['evidence_ids'] = [eid]
    payload['claims'][0]['support_quotes'][0]['evidence_id'] = eid
    assert 300 < len(item['passage']) < 1200
    payload['claims'][0]['support_quotes'][0]['quote'] = item['passage']
    rebound, _ = bind_article_quotes(payload, evidence, scope)
    assert all(len(q['quote']) <= 300 for q in rebound['claims'][0]['support_quotes'])
    assert validate_grounded(rebound, evidence, scope)['status'] == 'DRAFT_READY'
