"""Explicit opt-in, bounded single public feed request; no SDK collector or DB."""
import asyncio
import os

import pytest


@pytest.mark.skipif(os.getenv('RUN_MARKET_NEWS_SMOKE') != '1', reason='requires public feed opt-in')
def test_real_public_news_dates_and_snapshot_contract():
    from src.market_data.news import FireAntNews, NewsService
    from src.retrieval_orchestration.market_research import MarketResearch
    from src.retrieval_orchestration.live_research import analyze_live
    from src.b1_answering.evidence.citations import prepare_evidence

    # Memory-only repository: this check never writes into source crawler folders.
    class MemoryRepository:
        articles = []
        def runtime_write(self, symbol, kind, payload): self.articles = payload['articles']
        def get_news(self, symbol, limit): return {'symbol': symbol, 'articles': self.articles[:limit]}
    repository = MemoryRepository()
    source = FireAntNews()
    news = NewsService(source, repository)
    try:
        bridge = MarketResearch(repository, services=lambda: (None, news))
        result = asyncio.run(bridge.lookup(analyze_live('tin tức mới nhất FPT')['scope']))
        assert result['status'] == 'EVIDENCE_READY', result.get('reason_code')
        evidence = prepare_evidence(result['evidence_pack'])
        assert 1 <= len(evidence) <= 3
        today_result = asyncio.run(bridge.lookup(analyze_live('tóm tắt tin tức mới hôm nay của FPT')['scope']))
        assert today_result['status'] in ('EVIDENCE_READY', 'NO_DATA'), today_result.get('reason_code')
        print({'status': result['status'], 'items': len(evidence),
               'published_dates': [item['locator']['published_at'] for item in evidence.values()]})
        if os.getenv('RUN_MARKET_GEMINI_SMOKE') == '1':
            from dataclasses import replace
            from src.core.config import get_settings
            from src.b1_answering.core.policy import Limits
            from src.b1_answering.providers.gemini import GeminiProvider
            from src.retrieval_orchestration.live_research import LiveResearchService
            settings = get_settings()
            assert settings.gemini_api_key.get_secret_value() and settings.b1_gemini_free_tier_confirmed
            class ForbiddenRetriever:
                async def retrieve(self, *args): raise AssertionError('current news must not query corpus')
            limits = replace(Limits.load(), max_generation_calls=1)
            class RecordingProvider(GeminiProvider):
                payload = None
                async def generate(self, request):
                    value = await super().generate(request)
                    self.payload = value.get('payload')
                    return value
            provider = RecordingProvider(limits, api_key=settings.gemini_api_key.get_secret_value(), free_tier_confirmed=True)
            engine = LiveResearchService(ForbiddenRetriever(), provider=provider, limits=limits, market=bridge)
            question = ('tóm tắt tin tức mới hôm nay của FPT' if today_result['status'] == 'EVIDENCE_READY'
                        else 'tóm tắt tin tức mới nhất FPT')
            answer = asyncio.run(engine.answer(question, 'market-smoke'))
            generated = answer.get('answering', {})
            if generated.get('status') != 'DRAFT_READY':
                import re
                from src.b1_answering.evidence.grounded import _facts, _numbers, _units
                prepared = prepare_evidence(answer['evidence_pack'])
                for claim in (provider.payload or {}).get('claims', []):
                    facts = '\n'.join(_facts(prepared[eid], [q['quote'] for q in claim['support_quotes']
                                                              if q['evidence_id'] == eid], answer['scope'])
                                      for eid in claim['evidence_ids'])
                    print({'unsupported_numbers': sorted(_numbers(claim['text']) - _numbers(facts)),
                           'unsupported_units': sorted(_units(claim['text']) - _units(facts)),
                           'unsupported_acronyms': sorted(set(re.findall(r'\b[A-ZĐ]{2,}\b', claim['text'])) - set(re.findall(r'\b[A-ZĐ]{2,}\b', facts))),
                           'quotes_exist': [q['quote'] in prepared[q['evidence_id']]['passage'] for q in claim['support_quotes']],
                           'claim': claim})
                from pathlib import Path
                import json
                artifact = Path(__file__).resolve().parents[2] / '.agent-state/news-gemini-rejection.json'
                artifact.write_text(json.dumps({'payload': provider.payload, 'evidence_pack': answer['evidence_pack'],
                                                'scope': answer['scope']}, ensure_ascii=False, indent=2), encoding='utf-8')
            assert generated.get('status') == 'DRAFT_READY', (generated.get('reason_code'), provider.payload)
            assert generated['manifest']['components']['gemini'] is True
            assert generated['budget']['calls_used'] == 1
            assert generated['citations']
            print({'status': generated['status'], 'draft': generated['draft'],
                   'generation_calls': generated['budget']['calls_used']})
    finally:
        source.close()


@pytest.mark.skipif(os.getenv('RUN_MARKET_QUOTE_SMOKE') != '1', reason='requires single SDK quote opt-in')
def test_real_quote_through_shared_coordinator_without_polling():
    from pathlib import Path
    from src.market_data.sdk import BatchSDKClient, CollectorLock
    from src.market_data.repository import FileMarketDataRepository
    from src.market_data.live import LiveCoordinator
    from src.retrieval_orchestration.market_research import MarketResearch
    from src.retrieval_orchestration.live_research import analyze_live
    root = Path(__file__).resolve().parents[2]
    lock = CollectorLock(root / '.agent-state/market-live/collector.lock')
    try:
        lock.acquire()
    except RuntimeError:
        pytest.skip('existing collector owns the SDK; do not start another')
    sdk = BatchSDKClient(root)
    try:
        repo = FileMarketDataRepository(root)
        live = LiveCoordinator(sdk, lambda exchange: False, repo, history_fetch=sdk.history)
        bridge = MarketResearch(repo, services=lambda: (live, None))
        result = asyncio.run(bridge.lookup(analyze_live('giá cổ phiếu FPT hôm nay là bao nhiêu')['scope']))
        assert result['status'] == 'PRICE_READY', result.get('reason_code')
        assert 'VND' in result['draft']
        assert live.status()['viewers'] == 0
        print({'status': result['status'], 'draft': result['draft']})
        import time
        from datetime import datetime, timedelta, timezone
        # Two source requests, separated by the existing shared SDK spacing.
        time.sleep(5)
        today = datetime.now(timezone(timedelta(hours=7))).date()
        historical = asyncio.run(bridge.lookup(analyze_live(
            'còn hôm qua', analyze_live('giá cổ phiếu FPT hôm nay')['scope'])['scope']))
        if today.weekday() == 0:
            assert historical['status'] == 'NO_DATA'
        else:
            assert historical['status'] in ('PRICE_READY', 'NO_DATA'), historical.get('reason_code')
            if historical['status'] == 'NO_DATA': assert historical['reason_code'] == 'NO_TRADING_DAY'
        print({'history_status': historical['status'], 'message': historical.get('draft') or historical.get('message')})
    finally:
        sdk.close()
        lock.close()
