import asyncio
import copy
import json

from src.retrieval_orchestration.live_research import analyze_live
from tests.test_market_dialogue import DetailedNews, Provider, engine
from tests.test_market_research import NOW, article
from src.b1_answering.evidence.grounded import build_grounded_request, validate_grounded
from src.b1_answering.core.policy import Limits
from src.b1_answering.evidence.citations import prepare_evidence

TITLE = 'Diễn biến mới nhất của siêu dự án công viên công nghệ 2 tỷ USD do Tập đoàn FPT đầu tư ở thành phố giàu nhất miền Bắc'
CONTENT = 'UBND phường Phú Diễn đề nghị các chủ sử dụng đất liên hệ trước ngày 30/10/2026 về dự án công nghệ của FPT.'


def items():
    other, target = article(ident='1'), article(ident='2')
    other['title'] = 'FPT thay đổi đăng ký doanh nghiệp'
    target.update(title=TITLE, description=CONTENT)
    return [other, target]


def test_direct_headline_is_news_detail_without_prior_chat():
    result = analyze_live('cho tôi biết chi tiết về: '+TITLE, today=NOW.date())
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['source_type'] == 'NEWS'
    assert result['scope']['companies'] == ['FPT']
    assert result['scope']['_market_request']['action'] == 'DETAIL'
    assert result['scope']['_market_request']['query']


def test_short_headlines_and_generic_news_questions_are_distinct():
    result = analyze_live('chi tiết bài FPT ra mắt chip', today=NOW.date())
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['_market_request']['query'] == 'fpt ra mat chip'
    for question in ('tóm tắt tin tức mới hôm nay của FPT', 'tóm tắt tin tức FPT hôm nay'):
        request = analyze_live(question, today=NOW.date())['scope']['_market_request']
        assert not request.get('query')
        assert request['day'] == '2026-10-23'


def test_direct_headline_fetches_matching_article_not_first_article():
    async def run():
        news = DetailedNews(items())
        result = await engine(news, Provider()).answer('cho tôi biết chi tiết về: '+TITLE, 't', today=NOW.date())
        assert result['answering']['status'] == 'DRAFT_READY'
        assert news.details == [items()[1]['url']]
        assert result['evidence_pack']['items'][0]['title'] == TITLE
    asyncio.run(run())


def test_pasted_summary_sentence_resolves_its_evidence_without_asking_again():
    async def run():
        news = DetailedNews(items())
        service = engine(news, Provider())
        first = await service.answer('tin tức FPT hôm nay', 't', today=NOW.date())
        target = first['evidence_pack']['items'][1]
        first['answering']['claims'] = [{'text': CONTENT, 'evidence_ids': [target['evidence_id']]}]
        result = await service.answer('tóm tắt '+CONTENT+' cho t', 't', first['scope'], previous_result=first, today=NOW.date())
        assert result['answering']['status'] == 'DRAFT_READY'
        assert news.calls == ['FPT']
        assert news.details == [items()[1]['url']]
    asyncio.run(run())


def test_unmatched_title_is_not_silently_replaced_by_last_single_article():
    async def run():
        news = DetailedNews(items()[:1])
        service = engine(news, Provider())
        first = await service.answer('tin tức FPT hôm nay', 't', today=NOW.date())
        result = await service.answer('chi tiết bài: '+TITLE, 't', first['scope'], previous_result=first, today=NOW.date())
        assert result['status'] == 'NO_DATA'
        assert result['reason_code'] == 'ARTICLE_NOT_FOUND'
        assert not news.details
    asyncio.run(run())


def test_article_detail_allows_four_supported_points_and_guides_a_fuller_answer():
    async def run():
        result = await engine(DetailedNews(items()), Provider()).answer('cho tôi biết chi tiết về: '+TITLE, 't', today=NOW.date())
        evidence = prepare_evidence(result['evidence_pack'])
        request = build_grounded_request('chi tiết', evidence, Limits.load(), result['scope'])
        schema = request['generationConfig']['responseJsonSchema']['properties']['claims']
        assert schema['maxItems'] == 4
        assert request['generationConfig']['maxOutputTokens'] == 2048
        assert 'bối cảnh' in request['systemInstruction']['parts'][0]['text']
        eid = next(iter(evidence))
        text = 'FPT triển khai công viên công nghệ tại Hà Nội.'
        claim = {'text': text, 'evidence_ids': [eid], 'support_quotes': [{'evidence_id': eid, 'quote': text}]}
        assert len(validate_grounded({'claims': [copy.deepcopy(claim) for _ in range(4)]}, evidence, result['scope'])['claims']) == 4
    asyncio.run(run())
