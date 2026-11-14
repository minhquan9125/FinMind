"""The web message endpoint must execute graph plans, not silently query NEWS."""
import asyncio
import copy
from dataclasses import replace
import hashlib
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api.routers import research_chat as api
from src.b1_answering.core.policy import Limits, Budget
from src.b1_answering.evidence.citations import prepare_evidence
from src.documents.db_chunking import news_documents, chunk_document
from src.graph_review.models import VerifiedSource, SourceProblem
from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine, SessionScope
from src.retrieval_orchestration.live_research import LiveResearchService
from src.retrieval_orchestration.web_chat_router import WebChatRouter, Neo4jChatRetriever, GraphChatError, anchor_graph_time
from src.retrieval_orchestration.web_sessions import SessionStore

CID, IID = str(uuid4()), str(uuid4())
QUOTE = 'Ông Trương Gia Bình là Chủ tịch FPT.'


def test_graph_relative_now_is_anchored_to_source_without_changing_support_quotes():
    original = 'Theo tài liệu, ông A là Chủ tịch từ tháng 05/2008 tới nay.'
    answer = dict(status='DRAFT_READY', draft=original+' [1]',
        claims=[dict(text=original, support_quotes=[dict(evidence_id='source', quote=original)])])
    anchor_graph_time(answer)
    assert '05/2008 đến thời điểm tài liệu ghi nhận' in answer['draft']
    assert 'tới nay' not in answer['draft']
    assert answer['claims'][0]['text'] in answer['draft']
    assert answer['claims'][0]['support_quotes'][0]['quote'] == original


def pack():
    doc = news_documents([dict(article_id=str(uuid4()), source='official', title='Nhân sự FPT',
        content=QUOTE, symbols=['FPT'], url='https://example.org/leadership')])[0]
    chunk = chunk_document(doc)[0]
    return dict(schema_version='1.1', query_id=str(uuid4()), corpus_version_id=CID, retrieval_backend='neo4j_source_replay',
        data_version=dict(kind='INDEX', id=IID), items=[dict(evidence_id=str(uuid4()),
        chunk_id=str(uuid4()), source_id=str(uuid4()), source_type='NEWS', title='Nhân sự FPT', passage=chunk.text,
        source_sha256='a'*64, content_sha256=chunk.content_hash, locator=chunk.locator,
        source_verified=True, score=dict(type='RRF', value=1.0))])


class Predictor:
    model_version = 'unit-policy'
    def predict(self, text):
        return (0.01, 0.99)


class Graph:
    def __init__(self, error=None):
        self.calls = []
        self.error = error
    async def retrieve(self, scope):
        self.calls.append(copy.deepcopy(scope.model_dump()))
        if self.error:
            raise self.error
        value = pack()
        return value, [dict(graph_version_id='verified-version', relation_id='reviewed-relation',
            companies=['FPT'], source_scoped=True, relation_type='HOLDS_ROLE',
            subject='Trương Gia Bình', object='FPT', position='Chủ tịch',
            evidence_ids=[value['items'][0]['evidence_id']])]


class Content:
    def __init__(self): self.calls = []
    async def retrieve(self, question, scope):
        self.calls.append(copy.deepcopy(scope))
        return pack()


class Provider:
    async def count_tokens(self, request): return 100
    async def generate(self, request):
        import json
        item = json.loads(request['contents'][0]['parts'][0]['text'])['evidence'][0]
        return dict(model_version='isolated-provider', usage=dict(input_tokens=100, output_tokens=10, total_tokens=110),
            payload=dict(claims=[dict(text=QUOTE, evidence_ids=[item['evidence_id']],
                support_quotes=[dict(evidence_id=item['evidence_id'], quote=QUOTE)])]))


def service(graph=None):
    content, graph = Content(), graph or Graph()
    route = WebChatRouter(lambda: DecisionEngine(Predictor()), graph, content)
    return LiveResearchService(content, provider=Provider(), hybrid_router=route), graph, content


@pytest.mark.parametrize('question', [
    'Ai là Chủ tịch FPT?', 'Chủ tịch HĐQT của VCB là ai?',
    'Liệt kê các thành viên hội đồng quản trị FPT.',
    'FPT có bao nhiêu thành viên hội đồng quản trị?',
    'Theo BCTN FPT năm 2025, ai là Chủ tịch?',
])
def test_graph_questions_never_fall_into_news_retrieval(question):
    engine, graph, content = service()
    result = asyncio.run(engine.answer(question, 'test'))
    assert len(graph.calls) == 1
    assert content.calls == []
    assert result['hybrid_router']['route'] == 'GRAPH'
    assert result['answering']['status'] == 'DRAFT_READY'
    assert result['hybrid_router']['vector_calls'] == 0
    assert prepare_evidence(result['evidence_pack'])
    assert 'chưa xác nhận chức vụ hiện tại' in result['answering']['draft']


def test_vector_financial_question_keeps_existing_content_pipeline():
    engine, graph, content = service()
    result = asyncio.run(engine.answer('Tổng tài sản FPT năm 2025?', 'test'))
    assert len(content.calls) == 1
    assert graph.calls == []
    assert content.calls[0]['source_type'] == 'BCTC'


def test_failed_classifier_keeps_financial_path_but_never_misroutes_graph_to_news():
    engine, graph, content = service()
    def unavailable(): raise OSError('isolated model path')
    engine.hybrid_router.planner_factory = unavailable
    result = asyncio.run(engine.answer('Ai là Chủ tịch FPT?', 'test'))
    assert result['reason_code'] == 'CHAT_ROUTER_UNAVAILABLE'
    assert not graph.calls and not content.calls
    asyncio.run(engine.answer('Tổng tài sản FPT năm 2025?', 'test'))
    assert len(content.calls) == 1


@pytest.mark.parametrize('error,code', [(OSError('private database detail'), 'GRAPH_CHAT_UNAVAILABLE'),
    (GraphChatError('GRAPH_SOURCE_MISMATCH'), 'GRAPH_SOURCE_MISMATCH'),
    (TimeoutError(), 'GRAPH_CHAT_TIMEOUT')])
def test_graph_failure_never_falls_back_to_news_or_leaks_exception(error, code):
    engine, graph, content = service(Graph(error))
    result = asyncio.run(engine.answer('Ai là Chủ tịch FPT?', 'test'))
    assert result['reason_code'] == code
    assert not content.calls
    assert 'private database' not in str(result)
    assert not result.get('answering')


def test_both_executes_graph_then_vector_and_pins_the_same_version():
    engine, graph, content = service()
    result = asyncio.run(engine.answer('Chủ tịch FPT nói gì về chiến lược năm 2025?', 'test'))
    assert result['hybrid_router']['route'] == 'BOTH'
    assert len(graph.calls) == len(content.calls) == 1
    assert result['retrieval_backend'] == 'neo4j_and_vector'


def test_both_rejects_mixed_corpus_versions():
    engine, graph, content = service()
    async def wrong(*args):
        value = pack()
        value['corpus_version_id'] = str(uuid4())
        return value
    content.retrieve = wrong
    result = asyncio.run(engine.answer('Chủ tịch FPT nói gì về chiến lược năm 2025?', 'test'))
    assert result['reason_code'] == 'GRAPH_VECTOR_VERSION_MISMATCH'
    assert not result.get('answering')


def test_both_deduplicates_identical_source_with_different_rank_score():
    engine, graph, content = service()
    shared = pack()
    async def graph_result(scope):
        return copy.deepcopy(shared), [dict(companies=['FPT'], relation_type='HOLDS_ROLE')]
    async def content_result(*args):
        value = copy.deepcopy(shared)
        value['items'][0]['score']['value'] = 0.01
        return value
    graph.retrieve, content.retrieve = graph_result, content_result
    result = asyncio.run(engine.answer('Chủ tịch FPT nói gì về chiến lược năm 2025?', 'test'))
    assert result['status'] == 'EVIDENCE_READY'
    assert len(result['evidence_pack']['items']) == 1
    assert result['answering']['status'] == 'DRAFT_READY'


def test_web_message_api_persists_graph_result_and_routes_followup(tmp_path):
    engine, graph, content = service()
    app = FastAPI()
    app.include_router(api.router)
    store = SessionStore(tmp_path, engine=engine)
    owner = str(uuid4())
    app.dependency_overrides[api.get_owner] = lambda: owner
    app.dependency_overrides[api.get_store] = lambda: store
    with TestClient(app) as client:
        snapshot = client.post('/api/research/chat/sessions').json()
        path = f"/api/research/chat/sessions/{snapshot['session_id']}/messages"
        first = client.post(path, json=dict(text='Ai là Chủ tịch FPT?', revision=0))
        assert first.status_code == 200, first.text
        first = first.json()
        assert first['messages'][-1]['result']['hybrid_router']['route'] == 'GRAPH'
        followup = client.post(path, json=dict(text='Có thể liệt kê ra không?', revision=first['revision']))
        assert followup.status_code == 200, followup.text
        assert followup.json()['messages'][-1]['result']['hybrid_router']['route'] == 'GRAPH'
        followup = followup.json()
        reference = client.post(path, json=dict(text='Nguồn đâu?', revision=followup['revision']))
        assert reference.status_code == 200, reference.text
        assert reference.json()['messages'][-1]['result']['reason_code'] == 'SOURCE_REFERENCE'
        assert 'Nhân sự FPT' in reference.json()['messages'][-1]['content']
        assert len(graph.calls) == 2
        assert not content.calls


def test_release_alias_replay_requires_hash_document_version_and_logical_source():
    old_cid, old_iid, old_chunk, new_chunk, doc = [str(uuid4()) for _ in range(5)]
    digest = hashlib.sha256(QUOTE.encode()).hexdigest()
    locator = dict(source_table='annual_reports', source_id='report:1', reconstruction=dict(document_id=doc))
    original = VerifiedSource(doc, 'a'*64, old_chunk, old_cid, old_iid, 'a'*64, digest, {}, QUOTE)
    current = replace(original, chunk_id=new_chunk, corpus_id=CID, index_version_id=IID)
    ref = dict(document_id=doc, document_version='a'*64, chunk_id=old_chunk, corpus_id=old_cid,
        index_version_id=old_iid, source_sha256='a'*64, content_hash=digest, locator={}, quote=QUOTE)

    class Reader:
        def __init__(self):
            self.cache = {('wbs06-row', old_chunk, old_cid): dict(locator_json=locator),
                          ('wbs06-row', new_chunk, CID): dict(locator_json=locator)}
            self.connection = self
            self.current = current
        async def read_current(self, chunk, corpus): return original if chunk == old_chunk else self.current
        async def prefetch(self, *args): pass
        async def fetch(self, sql, *args):
            assert "cv.status='FROZEN'" in sql and 'cd.document_hash=d.sha256' in sql
            assert args[-1] == doc
            return [dict(chunk_id=new_chunk)]

    reader = Reader()
    graph = Neo4jChatRetriever(None, None)
    replay, _ = asyncio.run(graph._replay(reader, ref, dict(source_scoped=True), CID, IID))
    assert replay.chunk_id == new_chunk
    reader.current = replace(current, source_sha256='b'*64)
    with pytest.raises(GraphChatError, match='GRAPH_SOURCE_VERSION_MISMATCH'):
        asyncio.run(graph._replay(reader, ref, dict(source_scoped=True), CID, IID))
    reader.current = replace(current, content_hash='b'*64)
    with pytest.raises(GraphChatError, match='GRAPH_SOURCE_VERSION_MISMATCH'):
        asyncio.run(graph._replay(reader, ref, dict(source_scoped=True), CID, IID))
    bad = {**ref, 'quote': 'Invented role'}
    with pytest.raises(SourceProblem):
        asyncio.run(graph._replay(reader, bad, dict(source_scoped=True), CID, IID))


def test_source_graph_filters_board_roles_without_counting_ceo_or_unreviewed_edges():
    from src.graph.viewer import SOURCE_SCOPE
    nodes = {
        'company': dict(id='company', type='Company', label='FPT', aliases=['FPT'], attributes=dict(symbol='FPT')),
        'chair': dict(id='chair', type='Person', label='Chair', aliases=[], attributes={}),
        'vice': dict(id='vice', type='Person', label='Vice', aliases=[], attributes={}),
        'ceo': dict(id='ceo', type='Person', label='CEO', aliases=[], attributes={}),
    }
    def edge(person, position):
        return dict(relation_id=person, subject_id=person, object_id='company',
            relation_type='HOLDS_ROLE', review_status='SOURCE_REVIEWED', evidence=[dict(chunk_id=str(uuid4()))],
            attributes=dict(position=position, source_report_year='2025',
                source_review_status='APPROVED_IN_SOURCE_REPORT', identity_scope='SOURCE_OCCURRENCE',
                time_scope='SOURCE_DOCUMENT_NOT_CURRENT_OFFICE'))
    edges = [edge('chair', 'Chủ tịch HĐQT'), edge('vice', 'Phó Chủ tịch HĐQT'), edge('ceo', 'Tổng Giám đốc')]
    class Viewer:
        def versions(self):
            return [dict(graph_version_id='source', status='READY', serving_scope=SOURCE_SCOPE)]
        def entities(self, *args): return [nodes['company']], False
        def nodes(self, *args): return nodes
        def neighborhood(self, *args, **kwargs):
            assert kwargs['hops'] == 1
            assert kwargs['relation_types'] == ['HOLDS_ROLE']
            return edges, False
    graph = Neo4jChatRetriever(None, Viewer)
    plan = DecisionEngine(Predictor()).decide('Liệt kê thành viên HĐQT FPT năm 2025.')
    facts = graph._query(plan.scope, CID, IID)
    assert {f['relation_id'] for f in facts} == {'chair', 'vice'}
    chair = DecisionEngine(Predictor()).decide('Chủ tịch HĐQT FPT năm 2025 là ai?')
    assert [f['relation_id'] for f in graph._query(chair.scope, CID, IID)] == ['chair']
    edges[0]['attributes']['source_report_year'] = '2024'
    latest_board = DecisionEngine(Predictor()).decide('Liệt kê HĐQT FPT.')
    assert [f['relation_id'] for f in graph._query(latest_board.scope, CID, IID)] == ['vice']
    latest_chair = DecisionEngine(Predictor()).decide('Chủ tịch HĐQT FPT là ai?')
    assert graph._query(latest_chair.scope, CID, IID) == []
    historical_chair = DecisionEngine(Predictor()).decide('Chủ tịch HĐQT FPT năm 2024 là ai?')
    assert [f['relation_id'] for f in graph._query(historical_chair.scope, CID, IID)] == ['chair']
    edges[0]['attributes']['source_report_year'] = '2025'
    edges[0]['attributes']['source_review_status'] = 'PENDING'
    with pytest.raises(GraphChatError, match='GRAPH_UNREVIEWED_RELATION'):
        graph._query(chair.scope, CID, IID)


def test_ownership_query_cannot_return_person_role_claims():
    plan = DecisionEngine(Predictor()).decide('FPT có những cổ đông nào?')
    assert plan.route == 'GRAPH'
    assert plan.scope.relation_types == ['OWNS_SHARES']


def test_global_graph_uses_trusted_ticker_mapping_and_bounded_viewer_limit():
    company = dict(id='canonical-company-id', type='Company', label='A canonical company name', aliases=[], attributes={})
    person = dict(id='person', type='Person', label='A reviewed person', aliases=[], attributes={})
    class Viewer:
        def versions(self):
            return [dict(graph_version_id='approved', status='READY', corpus_id=CID, index_version_id=IID)]
        def entities(self, version, query, kind, limit):
            assert query == company['id']
            return [company], False
        def nodes(self, *args): return {company['id']: company, 'person': person}
        def neighborhood(self, *args, **kwargs):
            # GraphViewerReader asks RelationRetrieval for limit+1 (max 200).
            assert kwargs['limit'] < 200
            return [dict(relation_id='approved-role', subject_id='person', object_id=company['id'],
                relation_type='HOLDS_ROLE', reviewer='trusted-reviewer', reviewed_at='2025-01-01',
                attributes=dict(position='Chủ tịch'), evidence=[dict(chunk_id=str(uuid4()))])], False
    graph = Neo4jChatRetriever(None, Viewer, lambda: {company['id']: 'TCB'})
    scope = DecisionEngine(Predictor()).decide('Ai là Chủ tịch TCB năm 2025?').scope
    facts = graph._query(scope, CID, IID)
    assert len(facts) == 1
    assert facts[0]['companies'] == ['TCB']
    assert facts[0]['origin_corpus_id'] == CID


def _viewer_with_versions(versions):
    company = dict(id='canonical-company-id', type='Company', label='A canonical company name', aliases=[], attributes={})
    person = dict(id='person', type='Person', label='A reviewed person', aliases=[], attributes={})
    class Viewer:
        def versions(self):
            return versions
        def entities(self, version, query, kind, limit):
            return [company], False
        def nodes(self, *args): return {company['id']: company, 'person': person}
        def neighborhood(self, *args, **kwargs):
            return [dict(relation_id='r', subject_id='person', object_id=company['id'], relation_type='HOLDS_ROLE',
                reviewer='trusted-reviewer', reviewed_at='2025-01-01', attributes=dict(position='Chủ tịch'),
                evidence=[dict(chunk_id=str(uuid4()))])], False
    return Viewer, {company['id']: 'TCB'}


def test_graph_of_an_earlier_corpus_is_used_only_when_it_is_listed_and_keeps_its_origin():
    EARLIER = 'earlier-corpus-id'
    Viewer, tickers = _viewer_with_versions([
        dict(graph_version_id='old', status='READY', corpus_id=EARLIER, index_version_id='old-index'),
        dict(graph_version_id='fixture', status='READY', corpus_id='wbs08-fixture-corpus', index_version_id='x')])
    graph = Neo4jChatRetriever(None, Viewer, lambda: tickers)
    scope = DecisionEngine(Predictor()).decide('Ai là Chủ tịch TCB năm 2025?').scope
    assert graph._query(scope, CID, IID) == []                                    # not listed: ignored, as before
    facts = graph._query(scope, CID, IID, frozenset({EARLIER}))
    assert [f['graph_version_id'] for f in facts] == ['old']                      # the fixture graph is never used
    assert facts[0]['origin_corpus_id'] == EARLIER                                # sources replay against the origin


class EmptyGraph(Graph):
    async def retrieve(self, scope):
        self.calls.append(copy.deepcopy(scope.model_dump()))
        value = pack()
        value['items'] = []
        return value, []


@pytest.mark.parametrize('question', [
    'Tổng tài sản FPT năm 2025 của công ty mẹ là bao nhiêu?',
])
def test_empty_graph_on_a_statement_question_falls_through_to_the_content_pipeline(question):
    engine, graph, content = service(EmptyGraph())
    result = asyncio.run(engine.answer(question, 'test'))
    assert len(graph.calls) == 1
    assert len(content.calls) == 1
    assert content.calls[0]['source_type'] == 'BCTC'
    assert result.get('reason_code') != 'GRAPH_NO_VERIFIED_RELATIONS'


def test_empty_graph_on_an_annual_report_relationship_question_searches_the_annual_report():
    engine, graph, content = service(EmptyGraph())
    result = asyncio.run(engine.answer('Theo BCTN FPT năm 2025, ai là Chủ tịch?', 'test'))
    assert len(graph.calls) == 1
    assert len(content.calls) == 1
    assert content.calls[0]['source_type'] == 'BCTN'
    assert result.get('reason_code') != 'GRAPH_NO_VERIFIED_RELATIONS'


def test_empty_graph_on_a_news_relationship_question_stays_no_data_and_never_reads_news():
    engine, graph, content = service(EmptyGraph())
    result = asyncio.run(engine.answer('Theo tin tức, FPT hợp tác với những đối tác nào?', 'test'))
    if graph.calls:
        assert content.calls == []
        assert result['reason_code'] == 'GRAPH_NO_VERIFIED_RELATIONS'


class EmptyContent(Content):
    async def retrieve(self, question, scope):
        self.calls.append(copy.deepcopy(scope))
        value = pack()
        value['items'] = []
        return value


def test_statement_fallback_with_no_evidence_reports_missing_evidence_not_a_relationship_error():
    content = EmptyContent()
    graph = EmptyGraph()
    engine = LiveResearchService(content, provider=Provider(), hybrid_router=WebChatRouter(lambda: DecisionEngine(Predictor()), graph, content))
    result = asyncio.run(engine.answer('Tổng tài sản FPT năm 2025 của công ty mẹ là bao nhiêu?', 'test'))
    assert len(content.calls) == 1
    assert result['reason_code'] == 'NO_DATA'
    assert 'quan hệ' not in result['message']


@pytest.mark.parametrize('question,metric', [
    ('Lợi nhuận sau thuế thuộc cổ đông công ty mẹ FPT năm 2025 là bao nhiêu?', 'PARENT_NET_PROFIT'),
    ('Vốn chủ sở hữu của FPT năm 2025 là bao nhiêu?', 'OWNERS_EQUITY'),
])
def test_relationship_words_inside_a_metric_name_do_not_send_a_financial_question_to_the_graph(question, metric):
    engine, graph, content = service()
    asyncio.run(engine.answer(question, 'test'))
    assert graph.calls == []
    assert len(content.calls) == 1 and content.calls[0]['metric_code'] == metric


def test_a_person_question_that_also_names_a_metric_still_uses_the_graph():
    engine, graph, content = service()
    asyncio.run(engine.answer('Chủ tịch FPT nói gì về lợi nhuận sau thuế năm 2025?', 'test'))
    assert len(graph.calls) == 1


def test_empty_graph_on_a_statement_question_that_needs_a_metric_choice_asks_that_choice():
    engine, graph, content = service(EmptyGraph())
    router = engine.hybrid_router
    async def never(question, context): return False          # force the graph route for this question
    router._only_a_metric_question = never
    result = asyncio.run(engine.answer('Lợi nhuận sau thuế thuộc cổ đông công ty mẹ và lãi cơ bản trên cổ phiếu của FPT năm 2025?', 'test'))
    if graph.calls:
        assert content.calls == []
        assert result['reason_code'] == 'MULTIPLE_METRICS'
        assert [o['metric_code'] for o in result['clarification_options']] == ['PARENT_NET_PROFIT', 'BASIC_EARNINGS_PER_SHARE']
