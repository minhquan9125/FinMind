"""Opt-in source/Gemini check for ambiguity, recovery and persisted selections."""
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.mark.skipif(os.getenv('RUN_CLARIFICATION_LIVE') != '1', reason='explicit actual-source/Gemini opt-in')
def test_actual_debt_and_revenue_clarification_recovery(tmp_path):
    from src.core.config import get_settings
    from src.core.db import connect, disconnect
    from src.documents.embeddings import get_embedding_service
    from src.b1_answering.core.policy import Limits
    from src.b1_answering.providers.gemini import GeminiProvider
    from src.retrieval_orchestration.live_research import DenseEvidenceRetriever, LiveResearchService
    from src.retrieval_orchestration.web_sessions import SessionStore
    settings = get_settings()
    if not settings.gemini_api_key.get_secret_value() or not settings.b1_gemini_free_tier_confirmed:
        pytest.skip('Gemini key/Free Tier not configured')

    async def run():
        pool = await asyncio.wait_for(connect(), 60)
        try:
            limits = replace(Limits.load(), max_generation_calls=2)
            provider = GeminiProvider(limits, api_key=settings.gemini_api_key.get_secret_value(), free_tier_confirmed=True)
            retriever = DenseEvidenceRetriever(pool, get_embedding_service(), backend=settings.research_retrieval_backend,
                                               corpus_version_id=settings.research_corpus_version_id,
                                               model_ref=settings.embedding_model_ref)
            await asyncio.wait_for(retriever.warmup(), 180)
            engine = LiveResearchService(retriever, provider=provider, limits=limits)
            owner, reports = str(uuid4()), []
            cases = [
                ('nợ', ['nợ của fpt trong quý 2 2026 là bao nhiêu', 'nợ', 'tổng'],
                 ['ASK_CLARIFICATION', 'ASK_CLARIFICATION', 'DRAFT_READY'], 'TOTAL_LIABILITIES'),
                ('doanh thu', ['doanh thu FPT quý 2/2026', 'doanh thu', 'doanh thu', 'thuần'],
                 ['ASK_CLARIFICATION', 'ASK_CLARIFICATION', 'CLARIFICATION_STALLED', 'DRAFT_READY'], 'NET_REVENUE'),
            ]
            for title, questions, expected, metric in cases:
                store = SessionStore(tmp_path, engine=engine)
                snap = await store.create(owner)
                turns = []
                for text, status in zip(questions, expected):
                    # Recreate the store to verify state is in saved JSON, not RAM.
                    store = SessionStore(tmp_path, engine=engine)
                    before = engine.budget.snapshot()['calls_used']
                    snap = await store.send(owner, snap['session_id'], text, snap['revision'])
                    message = snap['messages'][-1]
                    result = message['result']
                    answer = result.get('answering') or {}
                    actual = answer.get('status', result['status'])
                    assert actual == status, {'expected': status, 'actual': actual, 'reason': answer.get('reason_code')}
                    if status != 'DRAFT_READY':
                        assert before == engine.budget.snapshot()['calls_used']
                        assert result['clarification_options']
                    else:
                        assert result['scope']['metric_code'] == metric
                        assert result['scope']['companies'] == ['FPT']
                        assert result['scope']['periods'] == ['2026-Q2']
                        assert answer['citations']
                    turns.append({'user': text, 'status': actual, 'response': message['content'],
                                  'options': result.get('clarification_options', []),
                                  'generation_calls': engine.budget.snapshot()['calls_used']-before})
                reports.append({'topic': title, 'turns': turns, 'passed': True})
            root = Path(__file__).resolve().parents[1] / 'src/retrieval_orchestration/evaluations'
            root.mkdir(exist_ok=True)
            report = {'mode': 'ACTUAL_CORPUS_AND_GEMINI', 'conversations': reports, 'budget': engine.budget.snapshot()}
            (root / 'clarification_flow_results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False))
        finally:
            await disconnect()
    asyncio.run(run())
