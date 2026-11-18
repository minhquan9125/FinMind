"""Summary acceptance: only saved, validated answers in the current conversation."""
import asyncio
import copy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.b1_answering.evidence.grounded import validate_grounded
from src.documents.db_chunking import chunk_document, news_documents
from src.retrieval_orchestration.chat_logic import append_turn, new_document


def sourced_result(symbol='FPT', year='2025', text=None):
    text = text or f'{symbol} phát triển nền tảng công nghệ.'
    doc = news_documents([dict(article_id=str(uuid4()), source='official', title=f'Tin {symbol} {year}',
                              content=text, symbols=[symbol], url='https://example.org/test-source')])[0]
    chunk = chunk_document(doc)[0]
    item = dict(evidence_id=str(uuid4()), chunk_id=str(uuid4()), source_id=str(uuid4()),
                source_type='NEWS', source_sha256='a'*64, content_sha256=chunk.content_hash,
                passage=chunk.text, title=f'Tin {symbol} {year}', source_verified=True, locator=chunk.locator,
                score={'type': 'RRF', 'value': 1.0})
    scope = dict(companies=[symbol], periods=[year], source_type='NEWS')
    answer = validate_grounded({'claims': [dict(text=text, evidence_ids=[item['evidence_id']],
                    support_quotes=[dict(evidence_id=item['evidence_id'], quote=text)])]}, {item['evidence_id']: item}, scope)
    answer['manifest'] = {'response_mode': 'GROUNDED'}
    return dict(status='EVIDENCE_READY', execution_mode='LIVE', scope=scope,
                answering=answer, message='Có nguồn', evidence_pack=dict(schema_version='1.1',
                query_id=str(uuid4()), corpus_version_id=str(uuid4()),
                data_version={'kind': 'INDEX', 'id': str(uuid4())}, items=[item]))


class SequenceEngine:
    retrieval_timeout = 1
    limits = SimpleNamespace(read_timeout_seconds=1)

    def __init__(self, results):
        self.results = copy.deepcopy(results)
        self.calls = 0

    async def answer(self, *args, **kwargs):
        self.calls += 1
        assert self.results, 'Summary must not retrieve or generate again'
        return self.results.pop(0)


async def two_turns():
    results = [sourced_result(), sourced_result('VCB', '2024')]
    engine = SequenceEngine(results)
    doc = new_document(str(uuid4()), str(uuid4()))
    for text in ('Hỏi về FPT năm 2025', 'Hỏi về VCB năm 2024'):
        doc = await append_turn(doc, text, engine)
    return doc, engine, results


@pytest.mark.parametrize('question', ['Tổng hợp nãy giờ', 'Tóm tắt nội dung phiên hiện tại', 'tong ket nhung gi vua trao doi'])
def test_summary_keeps_company_period_sources_and_renumbers_citations(question):
    async def run():
        doc, engine, originals = await two_turns()
        before = copy.deepcopy(doc)
        updated = await append_turn(doc, question, engine)
        result = updated['messages'][-1]['result']
        assert result['answering']['manifest']['response_mode'] == 'SESSION_SUMMARY'
        assert 'FPT' in result['answering']['draft'] and '2025' in result['answering']['draft']
        assert 'VCB' in result['answering']['draft'] and '2024' in result['answering']['draft']
        assert [c['citation_number'] for c in result['answering']['citations']] == [1, 2]
        assert result['answering']['citations'][0]['locator'] == originals[0]['answering']['citations'][0]['locator']
        assert result['scope'] == before['metadata']['live_context']
        assert engine.calls == 2 and doc == before
    asyncio.run(run())


def test_empty_session_summary_does_not_call_engine():
    async def run():
        engine = SequenceEngine([])
        doc = new_document(str(uuid4()), str(uuid4()))
        updated = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        assert updated['messages'][-1]['result']['status'] == 'ASK_CLARIFICATION'
        assert engine.calls == 0
    asyncio.run(run())


def test_reset_boundary_excludes_previous_answers_and_cannot_read_other_sessions():
    async def run():
        doc, _, _ = await two_turns()
        doc['messages'].append({'role': 'user', 'content': '/new'})
        doc['metadata']['live_context'] = {}
        engine = SequenceEngine([sourced_result('BID')])
        doc = await append_turn(doc, 'Hỏi về BID', engine)
        updated = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        draft = updated['messages'][-1]['result']['answering']['draft']
        assert 'BID' in draft and 'FPT' not in draft and 'VCB' not in draft
    asyncio.run(run())


@pytest.mark.parametrize('mutation', ['hash', 'locator', 'claim'])
def test_corrupt_or_unsupported_saved_answer_is_not_repeated(mutation):
    async def run():
        result = sourced_result()
        if mutation == 'hash':
            result['evidence_pack']['items'][0]['passage'] += ' tampered'
        elif mutation == 'locator':
            result['answering']['citations'][0]['locator']['source_id'] = 'tampered'
        else:
            result['answering']['claims'][0]['text'] = 'FPT có lợi nhuận 999 tỷ đồng.'
        engine = SequenceEngine([result])
        doc = await append_turn(new_document(str(uuid4()), str(uuid4())), 'Hỏi FPT', engine)
        updated = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        summary = updated['messages'][-1]['result']
        assert summary['status'] == 'ASK_CLARIFICATION'
        assert '999' not in updated['messages'][-1]['content']
        assert not (summary.get('answering') or {}).get('citations')
    asyncio.run(run())


def test_repeated_summaries_do_not_summarize_themselves_or_duplicate_claims():
    async def run():
        doc, engine, _ = await two_turns()
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        summary = doc['messages'][-1]['result']
        assert len(summary['answering']['claims']) == 2
        assert len(summary['answering']['citations']) == 2
        assert engine.calls == 2
    asyncio.run(run())


def test_source_reference_after_summary_replays_all_original_packs():
    from src.retrieval_orchestration.live_research import LiveResearchService
    async def run():
        doc, engine, _ = await two_turns()
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        summary = doc['messages'][-1]['result']
        result = await LiveResearchService(object()).answer('Nguồn đâu?', 'summary', summary['scope'], previous_result=summary)
        assert result['reason_code'] == 'SOURCE_REFERENCE'
        assert result['evidence_packs'] == summary['evidence_packs']
        assert len(result['answering']['citations']) == 2
    asyncio.run(run())


def test_limit_is_explicit_and_keeps_recent_turns():
    async def run():
        from src.retrieval_orchestration.conversation_summary import MAX_TURNS
        results = [sourced_result(year=str(2000+i)) for i in range(MAX_TURNS+1)]
        engine = SequenceEngine(results)
        doc = new_document(str(uuid4()), str(uuid4()))
        for _ in results:
            doc = await append_turn(doc, 'Hỏi tin có nguồn', engine)
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        summary = doc['messages'][-1]['result']
        assert len(summary['conversation_summary']['included_turns']) == MAX_TURNS
        assert summary['conversation_summary']['omitted_turns'] == 1
        assert '2000' not in summary['answering']['draft'] and '2012' in summary['answering']['draft']
        assert summary['answering']['cautions']
    asyncio.run(run())


def test_same_evidence_id_with_different_sources_is_not_silently_merged():
    async def run():
        first, second = sourced_result(), sourced_result('VCB', '2024')
        old, eid = second['evidence_pack']['items'][0]['evidence_id'], first['evidence_pack']['items'][0]['evidence_id']
        second['evidence_pack']['items'][0]['evidence_id'] = eid
        second['answering']['citations'][0]['evidence_id'] = eid
        second['answering']['claims'][0]['evidence_ids'] = [eid]
        second['answering']['claims'][0]['support_quotes'][0]['evidence_id'] = eid
        engine = SequenceEngine([first, second])
        doc = new_document(str(uuid4()), str(uuid4()))
        doc = await append_turn(doc, 'FPT', engine)
        doc = await append_turn(doc, 'VCB', engine)
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        summary = doc['messages'][-1]['result']
        assert len(summary['answering']['citations']) == 1
        assert summary['conversation_summary']['omitted_turns'] == 1
        assert 'VCB' not in summary['answering']['draft']
    asyncio.run(run())


@pytest.mark.parametrize('storage', ['file', 'postgres_contract'])
def test_api_summary_survives_reopen_and_resume_without_cross_session_leak(tmp_path, storage):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.routers import research_chat as api
    from src.retrieval_orchestration.web_sessions import SessionStore
    from src.retrieval_orchestration.postgres_sessions import PostgresSessionStore
    from tests.test_postgres_chat_store import Repository
    engine = SequenceEngine([sourced_result(), sourced_result('VCB', '2024')])
    repository = Repository()
    app = FastAPI()
    app.include_router(api.router)
    owner = str(uuid4())
    app.dependency_overrides[api.get_owner] = lambda: owner
    app.dependency_overrides[api.get_store] = (lambda: SessionStore(tmp_path, engine=engine)) if storage == 'file' else (
        lambda: PostgresSessionStore(repository=repository, engine=engine))
    with TestClient(app) as client:
        original = client.post('/api/research/chat/sessions').json()
        path = '/api/research/chat/sessions/'+original['session_id']
        for text in ('Hỏi tin FPT', 'Hỏi tin VCB', 'Tổng hợp nãy giờ'):
            response = client.post(path+'/messages', json={'text': text, 'revision': original['revision']})
            assert response.status_code == 200, response.text
            original = response.json()
        assert client.get(path).json() == original
        child = client.post(path+'/resume').json()
        response = client.post('/api/research/chat/sessions/'+child['session_id']+'/messages',
                               json={'text': 'Tổng hợp nãy giờ', 'revision': 0})
        assert len(response.json()['messages'][-1]['result']['answering']['citations']) == 2
        assert client.get(path).json() == original
        fresh = client.post('/api/research/chat/sessions').json()
        response = client.post('/api/research/chat/sessions/'+fresh['session_id']+'/messages',
                               json={'text': 'Tổng hợp nãy giờ', 'revision': 0})
        assert response.json()['messages'][-1]['result']['status'] == 'ASK_CLARIFICATION'
        app.dependency_overrides[api.get_owner] = lambda: str(uuid4())
        assert client.get(path).status_code == 404
        assert engine.calls == 2


@pytest.mark.parametrize('text, expected', [
    ('Bạn có thể tổng hợp nãy giờ không?', True),
    ('Tổng hợp lại toàn bộ nội dung đã trao đổi', True),
    ('Tổng hợp tin tức FPT hôm nay', False),
    ('Tóm tắt BCTN FPT 2025', False),
    ('Tóm tắt bài này', False),
    ('tổng hợp chi tiết tổng quan về nội dung chat đi', True),
    ('Tổng hợp những nội dung tôi nhắn nãy giờ đi', True),
    ('Tóm tắt cuộc hội thoại này đi', True),
    ('Giúp tôi tóm tắt chi tiết lịch sử chat nhé', True),
    ('Tổng hợp chi tiết tổng quan về công ty FPT đi', False),
    ('Tóm tắt BCTN FPT rồi tổng hợp cuộc hội thoại', False),
    ('Đừng tổng hợp nội dung chat', False),
    ('Tổng hợp nội dung chat rồi xóa lịch sử', False),
    ('vậy giờ tôi cần bạn tổng hợp lại thôi không cần phải đưa ra chi tiết từng đoạn chat', True),
    ('Tôi muốn bạn tổng hợp nội dung chat ngắn gọn thôi', True),
    ('Tôi cần bạn tổng hợp tin tức FPT hôm nay', False),
])
def test_session_command_does_not_intercept_new_research_or_article_summary(text, expected):
    from src.retrieval_orchestration.conversation_actions import is_session_summary
    assert is_session_summary(text) is expected


def test_brief_summary_is_grouped_not_a_new_news_search():
    async def run():
        doc,engine,_=await two_turns()
        calls=engine.calls
        result=await append_turn(doc,'vậy giờ tôi cần bạn tổng hợp lại thôi không cần phải đưa ra chi tiết từng đoạn chat',engine)
        answer=result['messages'][-1]['result']
        assert answer['reason_code']=='SESSION_SUMMARY'
        assert answer['conversation_summary']['style']=='GROUPED_BRIEF'
        assert answer['answering']['draft'].startswith('Tổng hợp chung')
        assert 'FPT · 2025 · Tin tức:' in answer['answering']['draft']
        assert 'VCB · 2024 · Tin tức:' in answer['answering']['draft']
        assert engine.calls==calls
        assert len(answer['answering']['citations'])==2
    asyncio.run(run())


def test_natural_chat_summary_wins_over_company_profile_and_never_calls_engine():
    async def run():
        doc,engine,_=await two_turns()
        calls=engine.calls
        result=await append_turn(doc,'tổng hợp chi tiết tổng quan về nội dung chat đi',engine)
        summary=result['messages'][-1]['result']
        assert summary['reason_code']=='SESSION_SUMMARY'
        assert summary['answering']['manifest']['response_mode']=='SESSION_SUMMARY'
        assert engine.calls==calls
        assert summary['scope']==doc['metadata']['live_context']
    asyncio.run(run())


def test_evidence_size_limit_is_visible_instead_of_a_false_no_data_claim(monkeypatch):
    from src.retrieval_orchestration import conversation_summary
    async def run():
        doc, engine, _ = await two_turns()
        monkeypatch.setattr(conversation_summary, 'MAX_EVIDENCE_BYTES', 1)
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        result = doc['messages'][-1]['result']
        assert result['reason_code'] == 'SUMMARY_LIMIT_REACHED'
        assert result['conversation_summary']['omitted_turns'] == 2
        assert not result.get('answering')
    asyncio.run(run())


def test_news_list_without_model_claims_is_extracted_from_the_bound_source():
    async def run():
        result = sourced_result()
        result['answering']['claims'] = []
        result['answering']['manifest']['response_mode'] = 'NEWS_LIST'
        engine = SequenceEngine([result])
        doc = await append_turn(new_document(str(uuid4()), str(uuid4())), 'Tin FPT', engine)
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        summary = doc['messages'][-1]['result']
        assert summary['answering']['claims'][0]['text'] == result['evidence_pack']['items'][0]['title']
        assert len(summary['answering']['citations']) == 1
    asyncio.run(run())


@pytest.mark.parametrize('fixture_mode', ['execution_mode', 'legacy_pack'])
def test_fixture_history_is_not_presented_as_live_financial_sources(fixture_mode):
    async def run():
        result = sourced_result()
        if fixture_mode == 'execution_mode':
            result['execution_mode'] = 'FIXTURE'
        else:
            result['evidence_pack']['schema_version'] = '1.0'
            result['evidence_pack']['items'][0]['locator'] = {'page_number': 1}
            result['answering']['citations'][0]['locator'] = {'page_number': 1}
        engine = SequenceEngine([result])
        doc = await append_turn(new_document(str(uuid4()), str(uuid4())), 'FPT', engine)
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        assert doc['messages'][-1]['result']['status'] == 'ASK_CLARIFICATION'
        assert not doc['messages'][-1]['result'].get('answering')
    asyncio.run(run())


@pytest.mark.parametrize('kind', ['NEWS', 'PRICE'])
def test_corpus_and_feed_packs_keep_independent_versions_in_one_summary(kind):
    from src.b1_answering.evidence.citations import validate_draft
    from src.b1_answering.evidence.market_contract import feed_pack
    async def run():
        snapshot = dict(kind=kind, symbol='VCB', observed_at='2026-11-17T09:00:00+07:00')
        if kind == 'NEWS':
            snapshot.update(provider='fireant', title='VCB phát triển thanh toán số', description='Tin có nguồn',
                            published_at='2026-11-17', url='https://fireant.vn/bai-viet/test-summary/123')
        else:
            snapshot.update(provider='vnstock_kbs', price_vnd='90000', trading_day='2026-11-17')
        pack = feed_pack([snapshot])
        item = pack['items'][0]
        answer = validate_draft({'claims': [{'text': item['passage'], 'evidence_ids': [item['evidence_id']]}]},
                                {item['evidence_id']: item})
        answer['manifest'] = {'response_mode': 'GROUNDED'}
        feed = dict(execution_mode='LIVE', status='EVIDENCE_READY', message='Có nguồn',
                    scope={'companies': ['VCB'], 'periods': ['2026-11-17'], 'source_type': kind},
                    evidence_pack=pack, answering=answer)
        first = sourced_result()
        engine = SequenceEngine([first, feed])
        doc = new_document(str(uuid4()), str(uuid4()))
        doc = await append_turn(doc, 'FPT', engine)
        doc = await append_turn(doc, 'VCB', engine)
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        result = doc['messages'][-1]['result']
        assert [p['schema_version'] for p in result['evidence_packs']] == ['1.1', '1.2']
        assert result['evidence_packs'][0]['data_version'] == first['evidence_pack']['data_version']
        assert result['evidence_packs'][1] == pack
        assert len(result['answering']['citations']) == 2
    asyncio.run(run())


def test_summary_keeps_original_source_cautions():
    async def run():
        result = sourced_result()
        caution = 'Nguồn tin đang dùng bản lưu cũ do nhà cung cấp chưa cập nhật.'
        result['answering']['cautions'] = [caution]
        engine = SequenceEngine([result])
        doc = await append_turn(new_document(str(uuid4()), str(uuid4())), 'Tin FPT', engine)
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        summary = doc['messages'][-1]['result']
        assert caution in summary['answering']['draft']
        assert caution in summary['answering']['cautions']
    asyncio.run(run())


def test_an_earlier_empty_summary_is_not_counted_as_missing_research():
    async def run():
        engine = SequenceEngine([sourced_result()])
        doc = new_document(str(uuid4()), str(uuid4()))
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        doc = await append_turn(doc, 'Tin FPT', engine)
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        summary = doc['messages'][-1]['result']
        assert summary['conversation_summary']['omitted_turns'] == 0
        assert len(summary['answering']['claims']) == 1
    asyncio.run(run())


def test_summary_cautions_are_bounded_and_disclose_truncation():
    async def run():
        original = sourced_result()
        original['answering']['cautions'] = ['Lưu ý dài '+('a'*1600)] + [f'Lưu ý {i}' for i in range(5)]
        engine = SequenceEngine([original])
        doc = await append_turn(new_document(str(uuid4()), str(uuid4())), 'Tin FPT', engine)
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        summary = doc['messages'][-1]['result']
        assert len(summary['answering']['cautions']) == 5  # Four cautions + omission notice.
        assert len(summary['answering']['cautions'][0]) == 1501
        assert summary['conversation_summary']['omitted_turns'] == 3
        assert 'giới hạn' in summary['answering']['draft']
    asyncio.run(run())


def test_summary_preserves_stored_news_publication_cutoff_without_live_fetch(monkeypatch):
    from src.retrieval_orchestration.live_research import LiveResearchService
    from src.retrieval_orchestration.market_research import MarketResearch
    from tests.test_market_research import News, Repository, NOW
    from tests.test_s5_wbs091_context import EmptyContent
    from tests.stored_news_fixture import stored_pack
    from tests.test_market_research import article
    async def read(retriever,scope):
        return stored_pack([article()],scope,'FPT công bố kết quả kinh doanh mới.')
    monkeypatch.setattr('src.retrieval_orchestration.stored_news.latest_news',read)

    async def run():
        news = News(stale=True)
        market = MarketResearch(Repository(), services=lambda: (None, news), now=lambda: NOW)
        engine = LiveResearchService(EmptyContent(), market=market)
        doc = await append_turn(new_document(str(uuid4()), str(uuid4())), 'Tin FPT mới nhất', engine)
        original = doc['messages'][-1]['result']
        assert original['retrieval_backend'] == 'stored_news_corpus'
        assert news.calls == []
        assert original['answering']['status'] == 'DRAFT_READY'
        doc = await append_turn(doc, 'Tổng hợp nãy giờ', engine)
        summary = doc['messages'][-1]['result']
        assert any('đã nạp' in warning and '23/10/2026' in warning for warning in summary['answering']['cautions'])
        assert '23/10/2026' in summary['answering']['draft']
        assert 'không phải tin được cập nhật trực tiếp lúc hỏi' in summary['answering']['draft']
    asyncio.run(run())
