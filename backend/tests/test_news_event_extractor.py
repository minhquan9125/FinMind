import hashlib
import json

import pytest

from src.documents.news_event_extractor import extract_batch, rule_candidates


def manifest(ids=('a1', 'a2')):
    docs = [{'document_id': 'doc-' + aid, 'doc_type': 'NEWS',
             'chunks': [{'locator': {'source_table': 'news_articles', 'source_id': aid}}]}
            for aid in ids]
    payload = {'documents': docs}
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                        separators=(',', ':')).encode()).hexdigest()
    return {'corpus_version_id': 'corpus-1', 'manifest_sha256': digest, 'manifest': payload}


def article(aid, body, published='2026-10-14T09:00:00+07:00'):
    return {'article_id': aid, 'source': 'fireant', 'url': f'https://example.org/{aid}',
            'content': body, 'published_at': published, 'symbols': ['FPT']}


def candidate(span, *, status='OCCURRED', event_ref=None, object_='hai AI Factory'):
    return {'event_type': 'FACILITY_COMPLETION', 'status': status,
            'subject': {'name': 'FPT', 'symbol': 'FPT', 'role': 'operator'},
            'participants': [], 'object': object_, 'source_span': span,
            'event_time': None, 'event_time_precision': 'unknown',
            'event_ref': event_ref}


def test_batch_groups_updates_and_keeps_conflicting_claims():
    a = article('a1', 'FPT đã hoàn thiện hai AI Factory tại Nhật Bản và Việt Nam.')
    b = article('a2', 'FPT dự kiến hoàn thiện hai AI Factory tại Nhật Bản và Việt Nam.')
    proposals = {'a1': [candidate(a['content'], event_ref='factory-pair')],
                 'a2': [candidate(b['content'], status='PLANNED', event_ref='factory-pair')]}
    result = extract_batch(manifest(), [a, b], lambda row: proposals[row['article_id']])
    assert len(result['events']) == 1
    group = result['events'][0]
    assert group['status'] == 'CONFLICT'
    assert len(group['source_claims']) == 2
    assert {c['evidence']['article_id'] for c in group['source_claims']} == {'a1', 'a2'}
    assert {c['published_at'] for c in group['source_claims']} == {a['published_at']}
    assert all(c['event_time'] is None for c in group['source_claims'])


def test_ungrounded_claim_goes_to_review_not_event():
    a = article('a1', 'FPT có kế hoạch phát triển công nghệ.')
    result = extract_batch(manifest(), [a], lambda _: [candidate('FPT đã hoàn thiện hai AI Factory')])
    assert result['events'] == []
    assert result['article_results'][0]['review'][0]['reason'] == 'source_span_not_in_body'


def test_explicit_batch_and_manifest_required():
    a = article('outside', 'FPT đã hoàn thiện hai AI Factory.')
    with pytest.raises(ValueError, match='outside frozen'):
        extract_batch(manifest(), [a], rule_candidates)
    with pytest.raises(ValueError, match='Batch must'):
        extract_batch(manifest(), [], rule_candidates)
    tampered = manifest()
    tampered['manifest']['documents'][0]['chunks'][0]['locator']['source_id'] = 'other'
    with pytest.raises(ValueError, match='hash mismatch'):
        extract_batch(tampered, [article('a1', 'FPT đã hoàn thiện hai AI Factory.')], rule_candidates)


def test_conservative_rules_and_no_symbol_only_event():
    a = article('a1', 'FPT đã hoàn thiện hai AI Factory tại Nhật Bản và Việt Nam.')
    proposals = rule_candidates(a)
    assert len(proposals) == 1
    assert proposals[0]['event_type'] == 'FACILITY_COMPLETION'
    assert proposals[0]['event_time'] is None
    tagged = article('a2', 'FPT Retail được dự báo tăng trưởng.')
    assert rule_candidates(tagged) == []


def test_event_date_needs_its_own_body_evidence():
    a = article('a1', 'FPT đã hoàn thiện hai AI Factory ngày 12/10/2026.')
    item = candidate(a['content'])
    item['event_time'] = '2026-10-12'
    item['event_time_precision'] = 'day'
    item['event_time_source_span'] = 'ngày 12/10/2026'
    result = extract_batch(manifest(), [a], lambda _: [item])
    assert result['events'][0]['source_claims'][0]['event_time'] == '2026-10-12'
    item['event_time'] = '2026-10-14'  # article publication day, absent from body
    result = extract_batch(manifest(), [a], lambda _: [item])
    assert result['events'] == []
    assert result['article_results'][0]['status'] == 'REVIEW'
