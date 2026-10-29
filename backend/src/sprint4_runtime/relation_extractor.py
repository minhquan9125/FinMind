"""Conservative BCTN company-relation candidates for the WBS02 contract.

The resolver owns entity identity. This module only recognizes explicit wording in
one sentence and never changes a review state to APPROVED.
"""

import hashlib
import json
import re
from copy import deepcopy
from datetime import date

from .contracts import validate_envelope
from .entities import normalize, text_view


_OWN = re.compile(r"\b(?:sở hữu|nắm giữ)\b", re.I)
_SUB = re.compile(r"\b(?:công ty con|đơn vị trực thuộc)\b", re.I)
_ASSOC = re.compile(r"\b(?:công ty liên kết|doanh nghiệp liên kết)\b", re.I)
_COOP = re.compile(r"\b(?:hợp tác|liên doanh|ký (?:kết )?(?:thỏa thuận|thoả thuận|hợp đồng hợp tác))\b", re.I)
_NEGATE = re.compile(r"\b(?:không|chưa|chẳng|bác bỏ|phủ nhận)\b", re.I)
_PLANNED = re.compile(r"\b(?:dự kiến|dự định|có kế hoạch|sẽ|đề xuất|đang đàm phán)\b", re.I)
_CONDITIONAL = re.compile(r"\b(?:nếu|trong trường hợp|tùy thuộc|tuỳ thuộc)\b", re.I)
_HISTORICAL = re.compile(r"\b(?:từng|trước đây|đã thoái vốn|không còn|chấm dứt)\b", re.I)
_PERCENT = re.compile(r"(?<!\d)(\d{1,3}(?:[.,]\d{1,3})?)\s*%")
_ISO_DAY = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_VN_DAY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b")
_BREAK = re.compile(r"(?<!\d)[.!?;](?!\d)|\n")
_ISSUER_SUBSIDIARY = re.compile(
    r"\b(?:các\s+)?công ty con\s*(?:kiểm soát\s+(?:trực tiếp|gián tiếp)\s*)?(?::|là|gồm)?\s*",
    re.I)
_GENERIC_COMPANY_NAMES = {
    'công ty cổ phần', 'công ty cp', 'công ty tnhh',
    'công ty trách nhiệm hữu hạn', 'ngân hàng thương mại cổ phần',
}


def _sentences(text):
    start = 0
    for marker in _BREAK.finditer(text):
        end = marker.end()
        if text[start:end].strip():
            yield start, end, text[start:end]
        start = end
    if text[start:].strip():
        yield start, len(text), text[start:]


def _day(text):
    iso = _ISO_DAY.search(text)
    vn = _VN_DAY.search(text)
    try:
        if iso:
            return date.fromisoformat(iso.group(1)).isoformat()
        if vn:
            return date(int(vn.group(3)), int(vn.group(2)), int(vn.group(1))).isoformat()
    except ValueError:
        pass
    return None


def _recognize(sentence, first, second):
    """Return (type, subject, object, attributes) only for an explicit cue."""
    between = sentence[first['end']:second['start']]
    after = sentence[second['end']:]
    if _COOP.search(between) or (re.fullmatch(r"\s*(?:và|,)\s*", between, re.I)
                                 and _COOP.search(after[:100])):
        ids = sorted((first['entity_id'], second['entity_id']))
        scope = re.sub(r"^\s*(?:đã\s+)?(?:ký\s+)?(?:thỏa thuận\s+|thoả thuận\s+)?hợp tác\s*(?:với\s+)?",
                       '', after, flags=re.I).strip(' .,:;')
        return 'COOPERATES_WITH', *ids, ({'cooperation_scope': scope[:200]} if scope else {})
    if _SUB.search(between):
        if re.search(r"(?:\blà\b|\btrở thành\b).{0,25}công ty con\s+của\s*$", between, re.I):
            return 'HAS_SUBSIDIARY', second['entity_id'], first['entity_id'], {}
        if re.search(r"(?:\bcó\b|\bsở hữu\b).{0,25}công ty con\s+(?:là\s*)?$", between, re.I):
            return 'HAS_SUBSIDIARY', first['entity_id'], second['entity_id'], {}
    if _ASSOC.search(between):
        if re.search(r"(?:\blà\b|\btrở thành\b).{0,25}(?:công ty|doanh nghiệp) liên kết\s+của\s*$", between, re.I):
            return 'HAS_ASSOCIATE', second['entity_id'], first['entity_id'], {}
        if re.search(r"\bcó\b.{0,25}(?:công ty|doanh nghiệp) liên kết\s+(?:là\s*)?$", between, re.I):
            return 'HAS_ASSOCIATE', first['entity_id'], second['entity_id'], {}
    if _OWN.search(between) and len(between) <= 100 and not _SUB.search(between) and not _ASSOC.search(between):
        if re.search(r"\bnắm giữ\b", between, re.I) and not re.search(r"(?:%|cổ phần|cổ phiếu|vốn|quyền sở hữu)", between + after[:50], re.I):
            return None
        if re.search(r"\bsở hữu\s+(?:công nghệ|sản phẩm|thương hiệu|lợi thế|vị thế|năng lực|giải pháp)\b", between, re.I):
            return None
        attributes = {}
        matches = _PERCENT.findall(between + after[:80])
        if len(matches) == 1:
            value = matches[0].replace(',', '.')
            if float(value) <= 100:
                attributes['ownership_percent'] = str(float(value)).rstrip('0').rstrip('.') if '.' in value else value
        if re.search(r"\bgián tiếp\b", between, re.I):
            attributes['holding_basis'] = 'indirect'
        elif re.search(r"\btrực tiếp\b", between, re.I):
            attributes['holding_basis'] = 'direct'
        return 'OWNS_SHARES', first['entity_id'], second['entity_id'], attributes
    return None


def _issuer_entity(document, registry):
    """Use the DB company binding only when it exactly matches one verified registry row."""
    if document.get('doc_type') != 'ANNUAL_REPORT':
        return None
    symbol, name = document.get('issuer_symbol'), document.get('issuer_company_name')
    if not symbol or not name or not document.get('issuer_company_id'):
        return None
    if not re.match(r'^\s*' + re.escape(symbol) + r'\s*[—–-]', document.get('title', ''), re.I):
        return None
    key = text_view(name)[0].strip()
    matches = [row for row in registry if row['entity_type'] == 'Company' and row['verified']
               and row.get('identity_key') and any(text_view(alias)[0].strip() == key
               for alias in [row['canonical_name']] + row['aliases'])]
    if len(matches) != 1:
        return None
    row = matches[0]
    if text_view(row['canonical_name'])[0].strip() in _GENERIC_COMPANY_NAMES:
        return None
    return {'entity_id': row['entity_id'], 'entity_type': 'Company',
            'canonical_name': row['canonical_name'], 'aliases': [name],
            'resolution_status': 'resolved', 'identity_key': row['identity_key'], 'attributes': {}}


def extract_candidates(envelope, registry):
    """Resolve names and add PENDING candidate relations to a 2.1.0 envelope.

    All input documents/chunks must already be verified. Ambiguous, negated,
    planned and historical sentences are skipped rather than asserted as facts.
    """
    result = deepcopy(envelope)
    if result['relations'] or result['entities'] or result['mentions']:
        raise ValueError('Expected document/chunk-only input')
    relevant_chunks = [chunk for chunk in result['chunks']
                       if any(pattern.search(chunk['text']) for pattern in (_OWN, _SUB, _ASSOC, _COOP))]
    resolved = normalize(relevant_chunks, registry=registry)
    result.update(resolved)
    entities = {e['entity_id']: e for e in result['entities']}
    def complete_company(entity_id):
        entity = entities[entity_id]
        return (entity['resolution_status'] == 'resolved'
                and entity['canonical_name'] is not None
                and text_view(entity['canonical_name'])[0].strip() not in _GENERIC_COMPANY_NAMES)
    def reviewable_company(mention):
        entity = entities[mention['entity_id']]
        name = mention['raw_name'].strip()
        return (entity['resolution_status'] == 'unresolved'
                and 4 <= len(name.split()) <= 14 and len(name) <= 100
                and re.match(r'^(?:Công ty|CTCP|Tổng Công ty|Ngân hàng)\b', name, re.I) is not None
                and text_view(name)[0].strip() not in _GENERIC_COMPANY_NAMES
                and not re.search(r'[.;]|\s(?:và|&)\s', name, re.I))
    def credible_mention(mention):
        name = mention['raw_name'].strip()
        if not complete_company(mention['entity_id']):
            return False
        if re.match(r'^(?:Công ty|CTCP|Tổng Công ty|Tập đoàn|Ngân hàng)\b', name, re.I):
            return len(name.split()) >= 4
        if len(name.split()) == 1:
            return (name.isupper() and name.isalpha() and 2 <= len(name) <= 5) or (len(name) >= 5 and name[0].isupper())
        return name[0].isupper() and not name.islower()
    issuers = {}
    for document in result['documents']:
        issuer = _issuer_entity(document, registry)
        if issuer:
            issuers[document['document_id']] = issuer['entity_id']
            if issuer['entity_id'] not in entities:
                entities[issuer['entity_id']] = issuer
                result['entities'].append(issuer)
    by_chunk = {}
    for mention in result['mentions']:
        if entities[mention['entity_id']]['entity_type'] == 'Company':
            by_chunk.setdefault((mention['document_id'], mention['chunk_id']), []).append(mention)
    relations = {}
    def record(kind, subject, target, attributes, temporal, evidence):
        key = (kind, subject, target, json.dumps(attributes, ensure_ascii=False, sort_keys=True),
               json.dumps(temporal, sort_keys=True))
        if key in relations:
            if evidence not in relations[key]['evidence']:
                relations[key]['evidence'].append(evidence)
            return
        digest = hashlib.sha256(json.dumps(key, ensure_ascii=False).encode('utf-8')).hexdigest()[:32]
        relations[key] = {'relation_id': 'rel:' + digest, 'relation_type': kind,
                          'subject_id': subject, 'object_id': target, 'attributes': attributes,
                          'temporal': temporal, 'evidence': [evidence],
                          'review': {'status': 'PENDING', 'reviewer': None, 'reviewed_at': None}}

    for chunk in result['chunks']:
        mentions = by_chunk.get((chunk['document_id'], chunk['chunk_id']), [])
        for start, end, sentence in _sentences(chunk['text']):
            quote = sentence.strip()
            if not quote or any(p.search(quote) for p in (_NEGATE, _PLANNED, _CONDITIONAL, _HISTORICAL)):
                continue
            present = sorted((m for m in mentions if start <= m['start'] < m['end'] <= end),
                             key=lambda m: (m['start'], -m['end']))
            # Only two non-overlapping, resolved legal persons in a sentence.
            selected = []
            for mention in present:
                if selected and mention['start'] < selected[-1]['end']:
                    continue
                selected.append(mention)
            if len(selected) != 2 or selected[0]['entity_id'] == selected[1]['entity_id']:
                continue
            if any(not credible_mention(m) for m in selected):
                continue
            local = [dict(m, start=m['start'] - start, end=m['end'] - start) for m in selected]
            recognized = _recognize(sentence, *local)
            if not recognized:
                continue
            kind, subject, target, attributes = recognized
            # A report year alone does not prove the relation's effective date.
            temporal = {'as_of': _day(quote), 'valid_from': None, 'valid_to': None}
            evidence = {'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'], 'quote': quote}
            record(kind, subject, target, attributes, temporal, evidence)
        issuer_id = issuers.get(chunk['document_id'])
        if not issuer_id:
            continue
        for cue in _ISSUER_SUBSIDIARY.finditer(chunk['text']):
            # The child must immediately follow an explicit subsidiary heading.
            following = sorted((m for m in mentions if cue.end() <= m['start'] <= cue.end() + 12),
                               key=lambda m: (m['start'], -m['end']))
            if not following or chunk['text'][cue.end():following[0]['start']].strip():
                continue
            child = next((m for m in following if credible_mention(m)), None)
            if child is None:
                child = next((m for m in following if reviewable_company(m)), None)
            if child is None or child['entity_id'] == issuer_id:
                continue
            quote = chunk['text'][cue.start():child['end']]
            if any(p.search(quote) for p in (_NEGATE, _PLANNED, _CONDITIONAL, _HISTORICAL)):
                continue
            evidence = {'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'], 'quote': quote}
            record('HAS_SUBSIDIARY', issuer_id, child['entity_id'],
                   {'inference_basis': 'document_issuer'},
                   {'as_of': None, 'valid_from': None, 'valid_to': None}, evidence)
    result['relations'] = sorted(relations.values(), key=lambda r: r['relation_id'])
    return validate_envelope(result)
