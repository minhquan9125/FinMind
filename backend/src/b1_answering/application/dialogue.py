"""Context-aware facade; unsupported scope never reaches retrieval."""
from copy import deepcopy
from datetime import date
import calendar
import re
import unicodedata
import uuid

ALIASES = {'lnst': 'loi nhuan sau thue', 'lntt': 'loi nhuan truoc thue',
           'tts': 'tong tai san', 'ln': 'loi nhuan'}
METRICS = {
    'TOTAL_ASSETS': ('tổng tài sản', r'\btong tai san\b', True),
    'PROFIT_BEFORE_TAX': ('lợi nhuận trước thuế', r'\bloi nhuan truoc thue\b', True),
    'PROFIT_AFTER_TAX': ('lợi nhuận sau thuế', r'\bloi nhuan sau thue\b', True),
    'CASH_FLOW_OPERATING': ('lưu chuyển tiền thuần từ hoạt động kinh doanh', r'\bluu chuyen tien thuan tu hoat dong kinh doanh\b', True),
    'PROFIT': ('lợi nhuận', r'\bloi nhuan\b', True),
    'DEBT': ('nợ phải trả', r'\b(?:tong no|no(?: phai tra)?)\b', False),
    'REVENUE': ('doanh thu', r'\bdoanh thu\b', False),
    'EQUITY': ('vốn chủ sở hữu', r'\bvon chu so huu\b', False),
    'EPS': ('EPS', r'\beps\b', False), 'ROE': ('ROE', r'\broe\b', False),
    'ROA': ('ROA', r'\broa\b', False), 'PE': ('P/E', r'\bp\s*/?\s*e\b', False),
    'PB': ('P/B', r'\bp\s*/?\s*b\b', False),
}
SHORT_PROFIT = {'sau': 'PROFIT_AFTER_TAX', 'sau thue': 'PROFIT_AFTER_TAX', 'st': 'PROFIT_AFTER_TAX',
                'truoc': 'PROFIT_BEFORE_TAX', 'truoc thue': 'PROFIT_BEFORE_TAX',
                'trc': 'PROFIT_BEFORE_TAX', 'tt': 'PROFIT_BEFORE_TAX'}


def normalize(text):
    folded = unicodedata.normalize('NFKD', text.lower().replace('đ', 'd'))
    folded = ' '.join(''.join(c for c in folded if not unicodedata.combining(c)).split())
    folded = re.sub(r'\b(nam|ngay|quy)(?=\d)', r'\1 ', folded)
    folded = re.sub(r'\b([a-z]{3})(?=(?:19|20|21)\d{2}\b)', r'\1 ', folded)
    return re.sub(r'\b(?:lnst|lntt|tts|ln)\b', lambda m: ALIASES[m[0]], folded)


def indicators(text):
    found = [code for code, (_, pattern, _) in METRICS.items() if re.search(pattern, text)]
    if 'PROFIT' in found and any(code in found for code in ('PROFIT_BEFORE_TAX', 'PROFIT_AFTER_TAX')):
        found.remove('PROFIT')
    # A tax modifier with a different indicator is ambiguous, never silently attached to debt/assets.
    if found and not any(code.startswith('PROFIT') for code in found):
        for phrase, code in (('sau thue', 'PROFIT_AFTER_TAX'), ('truoc thue', 'PROFIT_BEFORE_TAX')):
            if re.search(r'\b' + phrase + r'\b', text):
                found.append(code)
    return found


def period(text):
    dates = list(re.finditer(r'\b(\d{1,2})[/-](\d{1,2})[/-]((?:19|20|21)\d{2})\b', text))
    if dates:
        try:
            ends = [date(int(m[3]), int(m[2]), int(m[1])).isoformat() for m in dates]
        except ValueError:
            return '', [], 'INVALID_DATE'
        return ' '.join(m[0] for m in dates), list(dict.fromkeys(ends)), None
    quarter = re.search(r'\b(?:quy|q)\s*([0-9]+)\s*(?:/|-|nam|\s)\s*((?:19|20|21)\d{2})\b', text)
    if quarter:
        q, year = int(quarter[1]), int(quarter[2])
        if not 1 <= q <= 4:
            return '', [], 'INVALID_DATE'
        raw = ('luy ke ' if 'luy ke' in text else '') + f'quy {q}/{year}'
        return raw, [date(year, q * 3, calendar.monthrange(year, q * 3)[1]).isoformat()], None
    years = list(dict.fromkeys(re.findall(r'\b(?:19|20|21)\d{2}\b', text)))
    return ' '.join('nam ' + y for y in years), [y + '-12-31' for y in years], None


class DialogueSession:
    def __init__(self, session_id=None, today=None):
        from src.retrieval_orchestration.retrieval_flow.conversation import ChatSession
        from src.retrieval_orchestration.retrieval_flow.intent import TICKERS
        self._core = ChatSession(session_id=session_id, today=today)
        self._tickers = TICKERS
        self.session_id = self._core.session_id
        self.reset()

    def reset(self):
        self._core.reset()
        self._last = None
        self._options = []
        self._selected = None
        self._custom_context = False
        self._context = {'companies': [], 'periods': [], 'period_text': '', 'entity': ''}

    @property
    def last_result(self):
        return deepcopy(self._last)

    def context_summary(self):
        return self._summary() if self._custom_context else self._core.context_summary()

    def _summary(self):
        parts = []
        if self._context['companies']:
            parts.append('Công ty: ' + ', '.join(self._context['companies']))
        if self._context['periods']:
            parts.append('Kỳ: ' + ', '.join(self._context['periods']))
        return ' | '.join(parts)

    def _envelope(self, status, reason, message):
        scope = {'companies': list(self._context['companies']), 'periods': list(self._context['periods']),
                 'metric_code': None, 'topic': None, 'measure_basis': None,
                 'reporting_entity': 'UNKNOWN', 'source_type': 'BCTC'}
        detail = self._summary()
        message += (' Đã ghi nhận: ' + detail + '.') if detail else ''
        self._last = {'request_id': str(uuid.uuid4()), 'query_id': None, 'execution_mode': 'FIXTURE',
                      'b1_decision': status, 'status': status, 'reason_code': reason, 'message': message,
                      'scope': scope, 'clarification': message if status == 'ASK_CLARIFICATION' else None,
                      'evidence_pack': None, 'errors': []}
        return deepcopy(self._last)

    def _explicit(self, text):
        companies = [ticker for ticker in self._tickers if re.search(r'\b' + ticker.lower() + r'\b', text)]
        if not companies:
            unknown = re.search(r'\b(?:cua|ma|co phieu)\s+([a-z]{3})\b', text)
            if unknown and unknown[1] not in ('nam', 'quy', 'loi', 'no', 'eps', 'roe', 'roa'):
                companies = [unknown[1].upper()]
        raw, ends, error = period(text)
        entity = 'hop nhat' if 'hop nhat' in text else 'rieng' if re.search(r'\b(?:rieng|cong ty me)\b', text) else ''
        return companies, raw, ends, error, entity

    def _merge(self, companies, raw, ends, entity):
        if companies:
            self._context['companies'] = companies
        if raw:
            self._context.update(period_text=raw, periods=ends)
        if entity:
            self._context['entity'] = entity

    def _awaiting_profit(self):
        if self._options or not self._last or self._last['status'] != 'ASK_CLARIFICATION':
            return False
        decision = self._core.last_decision or {}
        question = normalize(self._last.get('clarification') or '')
        return ('truoc thue' in question and 'sau thue' in question
                and 'metric.code' in decision.get('missing_fields', []))

    def _short_choice(self, text):
        text = re.sub(r'^(?:chon|lay|la|cho toi|cho minh|toi muon)\s+', '', text).strip(' .?!')
        text = re.sub(r'\s+(?:nhe|di|a|voi)$', '', text)
        correction = re.fullmatch(r'khong(?: phai)? (.+?)[, ]+(?:ma |la )?(.+)', text)
        if correction and correction[1] in SHORT_PROFIT and correction[2] in SHORT_PROFIT:
            return SHORT_PROFIT[correction[2]] if SHORT_PROFIT[correction[1]] != SHORT_PROFIT[correction[2]] else None
        return SHORT_PROFIT.get(text)

    async def _delegate(self, text):
        result = await self._core.ask(text)
        self._last = deepcopy(result)
        scope = result.get('scope') or {}
        if scope:
            decision = self._core.last_decision or {}
            value = decision.get('slots', {}).get('period') or {}
            raw = value.get('raw', '')
            if value.get('measure_basis') == 'YTD' and 'luy ke' not in normalize(raw):
                raw = 'luy ke ' + raw
            self._context.update(companies=list(scope.get('companies', [])), periods=list(scope.get('periods', [])),
                                 period_text=raw, entity={'CONSOLIDATED': 'hop nhat', 'PARENT': 'rieng'}.get(scope.get('reporting_entity'), ''))
        if result.get('reason_code') == 'UNKNOWN_TICKER':
            self._context['companies'] = []
        return deepcopy(result)

    def _ask_options(self):
        return self._envelope('ASK_CLARIFICATION', 'AMBIGUOUS_METRIC',
                              'Bạn muốn xem ' + ' hay '.join(METRICS[code][0] for code in self._options) + '?')

    async def _select(self, code):
        self._options = []
        self._selected = None
        self._custom_context = True
        label, _, supported = METRICS[code]
        if not supported:
            self._core.reset()
            return self._envelope('UNSUPPORTED', 'UNSUPPORTED_METRIC',
                                  f'Chỉ tiêu {label} chưa được hỗ trợ trong bản fixture. Có thể hỏi tổng tài sản, lợi nhuận trước/sau thuế hoặc dòng tiền hoạt động kinh doanh.')
        query = ' '.join([label, ' '.join(self._context['companies']), self._context['period_text'], self._context['entity']])
        self._core.reset()
        self._custom_context = False
        return await self._delegate(query)

    async def ask(self, text):
        text = text.strip() if isinstance(text, str) else ''
        if not text:
            return self.last_result or self._envelope('ASK_CLARIFICATION', 'INSUFFICIENT_INFORMATION', 'Bạn muốn hỏi chỉ tiêu nào, của công ty và kỳ nào?')
        if text == '/moi':
            self.reset()
            return self._envelope('ASK_CLARIFICATION', 'NEW_CONVERSATION', 'Bạn muốn hỏi chỉ tiêu nào, của công ty và kỳ nào?')
        norm = normalize(text)
        choice = self._short_choice(norm)
        if self._options and choice in self._options:
            if len(self._context['companies']) > 1 or len(self._context['periods']) > 1:
                self._selected = choice
                return self._envelope('ASK_CLARIFICATION', 'AMBIGUOUS_SCOPE', 'Bạn muốn chọn công ty và kỳ cụ thể nào?')
            return await self._select(choice)
        if self._awaiting_profit():
            if choice:
                return await self._delegate(METRICS[choice][0])
            if re.search(r'\bsau\b', norm) and re.search(r'\b(?:truoc|trc)\b', norm):
                self._options = ['PROFIT_BEFORE_TAX', 'PROFIT_AFTER_TAX']
                self._custom_context = True
                self._core.reset()
                return self._ask_options()
        if choice or norm == 'nam sau':
            return self._envelope('ASK_CLARIFICATION', 'INSUFFICIENT_INFORMATION',
                                  'Bạn muốn bổ sung chỉ tiêu hoặc kỳ nào? Vui lòng nói rõ theo câu hỏi đang hỏi.')
        # Preserve existing policy/source/reference decisions before financial normalization.
        if re.search(r'\b(?:nen mua|nen ban|gia muc tieu|tin tuc|bctn|bao cao thuong nien|nguon|citation)\b', norm):
            self._options = []
            return await self._delegate(norm)
        found = indicators(norm)
        companies, raw, ends, error, entity = self._explicit(norm)
        is_comparison = bool(re.search(r'\b(?:so sanh|compare|xu huong|trend)\b', norm))
        if self._options and len(found) == 1 and companies and raw:
            self._options, self._selected = [], None
            self._custom_context = False
            self._core.reset()
        # A new question with a named company replaces old missing fields; a pending option reply can update them.
        if found and companies and not self._options and not re.match(r'^(?:doi|con|khong|y toi)', norm):
            self._context = {'companies': [], 'periods': [], 'period_text': '', 'entity': ''}
            self._custom_context = False
        if len(found) == 1 and METRICS[found[0]][2] and is_comparison:
            self._options = []
            return await self._delegate(norm)
        self._merge(companies, raw, ends, entity)
        if error:
            return self._envelope('ASK_CLARIFICATION', error, 'Ngày hoặc kỳ chưa hợp lệ; bạn muốn chọn kỳ nào?')
        if len(found) > 1:
            self._options = found
            self._custom_context = True
            self._core.reset()
            return self._ask_options()
        if self._options:
            if self._selected and len(self._context['companies']) <= 1 and len(self._context['periods']) <= 1:
                return await self._select(self._selected)
            choices = found
            if choices == ['PROFIT']:
                choices = [code for code in self._options if code.startswith('PROFIT')]
            if len(choices) == 1 and choices[0] in self._options:
                if len(self._context['companies']) > 1 or len(self._context['periods']) > 1:
                    self._selected = choices[0]
                    return self._envelope('ASK_CLARIFICATION', 'AMBIGUOUS_SCOPE', 'Bạn muốn chọn công ty và kỳ cụ thể nào?')
                return await self._select(choices[0])
            return self._ask_options()
        if found and not METRICS[found[0]][2]:
            return await self._select(found[0])
        if self._custom_context:
            if found:
                return await self._select(found[0])
            return self._envelope('ASK_CLARIFICATION', 'INSUFFICIENT_INFORMATION', 'Bạn muốn xem chỉ tiêu cụ thể nào? Có thể dùng tên đầy đủ hoặc LNST/LNTT/TTS.')
        return await self._delegate(norm)
