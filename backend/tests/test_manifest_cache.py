import asyncio
import hashlib
import json
import uuid

import pytest

from src.documents.corpus_manifest import sha256
from src.vector_retrieval import backend as cache


def fixture():
    index,document,chunk=[str(uuid.uuid4()) for _ in range(3)]
    text='Tin nguồn đã duyệt: dữ liệu kiểm tra.'
    digest=hashlib.sha256(text.encode()).hexdigest()
    locator={'source_table':'news_articles','source_id':str(uuid.uuid4()),'row_keys':['p1'],
             'symbol':'ICT','published_at':'2026-07-30','url':'https://fireant.vn/bai-viet/test/123'}
    row=dict(chunk_id=chunk,document_id=document,chunk_index=0,content_hash=digest,
             source_sha256='d'*64,company='ICT',symbols=['ICT'],period='2026-07-30',doc_type='NEWS',
             source_url=locator['url'],locator_json=locator)
    payload={'index':{'index_version_id':index,'embedding_model':cache.MODEL},'chunk_count':1,
             'documents':[{'document_id':document,'document_hash':'d'*64,'chunks':[
                 {'chunk_id':chunk,'chunk_index':0,'content_hash':digest,'text':text,'locator':locator}]}]}
    return {'manifest':payload,'manifest_sha256':sha256(payload),'corpus_version_id':str(uuid.uuid4())},row


def fake_reader(monkeypatch,rows):
    async def info(*args):return {'embedding_model':cache.MODEL}
    async def fetch(*args):return rows
    async def fingerprint(*args):return 'a'*32
    monkeypatch.setattr(cache.HybridRetriever,'_index',info)
    monkeypatch.setattr(cache.HybridRetriever,'_fetch',fetch)
    monkeypatch.setattr(cache.HybridRetriever,'_value',fingerprint)


def test_verified_manifest_prepares_search_without_rereading_sources(tmp_path,monkeypatch):
    manifest,row=fixture();fake_reader(monkeypatch,[row]);path=tmp_path/'cache.json'
    result=asyncio.run(cache.cache_verified_manifest(None,manifest,path))
    assert result=={'chunks':1,'status':'CACHE_READY'}
    saved=json.loads(path.read_text(encoding='utf-8'))['payload']
    assert saved['rows'][0]['tokens']==cache.tokenize(manifest['manifest']['documents'][0]['chunks'][0]['text'])
    assert saved['rows'][0]['company']=='ICT'


@pytest.mark.parametrize('changed',['content_hash','source_sha256','document_id','locator_json'])
def test_mismatched_db_rows_cannot_seed_search_cache(tmp_path,monkeypatch,changed):
    manifest,row=fixture()
    row[changed]={'symbol':'BID'} if changed=='locator_json' else 'e'*64
    fake_reader(monkeypatch,[row]);path=tmp_path/'cache.json'
    with pytest.raises(cache.RetrievalError,match='HASH_MISMATCH'):
        asyncio.run(cache.cache_verified_manifest(None,manifest,path))
    assert not path.exists()
