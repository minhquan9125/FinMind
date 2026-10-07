import io
import json
import os
import sys
from types import SimpleNamespace

import pandas as pd

from ohlcv.sdk import worker
from ohlcv.storage.store import ProjectPaths


def test_index_worker_dispatch_and_no_equity_catalog(local_tmp,monkeypatch):
    calls=[]
    class Index:
        def ohlcv(self,**kwargs):
            calls.append(kwargs)
            return pd.DataFrame([{'time':'2026-10-06','open':1700.,'high':1710.25,'low':1690.,'close':1705.5,'volume':123456789}])
    class Market:
        def index(self,symbol):assert symbol=='HNXINDEX';return Index()
        def equity(self,symbol):raise AssertionError('Index routed as equity')
    monkeypatch.setitem(sys.modules,'vnstock',SimpleNamespace(Market=Market,Reference=lambda:None))
    monkeypatch.setattr('ohlcv.storage.store.ProjectPaths',lambda:ProjectPaths(local_tmp))
    monkeypatch.setattr('importlib.metadata.version',lambda name:'test')
    for name in ('USERPROFILE','VNSTOCK_DISABLE_AGENT_SETUP','VNSTOCK_AGENT_TARGETS','VNSTOCK_TELEMETRY','MPLCONFIGDIR','TEMP','TMP','VNSTOCK_API_KEY'):
        monkeypatch.setenv(name,os.environ.get(name,''))
    monkeypatch.setattr(sys,'dont_write_bytecode',True)
    monkeypatch.setattr(sys,'argv',['worker','--serve'])
    monkeypatch.setattr(sys,'stdin',io.StringIO('\n'.join(json.dumps({'action':action,'symbol':'HNX'}) for action in ('history','quote'))+'\n'))
    output=io.StringIO();monkeypatch.setattr(sys,'stdout',output)
    assert worker.main()==0
    replies=[json.loads(line) for line in output.getvalue().splitlines()]
    assert len(replies)==2 and all(reply['symbol']=='HNXINDEX' and reply['instrument_type']=='index' for reply in replies)
    assert replies[1]['rows'][0]['close']=='1705.5'
    assert calls[0]['count']==400 and calls[1]['count']==1
    assert calls[1]['start']==calls[1]['end']
