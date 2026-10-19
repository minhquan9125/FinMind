"""Small session adapter around the fixture B1 and evidence gates."""
from __future__ import annotations
import copy
from datetime import date, datetime, timedelta, timezone
import re
import unicodedata
import uuid
from .intent import METRICS, TICKERS, analyze
from .orchestrator import orchestrate
LABELS = {'TOTAL_ASSETS': 'Tổng tài sản', 'PROFIT_BEFORE_TAX': 'Lợi nhuận trước thuế', 'PROFIT_AFTER_TAX': 'Lợi nhuận sau thuế', 'CASH_FLOW_OPERATING': 'Lưu chuyển tiền thuần từ hoạt động kinh doanh'}
STOP_WORDS = set('nam nay sau cho con xem cua moi bao loi doi sang hay dau voi hoi gia von ngay quy thue truoc tong tai san nhuan dong tien the nao khi can ban toi gi bao nhieu cong vang hello yes'.split())

def _fold(text: str) -> str:
    value = unicodedata.normalize('NFKD', text.lower().replace('đ', 'd'))
    return ' '.join(''.join((c for c in value if not unicodedata.combining(c))).split())

def _resolve_relative_periods(text: str, today: date) -> str:
    """Resolve relative date expressions to explicit periods."""
    folded = _fold(text)
    year = today.year
    month = today.month
    previous_year = year - 1
    if month <= 3:
        previous_quarter = 4
        previous_quarter_year = year - 1
    else:
        previous_quarter = (month - 1) // 3
        previous_quarter_year = year
    current_quarter = (month - 1) // 3 + 1
    replacements = [('\\bnam nay\\b', f'năm {year}'), ('\\bnam ngoai\\b', f'năm {previous_year}'), ('\\bnam truoc\\b', f'năm {previous_year}'), ('\\bquy nay\\b', f'quý {current_quarter}/{year}'), ('\\bquy truoc\\b', f'quý {previous_quarter}/{previous_quarter_year}')]
    result = folded
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result

def _unknown(text: str, slot_reply: bool) -> str | None:
    normalized = _fold(text).strip(' .?!')
    tokens = re.findall('\\b[A-Z]{3,5}\\b', text)
    pattern = '\\b(?:ma(?: ck| co phieu)?|co phieu|loi nhuan(?: sau thue| truoc thue)?|tong tai san|doanh thu)(?: cua)?\\s+([a-z]{3,5})\\b'
    tokens += re.findall(pattern, normalized)
    if re.search('\\b(?:loi nhuan|tong tai san|doanh thu|dong tien)\\b', normalized):
        tokens += re.findall('\\bcua\\s+([a-z]{3,5})\\b', normalized)
    if slot_reply and text.isascii() and re.fullmatch('[a-z]{3}', normalized):
        tokens.append(normalized)
    correction = re.fullmatch('(?:(?:khong|ko|k),?\\s*)?(?:la|doi(?: ma)?(?: sang)?|con)\\s+([a-z]{3})(?:\\s+thi\\s+sao)?', normalized)
    if correction:
        tokens.append(correction[1])
    if slot_reply:
        tokens += re.findall('(?:^|[,\\s])([a-z]{3})(?=\\s*(?:,|sau thue|truoc thue|nam\\s+\\d|quy\\s+\\d))', normalized)
    for token in tokens:
        if token.lower() not in STOP_WORDS and token.upper() not in (*TICKERS, 'BCTC', 'BCTN', 'YTD'):
            return token.upper()
    return None

def _period_words(period: dict | None) -> str:
    if not period:
        return ''
    raw = period['raw']
    if period['measure_basis'] == 'YTD':
        return 'lũy kế ' + raw if period['granularity'] == 'QUARTER' else f"6 tháng đầu {period['year']}"
    return raw

def _is_natural_correction(normalized: str) -> bool:
    """Detect natural correction patterns."""
    patterns = ['^(?:khong|ko|k),?\\s*(?:la|doi(?: sang)?)\\s+', '^y toi la\\b', '^con\\s+[a-z]{3}\\b', '^doi(?: chi tieu)?(?: sang)?\\b']
    return any((re.search(p, normalized) for p in patterns))

def _single_slot_update(text: str) -> dict | None:
    """Parse slot updates, handling corrections that reference existing slots."""
    value = text.strip(' .?!')
    normalized = _fold(value)
    correction_match = re.fullmatch('(?:(?:khong|ko|k),?\\s*)?(?:la|doi(?: sang)?)\\s+([a-z]{3})', normalized)
    if correction_match and correction_match.group(1).upper() in TICKERS:
        return {'company': correction_match.group(1).upper()}
    period_correction = re.fullmatch('y toi la\\s+(.*)', normalized)
    if period_correction:
        inner = period_correction.group(1)
        if re.fullmatch('(?:nam\\s*)?(?:19|20|21)\\d{2}', inner):
            return {'period': inner.replace('nam ', 'năm ')}
        if re.fullmatch('(?:quy|q)\\s*\\d+\\s*[/\\s-]\\s*\\d{4}', inner):
            return {'period': inner}
    con_match = re.fullmatch('con\\s+([a-z]{3})(?:\\s+thi\\s+sao)?', normalized)
    if con_match and con_match.group(1).upper() in TICKERS:
        return {'company': con_match.group(1).upper()}
    doi_match = re.match('^doi(?: chi tieu)?(?: sang)?\\s+(.+)$', normalized)
    if doi_match:
        metric_text = doi_match.group(1)
        if metric_text in ('sau thue', 'truoc thue'):
            return {'metric': 'lợi nhuận ' + metric_text}
        for aliases in METRICS.values():
            if metric_text in aliases:
                return {'metric': aliases[0]}
        if metric_text in ('loi nhuan', 'doanh thu', 'dong tien'):
            return {'metric': metric_text}
    match = re.fullmatch('(?:(?:doi(?: ma)?(?: sang)?|chuyen sang|con|ma(?: ck| co phieu)?(?: la)?)\\s+)?([a-z]{3})', value)
    if match and match.group(1).upper() in TICKERS:
        return {'company': match.group(1).upper()}
    if re.fullmatch('(?:nam\\s*)?(?:19|20|21)\\d{2}|(?:quy|q)\\s*\\d+\\s*[/ -]\\s*\\d{4}|\\d{1,2}[/-]\\d{1,2}[/-]\\d{4}|(?:luy ke\\s+)?6 thang dau(?: nam)?\\s+\\d{4}', value):
        return {'period': value}
    value = re.sub('^doi (?:chi tieu )?(?:sang )?', '', value)
    if value in ('sau thue', 'truoc thue'):
        return {'metric': 'lợi nhuận ' + value}
    for aliases in METRICS.values():
        if value in aliases:
            return {'metric': aliases[0]}
    if value in ('loi nhuan', 'doanh thu', 'dong tien'):
        return {'metric': value}
    if value in ('hop nhat', 'bao cao hop nhat', 'rieng', 'bao cao rieng', 'cong ty me'):
        return {'entity': 'hop nhat' if 'hop nhat' in value else 'rieng'}
    return None
PERIOD_RE = re.compile('(?:luy ke\\s+)?(?:quy|q)\\s*\\d+\\s*[/ -]\\s*\\d{4}|\\d{1,2}[/-]\\d{1,2}[/-]\\d{4}|(?:luy ke\\s+)?6 thang dau(?: nam)?\\s+\\d{4}|(?:nam\\s*)?(?:19|20|21)\\d{2}')
ENTITY_RE = re.compile('\\b(?:bao cao )?(?:hop nhat|rieng|cong ty me)\\b')

def _choices(text: str) -> dict | None:
    companies = list(dict.fromkeys(re.findall('\\b(?:' + '|'.join((t.lower() for t in TICKERS)) + ')\\b', text)))
    if len(companies) > 1 and (not re.search('\\b(?:so sanh|compare)\\b', text)):
        return {'type': 'company', 'choices': [v.upper() for v in companies]}
    if 'truoc thue' in text and 'sau thue' in text:
        return {'type': 'metric', 'choices': ['trước thuế', 'sau thuế']}
    periods = list(dict.fromkeys((m.group() for m in PERIOD_RE.finditer(text))))
    if len(periods) > 1 and (not re.search('\\b(?:so sanh|compare|xu huong|trend)\\b', text)):
        return {'type': 'period', 'choices': periods}
    entities = {'hop nhat' if 'hop nhat' in m.group() else 'rieng' for m in ENTITY_RE.finditer(text)}
    if len(entities) > 1:
        return {'type': 'entity', 'choices': ['hợp nhất', 'riêng']}
    return None

def _slot_update(text: str, parts: dict | None=None) -> dict | None:
    """Consume only a clear slot-only reply, never arbitrary residual prose."""
    value = text.strip(' .?!')
    single = _single_slot_update(value)
    if single:
        return single
    explicit = _is_natural_correction(value)
    remainder = re.sub('^(?:y toi la|khong,?\\s*la|doi(?: chi tieu)?(?: sang)?)\\s+', '', value)
    updates = {}
    companies = re.findall('\\b(?:' + '|'.join((t.lower() for t in TICKERS)) + ')\\b', remainder)
    if len(set(companies)) > 1:
        return None
    if companies:
        updates['company'] = companies[0].upper()
        remainder = re.sub('\\b' + companies[0] + '\\b', ' ', remainder)
    periods = list(PERIOD_RE.finditer(remainder))
    if len(periods) > 1:
        return None
    if periods:
        updates['period'] = periods[0].group()
        remainder = remainder[:periods[0].start()] + ' ' + remainder[periods[0].end():]
    entities = list(ENTITY_RE.finditer(remainder))
    if entities:
        updates['entity'] = 'hop nhat' if 'hop nhat' in entities[0].group() else 'rieng'
        remainder = ENTITY_RE.sub(' ', remainder)
    full_metric = False
    aliases = sorted(((alias, values[0]) for values in METRICS.values() for alias in values), key=lambda pair: -len(pair[0]))
    for alias, canonical in aliases:
        pattern = '\\b' + re.escape(alias) + '\\b'
        if re.search(pattern, remainder):
            updates['metric'] = canonical
            full_metric = True
            remainder = re.sub(pattern, ' ', remainder)
            break
    if 'metric' not in updates:
        for phrase in ('sau thue', 'truoc thue', 'loi nhuan', 'doanh thu', 'dong tien'):
            if re.search('\\b' + phrase + '\\b', remainder):
                updates['metric'] = 'loi nhuan ' + phrase if phrase in ('sau thue', 'truoc thue') else phrase
                full_metric = phrase in ('loi nhuan', 'doanh thu', 'dong tien')
                remainder = re.sub('\\b' + phrase + '\\b', ' ', remainder)
                break
    if full_metric and ('company' in updates or 'period' in updates) and (not explicit):
        return None
    remainder = re.sub('\\b(?:va|cho|ma|la|cua|di|thoi|thi|sao|doi|sang|toi|nhung)\\b', ' ', remainder)
    return updates if updates and (not remainder.strip(' ,')) else None

class ChatSession:
    """Memory belongs only to this session; explicit new questions replace it."""

    def __init__(self, session_id: str | None=None, today: date | None=None) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.today = today or datetime.now(timezone(timedelta(hours=7))).date()
        self.reset()

    def reset(self) -> None:
        self._active: dict | None = None
        self._parts: dict | None = None
        self._unknown_company: str | None = None
        self._last_decision: dict | None = None
        self._last_result: dict | None = None

    @property
    def last_decision(self) -> dict | None:
        return copy.deepcopy(self._last_decision)

    @property
    def last_result(self) -> dict | None:
        return copy.deepcopy(self._last_result)

    def context_summary(self) -> str:
        """Return readable Vietnamese summary of current active scope."""
        if not self._active:
            return 'Không có câu hỏi đang diễn ra.'
        scope = self._active.get('scope', {})
        current = self._parts or {'company': ', '.join(scope.get('companies', [])), 'metric': LABELS.get(scope.get('metric_code'), scope.get('topic') or ''), 'period': ', '.join(scope.get('periods', [])), 'entity': scope.get('reporting_entity') if scope.get('reporting_entity') != 'UNKNOWN' else ''}
        parts = []
        if current.get('company'):
            parts.append(f"Công ty: {current['company']}")
        if current.get('metric'):
            metric = current['metric']
            parts.append('Chỉ tiêu: ' + next((LABELS[code] for code, aliases in METRICS.items() if metric in aliases), metric))
        if current.get('period'):
            parts.append(f"Kỳ: {current['period']}")
        if current.get('entity'):
            parts.append(f"Báo cáo: {current['entity']}")
        if not parts:
            return 'Không có câu hỏi đang diễn ra.'
        scope = self._active.get('scope', {})
        missing = self._active.get('missing_fields', [])
        summary = 'Đang hỏi: ' + ', '.join(parts) + '.'
        if self._unknown_company:
            summary += f' Mã {self._unknown_company} chưa được hỗ trợ; chờ mã trong phạm vi.'
        elif 'companies' in missing:
            summary += ' Chờ: công ty.'
        elif 'metric.code' in missing:
            summary += ' Chờ: chỉ tiêu cụ thể.'
        elif 'period' in missing:
            summary += ' Chờ: kỳ.'
        elif 'reporting_entity' in missing:
            summary += ' Chờ: báo cáo hợp nhất hay riêng.'
        return summary

    def _remember(self, decision: dict, question: str) -> None:
        if decision['decision'] not in ('SEARCH', 'ASK_CLARIFICATION') or not decision.get('scope'):
            return
        self._active = copy.deepcopy(decision)
        if decision['intent'] != 'FINANCIAL_METRIC':
            self._parts = None
            return
        scope = decision['scope']
        code = scope.get('metric_code')
        metric = METRICS[code][0] if code in METRICS else next((v for v in ('loi nhuan', 'doanh thu', 'dong tien') if v in question), '')
        self._parts = {'metric': metric, 'company': ' '.join(scope['companies']), 'period': _period_words(decision['slots']['period']), 'entity': {'CONSOLIDATED': 'hop nhat', 'PARENT': 'rieng'}.get(scope['reporting_entity'], '')}

    def _outside(self, ticker: str, question: str) -> dict:
        decision = analyze(question, self.session_id)
        decision.update(decision='OUT_OF_SCOPE', reason_code='UNKNOWN_TICKER', clarification_question=f"Mã {ticker} nằm ngoài phạm vi fixture. Các mã hỗ trợ: {', '.join(TICKERS)}.")
        decision['scope'] = {}
        return decision

    async def _run(self, text: str, decision: dict) -> dict:
        result = await orchestrate(text, self.session_id, analyzer=lambda *_: copy.deepcopy(decision))
        if result['status'] == 'ASK_CLARIFICATION':
            questions = {'companies': 'Bạn muốn xem công ty nào?', 'metric.code': 'Bạn muốn lợi nhuận trước thuế hay sau thuế?' if 'loi nhuan' in _fold(text) else 'Bạn muốn xem chỉ tiêu cụ thể nào?', 'period': 'Bạn muốn xem kỳ nào? Ví dụ: năm 2025 hoặc quý 2/2026.', 'period.measure_basis': 'Bạn muốn số riêng quý hay lũy kế từ đầu năm?', 'reporting_entity': 'Bạn muốn báo cáo hợp nhất hay báo cáo riêng?', 'topic': 'Bạn muốn xem chủ đề nào trong báo cáo thường niên?'}
            missing = decision.get('missing_fields', [])
            question = next((message for key, message in questions.items() if key in missing), None)
            if question:
                result.update(message=question, clarification=question)
        self._last_decision = copy.deepcopy(decision)
        self._last_result = copy.deepcopy(result)
        return result

    async def ask(self, text: str) -> dict:
        original = text.strip()
        if not original:
            return self.last_result or await orchestrate('', self.session_id)
        resolved = _resolve_relative_periods(original, self.today)
        normalized = _fold(resolved)
        direct = analyze(normalized, self.session_id)
        if direct['decision'] == 'UNSUPPORTED' or direct['reason_code'] in ('SOURCE_NOT_APPROVED', 'SOURCE_CONFLICT'):
            return await self._run(original, direct)
        update = _slot_update(normalized, self._parts)
        reference = normalized.strip(' .?!') in ('chu de truoc', 'cau hoi truoc', 'tiep tuc')
        unknown = _unknown(original, bool(self._active))
        multi = _choices(normalized)
        if multi:
            if multi['type'] == 'company':
                question = f"Bạn muốn xem công ty nào: {multi['choices'][0]} hay {multi['choices'][1]}?"
            elif multi['type'] == 'metric':
                question = 'Bạn muốn lợi nhuận trước thuế hay sau thuế?'
            elif multi['type'] == 'period':
                question = 'Bạn muốn chọn kỳ nào? ' + ', '.join(multi['choices'])
            else:
                question = 'Bạn muốn báo cáo hợp nhất hay báo cáo riêng?'
            if not self._active:
                cleaned = normalized
                for choice in multi['choices']:
                    cleaned = re.sub('\\b' + re.escape(_fold(choice)) + '\\b', ' ', cleaned)
                cleaned = re.sub('\\b(?:hoac|hay)\\b', ' ', cleaned)
                self._remember(analyze(cleaned, self.session_id), cleaned)
            direct['decision'] = 'ASK_CLARIFICATION'
            direct['clarification_question'] = question
            direct['missing_fields'] = []
            direct['reason_code'] = 'MULTI_INTENT_SPLIT_REQUIRED'
            direct['scope'] = copy.deepcopy(self._active.get('scope', {})) if self._active else {}
            return await self._run(original, direct)
        if unknown:
            if not update and direct.get('scope'):
                cleaned = re.sub('\\b' + re.escape(unknown.lower()) + '\\b', '', normalized)
                self._remember(analyze(cleaned, self.session_id), cleaned)
            if self._parts:
                self._parts['company'] = ''
            self._unknown_company = unknown
            return await self._run(original, self._outside(unknown, normalized))
        if reference and self._unknown_company:
            return await self._run(original, self._outside(self._unknown_company, normalized))
        if direct.get('scope') and direct['intent'] == 'FINANCIAL_METRIC':
            scope = direct['scope']
            has_company = bool(scope.get('companies'))
            has_period = bool(scope.get('periods'))
            has_metric = bool(scope.get('metric_code'))
            if has_company and (not has_period) and has_metric:
                self._remember(direct, normalized)
                self._unknown_company = None
                return await self._run(normalized, direct)
        if self._active and (update or reference):
            if self._parts is None:
                if reference:
                    decision = copy.deepcopy(self._active)
                    decision['request_id'] = str(uuid.uuid4())
                    return await self._run(original, decision)
                direct = analyze('', self.session_id)
                direct['clarification_question'] = 'Vui lòng nhập đầy đủ câu hỏi so sánh, xu hướng hoặc BCTN đã cập nhật.'
                return await self._run(original, direct)
            parts = copy.deepcopy(self._parts)
            parts.update(update or {})
            self._parts = copy.deepcopy(parts)
            if update and 'company' in update:
                self._unknown_company = None
            if self._unknown_company:
                return await self._run(original, self._outside(self._unknown_company, normalized))
            question = ' '.join(parts.values())
            decision = analyze(question, self.session_id)
            for company in decision['slots']['companies']:
                company['origin'] = 'CLARIFICATION' if update and 'company' in update else 'SESSION_CONTEXT'
            for field, key in (('metric', 'metric'), ('period', 'period')):
                value = decision['slots'].get(field)
                if isinstance(value, dict):
                    value['origin'] = 'CLARIFICATION' if update and key in update else 'SESSION_CONTEXT'
            self._remember(decision, question)
            return await self._run(question, decision)
        if direct['reason_code'] == 'UNRECOGNIZED_INTENT':
            direct['clarification_question'] = 'Mình chưa hiểu yêu cầu này. Bạn có thể bổ sung mã, kỳ, chỉ tiêu cho câu đang hỏi, hoặc gõ /moi để bắt đầu lại.' if self._active else 'Bạn muốn tra cứu chỉ tiêu tài chính nào, của công ty nào?'
            return await self._run(original, direct)
        self._unknown_company = None
        if re.search('\\b(?:cong ty nay|cung ky)\\b', normalized) and self._active:
            context = {'session_id': self.session_id, 'confirmed': True, 'expired': False, 'last_resolved_query': copy.deepcopy(self._active)}
            direct = analyze(normalized, self.session_id, context)
        self._remember(direct, normalized)
        return await self._run(normalized, direct)

def render_response(result: dict) -> str:
    """Human text is separate from the unchanged machine envelope."""
    lines = [result.get('clarification') or result.get('message', '')]
    scope = result.get('scope', {})
    summary = []
    if scope.get('companies'):
        summary.append('Công ty: ' + ', '.join(scope['companies']))
    code = scope.get('metric_code')
    if code:
        summary.append('Chỉ tiêu: ' + LABELS.get(code, code))
    if scope.get('periods'):
        summary.append('Kỳ kết thúc: ' + ', '.join(scope['periods']))
    if summary:
        lines.append('Đã ghi nhận: ' + ' | '.join(summary))
    if result.get('status') == 'EVIDENCE_READY':
        items = result['evidence_pack']['items']
        lines.append(f'Có {len(items)} đoạn bằng chứng giả lập, chưa phải đáp án hay số liệu tài chính thật.')
        lines += ['  - ' + item['passage'] for item in items[:3]]
    return '\n'.join(lines)
