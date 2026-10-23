"""Opt-in read-only startup measurement; absolutely no Gemini calls."""
import asyncio
import json
import os
import time

import pytest


@pytest.mark.skipif(os.getenv('RUN_RESEARCH_WARMUP_SMOKE') != '1', reason='explicit read-only startup smoke opt-in')
def test_real_startup_warms_shared_model_and_bm25(monkeypatch):
    from src import main
    from src.api.routers import research_chat
    from src.b1_answering.providers.gemini import GeminiProvider
    from src.retrieval_orchestration.live_research import analyze_live

    async def forbidden(*args, **kwargs): raise AssertionError('warmup must not call Gemini')
    monkeypatch.setattr(GeminiProvider, 'count_tokens', forbidden)
    monkeypatch.setattr(GeminiProvider, 'generate', forbidden)
    monkeypatch.setenv('FINMIND_LIVE_ENABLED', '0')

    async def run():
        async with main.lifespan(main.app):
            deadline = time.monotonic() + 200
            while main.app.state.research_warmup.get('status') == 'warming' and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
            status = main.app.state.research_warmup
            assert status['status'] == 'ready', status
            engine = research_chat.get_store().engine
            retriever = engine.retriever
            model = retriever.embedder._model
            assert model is not None
            lexical = retriever._hybrid._loaded if retriever.backend == 'hybrid' else None
            if retriever.backend == 'hybrid': assert lexical is not None
            started = time.monotonic()
            scope = analyze_live('Tiền và tương đương tiền FPT quý 2/2026')['scope']
            result = await retriever.retrieve('Tiền và tương đương tiền FPT quý 2/2026', scope)
            seconds = round(time.monotonic()-started, 2)
            assert result['items']
            assert retriever.embedder._model is model
            if lexical is not None: assert retriever._hybrid._loaded is lexical
            assert engine.budget.snapshot()['calls_used'] == 0
            print(json.dumps({'startup': status, 'first_retrieval_seconds': seconds,
                              'hits': len(result['items']), 'gemini_calls': 0}))
    asyncio.run(run())
