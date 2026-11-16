"""S5-WBS07.2 runner over Huyền's v2 APIs (04.2 decide_intent_route_v2, 07.1 *_v2 fallback contract).

Huyền's modules decide and validate; this module only calls Gemini within the question's budget and a
hard time limit, then hands the validated label back to the chat. Any failure returns no label, so the
chat keeps its existing behaviour (it asks the user again).
"""
import asyncio
import json

from ..b1_answering.core.policy import PolicyError
from ..b1_answering.providers.gemini import GeminiError
from .intent_fallback_contract import (
    V2_RESPONSE_JSON_SCHEMA, prepare_fallback_request_v2, validate_fallback_response_v2,
)
from .intent_routing import IntentClassificationContractError, decide_intent_route_v2

FALLBACK_TIMEOUT_SECONDS = 8
RESPONSE_SCHEMA = V2_RESPONSE_JSON_SCHEMA  # the provider JSON is Huyền's v2 wire schema
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


def decide(classification, question, company=None):
    """Huyền's 04.2 v2 decision with the chat's verified company, or None for a malformed or stale classification.
    company_required=False: the chat itself asks for a missing company, and a refusal never needs one."""
    try:
        return decide_intent_route_v2(classification, question=question, company_ticker=company,
                                      company_required=False)
    except IntentClassificationContractError:
        return None


def validate_fallback(payload, *, request, query_components=None, query_components_confirmed=False, **failure):
    """Huyền's 07.1 v2 validation, reduced to what the chat needs: a label and route, or the failure reason."""
    checked = validate_fallback_response_v2(payload, request=request, company_required=False,
                                            query_components=query_components,
                                            query_components_confirmed=query_components_confirmed, **failure)
    if checked['status'] != 'FALLBACK_VALIDATED':
        return dict(label=None, route=None, reason=checked['reason_code'], confidence=None)
    # The provider's score is self-reported and uncalibrated; it is a gate, never a probability.
    return dict(label=checked['canonical_intent'], route=checked['route'], reason=None,
                confidence=checked['confidence'])


async def ask_fallback(provider, budget, decided, question, *, timeout=FALLBACK_TIMEOUT_SECONDS):
    """One Gemini call for a NEED_FALLBACK decision, within the question's budget and a hard time limit."""
    prepared = prepare_fallback_request_v2(decided, question=question, company_required=False)
    if not prepared['need_fallback']:
        return dict(label=None, route=None, reason=prepared['reason_code'], confidence=None)
    request = prepared['request']
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

    payload, failure = None, {}
    try:
        payload = ((await asyncio.wait_for(call(), timeout)) or {}).get('payload')
    except TimeoutError:
        failure = dict(timed_out=True)
    except (PolicyError, GeminiError) as exc:
        failure = dict(provider_error=exc)
    checked = validate_fallback(payload, request=request, **prepared['validation_context'], **failure)
    if isinstance(failure.get('provider_error'), PolicyError):
        checked['reason'] = 'BUDGET_EXCEEDED'
    return checked
