"""Independent adversarial scope checks; no network or writes to Neo4j."""
from copy import deepcopy
from uuid import uuid4
import pytest
from src.graph.viewer import SOURCE_SCOPE
from src.retrieval_orchestration.hybrid_router.decision_engine import SessionScope
from src.retrieval_orchestration.web_chat_router import Neo4jChatRetriever,GraphChatError

CID,IID=str(uuid4()),str(uuid4())

def company(ident,symbol): return dict(id=ident,type='Company',label=symbol,aliases=[symbol],attributes=dict(symbol=symbol))
def role(person='chair',year='2025',position='Chủ tịch HĐQT'):
    return dict(relation_id=person,subject_id=person,object_id='fpt',relation_type='HOLDS_ROLE',
        review_status='SOURCE_REVIEWED',evidence=[dict(chunk_id=str(uuid4()))],
        attributes=dict(position=position,source_report_year=year,source_review_status='APPROVED_IN_SOURCE_REPORT',
            identity_scope='SOURCE_OCCURRENCE',time_scope='SOURCE_DOCUMENT_NOT_CURRENT_OFFICE'))

def adapter(edges,*,source=False,truncated=False,ready=True):
    nodes={'fpt':company('fpt','FPT'),'other':company('other','OTHER'),
        **{name:dict(id=name,type='Person',label=name,aliases=[],attributes={}) for name in ['chair','vice','ceo']}}
    class Reader:
        def versions(self):
            return [dict(graph_version_id='isolated-reviewed',status='READY' if ready else 'BUILDING',
                         corpus_id=CID,index_version_id=IID,**(dict(serving_scope=SOURCE_SCOPE) if source else {}))]
        def entities(self,*args): return [nodes['fpt']],False
        def neighborhood(self,*args,**kwargs): return deepcopy(edges),truncated
        def nodes(self,*args): return nodes
    return Neo4jChatRetriever(None,Reader)

def scope(types=None,period='2025',position=None):
    return SessionScope(companies=['FPT'],periods=[period],relation_types=types or ['HAS_SUBSIDIARY'],position_code=position)

def relation(subject,object_,kind='HAS_SUBSIDIARY'):
    return dict(relation_id=subject+'-'+object_,subject_id=subject,object_id=object_,relation_type=kind,
        reviewer='approved-reviewer',reviewed_at='2025-01-01',attributes={},evidence=[dict(chunk_id=str(uuid4()))])


def test_requested_subsidiaries_do_not_include_incoming_parent_edges():
    # Business requirement independent of implementation: children OF FPT, not FPT's parent.
    graph=adapter([relation('other','fpt')])
    facts=graph._query(scope(),CID,IID)
    assert not facts, 'Incoming OTHER -> FPT was accepted for subsidiaries OF FPT'


def test_requested_associates_do_not_include_incoming_owner_edges():
    graph=adapter([relation('other','fpt','HAS_ASSOCIATE')])
    assert not graph._query(scope(['HAS_ASSOCIATE']),CID,IID), 'Incoming relation accepted for associates OF FPT'


def test_outgoing_subsidiary_edge_is_kept():
    facts=adapter([relation('fpt','other')])._query(scope(),CID,IID)
    assert len(facts)==1 and facts[0]['subject']=='FPT' and facts[0]['object']=='OTHER'


def test_associate_does_not_replace_subsidiary():
    assert not adapter([relation('fpt','other','HAS_ASSOCIATE')])._query(scope(),CID,IID)


def test_building_graph_is_not_a_ready_source():
    assert not adapter([relation('fpt','other')],ready=False)._query(scope(),CID,IID)


def test_graph_truncation_is_not_silent_success():
    with pytest.raises(GraphChatError,match='GRAPH_RESULT_TRUNCATED'):
        adapter([relation('fpt','other')],truncated=True)._query(scope(),CID,IID)


def test_pending_source_relation_cannot_be_returned():
    edge=role();edge['attributes']['source_review_status']='PENDING'
    with pytest.raises(GraphChatError,match='GRAPH_UNREVIEWED_RELATION'):
        adapter([edge],source=True)._query(scope(['HOLDS_ROLE']),CID,IID)


def test_explicit_report_year_does_not_return_another_year():
    assert not adapter([role(year='2024')],source=True)._query(scope(['HOLDS_ROLE'],period='2025'),CID,IID)


def test_report_year_cannot_be_promoted_to_quarter_of_office():
    assert not adapter([role()],source=True)._query(scope(['HOLDS_ROLE'],period='2025-Q1'),CID,IID)


def test_chairman_is_not_vice_chairman():
    from src.retrieval_orchestration.hybrid_router.decision_engine import ScopeResolver
    resolved=ScopeResolver().resolve('Ai là Chủ tịch HĐQT FPT năm 2025?')
    rows=adapter([role(),role('vice',position='Phó Chủ tịch HĐQT')],source=True)._query(resolved.scope,CID,IID)
    assert [r['subject'] for r in rows]==['chair']
