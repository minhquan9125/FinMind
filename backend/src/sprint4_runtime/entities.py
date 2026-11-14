"""Nhận diện ứng viên và resolve alias có căn cứ, giữ offset block gốc."""
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from .contracts import validate_chunk

_types = {'Company', 'Person', 'Event'}
_generic = {'công ty', 'tập đoàn', 'ngân hàng', 'công ty mẹ', 'công ty con', 'company', 'the company', 'the group'}
_risky_tickers = {'ceo', 'dat', 'pet', 'tig', 'hot', 'one', 'sam', 'gas', 'fit'}
_forms = [(r'\b(?:ctcp|ct\s+cp|cty\s+cp|công\s+ty\s+cp)\b', 'công ty cổ phần'),
          (r'\b(?:nh\s+tmcp|nhtmcp|ngân\s+hàng\s+tmcp)\b', 'ngân hàng thương mại cổ phần')]
_company = re.compile(r'\b(?:(?:Tổng\s+)?Công\s+ty\s+(?:Cổ\s+phần|CP|TNHH)|CTCP|Ngân\s+hàng\s+(?:TMCP|Thương\s+mại\s+Cổ\s+phần))\s+[^\n.;:]{2,160}', re.I)
_person = re.compile(r'\b(?:Ông|Bà|Chủ tịch|Tổng [Gg]iám đốc|Giám đốc)\s+((?:[A-ZÀ-ỸĐ][a-zà-ỹđ]+\s+){1,5}[A-ZÀ-ỸĐ][a-zà-ỹđ]+)\b')
_events = {
    'SHAREHOLDER_MEETING': r'đại hội(?: đồng)? cổ đông|đhđcđ', 'APPOINTMENT': r'bổ nhiệm',
    'DISMISSAL': r'miễn nhiệm|bãi nhiệm', 'LISTING': r'niêm yết', 'DIVIDEND': r'cổ tức',
    'SHARE_ISSUANCE': r'phát hành cổ phiếu', 'CAPITAL_INCREASE': r'tăng vốn',
    'STAKE_TRANSFER': r'chuyển nhượng', 'DIVESTMENT': r'thoái vốn', 'ACQUISITION': r'mua lại|mua cổ phần',
    'ESTABLISHMENT': r'thành lập', 'DISSOLUTION': r'giải thể', 'RENAME': r'đổi tên',
    'BORROWING': r'vay vốn|hợp đồng vay', 'BOND_ISSUANCE': r'phát hành trái phiếu',
    'PENALTY': r'xử phạt', 'MERGER': r'sáp nhập', 'RESTRUCTURING': r'tái cấu trúc',
    'INVESTMENT': r'đầu tư dự án', 'PROJECT_LAUNCH': r'khởi công|khánh thành',
    'SHARE_BUYBACK': r'mua cổ phiếu quỹ', 'BANKRUPTCY': r'phá sản'}
_event_pattern = re.compile('|'.join('(?P<E%d>%s)' % (i, pat) for i, pat in enumerate(_events.values())), re.I)

def _need(ok, message):
    if not ok:
        raise ValueError(message)

def _text(value):
    return isinstance(value, str) and bool(value.strip())

def _id(prefix, *values):
    raw = json.dumps(values, ensure_ascii=False, separators=(',', ':')).encode()
    return prefix + ':' + hashlib.sha256(raw).hexdigest()[:32]

def text_view(raw):
    """Cùng khóa cho alias/block; mỗi ký tự chuẩn có span về nguyên bản."""
    chars, spans = [], []
    i = 0
    while i < len(raw):
        end = i + 1
        while end < len(raw) and unicodedata.combining(raw[end]):
            end += 1
        part = unicodedata.normalize('NFC', raw[i:end]).replace('ƣ', 'ư').replace('Ƣ', 'Ư').casefold()
        for char in part:
            if char in '\u200b\ufeff\u00ad':
                continue
            if char.isspace():
                char = ' '
                if chars and chars[-1] == ' ':
                    spans[-1] = (spans[-1][0], end)
                    continue
            if char in '–—':
                char = '-'
            chars.append(char); spans.append((i, end))
        i = end
    text = ''.join(chars)
    for pattern, replacement in _forms:
        for m in reversed(list(re.finditer(pattern, text))):
            span = (spans[m.start()][0], spans[m.end()-1][1])
            text = text[:m.start()] + replacement + text[m.end():]
            spans[m.start():m.end()] = [span] * len(replacement)
    return text, spans

def _key(raw):
    return text_view(raw)[0].strip()

def _chunks(chunks):
    _need(type(chunks) is list, 'chunks must be a list')
    result = {}
    for chunk in chunks:
        validate_chunk(chunk)
        key = chunk['document_id'], chunk['chunk_id']
        _need(key not in result or result[key] == chunk, 'Conflicting chunk duplicate')
        result[key] = chunk
    versions = defaultdict(set)
    for c in result.values():
        versions[c['document_id']].add(c['document_version'])
    _need(all(len(v) == 1 for v in versions.values()), 'Conflicting document versions')
    return result

def _registry(registry):
    _need(registry is None or type(registry) is list, 'registry must be a list')
    by_alias, by_id = defaultdict(dict), {}
    for row in registry or []:
        _need(type(row) is dict, 'Invalid registry row')
        _need(all(_text(row.get(k)) for k in ('entity_id', 'entity_type', 'canonical_name')), 'Registry identity')
        _need(row['entity_type'] in _types and type(row.get('verified')) is bool, 'Registry type/verified')
        _need(type(row.get('aliases')) is list and all(_text(a) for a in row['aliases']), 'Registry aliases')
        _need(type(row.get('ticker_aliases', [])) is list and all(_text(a) for a in row.get('ticker_aliases', [])), 'Ticker aliases')
        _need(all(_key(a) in {_key(x) for x in row['aliases']} for a in row.get('ticker_aliases', [])), 'Ticker not in aliases')
        _need(row['entity_id'] not in by_id or by_id[row['entity_id']] == row, 'Conflicting registry ID')
        if 'context' in row:
            _need(type(row['context']) is dict and all(_text(v) for v in row['context'].values()), 'Invalid registry context')
        by_id[row['entity_id']] = row
        for alias in set(row['aliases'] + [row['canonical_name']]):
            by_alias[(_key(alias), row['entity_type'])][row['entity_id']] = row
    return by_alias

def _ticker_cue(text, start, raw):
    before = text[max(0, start-80):start]
    return bool(re.search(r'(?:mã\s+(?:chứng\s+khoán|cổ\s+phiếu|ck)|cổ\s+phiếu|ticker|HOSE|HNX|UPCoM)\s*:?\s*$', before, re.I)
                or re.search(r'(?:công ty|tập đoàn|ngân hàng)\s*$', before, re.I)
                or re.match(r'\s+là\s+(?:một\s+)?(?:công ty|tập đoàn|ngân hàng)\b', text[start+len(raw):], re.I))

def normalize(chunks, registry=None, proposals=None):
    source = _chunks(chunks); aliases = _registry(registry)
    _need(proposals is None or type(proposals) is list, 'proposals must be a list')
    found = {}
    def add(chunk, kind, start, end, context=None, event_type=None):
        _need(type(kind) is str and kind in _types and type(start) is int and type(end) is int, 'Invalid proposal type/span')
        _need(0 <= start < end <= len(chunk['text']), 'Invalid proposal span')
        _need(context is None or type(context) is dict and all(_text(v) for v in context.values()), 'Invalid proposal context')
        key = chunk['document_id'], chunk['chunk_id'], kind, start, end
        value = {'chunk': chunk, 'type': kind, 'start': start, 'end': end, 'context': context or {}, 'event_type': event_type}
        if key in found:
            old = found[key]
            _need(not old['context'] or not value['context'] or old['context'] == value['context'], 'Conflicting proposal context')
            if value['context']:
                old['context'] = value['context']
            if value['event_type']:
                old['event_type'] = value['event_type']
        else:
            found[key] = value
    alias_keys = sorted({k[0] for k in aliases if k[0] and k[0] not in _generic}, key=lambda k: (-len(k), k))
    pattern = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(k) for k in alias_keys) + r')(?!\w)') if alias_keys else None
    for c in sorted(source.values(), key=lambda x: (x['document_id'], x['chunk_id'])):
        text, mapping = text_view(c['text'])
        if pattern:
            for m in pattern.finditer(text):
                for kind in sorted(_types):
                    if (m.group(), kind) in aliases:
                        add(c, kind, mapping[m.start()][0], mapping[m.end()-1][1])
        for m in _company.finditer(c['text']):
            raw = m.group().rstrip(' ,\t\r'); end = m.start()+len(raw)
            if raw:
                add(c, 'Company', m.start(), end)
        for m in _person.finditer(c['text']):
            add(c, 'Person', *m.span(1))
        for m in _event_pattern.finditer(c['text']):
            add(c, 'Event', *m.span(), event_type=list(_events)[int(m.lastgroup[1:])])
    for p in proposals or []:
        _need(type(p) is dict and all(k in p for k in ('document_id', 'chunk_id', 'entity_type', 'start', 'end')), 'Invalid proposal')
        _need(_text(p['document_id']) and _text(p['chunk_id']), 'Invalid proposal source')
        c = source.get((p['document_id'], p['chunk_id']))
        _need(c is not None, 'Unknown proposal source')
        add(c, p['entity_type'], p['start'], p['end'], p.get('context'))
    entities, mentions = {}, {}
    for loc, f in sorted(found.items()):
        c, kind, start, end = f['chunk'], f['type'], f['start'], f['end']
        raw = c['text'][start:end]; key = _key(raw)
        candidates = list(aliases.get((key, kind), {}).values())
        approved = []
        for r in candidates:
            if r['verified'] is not True or not _text(r.get('identity_key')) or key in _generic or re.search(r'(?:\bvà|&)\s*$', key):
                continue
            if (key in _risky_tickers or key in {_key(t) for t in r.get('ticker_aliases', [])}) and not _ticker_cue(c['text'], start, raw):
                continue
            if kind == 'Person':
                rc = r.get('context', {})
                if f['context'].get('company_id') != rc.get('company_id') or not f['context'].get('company_id') or not f['context'].get('position') or _key(f['context']['position']) != _key(rc.get('position', '')):
                    continue
            if kind == 'Event' and r.get('context', {}).get('document_id') != c['document_id']:
                continue
            approved.append(r)
        status = 'resolved' if len(approved) == 1 else 'ambiguous' if len(approved) > 1 or len(candidates) > 1 else 'unresolved'
        match = approved[0] if status == 'resolved' else None
        eid = match['entity_id'] if match else _id('ent', *loc)
        attrs = {'candidate_ids': sorted(r['entity_id'] for r in candidates)} if not match else {}
        if kind == 'Event':
            attrs.update(event_type=f['event_type'] or 'UNSPECIFIED', occurred_at=None, assertion_status='UNCERTAIN')
        entity = {'entity_id': eid, 'entity_type': kind, 'canonical_name': match['canonical_name'] if match else None,
                  'aliases': [raw], 'resolution_status': status, 'identity_key': match['identity_key'] if match else None, 'attributes': attrs}
        if eid in entities:
            entities[eid]['aliases'] = sorted(set(entities[eid]['aliases'] + [raw]))
        else:
            entities[eid] = entity
        mid = _id('men', *loc)
        mentions[mid] = {'mention_id': mid, 'entity_id': eid, 'document_id': c['document_id'], 'chunk_id': c['chunk_id'], 'start': start, 'end': end, 'raw_name': raw}
    return {'entities': [entities[k] for k in sorted(entities)], 'mentions': [mentions[k] for k in sorted(mentions)]}
