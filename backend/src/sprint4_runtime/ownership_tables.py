"""Subsidiary/associate ownership tables in verified annual-report chunks.

Annual reports list group structure as multi-column tables. In the stored chunk
text one table row becomes several lines where the legal-name column is
interleaved with address, licence or activity columns. A row is accepted only
when the first words of its lines spell exactly one verified registry name, so
a column boundary is never guessed and no identity is created here.

The relation kind comes only from an explicit section heading ("Công ty con",
"(ii) Công ty liên kết trực tiếp", "Công ty liên doanh", "Các công ty con của X
bao gồm:"). A combined heading ("Các công ty con, công ty liên kết") does not say
which row is which, so those rows are reported, not asserted.
"""

import re
import unicodedata
from datetime import date

from .entities import text_view

_LEGAL_START = re.compile(r'(?:Tổng\s+)?Công\s+ty\b|Ngân\s+hàng\b|Trường\b|Viện\b|Tập\s+đoàn\b', re.I)
_NUM = r'\d{1,3}(?:[.,]\d{1,3})?'
_PCT_TAIL = re.compile(r'(?<![\d.,])(?P<p>' + _NUM + r')\s*%(?:\s+' + _NUM + r'\s*%){0,3}\s*(?:\(\*+\))?\s*$')
_OWNER_TAIL = re.compile(r'\s(?:sở hữu|nắm giữ)\s+(?P<p>' + _NUM + r')\s*%\s*(?:vốn góp|vốn điều lệ|cổ phần)?\s*$', re.I)
_ROW_NUMBER = re.compile(r'^\s*\d{1,2}(?:\s+\d{1,2}){0,2}\s+(?=\S)')
# A heading is the whole line, or follows a list marker such as "(ii)" or "b." after a side menu;
# prose that merely ends with "... các công ty con" is not a heading.
_MARKER = r'(?:\(?[ivx]{1,4}\)|[a-z]\.|\d{1,2}(?:\.\d{1,2})*\.)'
_MARK = r'(?:^\s*(?:' + _MARKER + r')?|\s' + _MARKER + r')\s*'
_TAIL = r'(?:\s+(?:trực tiếp|gián tiếp|sở hữu trực tiếp))?\s*(?:\(tiếp theo\))?\s*:?\s*$'
_NESTED = re.compile(r'^\s*(?:các\s+)?công ty con của\s+(?P<parent>.+?)\s*(?:bao\s+)?gồm\s*:?\s*$', re.I)
_MIXED = re.compile(_MARK + r'(?:các\s+)?công ty con\s*(?:,|và)\s*(?:các\s+)?công ty liên (?:kết|doanh)\s*:?\s*$', re.I)
_ASSOC = re.compile(_MARK + r'(?:các\s+)?(?:công ty|doanh nghiệp) liên (?P<word>kết|doanh)(?:\s*,\s*liên kết)?' + _TAIL, re.I)
_SUB = re.compile(_MARK + r'(?:các\s+)?công ty con' + _TAIL, re.I)
# A numbered note heading ("2.4. Cơ sở hợp nhất") closes the table; amounts like "1.000.000 VNĐ" do not.
_RESET = re.compile(r'^\s*\d{1,2}(?:\.\d{1,2}){1,2}\.\s+[A-ZĐÀ-Ỹ]')
_DAY = r'(?:(?P<d1>\d{1,2})[/.](?P<m1>\d{1,2})[/.](?P<y1>20\d{2})|(?P<d2>\d{1,2})\s+tháng\s+(?P<m2>\d{1,2})\s+năm\s+(?P<y2>20\d{2}))'
_OTHER_DAY = r'(?:ngày\s+)?(?:\d{1,2}[/.]\d{1,2}[/.]20\d{2}|\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+20\d{2})'
# A table header: "Tại ngày 31/12/2025 [và 31/12/2024]" or two period columns "31.12.2025 31.12.2024".
# A lone wrapped date ("17 tháng 01 năm 2025" from a licence column) is not a header.
# "Công ty con | Hoạt động chính | ... | Tại ngày 31/12/2024 và 31/12/2023": the period sits at
# the end of the column-header row.
_DATE_TAIL = re.compile(r'(?:^|\s)(?P<at>tại ngày\s+)' + _DAY + r'(?P<second>\s+(?:và\s+)?' + _OTHER_DAY + r')?\s*:?\s*$', re.I)
# Side-menu furniture repeated on every page ("06 QUẢN TRỊ CÔNG TY"): two digits, no lowercase.
_MENU_START = re.compile(r'^\s*\d{2}\s+\S')
_DATE_LINE = re.compile(r'^\s*(?P<at>tại ngày\s+)?' + _DAY + r'(?P<second>\s+(?:và\s+)?' + _OTHER_DAY + r')?\s*:?\s*$', re.I)
_GENERIC = {'công ty cổ phần', 'công ty cp', 'công ty tnhh', 'công ty trách nhiệm hữu hạn',
            'ngân hàng thương mại cổ phần', 'công ty', 'ngân hàng', 'tập đoàn'}
# "Công ty Cổ phần Chứng khoán" names an industry, not a company: such registry rows are skipped.
_FORM_WORDS = set('tổng công ty cổ phần cp tnhh mtv một thành viên trách nhiệm hữu hạn ngân hàng tmcp thương mại tập đoàn'.split())
_INDUSTRY_WORDS = set(('chứng khoán bảo hiểm đầu tư xây dựng dịch vụ tài chính quản lý quỹ phát triển sản xuất '
                       'công nghệ viễn thông năng lượng bất động sản du lịch vận tải kinh doanh xuất nhập khẩu '
                       'cho thuê và giải pháp phần mềm thông tin nhà nước').split())
MAX_ROW_LINES = 12
MAX_SKIPPED_LINES = 2


_EXPAND = {'tmcp': ('thương', 'mại', 'cổ', 'phần'), 'ctcp': ('công', 'ty', 'cổ', 'phần')}


def _tokens(text):
    """Word tokens compared one by one, so a name split across lines ("Ngân hàng" / "TMCP")
    still matches. Abbreviated legal forms are expanded and a free-standing dash dropped,
    on both sides: "TNHH MTV - Ngân hàng TMCP" equals "TNHH MTV Ngân hàng Thương mại Cổ phần"."""
    text = unicodedata.normalize('NFC', text).replace('ƣ', 'ư').replace('Ƣ', 'Ư').casefold()
    words = []
    for word in re.split(r'\s+', text.replace('–', '-').replace('—', '-').replace('​', '')):
        if word and word != '-':
            words.extend(_EXPAND.get(word, (word,)))
    return words


def _key(text):
    return text_view(text)[0].strip()


def name_index(registry):
    """Verified Company aliases as token tuples, grouped by first token."""
    by_tokens = {}
    for row in registry:
        if row.get('entity_type') != 'Company' or row.get('verified') is not True:
            continue
        for alias in {row['canonical_name'], *row['aliases']}:
            tokens = tuple(_tokens(alias))
            distinctive = [t for t in tokens if t not in _FORM_WORDS]
            if (len(tokens) >= 3 and _key(alias) not in _GENERIC
                    and any(t not in _INDUSTRY_WORDS for t in distinctive)):
                by_tokens.setdefault(tokens, set()).add(row['entity_id'])
    by_first = {}
    for tokens, ids in by_tokens.items():
        if len(ids) == 1:
            by_first.setdefault(tokens[0], []).append((tokens, next(iter(ids))))
    return by_first


def _spells(lines, alias):
    """Last contributing line index when alias = non-empty prefix of line 0 + prefixes of
    following lines, else None.

    Up to MAX_SKIPPED_LINES consecutive lines may contribute nothing: they belong
    to another column (licence text, a side menu) between two name fragments.
    """
    def go(line, position, skipped):
        if position == len(alias):
            return line - 1 - skipped  # index of the last line that contributed a word
        if line == len(lines):
            return None
        words = lines[line]
        for size in range(min(len(words), len(alias) - position), 0, -1):
            if tuple(words[:size]) == alias[position:position + size]:
                last = go(line + 1, position + size, 0)
                if last is not None:
                    return last
        # Line 1 must continue the name: skipping right after line 0 would let "Công ty Cổ phần"
        # plus some later line spell an unrelated company.
        if line > 1 and skipped < MAX_SKIPPED_LINES:
            return go(line + 1, position, skipped + 1)
        return None
    return go(0, 0, 0)


def _row_name(lines, by_first):
    """(entity_id, last_line, None) for exactly one longest verified name, else (None, 0, reason)."""
    tokens = [_tokens(text) for text in lines]
    if not tokens[0]:
        return None, 0, 'CHILD_UNRESOLVED'
    found = []
    for alias, entity_id in by_first.get(tokens[0][0], []):
        last = _spells(tokens, alias)
        if last is not None:
            found.append((len(alias), entity_id, last))
    if not found:
        return None, 0, 'CHILD_UNRESOLVED'
    best = max(size for size, _, _ in found)
    winners = {(entity_id, last) for size, entity_id, last in found if size == best}
    if len({entity_id for entity_id, _ in winners}) != 1:
        return None, 0, 'CHILD_AMBIGUOUS'
    entity_id, last = min(winners)
    return entity_id, last, None


def _owner(text, index):
    """Longest verified alias ending right before "sở hữu N%" in the same row."""
    words = text_view(text)[0].split()
    for size in range(min(12, len(words)), 0, -1):
        rows = index.get(' '.join(words[-size:]), {})
        if len(rows) == 1 and ' '.join(words[-size:]) not in _GENERIC:
            return next(iter(rows))
    return None


def _header_day(text):
    """Table date from a header line, or None (a lone date needs "Tại ngày" or a second period)."""
    match = _DATE_LINE.match(text)
    if match and (match.group('at') or match.group('second')):
        return _day(match)
    match = _DATE_TAIL.search(text)
    return _day(match) if match else None


def _day(match):
    groups = match.groupdict()
    day, month, year = ((groups['d1'], groups['m1'], groups['y1']) if groups['d1']
                        else (groups['d2'], groups['m2'], groups['y2']))
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def _heading(text, index):
    """(kind, label, parent_entity_or_marker) for a section heading line, else None."""
    nested = _NESTED.match(text)
    if nested:
        parent_text = re.sub(r'\([^()]*\)', ' ', nested.group('parent'))
        rows = index.get(_key(parent_text), {})
        parent = next(iter(rows)) if len(rows) == 1 else 'UNRESOLVED'
        return 'HAS_SUBSIDIARY', 'công ty con', parent
    if _MIXED.search(text):
        return None, 'công ty con, công ty liên kết', None
    associate = _ASSOC.search(text)
    if associate:
        return 'HAS_ASSOCIATE', 'công ty liên ' + associate.group('word').lower(), None
    if _SUB.search(text):
        return 'HAS_SUBSIDIARY', 'công ty con', None
    return None


def _is_menu(text):
    return bool(_MENU_START.match(text)) and '%' not in text and not any(char.islower() for char in text)


def _page_lines(chunks):
    """Per (document, page): ordered (chunk, start, end, text) body lines."""
    pages = {}
    ordered = sorted(chunks, key=lambda c: (c['document_id'], c['locator']['page'],
                                            c['locator'].get('section_index', 0),
                                            c['locator'].get('char_start', 0)))
    for chunk in ordered:
        text = chunk['text']
        lines = list(re.finditer(r'[^\n]+', text))
        # DB chunks start with a "SYMBOL | title | PDF trang N" header that is not page content.
        if chunk['locator'].get('kind') == 'db_text_span' and lines:
            lines = lines[1:]
        target = pages.setdefault((chunk['document_id'], chunk['locator']['page']), [])
        target.extend((chunk, m.start(), m.end(), m.group()) for m in lines if not _is_menu(m.group()))
    return pages


def _cite(lines):
    """One quote per chunk, each an exact substring of that chunk's text."""
    by_chunk = {}
    for chunk, start, end, _ in lines:
        span = by_chunk.setdefault(chunk['chunk_id'], [chunk, start, end])
        span[1], span[2] = min(span[1], start), max(span[2], end)
    return [{'document_id': chunk['document_id'], 'chunk_id': chunk['chunk_id'],
             'quote': chunk['text'][start:end]} for chunk, start, end in by_chunk.values()]


def table_rows(chunks, registry, index):
    """Yield parsed rows: dict(kind, label, parent, child, percent, as_of, evidence, reason, ...).

    parent is an entity_id, 'ISSUER' (the report's own company) or 'UNRESOLVED'.
    Rows with a reason are diagnostics, never relations.
    """
    by_first = name_index(registry)
    pages = _page_lines(chunks)
    section, as_of, previous_page = None, None, None
    for (document_id, page), lines in sorted(pages.items(), key=lambda item: (item[0][0], item[0][1])):
        # A table may continue on the next page without repeating its heading.
        if previous_page != (document_id, page - 1) or (section and section.get('carried')):
            section, as_of = None, None
        elif section:
            section = dict(section, carried=True)
        previous_page = (document_id, page)
        index_line = 0
        while index_line < len(lines):
            chunk, start, end, text = lines[index_line]
            index_line += 1
            if _RESET.match(text):
                section, as_of = None, None
                continue
            heading = _heading(text, index)
            if heading:
                kind, label, parent = heading
                outer = section if parent and section and not section.get('nested') else (
                    section.get('outer') if section and section.get('nested') else None)
                section = {'kind': kind, 'label': label, 'parent': parent or 'ISSUER',
                           'nested': bool(parent), 'outer': outer,
                           'evidence': _cite([lines[index_line - 1]])}
                continue
            dated = _header_day(text)
            if dated:
                as_of = dated
                if section is not None:
                    section = dict(section, evidence=section['evidence'] + _cite([lines[index_line - 1]]))
                continue
            if section is None:
                continue
            numbered = _ROW_NUMBER.match(text)
            body = text[numbered.end():] if numbered else text
            share = _OWNER_TAIL.search(body) or _PCT_TAIL.search(body)
            legal = _LEGAL_START.search(body)
            if not share or not legal or legal.start() >= share.start():
                continue
            section['carried'] = False
            if numbered and section.get('nested'):
                # A numbered row belongs to the outer table again.
                section = section['outer'] or {**section, 'kind': None, 'nested': False, 'parent': 'ISSUER'}
            block = [lines[index_line - 1]]
            while index_line < len(lines) and len(block) < MAX_ROW_LINES:
                following = lines[index_line][3]
                follow_body = following[_ROW_NUMBER.match(following).end():] if _ROW_NUMBER.match(following) else following
                next_share = _OWNER_TAIL.search(follow_body) or _PCT_TAIL.search(follow_body)
                next_legal = _LEGAL_START.search(follow_body)
                if (_RESET.match(following) or _heading(following, index) or _header_day(following)
                        or (next_share and next_legal and next_legal.start() < next_share.start())):
                    break
                block.append(lines[index_line])
                index_line += 1
            # A side menu ("06 QUẢN TRỊ CÔNG TY") may precede the name: try each legal-form start.
            child, last, reason = None, 0, 'CHILD_UNRESOLVED'
            for start_match in _LEGAL_START.finditer(body, 0, share.start()):
                prefix_end = len(text) - len(body) + start_match.start()
                child, last, reason = _row_name([text[prefix_end:]] + [line[3] for line in block[1:]], by_first)
                if child or reason == 'CHILD_AMBIGUOUS':
                    break
            parent = section['parent']
            if _OWNER_TAIL.search(body):
                parent = _owner(body[:share.start()], index) or 'UNRESOLVED'
            if reason is None and section['kind'] is None:
                reason = 'SECTION_KIND_AMBIGUOUS'
            if reason is None and parent == 'UNRESOLVED':
                reason = 'PARENT_UNRESOLVED'
            if reason is None and parent == child:
                reason = 'CHILD_IS_PARENT'
            yield {'document_id': document_id, 'page': page, 'kind': section['kind'],
                   'label': section['label'], 'parent': parent, 'child': child,
                   'percent': share.group('p'), 'as_of': as_of, 'reason': reason,
                   'line': text.strip(), 'chunk_id': chunk['chunk_id'],
                   # Quote the row only up to the last line that spells the name.
                   'evidence': section['evidence'] + _cite(block[:last + 1])}
