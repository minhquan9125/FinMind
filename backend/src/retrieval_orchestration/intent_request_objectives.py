"""Narrow taxonomy guards for explicit requests; no entity-specific exceptions."""
import re
from .intent_composition import _plain
from .intent_request_consensus import resolve


def explicit_intent(text):
    plain=_plain(text)
    if re.search(r'\b(bai tin|bai bao|ban tin|tin tuc|thong bao)\b',plain):
        return None
    source=bool(re.search(r'\b(bctn|bctc|bao cao)\b',plain))
    operation=bool(re.search(r'\b(mo ta|giai thich|tom tat|tom luoc|trich|chep|trinh bay)\b',plain))
    topic=bool(re.search(r'\b(chinh sach|chien luoc|ke hoach|cam ket|rui ro|tieu su|dinh huong)\b',plain))
    report=source and operation and topic
    quote=bool(re.search(r'\b(trich nguyen van|chep nguyen van)\b',plain))
    role=(not quote and bool(
        re.search(r'\bai\b.{0,80}\b(giu chuc|dam nhiem|duoc bo nhiem|duoc mien nhiem|la (?:pho )?(?:chu tich|tong giam doc|giam doc|ke toan truong|ktt|tgd))\b',plain)
        or re.search(r'\bchuc (vu|danh)\b.{0,32}\b(nao|gi)\b',plain)
        or (re.search(r'\b(bo nhiem|mien nhiem)\b',plain)
            and re.search(r'\b(ngay nao|khi nao|thoi diem nao|ngay hieu luc)\b',plain))))
    if report and not role: return 'REPORT_CONTENT'
    if role and not report: return 'PERSON_ROLE'
    return None


def resolve_objectives(base,parts,labels,texts):
    decision=resolve(base,parts,labels)
    explicit=[explicit_intent(text) for text in texts]
    known={label for label in explicit if label is not None}
    if len(known)>=2:
        decision.update(intent_label='MIXED',reason='TWO_EXPLICIT_REQUEST_TYPES',component_labels=sorted(known))
    elif known and all(label is not None for label in explicit):
        decision.update(intent_label=next(iter(known)),reason='EXPLICIT_REQUEST_TYPE',component_labels=[])
    decision.update(ranking_policy='intent-request-objectives-v1',
                    explicit_evidence=[dict(text=text,intent_label=label) for text,label in zip(texts,explicit) if label])
    return decision
