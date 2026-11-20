"""Independent fixtures for the two directional findings; no database access."""
from uuid import uuid4
import pytest
from src.retrieval_orchestration.web_chat_router import Neo4jChatRetriever
from src.retrieval_orchestration.hybrid_router.decision_engine import SessionScope


def facts(relation,incoming,direction=None):
    cid,iid=str(uuid4()),str(uuid4())
    nodes={name:dict(id=name,type='Company',label=name,aliases=[name],attributes=dict(symbol=name))
           for name in ('FPT','OTHER')}
    class Reader:
        def versions(self): return [dict(status='READY',graph_version_id='isolated-reviewed',corpus_id=cid,index_version_id=iid)]
        def entities(self,*args): return [nodes['FPT']],False
        def nodes(self,*args): return nodes
        def neighborhood(self,*args,**kwargs):
            return [dict(relation_id='fixture-relation',subject_id='OTHER' if incoming else 'FPT',
                object_id='FPT' if incoming else 'OTHER',relation_type=relation,
                reviewer='fixture-reviewer',reviewed_at='2025-01-01',attributes={},evidence=[dict(chunk_id=str(uuid4()))])],False
    scope=SessionScope(companies=['FPT'],periods=['2025'],relation_types=[relation], relation_direction=direction)
    return Neo4jChatRetriever(None,Reader)._query(scope,cid,iid)


@pytest.mark.parametrize('relation',['HAS_SUBSIDIARY','HAS_ASSOCIATE'])
def test_incoming_company_edge_is_not_a_related_company_owned_by_fpt(relation):
    assert not facts(relation,True)


@pytest.mark.parametrize('relation',['HAS_SUBSIDIARY','HAS_ASSOCIATE'])
def test_outgoing_company_edge_is_kept(relation):
    assert len(facts(relation,False))==1


def test_explicit_parent_query_keeps_only_incoming_subsidiary_edge():
    assert len(facts('HAS_SUBSIDIARY',True,'INCOMING')) == 1
    assert not facts('HAS_SUBSIDIARY',False,'INCOMING')


@pytest.mark.parametrize('relation',['OWNS_SHARES','COOPERATES_WITH','HOLDS_ROLE'])
def test_other_relation_directions_are_not_silently_removed(relation):
    assert len(facts(relation,True)) == 1
    assert len(facts(relation,False)) == 1
