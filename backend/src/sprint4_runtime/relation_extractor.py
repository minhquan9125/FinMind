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
_SECTION = re.compile(r"^\s*các công ty (con|liên kết)(?:\s+kiểm soát\s+(trực tiếp|gián tiếp))?\s*$", re.I)
_ROW_PERCENT = re.compile(r"^\s*Tỷ lệ sở hữu\s*:?\s*(\d{1,3}(?:[.,]\d{1,3})?)\s*%", re.I)
_CODE = r"[A-ZĐ][A-Za-z0-9&]{1,11}"
# "Full legal name (BIDV)" or "Full name (Techcom Securities - TCBS)" defines a document-local code.
_ABBREVIATION = re.compile(r"\(\s*(?:[^()\n]{1,40}?\s[-–]\s*)?(" + _CODE + r")\s*\)")
_APPOSITIVE = re.compile(
    r"(?<![\w-])(?P<child>" + _CODE + r")\s*[-–]\s*(?i:công ty con)(?P<indirect>\s+(?i:gián tiếp))?"
    r"\s+(?i:của)\s+(?P<parent>" + _CODE + r")(?![\w-])")
_PASSIVE_OWNER = re.compile(
    r"(?<![\w-])(?P<child>" + _CODE + r")\s+là\s+(?:một\s+)?"
    r"(?P<kind>(?i:công ty con|công ty liên kết|công ty|doanh nghiệp))\s+do\s+(?P<parent>" + _CODE + r")"
    r"\s+(?i:sở hữu|nắm giữ)\s+(?P<percent>\d{1,3}(?:[.,]\d{1,3})?)\s*%")
_BETWEEN = re.compile(r"(?P<cue>(?i:hợp tác|liên doanh))\s+(?i:giữa)\s+")
_STRUCTURE = re.compile(
    r"tỷ lệ sở hữu\b[^%()]{0,80}?công ty con\s*\(\s*(\d{1,2})/(\d{1,2})/(20\d{2})\s*\)", re.I)
_STRUCTURE_ITEM = re.compile(
    r"(?:^|(?<=\)))[ \t]*(?P<name>[^\s()][^\n()]{0,40}?)\s*\(\s*(?P<percent>\d{1,3}(?:[.,]\d{1,3})?)\s*%\s*\)", re.M)
_LEGAL_LINE = re.compile(r"^(?:Tổng\s+)?Công ty\s+(?:Cổ phần|CP|TNHH|Trách nhiệm hữu hạn)\s+\S", re.I)
_FIELD_LINE = re.compile(r"^(?:Địa chỉ|Điện thoại|Fax|Email|Tỷ lệ|Lĩnh vực|Tên cũ|Vốn|Mã số|Website|Lợi nhuận)\b", re.I)
_SUBSIDIARY_OF = re.compile(
    r"\(\s*là\s+công ty con\s+của\s+(?P<parent>(?:Tổng\s+)?Công ty\s+"
    r"(?:Cổ phần|CP|TNHH|Trách nhiệm hữu hạn)\s+[^)\n]+(?:\n[^)\n]+)?)\)", re.I)
_GENERIC_COMPANY_NAMES = {
    'công ty cổ phần', 'công ty cp', 'công ty tnhh',
    'công ty trách nhiệm hữu hạn', 'ngân hàng thương mại cổ phần',
    'công ty', 'ngân hàng', 'tập đoàn',
}
_BLOCKERS = (_NEGATE, _PLANNED, _CONDITIONAL, _HISTORICAL)
# A name ending in "và"/"&"/"," was cut by table columns or a line break.
_CUT_NAME = re.compile(r"(?:\bvà|&|,)$", re.I)


def _percent(raw):
    """Contract decimal string, or None outside 0-100."""
    value = raw.replace(',', '.')
    if float(value) > 100:
        return None
    return str(float(value)).rstrip('0').rstrip('.') if '.' in value else str(int(value))


def _blocked(text, start, end):
    """Check the whole clause around a match for negated/planned/conditional/past wording."""
    left = max(text.rfind(mark, 0, start) for mark in '.!?;\n') + 1
    rights = [i for i in (text.find(mark, end) for mark in '.!?;\n') if i >= 0]
    return any(p.search(text[left:min(rights, default=len(text))]) for p in _BLOCKERS)


def _registry_index(registry):
    """Verified Company rows by normalized alias; generic legal forms identify nobody."""
    index = {}
    for row in registry:
        if row['entity_type'] != 'Company' or row['verified'] is not True or not row.get('identity_key'):
            continue
        for alias in [row['canonical_name']] + row['aliases']:
            key = text_view(alias)[0].strip()
            if key and key not in _GENERIC_COMPANY_NAMES:
                index.setdefault(key, {})[row['entity_id']] = row
    return index


def _registry_entity(row, raw):
    return {'entity_id': row['entity_id'], 'entity_type': 'Company',
            'canonical_name': row['canonical_name'], 'aliases': [raw],
            'resolution_status': 'resolved', 'identity_key': row['identity_key'], 'attributes': {}}


def _abbreviations(chunks, index):
    """Codes defined in this document right after a verified, unambiguous full name."""
    by_last = {}
    for key in index:
        if len(key.split()) >= 3:
            by_last.setdefault(key.rsplit(' ', 1)[-1], []).append(key)
    found = {}
    for chunk in chunks:
        text = chunk['text']
        for match in _ABBREVIATION.finditer(text):
            before = text_view(text[max(0, match.start() - 160):match.start()])[0].rstrip()
            if not before:
                continue
            keys = [k for k in by_last.get(before.rsplit(' ', 1)[-1], [])
                    if before.endswith(k) and (len(before) == len(k) or not before[-len(k) - 1].isalnum())
                    and len(index[k]) == 1]
            if keys:
                found.setdefault(match.group(1), set()).update(index[max(keys, key=len)])
    result = {}
    for code, ids in found.items():
        registered = set(index.get(text_view(code)[0].strip(), {}))
        # A code defined twice, or already registered to someone else, is ambiguous.
        if len(ids) == 1 and (not registered or registered == ids):
            result[code] = ids.pop()
    return result


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
        if len(matches) == 1 and _percent(matches[0]) is not None:
            attributes['ownership_percent'] = _percent(matches[0])
        if re.search(r"\bgián tiếp\b", between, re.I):
            attributes['holding_basis'] = 'indirect'
        elif re.search(r"\btrực tiếp\b", between, re.I):
            attributes['holding_basis'] = 'direct'
        return 'OWNS_SHARES', first['entity_id'], second['entity_id'], attributes
    return None


def _issuer_entity(document, index):
    """Use the DB company binding only when it exactly matches one verified registry row."""
    if document.get('doc_type') != 'ANNUAL_REPORT':
        return None
    symbol, name = document.get('issuer_symbol'), document.get('issuer_company_name')
    if not symbol or not name or not document.get('issuer_company_id'):
        return None
    if not re.match(r'^\s*' + re.escape(symbol) + r'\s*[—–-]', document.get('title', ''), re.I):
        return None
    matches = list(index.get(text_view(name)[0].strip(), {}).values())
    if len(matches) != 1:
        return None
    row = matches[0]
    if text_view(row['canonical_name'])[0].strip() in _GENERIC_COMPANY_NAMES:
        return None
    return _registry_entity(row, name)


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
    def reviewable_company(mention, allow_cut=False):
        """allow_cut: a cut name may still be rescued by a verified alias (entry_identity)."""
        entity = entities[mention['entity_id']]
        name = mention['raw_name'].strip()
        return (entity['resolution_status'] == 'unresolved'
                and 4 <= len(name.split()) <= 14 and len(name) <= 100
                and re.match(r'^(?:Công ty|CTCP|Tổng Công ty|Ngân hàng)\b', name, re.I) is not None
                and text_view(name)[0].strip() not in _GENERIC_COMPANY_NAMES
                and not re.search(r'[.;]|\s(?:và|&)\s', name, re.I)
                and (allow_cut or not _CUT_NAME.search(name)))
    def cut_and_unresolved(child, child_id):
        return child_id == child['entity_id'] and _CUT_NAME.search(child['raw_name'].strip()) is not None
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
    index = _registry_index(registry)
    rows_by_id = {row['entity_id']: row for rows in index.values() for row in rows.values()}
    by_first = {}
    for key in index:
        by_first.setdefault(key.split(' ', 1)[0], []).append(key)
    by_document = {}
    for chunk in result['chunks']:
        by_document.setdefault(chunk['document_id'], []).append(chunk)
    abbreviations = {doc_id: _abbreviations(chunks, index) for doc_id, chunks in by_document.items()}
    def ensure(entity_id, raw):
        if entity_id not in entities:
            entities[entity_id] = _registry_entity(rows_by_id[entity_id], raw)
            result['entities'].append(entities[entity_id])
        return entity_id
    def resolve_code(document_id, raw, allow_ticker):
        """A short code resolves through this document's definition or one registry row.

        A bare ticker is accepted only where the clause itself says it is a company
        (allow_ticker), mirroring the shared resolver's ticker cue rule.
        """
        if raw in abbreviations.get(document_id, {}):
            return ensure(abbreviations[document_id][raw], raw)
        key = text_view(raw)[0].strip()
        rows = index.get(key, {})
        if len(rows) != 1:
            return None
        row = next(iter(rows.values()))
        if not allow_ticker and key in {text_view(t)[0].strip() for t in row.get('ticker_aliases', [])}:
            return None
        return ensure(row['entity_id'], raw)
    def party(document_id, text, start):
        """Longest verified name (or defined code) starting at start: (entity_id, end)."""
        norm, spans = text_view(text[start:start + 160])
        keys = [k for k in by_first.get(norm.split(' ', 1)[0], [])
                if norm.startswith(k) and (len(norm) == len(k) or not norm[len(k)].isalnum())
                and len(index[k]) == 1]
        if keys:
            key = max(keys, key=len)
            row = next(iter(index[key].values()))
            if key not in {text_view(t)[0].strip() for t in row.get('ticker_aliases', [])}:
                return ensure(row['entity_id'], text[start:start + spans[len(key) - 1][1]]), start + spans[len(key) - 1][1]
        code = re.match(_CODE + r'(?![\w-])', text[start:])
        if code and code.group() in abbreviations.get(document_id, {}):
            return resolve_code(document_id, code.group(), False), start + code.end()
        return None
    issuers = {}
    for document in result['documents']:
        issuer = _issuer_entity(document, index)
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
    sections, rows = {}, {}
    for chunk in sorted(result['chunks'], key=lambda c: (c['document_id'], c['locator']['page'],
                                                           c['locator'].get('section_index', 0),
                                                           c['locator'].get('char_start', 0))):
        page_key = chunk['document_id'], chunk['locator']['page']
        section, row = sections.get(page_key), rows.get(page_key)
        lines = chunk['text'].splitlines(keepends=True)
        offset = 0
        entries = []
        for line in lines:
            heading = _SECTION.match(line)
            if heading:
                kind = 'HAS_SUBSIDIARY' if heading.group(1).lower() == 'con' else 'HAS_ASSOCIATE'
                section = (kind, {'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'],
                                  'quote': line.strip()}, (heading.group(2) or '').lower() == 'gián tiếp')
                row = None
            if section and _LEGAL_LINE.match(line.strip()):
                # One list row runs until the next legal name/heading, possibly into the next chunk.
                row = {'shares': [], 'indirect': section[2]}
                entries.append((offset + len(line) - len(line.lstrip()), section[:2], row))
            elif row is not None and _ROW_PERCENT.match(line.strip()):
                row['shares'].append((_percent(_ROW_PERCENT.match(line.strip()).group(1)),
                                      {'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'],
                                       'quote': line.strip()}))
            offset += len(line)
        sections[page_key], rows[page_key] = section, row
        chunk['_wbs03_entries'] = entries
    relations = []
    def record(kind, subject, target, attributes, temporal, evidence):
        """Merge compatible statements of one pair in one report; keep conflicting values apart."""
        for relation in relations:
            if ((relation['relation_type'], relation['subject_id'], relation['object_id'], relation['_document'])
                    != (kind, subject, target, evidence['document_id'])):
                continue
            if (any(relation['attributes'].get(k, v) != v for k, v in attributes.items())
                    or any(v is not None and relation['temporal'][k] not in (None, v) for k, v in temporal.items())):
                continue
            relation['attributes'].update(attributes)
            relation['temporal'].update({k: v for k, v in temporal.items() if v is not None})
            if evidence not in relation['evidence']:
                relation['evidence'].append(evidence)
            return
        relations.append({'_document': evidence['document_id'], 'relation_type': kind,
                          'subject_id': subject, 'object_id': target, 'attributes': dict(attributes),
                          'temporal': dict(temporal), 'evidence': [evidence],
                          'review': {'status': 'PENDING', 'reviewer': None, 'reviewed_at': None}})

    for chunk in result['chunks']:
        mentions = by_chunk.get((chunk['document_id'], chunk['chunk_id']), [])
        text, doc_id = chunk['text'], chunk['document_id']
        def cite(start, end):
            return {'document_id': doc_id, 'chunk_id': chunk['chunk_id'], 'quote': text[start:end]}
        # "(BIC- Công ty con của BIDV)": a code in apposition to "công ty con của <owner>".
        for match in _APPOSITIVE.finditer(text):
            child = resolve_code(doc_id, match.group('child'), True)
            parent = resolve_code(doc_id, match.group('parent'), True)
            if child and parent and child != parent and not _blocked(text, match.start(), match.end()):
                record('HAS_SUBSIDIARY', parent, child,
                       {'holding_basis': 'indirect'} if match.group('indirect') else {},
                       {'as_of': None, 'valid_from': None, 'valid_to': None}, cite(*match.span()))
        # "VCBR là công ty con do Vietcombank sở hữu 100% vốn".
        for match in _PASSIVE_OWNER.finditer(text):
            child = resolve_code(doc_id, match.group('child'), True)
            parent = resolve_code(doc_id, match.group('parent'), False)
            percent = _percent(match.group('percent'))
            if not child or not parent or child == parent or percent is None or _blocked(text, *match.span()):
                continue
            kind = {'công ty con': 'HAS_SUBSIDIARY', 'công ty liên kết': 'HAS_ASSOCIATE'}.get(
                match.group('kind').lower(), 'OWNS_SHARES')
            record(kind, parent, child, {'ownership_percent': percent},
                   {'as_of': None, 'valid_from': None, 'valid_to': None}, cite(*match.span()))
        # "hợp tác/liên doanh giữa A và B" with exactly two verified parties.
        for match in _BETWEEN.finditer(text):
            first = party(doc_id, text, match.end())
            link = first and re.match(r'\s*(?:\([^()\n]{1,30}\))?\s*(?:và|với)\s+', text[first[1]:])
            second = link and party(doc_id, text, first[1] + link.end())
            if not second or second[0] == first[0]:
                continue
            word = re.match(r'\s*(?:\([^()\n]{1,30}\))?[ \t]*(\S*)', text[second[1]:]).group(1)
            # A capitalized word or another "và" means the name list continues: not two parties.
            if word and not (word[0] in '.;:)' or (word[0].islower() and word != 'và')):
                continue
            if _blocked(text, match.start(), second[1]):
                continue
            attributes = {'cooperation_scope': 'liên doanh'} if match.group('cue').lower() == 'liên doanh' else {}
            record('COOPERATES_WITH', *sorted((first[0], second[0])), attributes,
                   {'as_of': None, 'valid_from': None, 'valid_to': None}, cite(match.start(), second[1]))
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
        # "TỶ LỆ SỞ HỮU ... TẠI CÁC CÔNG TY CON (31/12/2024)" then "TCBS (94,1%) TechAMC (100%)".
        for heading in _STRUCTURE.finditer(text):
            try:
                as_of = date(int(heading.group(3)), int(heading.group(2)), int(heading.group(1))).isoformat()
            except ValueError:
                continue
            for item in _STRUCTURE_ITEM.finditer(text, heading.end(), min(len(text), heading.end() + 300)):
                child = resolve_code(doc_id, item.group('name').strip(), False)
                percent = _percent(item.group('percent'))
                if child and child != issuer_id and percent is not None:
                    record('HAS_SUBSIDIARY', issuer_id, child,
                           {'inference_basis': 'document_issuer', 'ownership_percent': percent},
                           {'as_of': as_of, 'valid_from': None, 'valid_to': None},
                           cite(heading.start(), item.end()))
        for cue in _ISSUER_SUBSIDIARY.finditer(chunk['text']):
            # The child must immediately follow an explicit subsidiary heading.
            following = sorted((m for m in mentions if cue.end() <= m['start'] <= cue.end() + 12),
                               key=lambda m: (m['start'], -m['end']))
            if not following or chunk['text'][cue.end():following[0]['start']].strip():
                continue
            child = next((m for m in following if credible_mention(m)), None)
            if child is None:
                child = next((m for m in following if reviewable_company(m, allow_cut=True)), None)
            if child is None:
                continue
            child_id, evidence_end = entry_identity(child, mentions, chunk, issuer_id)
            if child_id == issuer_id or cut_and_unresolved(child, child_id):
                continue
            quote = chunk['text'][cue.start():evidence_end]
            if any(p.search(quote) for p in (_NEGATE, _PLANNED, _CONDITIONAL, _HISTORICAL)):
                continue
            evidence = {'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'], 'quote': quote}
            record('HAS_SUBSIDIARY', issuer_id, child_id,
                   {'inference_basis': 'document_issuer'},
                   {'as_of': None, 'valid_from': None, 'valid_to': None}, evidence)
        for position, (kind, heading_evidence), row in entries:
            following = _best_company_mentions(mentions, position, min(len(chunk['text']), position + 180),
                                                lambda m: credible_mention(m) or reviewable_company(m, True), entities)
            child = next((m for m in following if m['start'] == position), None)
            if child is None:
                continue
            child_id, evidence_end = entry_identity(child, mentions, chunk, issuer_id)
            if child_id == issuer_id or cut_and_unresolved(child, child_id):
                continue
            quote = chunk['text'][child['start']:evidence_end]
            if any(p.search(quote) for p in (_NEGATE, _PLANNED, _CONDITIONAL, _HISTORICAL)):
                continue
            evidence = {'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'], 'quote': quote}
            attributes = {'inference_basis': 'document_issuer'}
            values = {value for value, _ in row['shares']}
            # Only this row's own "Tỷ lệ sở hữu" line; an indirect row's percentage
            # belongs to the intermediate owner, not to the issuer.
            if not row['indirect'] and len(values) == 1 and None not in values:
                attributes['ownership_percent'] = values.pop()
            no_time = {'as_of': None, 'valid_from': None, 'valid_to': None}
            record(kind, issuer_id, child_id, attributes, no_time, heading_evidence)
            record(kind, issuer_id, child_id, attributes, no_time, evidence)
            if 'ownership_percent' in attributes:
                record(kind, issuer_id, child_id, attributes, no_time, row['shares'][0][1])
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
            share = re.match(r'\s+(?:sở hữu|nắm giữ)\s+(\d{1,3}(?:[.,]\d{1,3})?)\s*%', text[owner['end']:], re.I)
            attributes = {'inference_basis': 'document_issuer'}
            if share and _percent(share.group(1)) is not None:
                attributes['ownership_percent'] = _percent(share.group(1))
            quote = text[name_start:owner['end'] + (share.end() if share else 0)]
            if any(p.search(quote) for p in (_NEGATE, _PLANNED, _CONDITIONAL, _HISTORICAL)):
                continue
            evidence = {'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'], 'quote': quote}
            record('HAS_SUBSIDIARY', issuer_id, child['entity_id'], attributes,
                   {'as_of': None, 'valid_from': None, 'valid_to': None}, evidence)
    output = []
    for relation in relations:
        # The report is part of the identity: one pair in two annual reports is two statements.
        key = (relation.pop('_document'), relation['relation_type'], relation['subject_id'],
               relation['object_id'], relation['attributes'], relation['temporal'])
        digest = hashlib.sha256(json.dumps(key, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:32]
        output.append({'relation_id': 'rel:' + digest, **relation})
    result['relations'] = sorted(output, key=lambda r: r['relation_id'])
    return validate_envelope(result)
