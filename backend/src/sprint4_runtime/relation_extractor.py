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
_SECTION = re.compile(r"^\s*các công ty (con|liên kết)(?:\s+kiểm soát\s+(?:trực tiếp|gián tiếp))?\s*$", re.I)
_LEGAL_LINE = re.compile(r"^(?:Tổng\s+)?Công ty\s+(?:Cổ phần|CP|TNHH|Trách nhiệm hữu hạn)\s+\S", re.I)
_FIELD_LINE = re.compile(r"^(?:Địa chỉ|Điện thoại|Fax|Email|Tỷ lệ|Lĩnh vực|Tên cũ|Vốn|Mã số|Website|Lợi nhuận)\b", re.I)
_SUBSIDIARY_OF = re.compile(
    r"\(\s*là\s+công ty con\s+của\s+(?P<parent>(?:Tổng\s+)?Công ty\s+"
    r"(?:Cổ phần|CP|TNHH|Trách nhiệm hữu hạn)\s+[^)\n]+(?:\n[^)\n]+)?)\)", re.I)
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


def _company_name_spans(chunk):
    """Offer the shared resolver complete legal names broken across two OCR lines."""
    text = chunk['text']
    lines = list(re.finditer(r'[^\n]+', text))
    for index, line in enumerate(lines):
        first = line.group().strip()
        if not _LEGAL_LINE.match(first):
            continue
        start = line.start() + len(line.group()) - len(line.group().lstrip())
        end = line.start() + len(line.group().rstrip())
        if index + 1 < len(lines):
            next_line = lines[index + 1].group().strip()
            # A continuation is short, contains no field label and is not a new legal name.
            if (next_line and len(next_line.split()) <= 8 and len(next_line) <= 80
                    and ':' not in next_line and not _FIELD_LINE.match(next_line)
                    and not _LEGAL_LINE.match(next_line) and not next_line.startswith('(')
                    and not (re.fullmatch(r'[A-Z]{2,5}', next_line) and len(next_line) < 5)):
                end = lines[index + 1].start() + len(lines[index + 1].group().rstrip())
        # Parentheses introduce an explanation such as "(Là công ty con...)".
        # They are not part of the legal name to resolve.
        parenthesis = text.find('(', start, end)
        if parenthesis >= 0:
            end = parenthesis
        while end > start and text[end - 1] in ') ,':
            end -= 1
        while end > start and text[end - 1].isspace():
            end -= 1
        yield start, end


def _best_company_mentions(mentions, start, end, credible, entities):
    """Prefer a verified identity over a longer unresolved OCR span."""
    found = {}
    for mention in mentions:
        if start <= mention['start'] < mention['end'] <= end and credible(mention):
            previous = found.get(mention['start'])
            rank = (entities[mention['entity_id']]['resolution_status'] == 'resolved', mention['end'])
            old_rank = ((entities[previous['entity_id']]['resolution_status'] == 'resolved', previous['end'])
                        if previous else None)
            if old_rank is None or rank > old_rank:
                found[mention['start']] = mention
    return [found[key] for key in sorted(found)]


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
        if re.search(r'\bchủ\s+sở hữu\b', between, re.I) and not re.search(r'\bnắm giữ\b', between, re.I):
            return None
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
    list_pages = {(chunk['document_id'], chunk['locator']['page']) for chunk in result['chunks']
                  if any(_SECTION.match(line) for line in chunk['text'].splitlines())}
    relevant_chunks = [chunk for chunk in result['chunks']
                       if (chunk['document_id'], chunk['locator']['page']) in list_pages
                       or any(pattern.search(chunk['text']) for pattern in (_OWN, _SUB, _ASSOC, _COOP))]
    proposals = [dict(document_id=chunk['document_id'], chunk_id=chunk['chunk_id'],
                      entity_type='Company', start=start, end=end)
                 for chunk in relevant_chunks for start, end in _company_name_spans(chunk)]
    proposals.extend(dict(document_id=chunk['document_id'], chunk_id=chunk['chunk_id'],
                          entity_type='Company', start=match.start('parent'), end=match.end('parent'))
                     for chunk in relevant_chunks for match in _SUBSIDIARY_OF.finditer(chunk['text']))
    resolved = normalize(relevant_chunks, registry=registry, proposals=proposals)
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
    def entry_identity(child, mentions, chunk, issuer_id):
        """Use a verified short alias printed inside a longer OCR heading."""
        if entities[child['entity_id']]['resolution_status'] == 'resolved':
            return child['entity_id'], child['end']
        aliases = [m for m in mentions
                   if child['start'] < m['start'] < m['end'] <= child['end'] + 80
                   and m['entity_id'] != issuer_id
                   and entities[m['entity_id']]['resolution_status'] == 'resolved'
                   and re.fullmatch(r'[A-Za-z]{3,10}', m['raw_name'])
                   and not any(_FIELD_LINE.match(line.strip()) or _LEGAL_LINE.match(line.strip())
                               for line in chunk['text'][child['end']:m['start']].splitlines())]
        ids = {m['entity_id'] for m in aliases}
        if len(ids) == 1:
            alias = min(aliases, key=lambda m: m['start'])
            return alias['entity_id'], max(child['end'], alias['end'])
        return child['entity_id'], child['end']
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
    # A heading may be in the preceding chunk, but only on the same verified page.
    sections = {}
    for chunk in sorted(result['chunks'], key=lambda c: (c['document_id'], c['locator']['page'],
                                                           c['locator'].get('section_index', 0),
                                                           c['locator'].get('char_start', 0))):
        page_key = chunk['document_id'], chunk['locator']['page']
        section = sections.get(page_key)
        lines = chunk['text'].splitlines(keepends=True)
        offset = 0
        entries = []
        for line in lines:
            heading = _SECTION.match(line)
            if heading:
                kind = 'HAS_SUBSIDIARY' if heading.group(1).lower() == 'con' else 'HAS_ASSOCIATE'
                section = (kind, {'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'],
                                  'quote': line.strip()})
            if section and _LEGAL_LINE.match(line.strip()):
                entries.append((offset + len(line) - len(line.lstrip()), section))
            offset += len(line)
        sections[page_key] = section
        chunk['_wbs03_entries'] = entries
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
        for match in _SUBSIDIARY_OF.finditer(chunk['text']):
            preceding = [span for span in _company_name_spans(chunk) if span[1] <= match.start()
                         and not chunk['text'][span[1]:match.start()].strip()]
            if not preceding:
                continue
            child_start, child_end = preceding[-1]
            child = next((m for m in mentions if m['start'] == child_start and m['end'] == child_end
                          and (credible_mention(m) or reviewable_company(m))), None)
            parent = next((m for m in mentions if m['start'] == match.start('parent')
                           and m['end'] == match.end('parent')
                           and (credible_mention(m) or reviewable_company(m))), None)
            if child is None or parent is None or child['entity_id'] == parent['entity_id']:
                continue
            quote = chunk['text'][child_start:match.end()]
            if any(p.search(quote) for p in (_NEGATE, _PLANNED, _CONDITIONAL, _HISTORICAL)):
                continue
            evidence = {'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'], 'quote': quote}
            record('HAS_SUBSIDIARY', parent['entity_id'], child['entity_id'], {},
                   {'as_of': None, 'valid_from': None, 'valid_to': None}, evidence)
        issuer_id = issuers.get(chunk['document_id'])
        entries = chunk.pop('_wbs03_entries', [])
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
            if child is None:
                continue
            child_id, evidence_end = entry_identity(child, mentions, chunk, issuer_id)
            if child_id == issuer_id:
                continue
            quote = chunk['text'][cue.start():evidence_end]
            if any(p.search(quote) for p in (_NEGATE, _PLANNED, _CONDITIONAL, _HISTORICAL)):
                continue
            evidence = {'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'], 'quote': quote}
            record('HAS_SUBSIDIARY', issuer_id, child_id,
                   {'inference_basis': 'document_issuer'},
                   {'as_of': None, 'valid_from': None, 'valid_to': None}, evidence)
        for position, (kind, heading_evidence) in entries:
            following = _best_company_mentions(mentions, position, min(len(chunk['text']), position + 180),
                                                lambda m: credible_mention(m) or reviewable_company(m), entities)
            child = next((m for m in following if m['start'] == position), None)
            if child is None:
                continue
            # The source excerpt contains the actual name; do not infer a percentage or date
            # from a different row/chunk of the report.
            child_id, evidence_end = entry_identity(child, mentions, chunk, issuer_id)
            if child_id == issuer_id:
                continue
            quote = chunk['text'][child['start']:evidence_end]
            if any(p.search(quote) for p in (_NEGATE, _PLANNED, _CONDITIONAL, _HISTORICAL)):
                continue
            evidence = {'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'], 'quote': quote}
            record(kind, issuer_id, child_id, {'inference_basis': 'document_issuer'},
                   {'as_of': None, 'valid_from': None, 'valid_to': None}, heading_evidence)
            record(kind, issuer_id, child_id, {'inference_basis': 'document_issuer'},
                   {'as_of': None, 'valid_from': None, 'valid_to': None}, evidence)
        # A short code can point to the complete legal heading immediately above it.
        # Require the clause itself to resolve the named owner to this report's issuer.
        for name_start, name_end in _company_name_spans(chunk):
            tail = chunk['text'][name_end:name_end + 180]
            match = re.match(r'\s*([A-Z]{2,5})\s*\n.{0,100}?\b\1\s+là\s+công ty con\s+do\s+', tail, re.I | re.S)
            if not match:
                continue
            owner_start = name_end + match.end()
            owner = next((m for m in mentions if m['start'] == owner_start and m['entity_id'] == issuer_id), None)
            child = next((m for m in mentions if m['start'] == name_start and m['end'] == name_end
                          and (credible_mention(m) or reviewable_company(m))), None)
            if not owner or not child or child['entity_id'] == issuer_id:
                continue
            quote = chunk['text'][name_start:owner['end']]
            if any(p.search(quote) for p in (_NEGATE, _PLANNED, _CONDITIONAL, _HISTORICAL)):
                continue
            evidence = {'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'], 'quote': quote}
            record('HAS_SUBSIDIARY', issuer_id, child['entity_id'],
                   {'inference_basis': 'document_issuer'},
                   {'as_of': None, 'valid_from': None, 'valid_to': None}, evidence)
    result['relations'] = sorted(relations.values(), key=lambda r: r['relation_id'])
    return validate_envelope(result)
