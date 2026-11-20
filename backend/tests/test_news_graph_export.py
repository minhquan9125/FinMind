import asyncio,copy,uuid
from datetime import datetime,timezone
import pytest
from src.graph_review.export import make_envelope
from src.graph_review.adapters import from_envelope
from src.graph_review.models import Evidence,VerifiedSource
from src.graph_review.sources import SourceProblem
from tests.test_news_graph_contract import payload

def run_export(monkeypatch,*,attributed=True,change=False):
    value=payload();candidate=from_envelope(value)[0]
    ref=Evidence.model_validate(candidate['evidence'][0])
    source=VerifiedSource(**{k:v for k,v in ref.model_dump().items() if k!='quote'},text=value['chunks'][0]['text'])
    class Connection:
        async def fetchrow(self,*args):return dict(reviewed_by=uuid.uuid4() if attributed else None,
                                                   reviewed_at=datetime.now(timezone.utc))
        async def fetchval(self,*args):return source.locator
    class Reader:
        async def read_current(self,*args):return source
    async def root(*args):return dict(sources=[dict(source_table='news_articles',source_id=ref.locator['source_id'],source_uri='finmind:news:fixture')])
    monkeypatch.setattr('src.graph_review.export.read_release_root',root)
    if change:candidate['evidence'][0]['quote']='Unverified statement'
    result=asyncio.run(make_envelope(Connection(),[dict(candidate=candidate,review_id=str(uuid.uuid4()))],Reader()))
    return result,value

def test_export_uses_news_profile_and_preserves_hash_locator_quote(monkeypatch):
    result,value=run_export(monkeypatch)
    assert result['schema_version']=='2.3.0'
    assert result['chunks'][0]['locator']==value['chunks'][0]['locator']
    assert 'page' not in result['chunks'][0]['locator']
    assert result['relations'][0]['evidence']==value['relations'][0]['evidence']

def test_export_requires_real_saved_review_attribution(monkeypatch):
    with pytest.raises(ValueError,match='APPROVAL_ATTRIBUTION_MISSING'):run_export(monkeypatch,attributed=False)

def test_export_replays_evidence_instead_of_trusting_saved_approved_label(monkeypatch):
    with pytest.raises(SourceProblem):run_export(monkeypatch,change=True)
