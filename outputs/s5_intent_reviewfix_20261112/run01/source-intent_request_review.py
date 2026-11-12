"""Offline successor to frozen V3: acronym-safe spans and role paraphrases.

Preserves old artifacts/source bytes. It does not enable router integration,
invent a confidence score, or decide the pending report/numeric boundary.
"""
import re

from .intent_composition import _plain, requests as legacy_requests
from .intent_request_consensus import resolve
from .intent_request_objectives import explicit_intent as legacy_explicit_intent


def _protect_ai(text, marker):
    def replace(match):
        before, after = _plain(text[:match.start()]), _plain(text[match.end():])
        # Preserve interrogative AI in all-caps questions; protect the technical
        # acronym elsewhere before the legacy predicate folds case/diacritics.
        who = re.search(r'\bla\s*$', before) or (
            not before.strip() and re.match(r'\s+(?:dang\s+)?(?:la|giu chuc|dam nhiem|duoc bo nhiem)\b', after))
        return match.group() if who else marker
    return re.sub(r'\bAI\b', replace, text)


def requests(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('INVALID_QUESTION')
    marker = '__TECH_TERM__'
    while marker in text:
        marker += '_'
    protected = _protect_ai(text, marker)
    # Elliptical list item: "doanh thu cloud và AI của X ... bao nhiêu".
    # The shared numeric question at the end does not give the AI noun its own
    # predicate. Preserve this conjunction; independent "AI được ..." questions
    # and "và tìm ..." requests still use the ordinary segmentation path.
    joins = {}
    def keep_list(match):
        key = marker + '_JOIN_' + str(len(joins))
        joins[key] = match.group()
        return key
    protected = re.sub(r'\s+(?:và|va)\s+(?=' + re.escape(marker) + r'\s+(?:của|cua)\b)',
                       keep_list, protected, flags=re.IGNORECASE)
    # Restore the exact original acronym; no masking enters the embedding text.
    result = legacy_requests(protected)
    for i, part in enumerate(result):
        for key, value in joins.items():
            part = part.replace(key, value)
        result[i] = part.replace(marker, 'AI')
    return result


def explicit_intent(text):
    plain = _plain(_protect_ai(text, '__TECH_TERM__'))
    if re.search(r'\b(bai tin|bai bao|ban tin|tin tuc|thong bao|trich nguyen van|chep nguyen van)\b', plain):
        return None
    previous = legacy_explicit_intent(text)
    if previous is not None:
        return previous
    title = r'(?:chu tich(?:\s+(?:hdqt|hoi dong quan tri))?|tong giam doc|giam doc|ke toan truong|ceo|cfo|tgd|ktt)'
    role = (
        re.search(r'\b' + title + r'\b.{0,100}\bla ai\b', plain)
        or re.search(r'\bai\b.{0,60}\bla\s+' + title + r'\b', plain)
        or re.search(r'\b(?:giu|dam nhiem)\s+chuc(?:\s+(?:vu|danh))?\s+(?:gi|nao)\b', plain)
        or re.search(r'\bwho\s+is\s+(?:the\s+)?(?:ceo|cfo|chairman|chairperson)\b', plain)
    )
    return 'PERSON_ROLE' if role else None


def resolve_objectives(base, parts, labels, texts):
    decision = resolve(base, parts, labels)
    explicit = [explicit_intent(text) for text in texts]
    known = {label for label in explicit if label is not None}
    if len(known) >= 2:
        decision.update(intent_label='MIXED', reason='TWO_EXPLICIT_REQUEST_TYPES', component_labels=sorted(known))
    elif known and all(label is not None for label in explicit):
        decision.update(intent_label=next(iter(known)), reason='EXPLICIT_REQUEST_TYPE', component_labels=[])
    decision.update(ranking_policy='intent-request-objectives-v2',
                    explicit_evidence=[dict(text=text, intent_label=label)
                                       for text, label in zip(texts, explicit) if label])
    return decision
