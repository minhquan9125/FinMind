"""Offline financial-value guard; scope validation stays a separate concern."""
import re

from .intent_composition import _plain
from .intent_request_review import (
    _protect_ai,
    explicit_intent as previous_explicit_intent,
    requests,
    resolve_objectives as previous_resolution,
)

FINANCIAL_METRIC = re.compile(
    r'\b(?:doanh thu|loi nhuan|lnst|lntt|eps|roe|roa|tong tai san|von chu so huu|vcsh|'
    r'dong tien|luu chuyen tien|co tuc|gia co phieu|bien loi nhuan|luong|tong no|no phai tra|ty le no)\b'
)
VALUE_REQUEST = re.compile(r'\b(?:bao nhieu|bang may|gia tri|so lieu|cho biet|lay|doc)\b')
OTHER_OBJECTIVE = re.compile(
    r'\b(?:tom tat|tom luoc|giai thich|mo ta|trinh bay|phan tich|danh gia|nhan dinh|'
    r'xu huong|chieu huong|kha thi|ben vung|vi sao|tai sao|du doan|uoc tinh|du bao|'
    r'trich nguyen van|chep nguyen van|ngay nao|khi nao|thoi diem nao|nam nao|ngay hieu luc|la gi|'
    r'noi dung|chinh sach|chien luoc|khai niem|y nghia)\b'
)


def financial_value_request(text):
    plain = _plain(_protect_ai(text, '__TECH_TERM__'))
    if not FINANCIAL_METRIC.search(plain) or not VALUE_REQUEST.search(plain):
        return False
    if OTHER_OBJECTIVE.search(plain):
        return False
    if re.search(r'\b(?:ke hoach|muc tieu)\b', plain) and not re.search(r'\b(?:bao nhieu|gia tri|so lieu)\b', plain):
        return False
    # Counts, ownership and person/entity questions do not become financial
    # requests merely because the surrounding description mentions revenue.
    if re.search(r'\bbao nhieu\s+(?:cong ty|doanh nghiep|doi tac|co dong|bai|tin|nguoi)\b', plain):
        return False
    if re.search(r'\b(?:ty le so huu|phan tram co phan|nguoi nao|don vi nao|cong ty nao|doanh nghiep nao|ai)\b', plain):
        return False
    if re.search(r'\b(?:tim|liet ke|trich|doi chieu)\b.{0,45}\b(?:bai tin|bai bao|ban tin|thong bao|tin tuc)\b', plain):
        return False
    return True


def explicit_intent(text):
    previous = previous_explicit_intent(text)
    if previous is not None:
        return previous
    return 'NUMERIC' if financial_value_request(text) else None


def resolve_objectives(base, parts, labels, texts):
    decision = previous_resolution(base, parts, labels, texts)
    explicit = [explicit_intent(text) for text in texts]
    known = {label for label in explicit if label is not None}
    if 'NUMERIC' in known:
        if len(known) >= 2:
            decision.update(intent_label='MIXED', reason='TWO_EXPLICIT_REQUEST_TYPES', component_labels=sorted(known))
        elif all(label is not None for label in explicit):
            decision.update(intent_label='NUMERIC', reason='EXPLICIT_FINANCIAL_VALUE_REQUEST', component_labels=[])
    decision.update(ranking_policy='intent-request-objectives-v3',
                    explicit_evidence=[dict(text=text, intent_label=label)
                                       for text, label in zip(texts, explicit) if label])
    return decision
