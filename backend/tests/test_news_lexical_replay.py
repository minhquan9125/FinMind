import asyncio,json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from src.retrieval_orchestration.live_research import DenseEvidenceRetriever


@pytest.mark.parametrize('changed',[False,True])
def test_news_lexical_index_replays_frozen_source_and_rejects_binding_changes(monkeypatch,changed):
    cid,iid,doc,chunk=map(str,[uuid4(),uuid4(),uuid4(),uuid4()])
    row=dict(chunk_id=chunk,document_id=doc,index_version_id=iid,content_hash='hash',
        locator_json=json.dumps({'source_table':'news_articles','source_id':'article'}))
    @asynccontextmanager
    async def transaction(**kw):
        assert kw['readonly']is True
        yield
    conn=SimpleNamespace(fetch=AsyncMock(return_value=[row]),transaction=transaction)
    @asynccontextmanager
    async def acquire():yield conn
    reader=SimpleNamespace(read_current=AsyncMock(return_value=SimpleNamespace(
        active=True,index_version_id=iid,document_id=doc,content_hash='changed'if changed else'hash',
        text='Tin | 2026-10-23\nDoanh thu bảo hiểm tăng, sản phẩm mới.',source_sha256='source-hash',
        locator={'source_table':'news_articles','source_id':'article'})))
    monkeypatch.setattr('src.graph_review.sources.PostgresSourceReader',lambda c:reader)
    retriever=DenseEvidenceRetriever(SimpleNamespace(acquire=acquire),None,corpus_version_id=cid)
    async def run():
        first=await retriever._news_lexical_rows('doanh thu bảo hiểm',{'index_version_id':iid},'TCB',None)
        second=await retriever._news_lexical_rows('sản phẩm bảo hiểm',{'index_version_id':iid},'TCB',None)
        assert first[0]['chunk_id']==second[0]['chunk_id']==chunk
        assert first[0]['text'].endswith('sản phẩm mới.')
        assert first[0]['source_sha256']=='source-hash'
        assert first[0]['source_verified']is True
        reader.read_current.assert_awaited_once_with(chunk,cid)
    if changed:
        with pytest.raises(Exception,match='NEWS_LEXICAL_BINDING_CHANGED|News ranking source binding changed'):
            asyncio.run(run())
    else:asyncio.run(run())
