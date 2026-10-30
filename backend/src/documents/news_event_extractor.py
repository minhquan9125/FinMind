"""Conservative, read-only batch contract for events in a frozen NEWS corpus.

Candidate generation can be supplied by a rule engine or an LLM.  This module
validates candidates against article bodies and preserves source-level claims.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from collections import defaultdict
from typing import Callable, Iterable

EVENT_TYPES = frozenset({
    'APPROVAL', 'DISCLOSURE', 'SECURITY_ISSUANCE', 'SECURITY_REPURCHASE',
    'DIVIDEND_OR_SHARE_DELIVERY', 'AGREEMENT_SIGNED', 'COLLABORATION',
    'FACILITY_ESTABLISHMENT', 'FACILITY_EXPANSION', 'FACILITY_COMPLETION',
    'INSIDER_TRADE_REGISTRATION', 'PERSONNEL_CHANGE', 'CANCELLATION_OR_DELAY',
})
STATUSES = frozenset({'OCCURRED', 'PLANNED', 'CANCELLED', 'UNCONFIRMED'})
PRECISIONS = frozenset({'day', 'month', 'year', 'range', 'unknown'})
NAMESPACE = uuid.UUID('81384aa5-411a-4659-8e95-dfa82318c564')

# Narrow rules only. New language patterns should be added with a source fixture.
_ACTORS = r'FPT|Techcombank|Vietcombank|MB|Ngân hàng Nhà nước'
_ACTION = re.compile(
    rf'\b(?P<actor>{_ACTORS})\b\s+(?P<cue>đã|dự kiến|sẽ)?\s*'
    r'(?P<verb>phát hành|phân phối|mua lại|tất toán|công bố|thông báo|'
    r'hoàn thiện|hợp tác|ký kết|hủy|hoãn)\s+(?P<object>[^.;\n]{8,220})', re.I)
_TYPE = {'phát hành': 'SECURITY_ISSUANCE', 'phân phối': 'SECURITY_ISSUANCE',
         'mua lại': 'SECURITY_REPURCHASE', 'tất toán': 'SECURITY_REPURCHASE',
         'công bố': 'DISCLOSURE', 'thông báo': 'DISCLOSURE',
         'hoàn thiện': 'FACILITY_COMPLETION', 'hợp tác': 'COLLABORATION',
         'ký kết': 'AGREEMENT_SIGNED', 'hủy': 'CANCELLATION_OR_DELAY',
         'hoãn': 'CANCELLATION_OR_DELAY'}
_ROLE = {'SECURITY_ISSUANCE': 'issuer', 'SECURITY_REPURCHASE': 'repurchaser',
         'DISCLOSURE': 'discloser', 'FACILITY_COMPLETION': 'operator',
         'COLLABORATION': 'collaborator', 'AGREEMENT_SIGNED': 'signatory',
         'CANCELLATION_OR_DELAY': 'canceller'}
_SYMBOL = {'fpt': 'FPT', 'techcombank': 'TCB', 'vietcombank': 'VCB', 'mb': 'MBB'}


def rule_candidates(article: dict) -> list[dict]:
    """Generate only explicit actor + verb + object candidates from body text."""
    body = article.get('content') or ''
    candidates = []
    for match in _ACTION.finditer(body):
        actor, verb = match.group('actor', 'verb')
        event_type = _TYPE[verb.lower()]
        cue = (match.group('cue') or '').lower()
        status = ('CANCELLED' if event_type == 'CANCELLATION_OR_DELAY' else
                  'PLANNED' if cue in {'dự kiến', 'sẽ'} else
                  'OCCURRED' if cue == 'đã' else 'UNCONFIRMED')
        candidates.append({
            'event_type': event_type, 'status': status,
            'subject': {'name': actor, 'symbol': _SYMBOL.get(actor.casefold()),
                        'role': _ROLE[event_type]},
            'participants': [], 'object': match.group('object').strip(),
            'source_span': match.group(0), 'event_time': None,
            'event_time_precision': 'unknown', 'announced_at': None,
        })
    return candidates


def _key(value: str) -> str:
    value = unicodedata.normalize('NFKC', value).casefold()
    return ' '.join(re.findall(r'\w+', value, re.UNICODE))


def _date_in_span(value: str, precision: str, span: str) -> bool:
    """Allow ISO date claims only when a matching date occurs in cited text."""
    if precision == 'day' and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        year, month, day = value.split('-')
        return bool(re.search(rf'(?<!\d){int(day):02d}[/-]{int(month):02d}[/-]{year}(?!\d)|'
                              rf'(?<!\d){int(day)}[/-]{int(month)}[/-]{year}(?!\d)|'
                              rf'(?<!\d){day}\s+tháng\s+{int(month)}\s+năm\s+{year}(?!\d)', span, re.I))
    if precision == 'month' and re.fullmatch(r'\d{4}-\d{2}', value):
        year, month = value.split('-')
        return bool(re.search(rf'(?<!\d)tháng\s+0?{int(month)}[/-](?:năm\s+)?{year}(?!\d)|'
                              rf'(?<!\d)tháng\s+0?{int(month)}\s+năm\s+{year}(?!\d)|'
                              rf'(?<!\d){int(month):02d}/{year}(?!\d)', span, re.I))
    if precision == 'year' and re.fullmatch(r'\d{4}', value):
        return bool(re.search(rf'(?<!\d){value}(?!\d)', span))
    return precision == 'range' and bool(value) and value in span


def manifest_news_ids(manifest: dict) -> dict[str, str]:
    """Return article_id -> document_id, using frozen chunk locators only."""
    payload = manifest.get('manifest', manifest)
    if 'manifest_sha256' in manifest:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               separators=(',', ':'), allow_nan=False).encode('utf-8')
        if hashlib.sha256(canonical).hexdigest() != manifest['manifest_sha256']:
            raise ValueError('Manifest hash mismatch')
    result: dict[str, str] = {}
    for doc in payload['documents']:
        if doc.get('doc_type') != 'NEWS':
            continue
        ids = {str(c['locator']['source_id']) for c in doc['chunks']
               if c['locator'].get('source_table') == 'news_articles'}
        if len(ids) != 1:
            raise ValueError(f"Ambiguous NEWS locators: {doc['document_id']}")
        article_id = ids.pop()
        if article_id in result:
            raise ValueError(f'Duplicate NEWS article: {article_id}')
        result[article_id] = str(doc['document_id'])
    return result


def validate_candidate(article: dict, candidate: dict) -> tuple[dict | None, str | None]:
    """Accept only claims directly grounded in the saved article body."""
    body = article.get('content') or ''
    span = candidate.get('source_span') or ''
    subject = candidate.get('subject') or {}
    object_ = candidate.get('object') or ''
    if not body or not span or span not in body:
        return None, 'source_span_not_in_body'
    if candidate.get('event_type') not in EVENT_TYPES:
        return None, 'invalid_event_type'
    if candidate.get('status') not in STATUSES:
        return None, 'invalid_status'
    if not subject.get('name') or not subject.get('role') or not object_:
        return None, 'missing_actor_role_or_object'
    if _key(subject['name']) not in _key(span) or _key(object_) not in _key(span):
        return None, 'actor_or_object_not_in_span'
    for participant in candidate.get('participants', []):
        if not participant.get('name') or not participant.get('role') or _key(participant['name']) not in _key(span):
            return None, 'participant_not_in_span'
    precision = candidate.get('event_time_precision', 'unknown')
    event_time = candidate.get('event_time')
    if precision not in PRECISIONS or bool(event_time) == (precision == 'unknown'):
        return None, 'invalid_event_time_precision'
    time_span = candidate.get('event_time_source_span')
    if event_time and (not time_span or time_span not in body or
                       not _date_in_span(str(event_time), precision, time_span)):
        return None, 'event_time_without_evidence'
    announced = candidate.get('announced_at')
    announced_span = candidate.get('announced_at_source_span')
    if announced and (not announced_span or announced_span not in body or
                      not _date_in_span(str(announced), 'day', announced_span)):
        return None, 'announced_at_without_evidence'
    if (candidate.get('status') == 'OCCURRED' and
            candidate.get('event_type') not in {'DISCLOSURE', 'APPROVAL'} and
            re.search(r'\b(dự kiến|có thể|đề xuất|sẽ|dự báo)\b', span, re.I)):
        return None, 'planned_wording_claimed_occurred'
    if candidate.get('status') == 'CANCELLED' and not re.search(r'\b(hủy|huỷ|hoãn|dừng)\b', span, re.I):
        return None, 'cancellation_without_evidence'
    accepted = {k: candidate.get(k) for k in (
        'event_type', 'status', 'subject', 'participants', 'object', 'event_time',
        'announced_at', 'event_time_precision')}
    accepted['participants'] = accepted['participants'] or []
    accepted['event_time_precision'] = precision
    accepted['event_time'] = event_time
    accepted['published_at'] = article.get('published_at')
    accepted['evidence'] = {
        'article_id': str(article['article_id']), 'source': article.get('source'),
        'url': article.get('url'), 'source_span': span,
        'event_time_source_span': time_span,
        'announced_at_source_span': announced_span,
    }
    accepted['claims'] = candidate.get('claims') or {}
    accepted['event_ref'] = candidate.get('event_ref')
    return accepted, None


def extract_batch(manifest: dict, articles: Iterable[dict],
                  propose: Callable[[dict], Iterable[dict]], *, max_articles: int = 100) -> dict:
    """Process an explicit bounded article batch. Never fetches or writes data."""
    members = manifest_news_ids(manifest)
    rows = list(articles)
    if not 1 <= len(rows) <= max_articles:
        raise ValueError(f'Batch must contain 1..{max_articles} articles')
    if len({str(row['article_id']) for row in rows}) != len(rows):
        raise ValueError('Duplicate article_id in batch')
    if any(str(row['article_id']) not in members for row in rows):
        raise ValueError('Article outside frozen NEWS manifest')
    accepted = []
    per_article = []
    for article in rows:
        article_id = str(article['article_id'])
        review = []
        count = 0
        for candidate in propose(article):
            item, reason = validate_candidate(article, candidate)
            if reason:
                review.append({'reason': reason, 'candidate': candidate})
            else:
                item['document_id'] = members[article_id]
                accepted.append(item)
                count += 1
        per_article.append({'article_id': article_id, 'document_id': members[article_id],
                            'status': 'REVIEW' if review else ('EVENT' if count else 'NO_EVENT'),
                            'event_count': count, 'review': review})
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for item in accepted:
        subject = item['subject']
        # event_ref is an externally reviewed identity for updates with changed details.
        identity = item['event_ref'] or (_key(item['object']), item['event_time'])
        groups[(_key(subject.get('symbol') or subject['name']), item['event_type'],
                json.dumps(identity, ensure_ascii=False, sort_keys=True))].append(item)
    events = []
    for key, claims in sorted(groups.items()):
        event_id = str(uuid.uuid5(NAMESPACE, json.dumps(key, ensure_ascii=False)))
        variants = [{k: claim[k] for k in ('status', 'object', 'event_time',
                    'event_time_precision', 'claims', 'evidence', 'published_at', 'announced_at')}
                    for claim in claims]
        events.append({'event_group_id': event_id, 'event_type': claims[0]['event_type'],
                       'subject': claims[0]['subject'], 'participants': claims[0]['participants'],
                       'status': claims[0]['status'] if len({c['status'] for c in claims}) == 1 else 'CONFLICT',
                       'source_claims': variants, 'document_ids': sorted({c['document_id'] for c in claims})})
    return {'schema_version': 'news-events-batch-v1', 'corpus_version_id': manifest.get('corpus_version_id'),
            'article_results': per_article, 'events': events}
