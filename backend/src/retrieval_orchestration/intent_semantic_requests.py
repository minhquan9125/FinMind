"""Offline goal evidence with spelling-sensitive tokens; never executes a route."""
import re
import unicodedata

from .intent_composition import _plain, _request
from .intent_request_consensus import resolve
from .intent_request_review import _protect_ai, requests as base_requests
from .intent_news_requests import explicit_intent as previous_explicit, ACTION, CONNECTOR
from .intent_numeric_requests import FINANCIAL_METRIC, VALUE_REQUEST, financial_value_request as previous_numeric


def _surface(text):
    return unicodedata.normalize('NFC', _protect_ai(text, '__TECH_TERM__')).casefold().strip()


def _read_imperative(text):
    return re.match(r'^(?:(?:hãy|hay|vui lòng|vui long|xin)\s+)?(?:đọc|doc)\b', _surface(text))


def _financial_metric(text):
    surface = _surface(text)
    plain = _plain(surface)
    # A folded match is insufficient for ambiguous words. In accented input,
    # require the actual salary spelling; ASCII aliases remain supported.
    metrics = [match.group() for match in FINANCIAL_METRIC.finditer(plain)]
    salary = re.search(r'\blương\b', surface) or re.search(
        r'\b(?:tien luong|luong (?:ceo|cfo|tgd|thuong|nhan vien|can bo|ban lanh dao))\b', plain)
    return bool(any(metric != 'luong' for metric in metrics) or salary)


def financial_value_request(text):
    if not previous_numeric(text) or not _financial_metric(text):
        return False
    surface = _surface(text)
    plain = _plain(surface)
    # "doc" means a read request only as an imperative, not inside a predicate
    # such as "co doc lap". Use original spelling before accent folding.
    read = _read_imperative(text)
    if read:
        object_text = _plain(surface[read.end():].strip())
        object_text = re.sub(r'^(?:cho toi|giup toi)\s+', '', object_text)
        read = FINANCIAL_METRIC.match(object_text) or re.match(r'^(?:bao cao|bctc|bctn|gia tri|so lieu|chi tieu)\b', object_text)
    other_operation = any(match.group() != 'doc' for match in VALUE_REQUEST.finditer(plain))
    return bool(read or other_operation)


def explicit_intent(text):
    previous = previous_explicit(text)
    if previous is not None and previous != 'NUMERIC':
        return previous
    if financial_value_request(text):
        return 'NUMERIC'
    plain = _plain(_surface(text))
    if re.search(r'\b(?:bai tin|bai bao|ban tin|tin tuc|thong bao|trich nguyen van|chep nguyen van)\b', plain):
        # Indirect questions explicitly requesting new news are still NEWS.
        return 'NEWS' if re.search(r'\bco tin(?: tuc)? gi moi\b', plain) else None
    if re.search(r'\bco tin gi moi\b', plain):
        return 'NEWS'
    if _read_imperative(text) and re.match(r'^(?:doc|hay doc)\s+(?:noi dung\s+)?(?:bao cao|bctc|bctn)\b', plain):
        return 'REPORT_CONTENT'
    title = r'(?:ceo|cfo|chu tich(?: hdqt)?|tong giam doc|giam doc|tgd|ke toan truong)'
    if (re.search(r'^ai\s+(?:hien\s+)?(?:dang\s+)?(?:lam|giu|dam nhiem)\s+(?:(?:chuc|chuc vu)\s+)?' + title + r'\b', plain)
            or re.search(r'\bnguoi dung dau\b.{0,100}\bla ai\b', plain)):
        return 'PERSON_ROLE'
    # Financial-change analysis fits TREND; attribution to a particular article
    # or report, and other kinds of "why", remain unforced for review.
    if (re.match(r'^(?:hay\s+)?giai thich (?:vi sao|tai sao)\b', plain)
            and _financial_metric(text)
            and re.search(r'\b(?:tang|giam|bien dong|chieu huong)\b', plain)
            and not re.search(r'\b(?:bctc|bctn|bao cao)\b', plain)):
        return 'TREND'
    return None


def requests(text):
    result = []
    for part in base_requests(text):
        tokens = CONNECTOR.split(part)
        current, chunks = tokens[0], []
        for separator, right in zip(CONNECTOR.finditer(part), tokens[1:]):
            left_plain, right_plain = _plain(_surface(current)), _plain(_surface(right))
            left_request = _request(left_plain) or explicit_intent(current) is not None
            right_action = ACTION.match(right_plain) or explicit_intent(right) == 'NEWS'
            if left_request and right_action:
                # A folded "doc" on the right still needs real read evidence.
                if not right_plain.startswith('doc ') or financial_value_request(right):
                    chunks.append(current.strip().rstrip('.'))
                    current = right
                    continue
            current += separator.group() + right
        if chunks:
            result.extend(chunks + [current.strip().rstrip('.')])
        else:
            result.append(part)
    return result


def resolve_objectives(base, parts, labels, texts):
    # Start from classifier/consensus evidence, not the old numeric override;
    # otherwise rejected homographs would survive in the inherited decision.
    decision = resolve(base, parts, labels)
    explicit = [explicit_intent(text) for text in texts]
    known = {label for label in explicit if label is not None}
    if len(known) >= 2:
        decision.update(intent_label='MIXED', reason='TWO_EXPLICIT_REQUEST_TYPES', component_labels=sorted(known))
    elif known and all(label is not None for label in explicit):
        decision.update(intent_label=next(iter(known)), reason='EXPLICIT_REQUEST_TYPE', component_labels=[])
    decision.update(ranking_policy='intent-request-objectives-v5',
                    explicit_evidence=[dict(text=text, intent_label=label) for text, label in zip(texts, explicit) if label],
                    unresolved_requests=[text for text, label in zip(texts, explicit) if label is None])
    return decision
