"""Deterministic answers to historical price questions, computed from the daily price table.

Prices are structured data, so the numbers are never written by a model: a question is read into a small
request (symbols, fields, operation, period), the bars of that period are read from `price_bars`, and the
answer is a fixed sentence per kind of operation. A question this module cannot read is left alone (it
returns None) so the established chat flow handles it; a question it reads but cannot answer from the data
(no session that day, symbol without prices) gets a plain reason instead of a guess.
"""
from __future__ import annotations

import re
import time
import unicodedata
import uuid
from datetime import date, timedelta
from decimal import Decimal

from .metric_vocabulary import find_metrics, without_metrics


def fold(text):
    """Lower case without diacritics, so 'Giá' and 'gia' read alike."""
    decomposed = unicodedata.normalize('NFD', text.lower().replace('đ', 'd'))
    return re.sub(r'\s+', ' ', ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')).strip()

MAX_SYMBOLS = 5
WHOLE = (date(1900, 1, 1), date(2200, 1, 1))
SOURCE_LINE = ('Nguồn: dữ liệu giá giao dịch hằng ngày trong cơ sở dữ liệu '
               '(giá chưa điều chỉnh; đơn vị nghìn đồng/cổ phiếu).')

FIELD_NAME = {'open': 'giá mở cửa', 'high': 'giá cao nhất trong phiên', 'low': 'giá thấp nhất trong phiên',
              'close': 'giá đóng cửa', 'volume': 'khối lượng giao dịch', 'range': 'biên độ (cao − thấp)'}
DAY_ORDER = ('open', 'high', 'low', 'close', 'range', 'volume')

_DATE = re.compile(
    r'(?<![\d/-])(\d{1,2})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{4})(?!\d)'
    r'|\bngay\s+(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})\b'
    r'|\bngay\s+(\d{1,2})\s*(?:/|\s+thang\s+)(\d{1,2})\b(?!\s*(?:/|nam)\s*\d{4})')
_QUARTER = re.compile(r'\bquy\s*([1-4])(?:\s*(?:/|-|nam)?\s*((?:19|20)\d{2}))?')
_MONTH = re.compile(r'\bthang\s+(\d{1,2})(?:\s*(?:/|-|nam)?\s*((?:19|20)\d{2}))?')
_YEAR = re.compile(r'\bnam\s+((?:19|20)\d{2})\b|(?<![\d/])\b((?:19|20)\d{2})\b(?![\d/])')
_LAST_DAYS = re.compile(r'\b(\d{1,3})\s*ngay\s*(?:qua|gan day|gan nhat|vua qua|truoc do)\b')
_LAST_BARS = re.compile(r'\b(\d{1,3})\s*phien\s*(?:gan nhat|gan day|qua|cuoi|vua qua)\b')

_PRICE_WORD = re.compile(
    r'\bgia\b(?!\s+(?:tri|von|ban|thanh|muc tieu))|\bthi gia\b|\bkhoi luong\b|\bvolume\b|\bdong cua\b|\bmo cua\b'
    r'|\bbien do\b|\bthanh khoan\b|\bphien giao dich\b|\bclose\b|\bhighest\b|\blowest\b|\bgia co phieu\b')
_NOT_PRICE = re.compile(
    r'\b(?:nen mua|nen ban|gia muc tieu|tu van|tin tuc|ly do|vi sao|tai sao|nguyen nhan|du bao|du doan|'
    r'hom nay|hien tai|bay gio|luc nay|phien hop)\b')
_MAX = re.compile(r'\b(?:cao nhat|lon nhat|nhieu nhat|ky luc|dinh|max|highest|peak)\b')
_MIN = re.compile(r'\b(?:thap nhat|nho nhat|it nhat|min|lowest)\b')
_AVG = re.compile(r'\b(?:trung binh|average|avg)\b')
_SUM = re.compile(r'\btong\b')
_COUNT = re.compile(r'\bbao nhieu phien\b|\bso phien\b')
_CHANGE = re.compile(r'\b(?:chenh lech|bien dong|thay doi|tang|giam|so voi|so sanh|phan tram)\b|%')
_FIELDS = (('close', re.compile(r'\bdong cua\b|\bclose\b|\bchot phien\b')),
           ('open', re.compile(r'\bmo cua\b|\bopen\b')),
           ('volume', re.compile(r'\bkhoi luong\b|\bvolume\b|\bthanh khoan\b')),
           ('range', re.compile(r'\bbien do\b|\bchenh lech cao thap\b')),
           ('high', re.compile(r'\bhigh\b|\bcao\b(?! nhat)')),
           ('low', re.compile(r'\blow\b|\bthap\b(?! nhat)')))
_WHOLE = re.compile(r'\b(?:toan bo|toan ky|lich su|tat ca du lieu|toan thoi gian|tu truoc den nay|tu khi niem yet)\b')


class PriceQuestionError(ValueError):
    """The question names a price request that cannot be right (a date that does not exist)."""


def _month_bounds(year, month):
    return date(year, month, 1), date(year + (month == 12), month % 12 + 1, 1)


def _take_dates(norm, today):
    """Explicit calendar days, in order of appearance, and the text with them removed."""
    found, last_end, parts = [], 0, []
    for match in _DATE.finditer(norm):
        groups = match.groups()
        if groups[0]:
            day, month, year = groups[0:3]
        elif groups[3]:
            day, month, year = groups[3:6]
        else:
            day, month, year = groups[6], groups[7], None
        try:
            value = date(int(year), int(month), int(day)) if year else None
            if value is None:
                value = date(today.year, int(month), int(day))
                if value > today:
                    value = date(today.year - 1, int(month), int(day))
        except ValueError as exc:
            raise PriceQuestionError(f'Ngày {day}/{month}' + (f'/{year}' if year else '') + ' không tồn tại.') from exc
        found.append(value)
        parts.append(norm[last_end:match.start()])
        last_end = match.end()
    parts.append(norm[last_end:])
    return found, ' '.join(parts)


def _period(norm, today):
    """A calendar period named in words: (start, end_exclusive, label) or None."""
    quarter = _QUARTER.search(norm)
    if quarter:
        year = int(quarter[2]) if quarter[2] else today.year
        month = 3 * int(quarter[1]) - 2
        if not quarter[2] and date(year, month, 1) > today:
            year -= 1
        start = date(year, month, 1)
        end = date(year + (month == 10), (month + 3 - 1) % 12 + 1, 1)
        return start, end, f'quý {quarter[1]}/{year}'
    month = _MONTH.search(norm)
    if month:
        number = int(month[1])
        if not 1 <= number <= 12:
            raise PriceQuestionError(f'Tháng {number} không tồn tại.')
        year = int(month[2]) if month[2] else (today.year if number <= today.month else today.year - 1)
        start, end = _month_bounds(year, number)
        return start, end, f'tháng {number}/{year}'
    if re.search(r'\bnam nay\b', norm):
        return date(today.year, 1, 1), date(today.year + 1, 1, 1), f'năm {today.year}'
    if re.search(r'\bnam (?:ngoai|truoc)\b', norm):
        return date(today.year - 1, 1, 1), date(today.year, 1, 1), f'năm {today.year - 1}'
    if re.search(r'\btu dau nam\b', norm):
        return date(today.year, 1, 1), today + timedelta(days=1), f'từ đầu năm {today.year}'
    year = _YEAR.search(norm)
    if year:
        value = int(year[1] or year[2])
        return date(value, 1, 1), date(value + 1, 1, 1), f'năm {value}'
    return None


def _relative(norm, today):
    from .market_dates import relative_market_range
    ranged = relative_market_range(norm, today)
    if ranged:
        start, end = date.fromisoformat(ranged['start_day']), date.fromisoformat(ranged['end_day'])
        return start, end + timedelta(days=1), ('tháng này' if 'thang nay' in norm else
                                                 'tháng trước' if 'thang truoc' in norm else
                                                 'tuần này' if 'tuan nay' in norm else 'tuần trước')
    days = _LAST_DAYS.search(norm)
    if days:
        return today - timedelta(days=int(days[1])), today + timedelta(days=1), f'{days[1]} ngày qua'
    return None


def parse(question, symbols, today):
    """Read a price question into a request dict, or None when it is not one this module answers.

    `symbols` are the symbols that have prices. Raises PriceQuestionError for an impossible date.
    """
    from .hybrid_router.decision_engine import DEFAULT_COMPANIES, NON_COMPANY_CODES
    norm = fold(question).strip(' .?!')
    if _NOT_PRICE.search(norm):
        return None
    found = []
    for token in re.findall(r'\b[A-Z]{3,4}\b', question):
        if token in symbols and token not in NON_COMPANY_CODES and token not in found:
            found.append(token)
    for alias, names in DEFAULT_COMPANIES.items():
        if len(alias) > 3 and names[0] in symbols and names[0] not in found and re.search(r'\b' + re.escape(alias) + r'\b', norm):
            found.append(names[0])
    for token in re.findall(r'\b(?:cua|ma|co phieu|cp)\s+([a-z]{3,4})\b', norm):
        if token.upper() in symbols and token.upper() not in found:
            found.append(token.upper())
    # A company the chat knows but that has no prices here: say so instead of answering about something else.
    unknown = []
    for alias, names in DEFAULT_COMPANIES.items():
        if names[0] not in symbols and names[0] not in unknown and (
                re.search(r'\b' + re.escape(alias) + r'\b', norm) if len(alias) > 3 else names[0] in re.findall(r'\b[A-Z]{3}\b', question)):
            unknown.append(names[0])
    if not found and not unknown:
        return None
    rest = without_metrics(norm)
    moves = re.search(r'\b(?:tang|giam)\b', rest) and re.search(r'%|\bphan tram\b|\bbao nhieu\b', rest)
    # "VCB tăng bao nhiêu %" is about the share price, unless a financial item (doanh thu ...) is what rises.
    if not _PRICE_WORD.search(rest) and not (moves and not find_metrics(norm)):
        return None
    days, text = _take_dates(norm, today)
    ops = [name for name, pattern in (('max', _MAX), ('min', _MIN), ('avg', _AVG), ('sum', _SUM),
                                      ('count', _COUNT), ('change', _CHANGE)) if pattern.search(text)]
    fields = [name for name, pattern in _FIELDS if pattern.search(text)]
    period = None
    last_bars = _LAST_BARS.search(text)
    if len(days) >= 2 and re.search(r'\btu\b', text) and not re.search(r'\bso (?:voi|sanh)\b|\bgiua\b', text):
        period = (min(days), max(days) + timedelta(days=1), f'từ {min(days):%d/%m/%Y} đến {max(days):%d/%m/%Y}')
        days = []
    elif not days:
        period = _relative(text, today) or _period(text, today)
        if period is None and _WHOLE.search(text):
            period = (*WHOLE, 'toàn bộ dữ liệu')
    if last_bars:
        period = (*WHOLE, f'{last_bars[1]} phiên gần nhất')
    stat_ops = [op for op in ops if op in ('max', 'min', 'avg', 'sum', 'count')]
    if not days and period is None and stat_ops:
        period = (*WHOLE, 'toàn bộ dữ liệu')
    if not days and period is None:
        return None
    if len(found) > MAX_SYMBOLS:
        raise PriceQuestionError(f'Bạn hỏi {len(found)} mã; vui lòng hỏi tối đa {MAX_SYMBOLS} mã mỗi lần.')
    return {'symbols': found, 'unknown': unknown, 'symbols_available': sorted(symbols),
            'days': sorted(dict.fromkeys(days)), 'period': period, 'ops': ops, 'fields': fields,
            'high_word': bool(re.search(r'\bcao nhat\b', text)), 'low_word': bool(re.search(r'\bthap nhat\b', text)),
            'last_n': int(last_bars[1]) if last_bars else None}


# -- formatting ----------------------------------------------------------------------------------------------
def _num(value, places=4):
    q = Decimal(value).quantize(Decimal(1).scaleb(-places))
    text = format(q.normalize(), 'f')
    sign = '-' if text.startswith('-') else ''
    whole, _, frac = text.lstrip('-').partition('.')
    return sign + f'{int(whole):,}'.replace(',', '.') + (',' + frac if frac else '')


def _day(value):
    return f'{value:%d/%m/%Y}'


def _value(bar, field):
    return bar['high'] - bar['low'] if field == 'range' else bar[field]


def _show(field, value):
    return f'{_num(value, 0)} cổ phiếu' if field == 'volume' else f'{_num(value)} nghìn đồng'


def _percent(first, last):
    return (last - first) / first * Decimal(100) if first else None


def _movement(first, last, field):
    diff = last - first
    word = 'tăng' if diff > 0 else 'giảm' if diff < 0 else 'không đổi'
    if diff == 0:
        return 'không đổi'
    pct = _percent(first, last)
    unit = ' cổ phiếu' if field == 'volume' else ' nghìn đồng'
    base = f'{word} {_num(abs(diff), 0 if field == "volume" else 4)}{unit}'
    return base + (f' ({"+" if diff > 0 else "−"}{_num(abs(pct), 2)}%)' if pct is not None else '')


def _extreme_label(field, largest):
    if field == 'high' and largest:
        return 'Giá cao nhất'
    if field == 'low' and not largest:
        return 'Giá thấp nhất'
    word = ('lớn nhất' if largest else 'nhỏ nhất') if field in ('volume', 'range') else ('cao nhất' if largest else 'thấp nhất')
    return f'{FIELD_NAME[field].capitalize()} {word}'


def _stat_field(fields, op):
    explicit = [f for f in fields if f in ('close', 'open', 'volume', 'range')]
    if explicit:
        return explicit
    if op == 'max':
        return ['high']
    if op == 'min':
        return ['low']
    return ['close']


class PriceStore:
    """Reads the daily bars; a replaceable seam, so tests need no database."""

    def __init__(self, pool, *, ttl=600.0, clock=time.monotonic):
        self.pool, self.ttl, self.clock, self._symbols = pool, ttl, clock, None

    async def symbols(self):
        if self._symbols is None or self.clock() - self._symbols[0] > self.ttl:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch('SELECT DISTINCT c.symbol FROM public.companies c '
                                        'JOIN public.price_bars p USING(company_id)')
            self._symbols = (self.clock(), {r['symbol'] for r in rows})
        return self._symbols[1]

    async def bars(self, symbol, start, end):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT p.trade_date AS date, p.open, p.high, p.low, p.close, p.volume '
                'FROM public.price_bars p JOIN public.companies c USING(company_id) '
                'WHERE c.symbol=$1 AND p.trade_date>=$2 AND p.trade_date<$3 ORDER BY p.trade_date', symbol, start, end)
        return [dict(r) for r in rows]


class PriceAnalytics:
    def __init__(self, store, *, today=None):
        self.store, self._today = store, today

    async def answer(self, question, today=None):
        """A chat result for a price question, or None when the question is not one of these."""
        today = today or self._today or date.today()
        symbols = await self.store.symbols()
        try:
            spec = parse(question, symbols, today)
        except PriceQuestionError as exc:
            return self._plain_reply('PRICE_REQUEST_INVALID', str(exc), [])
        if spec is None:
            return None
        lines, empty = [], []
        for symbol in spec['symbols']:
            text = await self._one(symbol, spec)
            (empty if text.startswith('!') else lines).append(text.lstrip('!'))
        if spec['unknown']:
            empty.append(f"Chưa có dữ liệu giá của {', '.join(spec['unknown'])}. "
                         f"Hiện có giá của {len(spec['symbols_available'])} mã: {', '.join(spec['symbols_available'])}.")
        if not lines:
            return self._plain_reply('PRICE_NOT_AVAILABLE', ' '.join(empty), spec['symbols'])
        draft = '\n\n'.join(lines + empty) + '\n\n' + SOURCE_LINE
        return self._plain_reply('SUCCESS', draft, spec['symbols'], ready=True)

    def _plain_reply(self, reason, text, symbols, *, ready=False):
        result = dict(request_id=str(uuid.uuid4()), query_id=None, execution_mode='LIVE', b1_decision='PRICE_ANALYTICS',
                      status='EVIDENCE_READY' if ready else 'NO_DATA', reason_code=reason, message=text,
                      scope={'companies': list(symbols)} if symbols else {}, evidence_pack=None, errors=[],
                      retrieval_backend='price_bars', presentation={'sources': 'HIDDEN'})
        if ready:
            result['answering'] = {
                'status': 'DRAFT_READY', 'reason_code': 'PRICE_ANALYTICS',
                'message': 'Tính trực tiếp từ dữ liệu giá giao dịch; không dùng mô hình để tạo số.',
                'draft': text, 'claims': [], 'citations': [], 'cautions': [],
                'manifest': {'mode': 'B1', 'response_mode': 'PRICE_ANALYTICS',
                             'components': {'gemini': False, 'citation_binding': False,
                                            'b3_evidence_gate': False, 'b3_answer_verification': False}},
                'trace': [{'event': 'price_analytics'}]}
        return result

    # -- one symbol -------------------------------------------------------------------------------------
    async def _one(self, symbol, spec):
        if spec['days']:
            return await self._days(symbol, spec)
        start, end, label = spec['period']
        label = label if label.startswith('từ') else 'trong ' + label
        if not spec['ops']:
            return (f'!Bạn muốn xem gì về giá {symbol} {label}? Hãy hỏi kèm phép tính, ví dụ: '
                    f'"Giá cao nhất của {symbol} {label}", "Khối lượng trung bình của {symbol} {label}" '
                    f'hoặc "{symbol} tăng hay giảm bao nhiêu % {label}".')
        bars = await self.store.bars(symbol, start, end)
        if spec['last_n']:
            bars = bars[-spec['last_n']:]
        if not bars:
            return f'!Không có phiên giao dịch của {symbol} {label}; dữ liệu giá của {symbol} chưa phủ giai đoạn này.'
        cover = f'{len(bars)} phiên, từ {_day(bars[0]["date"])} đến {_day(bars[-1]["date"])}'
        sentences = []
        for op in [o for o in spec['ops'] if o in ('max', 'min')]:
            for field in _stat_field(spec['fields'], op):
                pick = (max if op == 'max' else min)(bars, key=lambda b: (_value(b, field), -b['date'].toordinal()))
                sentences.append(f'{_extreme_label(field, op == "max")} của {symbol} {label} là '
                                 f'{_show(field, _value(pick, field))}, vào ngày {_day(pick["date"])}.')
        for op in [o for o in spec['ops'] if o in ('avg', 'sum')]:
            for field in _stat_field(spec['fields'], op):
                if field == 'range' and op == 'sum':
                    continue
                values = [_value(b, field) for b in bars]
                total = sum(values, Decimal(0))
                if op == 'avg':
                    unit = 'cổ phiếu/phiên' if field == 'volume' else 'nghìn đồng'
                    sentences.append(f'{FIELD_NAME[field].capitalize()} trung bình của {symbol} {label} là '
                                     f'{_num(total / len(values), 0 if field == "volume" else 4)} {unit}.')
                elif field == 'volume':
                    sentences.append(f'Tổng khối lượng giao dịch của {symbol} {label} là {_num(total, 0)} cổ phiếu.')
        if 'count' in spec['ops']:
            sentences.append(f'{symbol} có {len(bars)} phiên giao dịch {label}.')
        if 'change' in spec['ops'] and not sentences:
            first, last = bars[0], bars[-1]
            field = (_stat_field(spec['fields'], 'change')[0])
            sentences.append(f'{FIELD_NAME[field].capitalize()} của {symbol} {label}: từ {_show(field, _value(first, field))} '
                             f'({_day(first["date"])}) đến {_show(field, _value(last, field))} ({_day(last["date"])}), '
                             f'{_movement(_value(first, field), _value(last, field), field)}.')
        if not sentences:
            return f'!Chưa hiểu phép tính cần làm với giá của {symbol}; hãy nêu rõ cao nhất, thấp nhất, trung bình hoặc so sánh.'
        return ' '.join(sentences) + f' (Tính trên {cover}.)'

    async def _days(self, symbol, spec):
        found, notes = [], []
        for day in spec['days']:
            bars = await self.store.bars(symbol, day, day + timedelta(days=1))
            if bars:
                found.append(bars[0])
                continue
            earlier = (await self.store.bars(symbol, day - timedelta(days=10), day))[-1:]
            later = await self.store.bars(symbol, day, day + timedelta(days=10))
            if day.weekday() >= 5:
                why = 'là cuối tuần'
            elif later:
                why = 'là ngày nghỉ, không có phiên'
            else:
                why = 'nằm ngoài khoảng dữ liệu giá hiện có'
            hint = f' Phiên gần nhất trước đó là {_day(earlier[0]["date"])}.' if earlier else ''
            notes.append(f'{symbol} không có phiên giao dịch ngày {_day(day)}: ngày này {why}.{hint}')
        if not found:
            return '!' + ' '.join(notes)
        wanted = set(spec['fields'])
        if len(found) == 1:
            # On one day "cao nhất / thấp nhất" name that day's high and low.
            wanted = wanted | ({'high'} if spec['high_word'] else set()) | ({'low'} if spec['low_word'] else set())
            fields = [f for f in DAY_ORDER if f in wanted] or [f for f in DAY_ORDER if f != 'range']
            bar = found[0]
            parts = [f'{FIELD_NAME[f]} {_show(f, _value(bar, f))}' for f in fields]
            text = f'{symbol} phiên {_day(bar["date"])}: ' + '; '.join(parts) + '.'
        else:
            fields = [f for f in DAY_ORDER if f in wanted] or ['close']
            sentences = []
            for field in fields:
                values = ', '.join(f'ngày {_day(b["date"])} là {_show(field, _value(b, field))}' for b in found)
                sentence = f'{FIELD_NAME[field].capitalize()} của {symbol} {values}'
                if len(found) == 2:
                    sentence += f': {_movement(_value(found[0], field), _value(found[1], field), field)}'
                sentences.append(sentence + '.')
            text = ' '.join(sentences)
        return text + (' ' + ' '.join(notes) if notes else '')
