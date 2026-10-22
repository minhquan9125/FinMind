from fastapi.testclient import TestClient
import pytest

from src.main import app
from src.core.config import Settings,get_settings
from src.documents.embeddings import get_embedding_service
from src.documents import repository
from src.documents.corpus_scope import CorpusScope,CorpusScopeError

CID='a6459bfa-971f-4ef1-9c3c-faaabbdb9509'
IID='bb5d238b-3517-460a-88e2-5f66bfca01d3'
DID='3f06e7ea-c540-4701-91ee-cbfba7df33e5'


@pytest.fixture
def setup(monkeypatch):
    settings=Settings(_env_file=None)
    class Embedder:
        def embed_query(self,text):return '[0.1]'
    monkeypatch.setitem(app.dependency_overrides,get_settings,lambda:settings)
    monkeypatch.setitem(app.dependency_overrides,get_embedding_service,lambda:Embedder())
    monkeypatch.setattr('src.api.routers.search.get_pool',lambda:object())
    async def get_document(pool,document):return dict(id=document,file_type='DB')
    monkeypatch.setattr(repository,'get_document',get_document)
    return settings,TestClient(app)


def test_explicit_corpus_search_returns_citation_ids_and_version(setup,monkeypatch):
    settings,client=setup
    async def search(pool,corpus,vector,k,**kwargs):
        assert corpus==CID and kwargs['document_id'] is None
        return CorpusScope(CID,IID,'a'*64,'test'),[
            dict(chunk_id='chunk',document_id=DID,chunk_index=0,page=None,text='source text',score=.9)]
    monkeypatch.setattr(repository,'corpus_vector_search',search)
    response=client.post('/api/search',json={'corpus_version_id':CID,'query':'FPT'})
    assert response.status_code==200
    body=response.json()
    assert body['corpus_version_id']==CID and body['index_version_id']==IID
    assert body['results'][0]['document_id']==DID and body['results'][0]['chunk_id']=='chunk'


@pytest.mark.parametrize('with_document',[False,True])
def test_configured_default_routes_db_and_global_search(setup,monkeypatch,with_document):
    settings,client=setup;settings.default_corpus_version_id=CID;settings.default_corpus_manifest_sha256='a'*64
    async def search(pool,corpus,vector,k,**kwargs):
        assert corpus==CID and kwargs['expected_hash']=='a'*64
        assert kwargs['document_id']==(DID if with_document else None)
        return CorpusScope(CID,IID,'a'*64,'test'),[]
    async def forbidden(*args,**kwargs):raise AssertionError('Must not search legacy index')
    monkeypatch.setattr(repository,'corpus_vector_search',search)
    monkeypatch.setattr(repository,'vector_search',forbidden)
    payload={'query':'FPT'}
    if with_document:payload['document_id']=DID
    response=client.post('/api/search',json=payload)
    assert response.status_code==200 and response.json()['corpus_version_id']==CID


def test_default_corpus_does_not_capture_private_upload(setup,monkeypatch):
    settings,client=setup;settings.default_corpus_version_id=CID
    async def document(*args):return dict(id=DID,file_type='PDF')
    async def legacy(*args):return []
    async def forbidden(*args,**kwargs):raise AssertionError('Upload must retain its index')
    monkeypatch.setattr(repository,'get_document',document)
    monkeypatch.setattr(repository,'vector_search',legacy)
    monkeypatch.setattr(repository,'corpus_vector_search',forbidden)
    response=client.post('/api/search',json={'document_id':DID,'query':'file text'})
    assert response.status_code==200 and response.json()['corpus_version_id'] is None


@pytest.mark.parametrize('reason',['CORPUS_NOT_REGISTERED','CORPUS_NOT_READY','DOCUMENT_OUTSIDE_CORPUS'])
def test_corpus_errors_never_silently_search_legacy(setup,monkeypatch,reason):
    settings,client=setup
    async def fail(*args,**kwargs):raise CorpusScopeError(reason,'Blocked')
    async def forbidden(*args,**kwargs):raise AssertionError('No fallback')
    monkeypatch.setattr(repository,'corpus_vector_search',fail)
    monkeypatch.setattr(repository,'vector_search',forbidden)
    response=client.post('/api/search',json={'corpus_version_id':CID,'query':'FPT'})
    assert response.status_code==409 and response.json()['reason_code']==reason


def test_no_default_requires_explicit_scope_and_bounds_top_k(setup):
    settings,client=setup
    assert client.post('/api/search',json={'query':'FPT'}).status_code==400
    assert client.post('/api/search',json={'document_id':DID,'query':'FPT','top_k':0}).status_code==422
    assert client.post('/api/search',json={'corpus_version_id':'bad','query':'FPT'}).status_code==422
