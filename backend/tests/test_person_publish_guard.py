import asyncio,importlib.util,json,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
import pytest

scripts=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(scripts))
spec=importlib.util.spec_from_file_location('publish_people',scripts/'publish_reviewed_people.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_empty_approval_set_never_connects_to_neo4j(monkeypatch,tmp_path):
    gid=str(uuid.uuid4())
    (tmp_path/'receipt.json').write_text(json.dumps(dict(graph_version_id=gid)))
    (tmp_path/'registry-used.json').write_text('[]')
    class Connection:
        def transaction(self,**kwargs):
            assert kwargs['readonly'] is True;return self
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def execute(self,sql):assert sql=='SET LOCAL ROLE finmind_graph_reader'
        async def fetch(self,*args):return [dict(status='PENDING',count=126),dict(status='REJECTED',count=2)]
        async def close(self):pass
    async def connect(*args,**kwargs):return Connection()
    def forbidden(*args,**kwargs):raise AssertionError('No approval must mean no Neo4j connection')
    monkeypatch.setattr(module.asyncpg,'connect',connect)
    monkeypatch.setattr(module,'dsn',lambda:'not-used')
    monkeypatch.setattr(module.GraphDatabase,'driver',forbidden)
    asyncio.run(module.main(SimpleNamespace(intake=tmp_path,apply=True)))
    receipt=json.loads((tmp_path/'publish-receipt.json').read_text())
    assert receipt['status']=='BLOCKED' and receipt['neo4j_writes']==0
    assert receipt['eligible_after_live_revalidation']==0

def test_web_without_pdf_page_is_not_fabricated_for_old_contract():
    raw=dict(subject=dict(entity_id='p',entity_type='Person',canonical_name='A',aliases=[],identity_key='p',resolution_status='resolved'),
        object=dict(entity_id='c',entity_type='Company',canonical_name='C',aliases=[],identity_key='c',resolution_status='resolved'),
        evidence=[dict(chunk_id='chunk',corpus_id='corpus')])
    class Connection:
        async def fetchrow(self,*args):return dict(reviewed_by=uuid.uuid4(),reviewed_at=datetime.now(timezone.utc))
    class Reader:
        async def read_current(self,*args):return SimpleNamespace(locator={'kind':'web_snapshot','page':None})
    async def run():
        with pytest.raises(ValueError,match='NO_FAKE_PDF_PAGE'):
            await module.make_envelope(Connection(),[dict(candidate=raw,review_id=str(uuid.uuid4()))],Reader())
    asyncio.run(run())
