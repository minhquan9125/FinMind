"""Offline NEWS objectives and explicit read-value clauses; no score changes."""
import re

from .intent_composition import _plain, _request
from .intent_numeric_requests import (
    explicit_intent as previous_explicit_intent,
    financial_value_request,
    requests as previous_requests,
    resolve_objectives as previous_resolution,
)
from .intent_request_review import _protect_ai

NEWS_OUTPUT = re.compile(
    r'^(?:(?:hay|vui long|xin)\s+)?'
    r'(?:tim|liet ke|tom tat|tom luoc|trich(?: nguyen van)?|chep(?: nguyen van)?|doi chieu|so sanh)\s+'
    r'(?:(?:cho toi|giup toi)\s+)?(?:(?:mot|hai|ba|cac|nhung|2|3)\s+)*'
    r'(?:bai tin|bai bao|ban tin|tin tuc|thong bao)\b'
)
ACTION = re.compile(
    r'^(?:(?:hay|vui long)\s+)?(?:doc|cho biet|lay|tim|liet ke|tom tat|tom luoc|'
    r'trich|chep|giai thich|xac dinh|danh gia|nhan dinh|so sanh|doi chieu|ai)\b'
)
CONNECTOR = re.compile(r'\s+(?:và|va|rồi|roi|đồng thời|dong thoi|sau đó|sau do)\s+|[;\n]+', re.IGNORECASE)


def requests(text):
    original = previous_requests(text)
    result = []
    for part in original:
        tokens = CONNECTOR.split(part)
        current, chunks = tokens[0], []
        # Retain the old parser's decisions except where a read-value clause
        # was missed. Require an action on the right, not just a metric list.
        matches = list(CONNECTOR.finditer(part))
        for separator, right in zip(matches, tokens[1:]):
            left_plain = _plain(_protect_ai(current.strip(), '__TECH_TERM__'))
            right_plain = _plain(_protect_ai(right.strip(), '__TECH_TERM__'))
            read_left = left_plain.startswith('doc ') and financial_value_request(current)
            read_right = right_plain.startswith('doc ') and financial_value_request(right)
            if (read_left or read_right) and (_request(left_plain) or read_left) and ACTION.match(right_plain):
                chunks.append(current.strip().rstrip('.'))
                current = right
            else:
                current += separator.group() + right
        if chunks:
            result.extend(chunks + [current.strip().rstrip('.')])
        else:
            result.append(part)
    return result


def explicit_intent(text):
    plain = _plain(_protect_ai(text.strip(), '__TECH_TERM__'))
    if NEWS_OUTPUT.match(plain):
        return 'NEWS'
    return previous_explicit_intent(text)


def resolve_objectives(base, parts, labels, texts):
    decision = previous_resolution(base, parts, labels, texts)
    explicit = [explicit_intent(text) for text in texts]
    known = {label for label in explicit if label is not None}
    if len(known) >= 2:
        decision.update(intent_label='MIXED', reason='TWO_EXPLICIT_REQUEST_TYPES', component_labels=sorted(known))
    elif known and all(label is not None for label in explicit):
        decision.update(intent_label=next(iter(known)), reason='EXPLICIT_REQUEST_TYPE', component_labels=[])
    decision.update(ranking_policy='intent-request-objectives-v4',
                    explicit_evidence=[dict(text=text, intent_label=label)
                                       for text, label in zip(texts, explicit) if label])
    return decision
