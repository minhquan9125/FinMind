"""WBS10 adapter contract, scope and failures without DB/model/network."""
import asyncio,copy,threading
import pytest
from tests.test_live_research import pack,CORPUS,INDEX
from src.b1_answering.evidence.citations import prepare_evidence,validate_draft
from src.retrieval_orchestration.hybrid_router.adapters import AdapterResult
from src.retrieval_orchestration.hybrid_router.schemas import RouterTask
from src.retrieval_orchestration.hybrid_router.vector_adapter import VectorRAGAdapter
from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine,SessionScope
from src.vector_retrieval.backend import RetrievalError

@pytest.fixture
def loop():
    value=asyncio.new_event_loop();thread=threading.Thread(target=value.run_forever,daemon=True);thread.start()
    yield value
    value.call_soon_threadsafe(value.stop);thread.join();value.close()

def task(**kwargs):
    params=dict(question='Tiền FPT quý 2/2026?',companies=['FPT'],periods=['2026-Q2'],source_type='BCTC',corpus_version_id=CORPUS)
    params.update(kwargs)
    return RouterTask(id='v1',adapter='CONTENT',operation='find_metric',params=params)

def response(**scope):
    item=pack()['items'][0]
    return dict(corpus_version_id=CORPUS,index_version_id=INDEX,index_status='ACTIVE',scope_mode='CORPUS',scope=scope,
        results=[dict(chunk_id=item['chunk_id'],document_id=item['source_id'],text=item['passage'],title='FPT financial fixture',
        locator=item['locator'],content_hash=item['content_sha256'],source_sha256=item['source_sha256'],rrf_score=.03,
        dense_rank=1,bm25_rank=2)])

def test_full_source_and_citation_contract_survive(loop):
    calls=[]
    async def search(q,**kw):
        calls.append(kw);kw.pop('top_k');return response(**kw)
    adapter=VectorRAGAdapter(search,loop,corpus_version_id=CORPUS)
    result=adapter.execute(task())
    assert result.status=='OK'
    assert calls[0]['doc_type']=='FINANCIAL_STATEMENT'
    evidence=prepare_evidence(result.evidence_pack);item=next(iter(evidence.values()))
    draft=validate_draft(dict(claims=[dict(text=item['passage'],evidence_ids=[item['evidence_id']])]),evidence)
    assert draft['citations'][0]['chunk_id']==item['chunk_id']
    assert result.data[0]['text']==item['passage'] and result.data[0]['bm25_rank']==2
    assert result.evidence_pack['corpus_version_id']==CORPUS

def test_multi_scope_fans_out_without_broadening_and_partial_fails(loop):
    calls=[]
    async def search(q,**kw):
        calls.append(kw.copy());kw.pop('top_k');r=response(**kw)
        if kw['company']=='VCB':r['results']=[]
        return r
    result=VectorRAGAdapter(search,loop,corpus_version_id=CORPUS).execute(task(companies=['FPT','VCB'],periods=['2025','2026']))
    assert [(r['company'],r['period']) for r in calls]==[('FPT','2025'),('FPT','2026'),('VCB','2025'),('VCB','2026')]
    assert result.reason_code=='VECTOR_PARTIAL_COVERAGE' and not result.evidence

@pytest.mark.parametrize('code,status',[('CACHE_STALE','SYSTEM_UNAVAILABLE'),('HASH_MISMATCH','INSUFFICIENT_EVIDENCE'),('SOURCE_CHANGED','INSUFFICIENT_EVIDENCE')])
def test_failures_are_typed_and_never_expose_exception(loop,code,status):
    async def search(*a,**k):raise RetrievalError(code)
    result=VectorRAGAdapter(search,loop,corpus_version_id=CORPUS).execute(task())
    assert result.status==status and result.reason_code==code and not result.data

@pytest.mark.parametrize('change,expected',[('hash','INVALID_EVIDENCE'),('corpus','VECTOR_VERSION_MISMATCH'),('scope','VECTOR_SCOPE_MISMATCH')])
def test_rejects_changed_source_and_wrong_scope(loop,change,expected):
    async def search(q,**kw):
        kw.pop('top_k');r=response(**kw)
        if change=='hash':r['results'][0]['text']+=' altered'
        if change=='corpus':r['corpus_version_id']=INDEX
        if change=='scope':r['scope']['company']='VCB'
        return r
    result=VectorRAGAdapter(search,loop,corpus_version_id=CORPUS).execute(task())
    assert result.reason_code==expected and not result.evidence

def test_timeout_cancels_pending_retrieval(loop):
    cancelled=threading.Event()
    async def search(*a,**k):
        try:await asyncio.sleep(100)
        finally:cancelled.set()
    result=VectorRAGAdapter(search,loop,corpus_version_id=CORPUS,timeout=.05).execute(task())
    assert result.reason_code=='VECTOR_TIMEOUT' and cancelled.wait(1)

def test_dependency_ids_cannot_be_used_as_tickers(loop):
    async def search(*a,**k):raise AssertionError('must not broaden to all companies')
    dep=AdapterResult('g1','GRAPH','OK','OK',data=({'company_id':'entity-123'},))
    result=VectorRAGAdapter(search,loop,corpus_version_id=CORPUS).execute(task(),dependency=dep)
    assert result.reason_code=='VECTOR_DEPENDENCY_SCOPE_UNRESOLVED'

def test_vector_route_does_not_call_graph_and_passes_wbs10_scope(loop):
    class Predictor:
        model_version='test'
        def predict(self,q):return .01,.99
    class NoGraph:
        calls=[]
        def execute(self,*a,**k):raise AssertionError('VECTOR must not call GRAPH')
    async def search(q,**kw):kw.pop('top_k');return response(**kw)
    engine=DecisionEngine(Predictor(),graph_adapter=NoGraph(),content_adapter=VectorRAGAdapter(search,loop,corpus_version_id=CORPUS))
    result=engine.run('Tiền và tương đương tiền FPT quý 2 năm 2026?',context=SessionScope(source_type='BCTC',corpus_version_id=CORPUS,index_version_id=INDEX))
    assert result.status=='OK' and result.decision.route=='VECTOR'
    assert result.execution_mode=='LIVE' and result.reason_code=='LIVE_EXECUTION_OK'
    assert result.adapter_results[0].evidence_pack['data_version']['id']==INDEX

def test_empty_scope_returns_no_data(loop):
    async def search(q,**kw):
        kw.pop('top_k');r=response(**kw);r['results']=[];return r
    result=VectorRAGAdapter(search,loop,corpus_version_id=CORPUS).execute(task())
    assert result.status=='NO_DATA' and result.reason_code=='VECTOR_NO_RESULTS'
    assert not result.evidence and result.evidence_pack is None

def test_unknown_backend_error_never_leaks_connection_details(loop):
    async def search(*a,**k):raise RuntimeError('postgres://secret-password@private-host')
    result=VectorRAGAdapter(search,loop,corpus_version_id=CORPUS).execute(task())
    assert result.reason_code=='VECTOR_SEARCH_UNAVAILABLE' and 'secret' not in str(result.to_dict())

def test_factory_does_not_initialize_graph_for_vector(monkeypatch,loop):
    from src.api.routers import hybrid_router
    class Predictor:
        model_version='test';threshold=.65
        def predict(self,q):return .01,.99
    async def search(q,**kw):kw.pop('top_k');return response(**kw)
    monkeypatch.setattr(hybrid_router,'ArtifactPredictor',Predictor)
    monkeypatch.setattr(hybrid_router,'_build_live_content_adapter',lambda _:VectorRAGAdapter(search,loop,corpus_version_id=CORPUS))
    def forbidden():raise AssertionError('must not connect to Neo4j')
    monkeypatch.setattr(hybrid_router,'_build_live_graph_adapter',forbidden)
    result=hybrid_router._get_live_engine(loop).run('Tiền và tương đương tiền FPT quý 2 năm 2026?',context=SessionScope(source_type='BCTC'))
    assert result.status=='OK' and result.decision.route=='VECTOR'

def test_api_returns_full_evidence_pack_for_downstream(monkeypatch,loop):
    from src.api.routers import hybrid_router
    from types import SimpleNamespace
    class Predictor:
        model_version='test'
        def predict(self,q):return .01,.99
    async def search(q,**kw):kw.pop('top_k');return response(**kw)
    engine=DecisionEngine(Predictor(),content_adapter=VectorRAGAdapter(search,loop,corpus_version_id=CORPUS))
    monkeypatch.setattr(hybrid_router,'get_settings',lambda:SimpleNamespace(hybrid_router_mode='live'))
    monkeypatch.setattr(hybrid_router,'_get_live_engine',lambda _:engine)
    request=hybrid_router.RouterTestRequest(question='Tiền và tương đương tiền FPT quý 2 năm 2026?',
        context=hybrid_router.RouterContextPayload(source_type='BCTC',corpus_version_id=CORPUS))
    result=asyncio.run(hybrid_router.run_router(request))
    assert result['status']=='OK'
    item=result['adapter_results'][0]['evidence_pack']['items'][0]
    assert item['locator']['source_table']=='financial_reports' and len(item['content_sha256'])==64

def test_explicit_source_overrides_previous_source_but_keeps_corpus_pin():
    class Predictor:
        model_version='test'
        def predict(self,q):return .01,.99
    result=DecisionEngine(Predictor()).decide('Tóm tắt báo cáo thường niên FPT năm 2025.',
        context=SessionScope(source_type='NEWS',corpus_version_id=CORPUS,index_version_id=INDEX))
    assert result.scope.source_type=='BCTN'
    assert result.tasks[0].params['corpus_version_id']==CORPUS

def test_old_cache_with_page_numbers_as_period_is_not_reused():
    from src.vector_retrieval.backend import _validate_cache
    from src.vector_retrieval.ranking import TOKENIZER_VERSION
    old=dict(version=2,tokenizer=TOKENIZER_VERSION,index_id=INDEX,model='old',built_at=100,
        fingerprint='a'*32,rows=[])
    with pytest.raises(RetrievalError) as error:_validate_cache(old,INDEX,'old',100,3600)
    assert error.value.code=='CACHE_VERSION_MISMATCH'
