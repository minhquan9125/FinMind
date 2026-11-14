"""S5-WBS07.2 over Nhân's v2 classifier: trust rule evidence, ask Gemini for guesses, never invent a label.

Ported from Huyền's 07.1 contract (intent_fallback_contract.py, 7 labels) to the 11-label schema
s5-intent-labels-v2: the same three wire fields, the 0.60 provider-confidence floor (self-reported,
uncalibrated), strict JSON with no extra keys, the company-scope check, and "any failure keeps the
existing behaviour" (the chat then asks the user, as before). Returns signals only; never searches.
"""
import asyncio
import json
import math

from ..b1_answering.core.policy import PolicyError
from ..b1_answering.providers.gemini import GeminiError

POLICY = 'intent-request-objectives-v2-11-r2'
# label id -> fallback code, from docs/sprint5/intent-labels.v2.json (s5-intent-labels-v2)
FALLBACK_CODES = {
    'PRICE': 'GIA', 'NUMERIC': 'SO_LIEU', 'ANALYSIS': 'PHAN_TICH', 'NEWS': 'NEWS',
    'REPORT_CONTENT': 'BCTC_BCTN', 'PERSON_ROLE': 'CHUC_VU', 'ENTITY_RELATION': 'QUAN_HE',
    'COMPANY_OVERVIEW': 'TONG_QUAN', 'CONVERSATION': 'HOI_THOAI', 'OUT_OF_SCOPE': 'NGOAI_PHAM_VI',
    'MIXED': 'KET_HOP',
}
LABEL_FROM_CODE = {code: label for label, code in FALLBACK_CODES.items()}
ALLOWED_CODES = [*FALLBACK_CODES.values(), 'CLARIFY']
PROVIDER_CONFIDENCE_THRESHOLD = .60
FALLBACK_TIMEOUT_SECONDS = 8

RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'intent_label': {'type': 'string', 'enum': ALLOWED_CODES},
        'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
        'reason': {'type': 'string'},
        'extracted_company': {'type': ['string', 'null']},
    },
    'required': ['intent_label', 'confidence', 'reason'],
    'additionalProperties': False,
}
_PROMPT = (
    'Phân loại ý định câu hỏi của người dùng FinMind (nghiên cứu cổ phiếu Việt Nam) vào đúng một nhãn trong '
    'allowed_labels: GIA (giá, khối lượng, biến động giá thị trường), SO_LIEU (giá trị chỉ tiêu tài chính), PHAN_TICH '
    '(nhận định, xu hướng, định giá đắt/rẻ, chỉ báo kỹ thuật như RSI, MACD, Bollinger, nguyên nhân, giải thích thuật '
    'ngữ), NEWS (tin tức), BCTC_BCTN (nội dung báo cáo), CHUC_VU (người và '
    'chức vụ), QUAN_HE (công ty con, cổ đông, liên kết), TONG_QUAN (giới thiệu doanh nghiệp), HOI_THOAI (chào hỏi, '
    'câu nối tiếp), NGOAI_PHAM_VI (tư vấn mua bán, dự báo, giá mục tiêu, cam kết lợi nhuận, việc không liên quan tài '
    'chính), KET_HOP (hai mục tiêu khác nhóm). Không chắc thì trả CLARIFY. confidence là mức tự đánh giá 0–1. '
    'extracted_company là mã cổ phiếu nêu trong câu, hoặc null. Không trả lời câu hỏi.'
)


def decide(classification):
    """DIRECT: rule evidence, use it. FALLBACK: a classifier guess or an unfinished request, ask Gemini.
    REFUSE: rules found a restricted request. NEEDS_CONTEXT: a follow-up the session must resolve.
    IGNORE: not a v2 resolution."""
    resolution = (classification or {}).get('resolution') or {}
    label = resolution.get('intent_label')
    if resolution.get('ranking_policy') != POLICY or label not in FALLBACK_CODES:
        return dict(decision='IGNORE', label=None, reason='UNSUPPORTED_RESOLUTION')
    status, reason = resolution.get('status'), resolution.get('reason')
    ruled = status == 'PROPOSED' and reason in ('EXPLICIT_REQUEST_TYPE', 'MULTIPLE_REQUEST_TYPES')
    if status == 'NEEDS_CONTEXT':
        decision = 'NEEDS_CONTEXT'
    elif ruled and resolution.get('contains_restricted_component'):
        decision = 'REFUSE'
    else:
        decision = 'DIRECT' if ruled else 'FALLBACK'
    return dict(decision=decision, label=label, reason=reason,
                components=list(resolution.get('component_labels') or []))


def fallback_request(question, *, company=None, period=None):
    return {'question': question, 'conversation_scope': {'company_ticker': company, 'period': period},
            'allowed_labels': list(ALLOWED_CODES)}


def _failure(reason):
    return dict(label=None, reason=reason, confidence=None)


def validate_fallback(payload, *, request):
    if not isinstance(payload, dict) or set(payload) - set(RESPONSE_SCHEMA['properties']) \
            or not {'intent_label', 'confidence', 'reason'} <= set(payload):
        return _failure('INVALID_RESPONSE')
    code, confidence, company = payload['intent_label'], payload['confidence'], payload.get('extracted_company')
    if (code not in ALLOWED_CODES or type(confidence) not in (int, float) or not math.isfinite(confidence)
            or not 0 <= confidence <= 1 or not isinstance(payload['reason'], str) or not payload['reason'].strip()
            or company is not None and (not isinstance(company, str) or not company.strip())):
        return _failure('INVALID_RESPONSE')
    if code == 'CLARIFY':
        return _failure('PROVIDER_ASKED_CLARIFICATION')
    scoped = request['conversation_scope']['company_ticker']
    if company and scoped and company.strip().upper() != scoped.upper():
        return _failure('COMPANY_SCOPE_CONFLICT')
    if confidence < PROVIDER_CONFIDENCE_THRESHOLD:
        return _failure('LOW_PROVIDER_CONFIDENCE')
    # The provider's score is self-reported and uncalibrated; it is a gate, never a probability.
    return dict(label=LABEL_FROM_CODE[code], reason=None, confidence=confidence)


async def ask_fallback(provider, budget, request, *, timeout=FALLBACK_TIMEOUT_SECONDS):
    """One Gemini call within the question's budget and a hard time limit; any failure returns no label."""
    body = {
        'systemInstruction': {'parts': [{'text': _PROMPT}]},
        'contents': [{'role': 'user', 'parts': [{'text': json.dumps(request, ensure_ascii=False)}]}],
        'generationConfig': {'temperature': 0, 'maxOutputTokens': 512, 'responseMimeType': 'application/json',
                             'responseJsonSchema': RESPONSE_SCHEMA},
    }

    async def call():
        ticket = budget.reserve(await provider.count_tokens(body))
        generated = await provider.generate(body)
        try:
            budget.settle(ticket, generated.get('usage'))
        except PolicyError:
            pass  # the reservation is kept as the worst case; the answer itself is still valid
        return generated

    try:
        generated = await asyncio.wait_for(call(), timeout)
    except TimeoutError:
        return _failure('PROVIDER_TIMEOUT')
    except PolicyError:
        return _failure('BUDGET_EXCEEDED')
    except GeminiError:
        return _failure('PROVIDER_ERROR')
    return validate_fallback((generated or {}).get('payload'), request=request)
