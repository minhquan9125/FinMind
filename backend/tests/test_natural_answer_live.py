"""Explicit opt-in: one Gemini generation grounded in read-only Supabase sources."""
import asyncio
import json
import os
from dataclasses import replace

import pytest


@pytest.mark.skipif(os.getenv('RUN_LIVE_GEMINI_SMOKE') != '1', reason='requires explicit Gemini smoke opt-in')
def test_real_gemini_natural_answer_from_corpus():
    from src.core.config import get_settings
    from src.core.db import connect, disconnect
    from src.documents.embeddings import get_embedding_service
    from src.b1_answering.core.policy import Limits
    from src.b1_answering.providers.gemini import GeminiProvider
    from src.retrieval_orchestration.live_research import DenseEvidenceRetriever, LiveResearchService

    settings = get_settings()
    if not settings.gemini_api_key.get_secret_value() or not settings.b1_gemini_free_tier_confirmed:
        pytest.skip('Gemini key/Free Tier confirmation not configured')

    async def run():
        limits = replace(Limits.load(), max_generation_calls=1)
        provider = GeminiProvider(limits, api_key=settings.gemini_api_key.get_secret_value(), free_tier_confirmed=True)
        pool = await connect()
        try:
            service = LiveResearchService(DenseEvidenceRetriever(
                pool, get_embedding_service(), corpus_version_id=settings.research_corpus_version_id,
                model_ref=settings.embedding_model_ref, backend='dense'), provider=provider, limits=limits)
            question = os.getenv('B1_SMOKE_QUESTION', 'Tiền và tương đương tiền FPT quý 2/2026')
            result = await service.answer(question, 'natural-answer-smoke')
            answer = result.get('answering', {})
            assert answer.get('status') == 'DRAFT_READY', {
                'retrieval': result.get('status'), 'answer_status': answer.get('status'),
                'reason': answer.get('reason_code'),
            }
            assert answer['budget']['calls_used'] == 1
            assert answer['manifest']['components']['gemini'] is True
            assert answer['claims'][0]['support_quotes']
            assert answer['citations'][0]['citation_number'] == 1
            assert 'VND' in answer['draft']
            assert 'Nguồn chưa' not in answer['draft']
            assert answer['presentation']['version'] == 'b1-answer-style-v1'
            print(json.dumps({'status': answer['status'], 'draft': answer['draft'],
                              'model': answer['manifest']['model_returned'],
                              'prompt': answer['manifest']['prompt_version'],
                              'generation_calls': answer['budget']['calls_used']}, ensure_ascii=False))
        finally:
            await disconnect()
    asyncio.run(run())
