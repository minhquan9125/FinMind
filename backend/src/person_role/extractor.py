"""Conservative relation rules over contract-validated WBS02 mentions.

Ambiguous tables and unsupported events are returned in a separate audit report.
Source text, entity IDs and review decisions are never silently rewritten.
"""
from copy import deepcopy
from datetime import date
import hashlib
import json
import re

from .contract.contracts import validate_envelope

GENERIC_ORG_ALIASES = {'hđqt', 'hội đồng quản trị', 'bks', 'ban kiểm soát',
                       'bđh', 'ban điều hành', 'tgđ', 'tổng giám đốc', 'chủ tịch hđqt'}


def scoped_registry(registry):
    """Remove role-only Company aliases in a working copy, never edit upstream.

    A verified registry row does not make an ambiguous heading such as HĐQT a
    unique company name. Canonical identities are otherwise left unchanged.
    """
    if registry is None:
        return None, []
    working=deepcopy(registry)
    removed=[]
    for row in working:
        if row.get('entity_type') != 'Company':
            continue
        for field in ('aliases','ticker_aliases'):
            if field not in row:
                continue
            kept=[]
            for alias in row[field]:
                if ' '.join(alias.casefold().split()) in GENERIC_ORG_ALIASES:
                    removed.append(dict(entity_id=row['entity_id'],field=field,alias=alias,reason='ROLE_HEADING_IS_NOT_COMPANY_IDENTITY'))
                else:
                    kept.append(alias)
            row[field]=kept
        if ' '.join(row.get('canonical_name','').casefold().split()) in GENERIC_ORG_ALIASES:
            row['verified']=False
    return working, removed

POSITIONS = (
    ('DEPUTY_BOARD_CHAIR', r'phó\s+chủ\s+tịch\s+(?:hđqt|hội đồng quản trị)'),
    ('BOARD_CHAIR', r'chủ\s+tịch\s+(?:hđqt|hội đồng quản trị)'),
    ('BOARD_MEMBER', r'(?:thành\s+viên|tv)\s+(?:hđqt|hội đồng quản trị)'),
    ('DEPUTY_CEO', r'phó\s+tgđ'),
    ('CEO', r'\btgđ\b'),
    ('DEPUTY_CEO', r'phó\s+tổng\s+giám\s+đốc'),
    ('CEO', r'tổng\s+giám\s+đốc'),
    ('CHIEF_ACCOUNTANT', r'kế\s+toán\s+trưởng'),
    ('CFO', r'giám\s+đốc\s+tài\s+chính'),
    ('SUPERVISORY_HEAD', r'trưởng\s+ban\s+kiểm\s+soát'),
    ('SUPERVISORY_MEMBER', r'(?:thành\s+viên|tv)\s+(?:bks|ban kiểm soát)'),
)
ROLE = re.compile('|'.join(f'(?P<R{i}>{p})' for i, (_, p) in enumerate(POSITIONS)), re.I)
DATE = re.compile(r'(?:kể\s+)?từ\s+(?:ngày\s+)?(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b', re.I)


def extract(envelope):
    """Return (contract envelope, audit); requires real entity/mention input.

    Missing context causes abstention, not nearest-name guessing. Every emitted
    candidate remains PENDING, even if the source sentence is unambiguous.
    """
    validate_envelope(envelope)
    result = deepcopy(envelope)
    if result['relations']:
        raise ValueError('Extraction requires empty relations; preserve reviewed results separately')
    entities = {e['entity_id']: e for e in result['entities']}
    diagnostics, candidates = [], {}
    for chunk in result['chunks']:
        key = (chunk['document_id'], chunk['chunk_id'])
        mentions = [m for m in result['mentions'] if (m['document_id'], m['chunk_id']) == key]
        # Repeated source header is provenance, not evidence that every person
        # in the body works for that company.
        body_start = chunk['locator'].get('text_start', 0)
        text = chunk['text']
        for part in re.finditer(r'[^;\n]+', text[body_start:]):
            start, end = body_start + part.start(), body_start + part.end()
            quote = text[start:end]
            roles = list(ROLE.finditer(quote))
            if not roles:
                continue
            local = [m for m in mentions if start <= m['start'] < m['end'] <= end]
            people = {m['entity_id'] for m in local if entities[m['entity_id']]['entity_type'] == 'Person'}
            companies = {m['entity_id'] for m in local if entities[m['entity_id']]['entity_type'] == 'Company'}
            reason = None
            low = quote.casefold()
            if re.search(r'xin\s+từ\s+nhiệm|đơn\s+(?:xin\s+)?từ\s+nhiệm|đề\s+cử|ứng\s+cử|đề\s+nghị|dự\s+kiến|nếu\b|sẽ\b|chưa\b|không\b', low):
                reason = 'UNCONFIRMED_OR_NEGATED'
            elif re.search(r'từ\s+nhiệm', low):
                reason = 'RESIGNATION_REQUIRES_EVENT_CONTRACT'
            elif len(people) != 1 or len(companies) != 1 or len(roles) != 1:
                reason = 'AMBIGUOUS_PERSON_COMPANY_OR_POSITION'
            # Detect a mention swallowed a title due to OCR/NER boundaries.
            elif any(m['start'] < start + roles[0].end() and m['end'] > start + roles[0].start() for m in local if entities[m['entity_id']]['entity_type'] == 'Person'):
                reason = 'PERSON_POSITION_SPAN_OVERLAP'
            appointed = bool(re.search(r'bổ\s+nhiệm', low))
            dismissed = bool(re.search(r'miễn\s+nhiệm|bãi\s+nhiệm', low))
            held = bool(re.search(r'giữ\s+chức|đảm\s+nhiệm|\blà\b', low))
            if not reason and (appointed and dismissed):
                reason = 'MULTIPLE_EVENTS'
            if not reason and not (appointed or dismissed or held):
                reason = 'NO_EXPLICIT_ROLE_ASSERTION'
            dates = list(DATE.finditer(quote))
            effective = None
            if not reason and len(dates) > 1:
                reason = 'AMBIGUOUS_EFFECTIVE_DATE'
            if dates and not reason:
                try:
                    d, m, y = map(int, dates[0].groups())
                    effective = date(y, m, d).isoformat()
                except ValueError:
                    reason = 'INVALID_EFFECTIVE_DATE'
            if reason:
                diagnostics.append(dict(document_id=key[0], chunk_id=key[1], start=start, end=end, quote=quote, reason=reason))
                continue
            person, company = next(iter(people)), next(iter(companies))
            kind = 'APPOINTS' if appointed else 'DISMISSES' if dismissed else 'HOLDS_ROLE'
            subject, target = (person, company) if kind == 'HOLDS_ROLE' else (company, person)
            role = roles[0]
            identity = [result['corpus_id'], result['dataset_version'], *key, start, end, kind, subject, target, role.group()]
            rid = 'rel:' + hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
            candidates[rid] = dict(
                relation_id=rid, relation_type=kind, subject_id=subject, object_id=target,
                attributes=dict(position=role.group(), position_code=POSITIONS[int(role.lastgroup[1:])][0],
                    assertion_status='UNCERTAIN', event_stage='APPOINTED' if appointed else 'DISMISSED' if dismissed else 'ROLE_AT_SOURCE_TIME',
                    evidence_start=start, evidence_end=end, locator=deepcopy(chunk['locator']),
                    person_mention_ids=sorted(m['mention_id'] for m in local if m['entity_id'] == person),
                    company_mention_ids=sorted(m['mention_id'] for m in local if m['entity_id'] == company),
                    effective_date_proposed=effective, requires_human_review=True),
                # A source-date candidate does not establish the full interval.
                temporal=dict(as_of=None, valid_from=None, valid_to=None),
                evidence=[dict(document_id=key[0], chunk_id=key[1], quote=quote)],
                review=dict(status='PENDING', reviewer=None, reviewed_at=None))
    result['relations'] = [candidates[k] for k in sorted(candidates)]
    validate_envelope(result)
    return result, dict(candidate_count=len(candidates), abstentions=diagnostics,
                        source_verification='CONTRACT_AND_CHUNK_HASH_ONLY_NOT_LIVE_REPLAY')


def normalize_and_extract(envelope, registry=None, proposals=None):
    """Use the supplied WBS02 resolver without inventing canonical IDs."""
    from .contract.entities import normalize
    validate_envelope(envelope)
    if any(envelope[k] for k in ('entities', 'mentions', 'relations')):
        raise ValueError('Normalization requires empty entities/mentions/relations')
    normalized = deepcopy(envelope)
    safe_registry, removed=scoped_registry(registry)
    normalized.update(normalize(normalized['chunks'], safe_registry, proposals))
    result,audit=extract(normalized)
    audit['registry_aliases_excluded']=removed
    return result,audit
