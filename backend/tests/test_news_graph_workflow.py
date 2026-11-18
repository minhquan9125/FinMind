import asyncio,uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from src.auth.authorization import Principal
from src.graph_review import news_workflow as flow
from src.graph_review.adapters import from_envelope
from tests.test_news_graph_contract import payload

class Connection:
    def __init__(self,status='DRAFT'):self.status=status;self.queries=[]
    def transaction(self,**kwargs):return self
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def execute(self,sql,*args):self.queries.append(sql)
    async def fetchval(self,*args):return self.status

def actor(role='ADMINISTRATOR'):return Principal(uuid.uuid4(),frozenset({role}))

def candidate():return from_envelope(payload())[0]

def test_non_admin_never_starts_a_transaction():
    connection=Connection()
    with pytest.raises(PermissionError):asyncio.run(flow.approve_news(connection,actor('RESEARCHER'),uuid.uuid4(),candidate(),'note'))
    assert connection.queries==[]

def test_invalid_or_pending_claim_is_never_saved_as_approved(monkeypatch):
    store=SimpleNamespace(save=AsyncMock(),review=AsyncMock())
    monkeypatch.setattr(flow,'PostgresReviewStore',lambda _:store)
    monkeypatch.setattr(flow,'review_engine',lambda _:object())
    monkeypatch.setattr(flow,'evaluate_with_peers',AsyncMock(return_value=SimpleNamespace(
        status='PENDING',load_allowed=False,reasons=['WARN_ENTITY_UNVERIFIED'])))
    with pytest.raises(ValueError,match='NEWS_REVIEW_NOT_READY'):
        asyncio.run(flow.approve_news(Connection(),actor(),uuid.uuid4(),candidate(),'note'))
    store.save.assert_not_called();store.review.assert_not_called()

def test_ready_claim_uses_existing_store_audit_and_authenticated_actor(monkeypatch):
    store=SimpleNamespace(save=AsyncMock(return_value={'review_id':'review','result':{'status':'APPROVED'},'revision':1}),
                          review=AsyncMock(return_value={'saved':True}))
    monkeypatch.setattr(flow,'PostgresReviewStore',lambda _:store)
    monkeypatch.setattr(flow,'review_engine',lambda _:object())
    fresh=SimpleNamespace(status='APPROVED',load_allowed=True)
    monkeypatch.setattr(flow,'evaluate_with_peers',AsyncMock(return_value=fresh))
    principal=actor()
    result=asyncio.run(flow.approve_news(Connection(),principal,uuid.uuid4(),candidate(),'Reviewed exact quotes'))
    assert result=={'saved':True}
    assert store.save.call_args.args[3] is principal
    assert store.review.call_args.args[3] is principal
    assert store.review.call_args.args[4]=='Reviewed exact quotes'
    assert store.review.call_args.kwargs['evidence_confirmed'] is False

def test_published_graph_cannot_be_edited_during_new_approval():
    with pytest.raises(flow.ReviewConflict,match='GRAPH_VERSION_NOT_REVIEWABLE'):
        asyncio.run(flow.approve_news(Connection('READY'),actor(),uuid.uuid4(),candidate(),'note'))

def test_empty_approval_set_does_not_even_construct_a_neo4j_writer(monkeypatch):
    from src.graph_review import repository
    monkeypatch.setattr(repository,'approved_records',AsyncMock(return_value=[]))
    monkeypatch.setattr(flow,'review_engine',lambda _:object())
    def forbidden():raise AssertionError('no stored approvals means no Neo4j writer')
    with pytest.raises(ValueError,match='NO_APPROVED_NEWS_RELATIONS'):
        asyncio.run(flow.publish_news(Connection(),actor(),uuid.uuid4(),forbidden))

def test_saved_news_candidate_roundtrips_the_exact_export_gate():
    from src.graph_review.gate import core
    from src.graph_review.models import digest
    value=candidate()
    assert digest(core(flow.news_candidate(value)))==digest(core(value))
    value['conflicts']=['conflicting source']
    assert flow.news_candidate(value)['conflicts']==['conflicting source']

def test_publish_revalidates_and_updates_pg_only_after_ready_neo4j_receipt(monkeypatch):
    from src.graph_review import repository,export,gate
    from src.graph import wbs09_pipeline
    value=payload();candidate_raw=from_envelope(value)[0]
    monkeypatch.setattr(repository,'approved_records',AsyncMock(return_value=[dict(candidate=candidate_raw)]))
    monkeypatch.setattr(export,'make_envelope',AsyncMock(return_value=value))
    bound_gate=object()
    checked=AsyncMock(return_value=bound_gate)
    monkeypatch.setattr(gate,'build_gate',checked)
    monkeypatch.setattr(flow,'review_engine',lambda _:SimpleNamespace(reader=object()))
    def build(store,envelopes,*,graph_version_id,approve):
        assert envelopes==[value] and approve(value) is bound_gate
        return dict(status='READY',counts={'loaded':1})
    monkeypatch.setattr(wbs09_pipeline,'build_graph_version',build)
    connection=Connection()
    result=asyncio.run(flow.publish_news(connection,actor(),uuid.uuid4(),lambda:object()))
    assert result['status']=='READY' and checked.await_count==1
    assert any("status='READY'" in q for q in connection.queries)
