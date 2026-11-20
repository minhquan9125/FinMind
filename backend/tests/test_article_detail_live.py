"""Opt-in reproduction: direct headline, no prior chat, one real generation."""
import asyncio
from dataclasses import replace
import os

import pytest


@pytest.mark.skipif(os.getenv('RUN_NEWS_DETAIL_SMOKE') != '1', reason='requires explicit public feed/Gemini smoke opt-in')
def test_direct_headline_returns_article_detail_with_real_sources():
    from src.market_data.news import FireAntNews, NewsService
    from src.retrieval_orchestration.market_research import MarketResearch
    from src.retrieval_orchestration.live_research import LiveResearchService
    from src.b1_answering.providers.gemini import GeminiProvider
    from src.b1_answering.core.policy import Limits
    from src.core.config import get_settings

    class Repository:
        def __init__(self): self.articles = []
        def runtime_write(self, symbol, kind, payload): self.articles = payload['articles']
        def get_news(self, symbol, limit): return {'articles': self.articles[:limit]}
    class Retriever:
        async def retrieve(self, *args): raise AssertionError('must not require a prior corpus question')
    repository = Repository()
    source = FireAntNews()
    news = NewsService(source, repository)
    settings = get_settings()
    assert settings.gemini_api_key.get_secret_value() and settings.b1_gemini_free_tier_confirmed
    limits = replace(Limits.load(), max_generation_calls=1)
    class RecordingProvider(GeminiProvider):
        payload = None
        async def generate(self, request):
            value = await super().generate(request)
            self.payload = value.get('payload')
            return value
    provider = RecordingProvider(limits, api_key=settings.gemini_api_key.get_secret_value(), free_tier_confirmed=True)
    async def run():
        service = LiveResearchService(Retriever(), provider=provider, limits=limits,
            market=MarketResearch(repository, services=lambda: (None, news)))
        title = ('Diễn biến mới nhất của siêu dự án công viên công nghệ 2 tỷ USD do Tập đoàn FPT '
                 'đầu tư ở thành phố giàu nhất miền Bắc')
        result = await service.answer('cho tôi biết chi tiết về: '+title, 'direct-article-smoke')
        answer = result.get('answering') or {}
        if answer.get('status') != 'DRAFT_READY' and provider.payload:
            import json
            from pathlib import Path
            path = Path(__file__).resolve().parents[2] / '.agent-state/direct-article-rejection.json'
            path.write_text(json.dumps({'payload': provider.payload, 'evidence_pack': result['evidence_pack'],
                                        'scope': result['scope']}, ensure_ascii=False, indent=2), encoding='utf-8')
            print({'claims': provider.payload})
        assert answer.get('status') == 'DRAFT_READY', (result.get('reason_code'), answer.get('reason_code'))
        assert len(answer['claims']) >= 3, 'detail still too short'
        assert len(answer['citations']) == 1
        assert answer['budget']['calls_used'] == 1
        assert result['scope']['companies'] == ['FPT']
        assert result['evidence_pack']['items'][0]['title'] == title
        print({'status': answer['status'], 'draft': answer['draft'], 'claims': len(answer['claims']),
               'generation_calls': answer['budget']['calls_used'], 'tokens': answer['budget']['tokens_reserved'],
               'reason': answer.get('reason_code')})
    try: asyncio.run(run())
    finally: source.close()
