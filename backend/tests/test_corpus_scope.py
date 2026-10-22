import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
import json
from pathlib import Path
import sys
import uuid

import pytest
from src.documents.corpus_scope import (CorpusScopeError,load_scope,fact_value_hash,
                                        price_value_hash,read_prices)
from src.documents import repository
from src.financial.reader import read_financial_facts

CID='a6459bfa-971f-4ef1-9c3c-faaabbdb9509'
IID='bb5d238b-3517-460a-88e2-5f66bfca01d3'
DID='3f06e7ea-c540-4701-91ee-cbfba7df33e5'


def registration(**overrides):
    return dict(corpus_version_id=CID,index_version_id=IID,version_label='test-corpus',
        manifest_sha256='a'*64,corpus_status='FROZEN',frozen_at='frozen',index_status='ACTIVE',
        embedding_model='test-model',chunker_version='db-v1',**overrides)


class Conn:
    def __init__(self,reg=None):self.reg=registration() if reg is None else reg;self.calls=[]
    @asynccontextmanager
    async def transaction(self,**kwargs):
        assert kwargs==dict(readonly=True,isolation='repeatable_read');yield
    async def fetch(self,sql,*args):
        self.calls.append((sql,args))
        if 'FROM public.corpus_versions' in sql:return [] if self.reg=={} else [self.reg]
        raise AssertionError('Unexpected query')
    async def fetchval(self,sql,*args):
        if 'count(*)' in sql:return 0
        if 'corpus_documents' in sql:return 1
        raise AssertionError('Unexpected query')


class Pool:
    def __init__(self,conn):self.conn=conn
    @asynccontextmanager
    async def acquire(self):yield self.conn


@pytest.mark.parametrize('field,value,code',[
    ('index_status','BUILDING','CORPUS_NOT_READY'),('corpus_status','DRAFT','CORPUS_NOT_READY'),
    ('frozen_at',None,'CORPUS_NOT_READY'),('embedding_model','other','CORPUS_MODEL_MISMATCH')])
def test_corpus_cannot_fall_back_when_not_ready(field,value,code):
    c=Conn();c.reg[field]=value
    with pytest.raises(CorpusScopeError,match='.') as e:
        asyncio.run(load_scope(c,CID,model='test-model'))
    assert e.value.code==code


def test_unregistered_and_wrong_manifest_are_explicit_errors():
    with pytest.raises(CorpusScopeError) as e:asyncio.run(load_scope(Conn({}),CID))
    assert e.value.code=='CORPUS_NOT_REGISTERED'
    with pytest.raises(CorpusScopeError) as e:asyncio.run(load_scope(Conn(),CID,expected_hash='b'*64))
    assert e.value.code=='CORPUS_MANIFEST_MISMATCH'


def test_v2_manifest_cannot_point_to_unrelated_index():
    c=Conn();c.reg['chunker_version']='db-corpus-v2';c.reg['version_label']='corpus-v2'
    with pytest.raises(CorpusScopeError) as e:asyncio.run(load_scope(c,CID))
    assert e.value.code=='CORPUS_INDEX_MISMATCH'


def test_invalid_corpus_id_is_a_domain_error_not_unhandled_uuid_error():
    with pytest.raises(CorpusScopeError) as e:asyncio.run(load_scope(Conn(),'bad-id'))
    assert e.value.code=='INVALID_CORPUS_ID'


def fact(**overrides):
    result=dict(report_id='report-clean',symbol='FPT',period_code='2024-YEAR',section='BALANCE_SHEET',
        code='TOTAL_ASSETS',canonical_name='Assets',industry_scope='TECH',observation_id='observation',
        metric_id=str(uuid.uuid5(uuid.UUID('b77dbd7f-5d89-479d-90a3-421e5f0981ea'),
            'metric:TECH:BALANCE_SHEET:TOTAL_ASSETS')),value=Decimal('71999995678620'),unit='SOURCE_NATIVE',scale=1,currency=None,
        locator_json={},ingestion_schema='clean-v1',source_uri='data/FPT/tai_chinh_clean.json')
    result.update(overrides);return result


def test_fact_hash_is_numeric_format_independent_and_unit_sensitive():
    assert fact_value_hash(fact(value=Decimal('12.00')))==fact_value_hash(fact(value=Decimal('12')))
    assert fact_value_hash(fact())!=fact_value_hash(fact(unit='VND'))
    assert fact_value_hash(fact())!=fact_value_hash(fact(scale=1000))
    with pytest.raises(ValueError):fact_value_hash(fact(value=Decimal('NaN')))


def test_editing_global_metric_code_cannot_relabel_frozen_fact():
    row=fact();row['value_hash']=fact_value_hash(row);row['code']='OTHER_MEANING'
    class FinancialConn(Conn):
        async def fetch(self,sql,*args):
            if 'FROM public.financial_reports' in sql:return [row]
            return await super().fetch(sql,*args)
    with pytest.raises(CorpusScopeError) as e:
        asyncio.run(read_financial_facts(FinancialConn(),'FPT','2024-YEAR',corpus_version_id=CID))
    assert e.value.code=='CORPUS_METRIC_IDENTITY_CHANGED'


def test_default_corpus_also_applies_to_library_financial_reads(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('src.core.config.get_settings',lambda:SimpleNamespace(
        default_corpus_version_id=CID,default_corpus_manifest_sha256='a'*64))
    class FinancialConn(Conn):
        async def fetch(self,sql,*args):
            if 'FROM public.financial_reports' in sql:
                assert 'JOIN public.corpus_facts cf' in sql
                return []
            return await super().fetch(sql,*args)
    assert asyncio.run(read_financial_facts(FinancialConn(),'FPT','2024-YEAR'))==[]


@pytest.mark.parametrize('changed',[False,True])
def test_financial_reader_filters_members_before_selection_and_checks_hash(changed):
    row=fact();row['value_hash']=fact_value_hash(row)
    if changed:row['value']+=1
    class FinancialConn(Conn):
        async def fetch(self,sql,*args):
            if 'FROM public.financial_reports' in sql:
                assert 'JOIN public.corpus_facts cf' in sql
                assert 'cf.corpus_version_id=$3' in sql
                assert args==('FPT','2024-YEAR',uuid.UUID(CID))
                return [row]  # Other four reports are excluded by membership, not latest/report count.
            return await super().fetch(sql,*args)
    if changed:
        with pytest.raises(CorpusScopeError) as e:
            asyncio.run(read_financial_facts(FinancialConn(),'FPT','2024-YEAR',corpus_version_id=CID))
        assert e.value.code=='CORPUS_FACT_CHANGED'
    else:
        facts=asyncio.run(read_financial_facts(FinancialConn(),'FPT','2024-YEAR',corpus_version_id=CID))
        assert len(facts)==1 and facts[0]['corpus_version_id']==CID


@pytest.mark.parametrize('changed',[False,True])
def test_prices_are_scoped_and_hash_checked_including_indicator_changes(changed,monkeypatch):
    from src.core import config
    isolated=config.Settings(_env_file=None)
    monkeypatch.setattr(config,'get_settings',lambda:isolated)
    row=dict(price_id='price',company_id='company',trade_date='2026-01-01',is_adjusted=False,
        open=Decimal('10'),high=Decimal('11'),low=Decimal('9'),close=Decimal('10.5'),volume=100,price_scale=1000,
        sma20=None,sma50=None,rsi14=None)
    row['value_hash']=price_value_hash(row)
    if changed:row['rsi14']=50
    class PriceConn(Conn):
        async def fetch(self,sql,*args):
            if 'FROM public.corpus_prices' in sql:
                assert 'cp.corpus_version_id=$1' in sql and args[0]==uuid.UUID(CID)
                return [row]
            return await super().fetch(sql,*args)
    async def run():
        c=PriceConn();return await read_prices(c,await load_scope(c,CID),'FPT')
    if changed:
        with pytest.raises(CorpusScopeError) as e:asyncio.run(run())
        assert e.value.code=='CORPUS_PRICE_CHANGED'
    else:assert len(asyncio.run(run()))==1


def test_corpus_vector_search_uses_membership_and_pinned_index(monkeypatch):
    class VectorConn(Conn):
        async def fetch(self,sql,*args):
            if 'FROM public.corpus_documents cd' in sql:
                assert 'cd.corpus_version_id=$1 AND t.index_version_id=$2' in sql
                assert 't.superseded_at IS NULL' in sql and 'd.sha256=cd.document_hash' in sql
                assert args[:2]==(uuid.UUID(CID),uuid.UUID(IID))
                return []
            return await super().fetch(sql,*args)
    async def resolve(*args):return []
    monkeypatch.setattr(repository,'resolve_result_rows',resolve)
    scope,rows=asyncio.run(repository.corpus_vector_search(Pool(VectorConn()),CID,'[0.1]',3,model='test-model'))
    assert scope.corpus_version_id==CID and rows==[]


def test_outside_document_and_changed_document_never_fall_back():
    class BadConn(Conn):
        async def fetchval(self,sql,*args):return 0
    with pytest.raises(CorpusScopeError) as e:
        asyncio.run(repository.corpus_vector_search(Pool(BadConn()),CID,'[0.1]',3,model='test-model',document_id=DID))
    assert e.value.code=='DOCUMENT_OUTSIDE_CORPUS'
    class ChangedConn(Conn):
        async def fetchval(self,sql,*args):return 1
    with pytest.raises(CorpusScopeError) as e:
        asyncio.run(repository.corpus_vector_search(Pool(ChangedConn()),CID,'[0.1]',3,model='test-model'))
    assert e.value.code=='CORPUS_DOCUMENT_CHANGED'


def test_release_membership_keeps_only_uuid_price_rows():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    from prepare_corpus_v2_release import membership_ids
    snapshot={'manifest':{'documents':[
        {'source_table':'financial_reports','source_id':'r1','chunks':[{'locator':{'row_keys':[CID]}}]},
        {'source_table':'price_bars','source_id':'FPT','chunks':[{'locator':{'row_keys':['FPT:2026-04:summary',DID]}}]}]}}
    facts,prices,owners=membership_ids(snapshot)
    assert facts=={CID} and prices=={DID} and owners=={CID:'r1'}


def test_metric_filter_uses_registered_fact_ids_and_chunk_row_membership(monkeypatch):
    class FilterConn(Conn):
        async def fetch(self,sql,*args):
            if 'FROM public.corpus_facts' in sql:
                assert args==(uuid.UUID(CID),['FPT'],['2026-Q2'],['NET_REVENUE'])
                return [{'observation_id':DID}]
            if 'FROM public.corpus_documents cd' in sql:
                assert "(t.locator_json->'row_keys') ?| $8::text[]" in sql
                assert args[-1]==[DID]
                return []
            return await super().fetch(sql,*args)
    async def resolve(*args):return []
    monkeypatch.setattr(repository,'resolve_result_rows',resolve)
    asyncio.run(repository.corpus_vector_search(Pool(FilterConn()),CID,'[0.1]',5,
        model='test-model',symbols=['FPT'],period_codes=['2026-Q2'],metric_codes=['NET_REVENUE']))


def test_document_details_use_same_corpus_index_and_default_remains_unset():
    from types import SimpleNamespace
    from src.core.config import Settings
    assert Settings(_env_file=None).default_corpus_version_id is None
    settings=SimpleNamespace(default_corpus_version_id=CID,default_corpus_manifest_sha256='a'*64,
                             embedding_model_ref='test-model')
    index=asyncio.run(repository.index_for_read(Pool(Conn()),dict(id=DID,file_type='DB'),settings))
    assert index==IID
