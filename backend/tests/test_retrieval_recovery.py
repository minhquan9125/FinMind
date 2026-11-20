import asyncio
import copy
from unittest.mock import AsyncMock
import pytest
from src.retrieval_orchestration.retrieval_recovery import recover_content
from src.documents.chunk_reconstruction import ReconstructionError


def pack(body='', corpus='one'):
    return dict(corpus_version_id=corpus,data_version={'id':'index'},items=(
        [dict(evidence_id=body,passage='MBB header\n'+body)] if body else []),retrieval_backend='test')


SCOPE=dict(source_type='CONTENT',companies=['MBB'],periods=['LATEST_AVAILABLE_PERIOD'])


def test_good_primary_skips_fallback():
    reader=AsyncMock(return_value=pack('Chi nhánh Phú Quốc thay đổi địa điểm'))
    out=asyncio.run(recover_content(reader,'Chi nhánh Phú Quốc thay đổi địa điểm thế nào?',SCOPE))
    assert reader.await_count==1
    assert len(out['retrieval_trace'])==1


def test_unrelated_primary_gets_one_supplement_before_answering():
    reader=AsyncMock(side_effect=[pack('Giá cổ phiếu giảm'),pack('Chi nhánh Phú Quốc thay đổi địa điểm')])
    original=copy.deepcopy(SCOPE)
    out=asyncio.run(recover_content(reader,'Chi nhánh Phú Quốc thay đổi địa điểm thế nào?',SCOPE))
    assert reader.await_count==2
    assert out['items'][0]['passage'].endswith('Chi nhánh Phú Quốc thay đổi địa điểm')
    assert SCOPE==original


@pytest.mark.parametrize('source',['NEWS','BCTN','BCTC'])
def test_explicit_source_and_dates_never_change(source):
    scope={**SCOPE,'source_type':source,'periods':['2025'],'reporting_entity':'CONSOLIDATED'}
    reader=AsyncMock(return_value=pack())
    asyncio.run(recover_content(reader,'Nội dung báo cáo?',scope))
    change=reader.call_args.args[1]
    assert change==scope
    assert reader.await_count==1


def test_changed_corpus_fails_closed():
    reader=AsyncMock(side_effect=[pack(),pack('Bằng chứng',corpus='other')])
    with pytest.raises(ReconstructionError):
        asyncio.run(recover_content(reader,'Chi nhánh thay đổi địa điểm?',SCOPE))


def test_slow_fallback_returns_primary_without_waiting_indefinitely():
    async def retrieve(q,scope):
        if scope['source_type']=='BCTN':await asyncio.sleep(1)
        return pack()
    out=asyncio.run(recover_content(retrieve,'Chi nhánh thay đổi địa điểm?',SCOPE,fallback_timeout=.01))
    assert out['retrieval_trace'][-1]['reason']=='FALLBACK_TIMEOUT'


def test_dense_adapter_content_path_uses_the_recovery_before_generation():
    from src.retrieval_orchestration.live_research import DenseEvidenceRetriever
    class Adapter(DenseEvidenceRetriever):
        def __init__(self):
            self.calls=[]
        async def retrieve(self, question, scope):
            if scope['source_type']=='CONTENT':
                return await super().retrieve(question,scope)
            self.calls.append(copy.deepcopy(scope))
            return pack('Chi nhánh Phú Quốc thay đổi địa điểm' if scope['source_type']=='BCTN' else 'Giá cổ phiếu')
    adapter=Adapter()
    out=asyncio.run(adapter.retrieve('Chi nhánh Phú Quốc thay đổi địa điểm?',SCOPE))
    assert [s['source_type'] for s in adapter.calls]==['NEWS','BCTN']
    assert all(s['companies']==['MBB'] and s['periods']==SCOPE['periods'] for s in adapter.calls)
    assert len(out['retrieval_trace'])==2


def test_fallback_does_not_hide_a_source_integrity_failure():
    reader=AsyncMock(side_effect=[pack(),ReconstructionError('HASH_MISMATCH','changed')])
    with pytest.raises(ReconstructionError,match='changed'):
        asyncio.run(recover_content(reader,'Chi nhánh thay đổi địa điểm?',SCOPE))
