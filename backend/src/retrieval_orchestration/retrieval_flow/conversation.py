"""Small session adapter around the fixture B1 and evidence gates."""
from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone
import re
import unicodedata
import uuid

from .intent import METRICS, TICKERS, analyze
from .orchestrator import orchestrate

LABELS = {
    'TOTAL_ASSETS': 'Tổng tài sản', 'PROFIT_BEFORE_TAX': 'Lợi nhuận trước thuế',
    'PROFIT_AFTER_TAX': 'Lợi nhuận sau thuế',
    'CASH_FLOW_OPERATING': 'Lưu chuyển tiền thuần từ hoạt động kinh doanh',
}
STOP_WORDS = set('nam nay sau cho con xem cua moi bao loi doi sang hay dau voi hoi gia von ngay quy thue truoc tong tai san nhuan dong tien the nao khi can ban toi gi bao nhieu cong vang hello yes'.split())


def _fold(text: str) -> str:
    value = unicodedata.normalize('NFKD', text.lower().replace('đ', 'd'))
    return ' '.join(''.join(c for c in value if not unicodedata.combining(c)).split())


def _unknown(text: str, slot_reply: bool) -> str | None:
    normalized = _fold(text).strip(' .?!')
    tokens = re.findall(r'\b[A-Z]{3,5}\b', text)
    pattern = r'\b(?:ma(?: ck| co phieu)?|co phieu|loi nhuan(?: sau thue| truoc thue)?|tong tai san|doanh thu)(?: cua)?\s+([a-z]{3,5})\b'
    tokens += re.findall(pattern, normalized)
    if re.search(r'\b(?:loi nhuan|tong tai san|doanh thu|dong tien)\b', normalized):
        tokens += re.findall(r'\bcua\s+([a-z]{3,5})\b', normalized)
    if slot_reply and text.isascii() and re.fullmatch(r'[a-z]{3}', normalized):
        tokens.append(normalized)
    for token in tokens:
        if token.lower() not in STOP_WORDS and token.upper() not in (*TICKERS, 'BCTC', 'BCTN', 'YTD'):
            return token.upper()
    return None


def _period_words(period: dict | None) -> str:
    if not period:
        return ''
    raw = period['raw']
    if period['measure_basis'] == 'YTD':
        return ('luy ke ' + raw if period['granularity'] == 'QUARTER'
                else f"6 thang dau {period['year']}")
    return raw


def _slot_update(text: str) -> dict | None:
    value = text.strip(' .?!')
    match = re.fullmatch(r'(?:(?:doi(?: ma)?(?: sang)?|chuyen sang|con|ma(?: ck| co phieu)?(?: la)?)\s+)?([a-z]{3})', value)
    if match and match[1].upper() in TICKERS:
        return {'company': match[1].upper()}
    if re.fullmatch(r'(?:nam\s*)?(?:19|20|21)\d{2}|(?:quy|q)\s*\d+\s*[/ -]\s*\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{4}|(?:luy ke\s+)?6 thang dau(?: nam)?\s+\d{4}', value):
        return {'period': value}
    value = re.sub(r'^doi (?:chi tieu )?(?:sang )?', '', value)
    if value in ('sau thue', 'truoc thue'):
        return {'metric': 'loi nhuan ' + value}
    for aliases in METRICS.values():
        if value in aliases:
            return {'metric': aliases[0]}
    if value in ('loi nhuan', 'doanh thu', 'dong tien'):
        return {'metric': value}
    if value in ('hop nhat', 'bao cao hop nhat', 'rieng', 'bao cao rieng', 'cong ty me'):
        return {'entity': 'hop nhat' if 'hop nhat' in value else 'rieng'}
    return None


class ChatSession:
    """Memory belongs only to this session; explicit new questions replace it."""

    def __init__(self, session_id: str | None = None, today: date | None = None) -> None:
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

    def _remember(self, decision: dict, question: str) -> None:
        if decision['decision'] not in ('SEARCH', 'ASK_CLARIFICATION') or not decision.get('scope'):
            return
        self._active = copy.deepcopy(decision)
        if decision['intent'] != 'FINANCIAL_METRIC':
            self._parts = None
            return
        scope = decision['scope']
        code = scope.get('metric_code')
        metric = METRICS[code][0] if code in METRICS else next(
            (v for v in ('loi nhuan', 'doanh thu', 'dong tien') if v in question), '')
        self._parts = {
            'metric': metric, 'company': ' '.join(scope['companies']),
            'period': _period_words(decision['slots']['period']),
            'entity': {'CONSOLIDATED': 'hop nhat', 'PARENT': 'rieng'}.get(scope['reporting_entity'], ''),
        }

    def _outside(self, ticker: str, question: str) -> dict:
        decision = analyze(question, self.session_id)
        decision.update(decision='OUT_OF_SCOPE', reason_code='UNKNOWN_TICKER',
                        clarification_question=f'Mã {ticker} nằm ngoài phạm vi fixture. Các mã hỗ trợ: {", ".join(TICKERS)}.')
        decision['scope'] = {}
        return decision

    async def _run(self, text: str, decision: dict) -> dict:
        # The normal orchestrator still enforces query/index/schema/scope gates.
        result = await orchestrate(text, self.session_id,
            analyzer=lambda *_: copy.deepcopy(decision))
        if result['status'] == 'ASK_CLARIFICATION':
            questions = {
                'companies': 'Bạn muốn xem công ty nào?',
                'metric.code': 'Bạn muốn lợi nhuận trước thuế hay sau thuế?' if 'loi nhuan' in _fold(text) else 'Bạn muốn xem chỉ tiêu cụ thể nào?',
                'period': 'Bạn muốn xem kỳ nào? Ví dụ: năm 2025 hoặc quý 2/2026.',
                'period.measure_basis': 'Bạn muốn số riêng quý hay lũy kế từ đầu năm?',
                'reporting_entity': 'Bạn muốn báo cáo hợp nhất hay báo cáo riêng?',
                'topic': 'Bạn muốn xem chủ đề nào trong báo cáo thường niên?',
            }
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
        normalized = _fold(original)
        normalized = re.sub(r'\bnam nay\b', f'nam {self.today.year}', normalized)
        direct = analyze(normalized, self.session_id)
        # Advice and source gates take precedence over attempts to fill slots.
        if direct['decision'] == 'UNSUPPORTED' or direct['reason_code'] in ('SOURCE_NOT_APPROVED', 'SOURCE_CONFLICT'):
            return await self._run(original, direct)
        update = _slot_update(normalized)
        reference = normalized.strip(' .?!') in ('chu de truoc', 'cau hoi truoc', 'tiep tuc')
        unknown = _unknown(original, bool(self._active))
        if unknown:
            if not update and direct.get('scope'):
                # New financial question: retain its new period/metric, not the old company.
                cleaned = re.sub(r'\b' + re.escape(unknown.lower()) + r'\b', '', normalized)
                self._remember(analyze(cleaned, self.session_id), cleaned)
            if self._parts:
                self._parts['company'] = ''
            self._unknown_company = unknown
            return await self._run(original, self._outside(unknown, normalized))
        if reference and self._unknown_company:
            return await self._run(original, self._outside(self._unknown_company, normalized))
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
            # Chatter must never replace an unfinished financial question.
            direct['clarification_question'] = ('Mình chưa hiểu yêu cầu này. Bạn có thể bổ sung mã, kỳ, chỉ tiêu cho câu đang hỏi, '
                                                'hoặc gõ /moi để bắt đầu lại.' if self._active else
                                                'Bạn muốn tra cứu chỉ tiêu tài chính nào, của công ty nào?')
            return await self._run(original, direct)
        self._unknown_company = None
        if re.search(r'\b(?:cong ty nay|cung ky)\b', normalized) and self._active:
            context = {'session_id': self.session_id, 'confirmed': True, 'expired': False,
                       'last_resolved_query': copy.deepcopy(self._active)}
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
