import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from src.documents import shared_source
from src.documents.corpus_scope import price_value_hash,CorpusScopeError


@pytest.mark.parametrize('changed_hash',[False,True])
def test_historical_prices_use_original_payload_not_live_values(monkeypatch,changed_hash):
    scope=SimpleNamespace(corpus_version_id='a6459bfa-971f-4ef1-9c3c-faaabbdb9509',index_version_id='bb5d238b-3517-460a-88e2-5f66bfca01d3')
    identity=dict(price_id='original-price',company_id='company',trade_date=date(2026,4,13),is_adjusted=False)
    expected=dict(identity,open=Decimal('10'),high=Decimal('12'),low=Decimal('9'),close=Decimal('11'),
        volume=Decimal('100'),price_scale=1000,sma20=None,sma50=None,rsi14=None)
    recipe=dict(dates=['2026-04-13'],indicators={},binding={})
    async def release(*args):return dict(sources=[dict(source_table='price_bars',source_id='FPT',mode='existing-bars-payload',recipe=recipe)])
    async def payload(*args):return [dict(trade_date='2026-04-13',open='10',high='12',low='9',close='11',volume=100)]
    monkeypatch.setattr(shared_source,'read_release_root',release)
    monkeypatch.setattr('src.documents.reused_source.read_pinned_payload',payload)
    class Conn:
        async def fetch(self,sql,*args):
            assert 'p.close' not in sql and 'p.open' not in sql
            return [dict(identity,value_hash='0'*64 if changed_hash else price_value_hash(expected))]
    if changed_hash:
        with pytest.raises(CorpusScopeError):asyncio.run(shared_source.shared_price_rows(Conn(),scope,'FPT'))
    else:
        result=asyncio.run(shared_source.shared_price_rows(Conn(),scope,'FPT'))
        assert result[0]['close']==Decimal('11')
        assert asyncio.run(shared_source.shared_price_rows(Conn(),scope,'FPT',date(2026,4,14)))==[]


def test_missing_historical_price_member_is_blocked(monkeypatch):
    scope=SimpleNamespace(corpus_version_id='a6459bfa-971f-4ef1-9c3c-faaabbdb9509',index_version_id='bb5d238b-3517-460a-88e2-5f66bfca01d3')
    async def release(*args):return dict(sources=[dict(source_table='price_bars',source_id='FPT',mode='existing-bars-payload',recipe=dict(dates=['2026-04-13'],indicators={},binding={}))])
    async def payload(*args):return []
    monkeypatch.setattr(shared_source,'read_release_root',release)
    monkeypatch.setattr('src.documents.reused_source.read_pinned_payload',payload)
    class Conn:
        async def fetch(self,*args):return []
    with pytest.raises(CorpusScopeError,match='members differ'):
        asyncio.run(shared_source.shared_price_rows(Conn(),scope,'FPT'))
