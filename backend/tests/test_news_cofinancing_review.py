"""A direct co-financing claim must not be treated as mere co-occurrence."""
import asyncio,hashlib
import pytest
from src.graph_review.engine import IdentityRegistry,ReviewEngine
from src.graph_review.models import VerifiedSource
from src.graph_review.sources import FixtureSourceReader

def evaluate(sentence,*,date=True):
    rows=[dict(entity_id=ident,entity_type='Company',canonical_name=name,aliases=[name],
        ticker_aliases=[],identity_key='name:'+ident,verified=True) for ident,name in
        [('company:a','Ngân hàng A'),('company:b','Ngân hàng B')]]
    text=('Ngày 23/10/2026, ' if date else '')+sentence
    content_hash=hashlib.sha256(text.encode()).hexdigest()
    ref=dict(document_id='doc',document_version='1',chunk_id='chunk',corpus_id='corpus',index_version_id='index',
        source_sha256='a'*64,content_hash=content_hash,locator={'source_table':'news_articles','source_id':'article'},quote=text)
    source=VerifiedSource(**{k:v for k,v in ref.items() if k!='quote'},text=text)
    candidate=dict(candidate_id='cofinancing-proof',group='company',relation_type='COOPERATES_WITH',
        subject={k:v for k,v in rows[0].items() if k not in ('verified','ticker_aliases')}|{'resolution_status':'resolved'},
        object={k:v for k,v in rows[1].items() if k not in ('verified','ticker_aliases')}|{'resolution_status':'resolved'},
        evidence=[ref],attributes={'cooperation_scope':'đồng tài trợ'},
        temporal={'as_of':'2026-10-23'} if date else {})
    return asyncio.run(ReviewEngine(FixtureSourceReader([source]),IdentityRegistry(rows)).evaluate(candidate))

@pytest.mark.parametrize('sentence',[
    'Ngân hàng A và Ngân hàng B bắt tay đồng tài trợ dự án.',
    'Ngân hàng B và Ngân hàng A đã đồng tài trợ dự án.',
])
def test_explicit_two_party_cofinancing_is_supported(sentence):
    result=evaluate(sentence)
    assert result.status=='APPROVED' and result.checks['direct_relation_supported']
    assert not result.load_allowed  # A fixture never authorizes a real graph write.

@pytest.mark.parametrize('sentence',[
    'Ngân hàng A và Ngân hàng B cùng tham dự hội nghị đồng tài trợ.',
    'Ngân hàng A và Ngân hàng B không bắt tay đồng tài trợ.',
    'Ngân hàng A và Ngân hàng B sẽ bắt tay đồng tài trợ dự án.',
    'Ngân hàng A và Ngân hàng B dự kiến đồng tài trợ dự án.',
    'Ngân hàng A và Ngân hàng B có thể đồng tài trợ dự án.',
])
def test_mention_negation_or_plan_is_not_completed_cooperation(sentence):
    assert evaluate(sentence).status!='APPROVED'

def test_direct_action_does_not_invent_a_missing_effective_date():
    result=evaluate('Ngân hàng A và Ngân hàng B bắt tay đồng tài trợ dự án.',date=False)
    assert result.status=='PENDING'
    assert result.reasons==['WARN_TEMPORAL_BASIS_MISSING']
