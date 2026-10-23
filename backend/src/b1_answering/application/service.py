"""B1 retrieval-to-draft composition; no B3 verifier or hidden retries."""
import asyncio
import copy
import time
from ..core.policy import Budget, Limits, PolicyError
from ..evidence.citations import CitationError, prepare_evidence, validate_draft
from ..evidence.prompt import PROMPT_VERSION, build_request
from ..evidence import grounded
from ..providers.gemini import GeminiError, GeminiProvider
from .presentation import present_answer


async def complete_retrieval(question, result, *, provider, limits=None, budget=None):
    limits = limits or (budget.limits if budget is not None else Limits.load())
    budget = budget if budget is not None else Budget(limits)
    if budget.limits != limits or getattr(provider, 'limits', limits) != limits:
        raise PolicyError('LIMITS_MISMATCH')
    out, trace = copy.deepcopy(result), []
    natural = result.get('execution_mode') == 'LIVE'
    manifest = {
        'mode': 'B1', 'config_version': limits.version, 'model_requested': limits.model,
        'model_returned': None, 'prompt_version': grounded.PROMPT_VERSION if natural else PROMPT_VERSION,
        'max_input_tokens': limits.max_input_tokens, 'max_output_tokens': limits.max_output_tokens,
        'read_timeout_seconds': limits.read_timeout_seconds, 'retrieval_mode': result.get('execution_mode'),
        'retrieval_backend': result.get('retrieval_backend', 'fixture'),
        'billing_policy': 'FREE_TIER_ATTESTED_ONLY',
        'components': {'gemini': False, 'citation_binding': True, 'extractive_claim_check': not natural,
                       'support_quote_check': natural, 'numeric_source_check': natural,
                       'b3_evidence_gate': False, 'b3_answer_verification': False, 'tools': False},
    }

    def finish(status, code, message, draft=None):
        if draft and natural:
            draft = present_answer(draft, evidence, result.get('scope') or {})
            from ..evidence.news_policy import present_news
            draft = present_news(draft, evidence, result.get('scope') or {})
            if not draft['draft'].strip():
                return failure('UNSUPPORTED_CLAIM')
            if draft.get('presentation'):
                manifest['answer_style_version'] = draft['presentation']['version']
        snapshot = budget.snapshot()
        out['answering'] = {
            'status': status, 'reason_code': code, 'message': message,
            'draft': draft['draft'] if draft else None,
            'claims': draft['claims'] if draft else [], 'citations': draft['citations'] if draft else [],
            'cautions': draft.get('cautions', []) if draft else [],
            'presentation': draft.get('presentation') if draft else None,
            'manifest': manifest, 'trace': trace + [{'event': 'budget_snapshot', **snapshot}], 'budget': snapshot,
        }
        return out

    def failure(code):
        if code in ('NO_EVIDENCE', 'INVALID_EVIDENCE', 'INVALID_CITATION', 'UNSUPPORTED_CLAIM'):
            return finish('INSUFFICIENT_EVIDENCE', code, 'Chưa đủ bằng chứng phù hợp để trả lời.')
        if code in ('INPUT_LIMIT_EXCEEDED', 'CALL_LIMIT_EXCEEDED', 'BUDGET_EXCEEDED', 'OUTPUT_LIMIT_EXCEEDED', 'USAGE_LIMIT_EXCEEDED'):
            return finish('BUDGET_EXCEEDED', code, 'Yêu cầu đã chạm giới hạn cấu hình; không gọi lại tự động.')
        return finish('SYSTEM_UNAVAILABLE', code, 'Dịch vụ tạm thời chưa phản hồi hợp lệ; vui lòng thử lại sau.')

    if result.get('status') != 'EVIDENCE_READY':
        trace.append({'event': 'retrieval_not_ready'})
        return finish('SKIPPED', 'UPSTREAM_NOT_READY', 'Giữ phản hồi của bước hiểu câu hỏi và tìm bằng chứng.')
    if provider is None:
        return failure('PROVIDER_NOT_CONFIGURED')
    try:
        evidence = prepare_evidence(result.get('evidence_pack'))
        request = (grounded.build_grounded_request(question, evidence, limits, result.get('scope'))
                   if natural else build_request(question, evidence, limits))
    except CitationError as exc:
        return failure(exc.code)
    snap = budget.snapshot()
    if snap['calls_used'] >= limits.max_generation_calls or limits.max_total_tokens - snap['tokens_reserved'] < limits.max_output_tokens:
        return failure('BUDGET_EXCEEDED')
    deadline = time.monotonic() + limits.read_timeout_seconds

    async def bounded(factory):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        value = await asyncio.wait_for(factory(), remaining)
        if time.monotonic() > deadline:
            raise TimeoutError()
        return value

    try:
        tokens = await bounded(lambda: provider.count_tokens(request))
        ticket = budget.reserve(tokens)
    except TimeoutError:
        return failure('GEMINI_TIMEOUT')
    except (GeminiError, PolicyError) as exc:
        return failure(exc.code)
    trace.append({'event': 'generation_reserved', 'input_tokens': tokens})
    manifest['components']['gemini'] = isinstance(provider, GeminiProvider)

    def retain_unknown():
        try:
            budget.settle(ticket, None)
        except PolicyError:
            pass

    try:
        generated = await bounded(lambda: provider.generate(request))
    except BaseException as exc:
        retain_unknown()
        if isinstance(exc, TimeoutError):
            return failure('GEMINI_TIMEOUT')
        if isinstance(exc, GeminiError):
            return failure(exc.code)
        raise  # Cancellation, system interrupts and unexpected programming errors propagate.
    if not isinstance(generated, dict):
        retain_unknown()
        return failure('INVALID_GEMINI_RESPONSE')
    manifest['model_returned'] = generated.get('model_version')
    try:
        budget.settle(ticket, generated.get('usage'))
    except PolicyError as exc:
        return failure(exc.code)
    try:
        draft = (grounded.validate_grounded(generated.get('payload'), evidence, result.get('scope'))
                 if natural else validate_draft(generated.get('payload'), evidence))
    except CitationError as exc:
        if natural:
            if exc.code in ('UNSUPPORTED_CLAIM', 'INVALID_CITATION') and result.get('scope', {}).get('source_type') == 'NEWS':
                from ..evidence.news_binding import bind_article_quotes
                rebound = bind_article_quotes(generated.get('payload'), evidence, result['scope'])
                if rebound:
                    try:
                        news_draft = grounded.validate_grounded(rebound[0], evidence, result['scope'])
                    except CitationError:
                        pass
                    else:
                        trace.append({'event': 'article_quotes_bound', 'bindings': rebound[1]})
                        return finish('DRAFT_READY', 'NEWS_QUOTE_BOUND',
                                      'Bản tóm tắt có đoạn trích từ đúng nội dung bài.', news_draft)
            draft = grounded.source_row_fallback(evidence, result.get('scope'), reason_code=exc.code)
            if draft:
                trace.append({'event': 'draft_bound_to_source_row', 'reason_code': exc.code})
                return finish('DRAFT_READY', 'SOURCE_EXTRACT_FALLBACK',
                              'Trả lời trực tiếp theo đúng dòng chỉ tiêu trong nguồn; '
                              'Gemini chưa tạo được bản diễn đạt hợp lệ.', draft)
        return failure(exc.code)
    trace.append({'event': 'draft_bound_to_evidence'})
    return finish('DRAFT_READY', 'SUCCESS',
                  'Bản nháp diễn đạt từ bằng chứng có trích dẫn.' if natural
                  else 'Bản nháp trích nguyên văn từ nguồn ứng viên.', draft)


async def answer_question(question, session_id, *, context=None, provider, limits=None, budget=None, retriever=None):
    from src.retrieval_orchestration.retrieval_flow.orchestrator import orchestrate
    result = await orchestrate(question, session_id, context=context, retriever=retriever)
    return await complete_retrieval(question, result, provider=provider, limits=limits, budget=budget)
