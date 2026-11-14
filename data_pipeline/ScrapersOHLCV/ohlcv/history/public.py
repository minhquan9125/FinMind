"""Bounded anonymous daily history from DNSE's public chart endpoint.

This is a separate observational route, not authenticated OpenAPI recovery.
No inferred calendar, adjusted/raw basis or authoritative finality.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import hashlib
import json
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler
from zoneinfo import ZoneInfo

from ohlcv.providers.dnse import decode_daily
from ohlcv.storage.store import CandleStore, ProjectPaths
from ohlcv.app.snapshot import embed_chart_snapshot

ENDPOINT = 'https://api.dnse.com.vn/chart-api/v2/ohlcs/stock'
MAX_RESPONSE = 5 * 1024 * 1024
VN = ZoneInfo('Asia/Ho_Chi_Minh')
DEFAULT_DB = 'data/runtime/public-candles.sqlite3'
DEFAULT_OUTPUT = 'data/runtime/public-ohlcv.json'


def request_url(symbol: str, exchange: str, start: date, end: date, now: datetime) -> str:
    if not isinstance(symbol,str) or not re.fullmatch(r'[A-Z0-9]{1,10}',symbol):
        raise ValueError('Invalid symbol')
    if exchange not in ('HOSE','HNX','UPCOM'):
        raise ValueError('Invalid exchange')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Aware observation time required')
    if type(start) is not date or type(end) is not date or start > end or (end-start).days > 366:
        raise ValueError('Invalid daily range, maximum366 day difference')
    if end > now.astimezone(VN).date():
        raise ValueError('Future daily range prohibited')
    lower = int(datetime.combine(start,time.min,VN).timestamp())
    upper = min(int(now.timestamp()),int(datetime.combine(end+timedelta(days=1),time.min,VN).timestamp())-1)
    return ENDPOINT + '?' + urlencode({'symbol':symbol,'resolution':'1D','from':lower,'to':upper})


def parse_response(raw: bytes) -> dict:
    if not isinstance(raw,bytes) or len(raw) > MAX_RESPONSE:
        raise ValueError('Public response exceeds5MiB')
    def reject_constant(value):
        raise ValueError('Nonfinite JSON constant')
    try:
        payload=json.loads(raw.decode('utf-8'),parse_float=Decimal,parse_constant=reject_constant)
    except (UnicodeError,ValueError,RecursionError) as error:
        raise ValueError('Invalid public JSON response') from error
    if not isinstance(payload,dict):
        raise ValueError('Public JSON must be an object')
    return payload


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def fetch_response(url: str) -> tuple[bytes,str | None]:
    # Only internally generated requests to this endpoint; no user URL/proxy bypass.
    if not url.startswith(ENDPOINT+'?'):
        raise ValueError('Disallowed public URL')
    request=Request(url,headers={'Accept':'application/json','User-Agent':'FinMind-OHLCV/0.1'})
    opener=build_opener(_NoRedirect(),HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(request,timeout=20) as response:
            raw=response.read(MAX_RESPONSE+1)
            if len(raw)>MAX_RESPONSE:
                raise ValueError('Public response exceeds5MiB')
            return raw,response.headers.get('Date')
    except HTTPError as error:
        status=error.code
        error.close()
        raise RuntimeError(f'Public endpoint HTTP {status}; no retries') from None
    except URLError:
        raise RuntimeError('Public endpoint connection failed; no retries') from None


def _output_paths(paths: ProjectPaths, database: str, output: str):
    database_path=paths.output(database)
    output_path=paths.output(output)
    if output_path in {database_path,*(database_path.with_name(database_path.name+suffix)
                                     for suffix in ('-wal','-shm','-journal'))}:
        raise ValueError('JSON output must not overwrite database or its sidecars')
    return database_path,output_path


def ingest_response(payload: dict, *, symbol: str, exchange: str, start: date, end: date,
                    fetched_at: datetime, paths: ProjectPaths, database: str = DEFAULT_DB,
                    output: str = DEFAULT_OUTPUT, receipt: dict | None = None) -> dict:
    url=request_url(symbol,exchange,start,end,fetched_at)
    # Check paths and decode whole response before creating any database.
    _output_paths(paths,database,output)
    if isinstance(payload,dict) and isinstance(payload.get('t'),list) and len(payload['t'])>367:
        raise ValueError('Too many daily bars for one public request')
    bars=decode_daily(payload,symbol,exchange,fetched_at,Decimal('1'),'unknown','unknown')
    if not bars:
        raise ValueError('Public endpoint returned no bars; previous data retained')
    if len(bars)>367 or any(not start<=bar.trade_date<=end for bar in bars):
        raise ValueError('Public response contains dates outside requested range')
    bars=sorted((replace(bar,source='dnse_public',status='pending_reconciliation',reconciled_at=fetched_at)
                 for bar in bars),key=lambda bar:bar.trade_date)
    provenance={'endpoint':ENDPOINT,'url':url,'fetched_at':fetched_at.isoformat(),
                'requested_start':start.isoformat(),'requested_end':end.isoformat(),
                'authenticated':False,'price_multiplier':'1','price_basis':'unknown',
                'volume_basis':'unknown','calendar_verified':False,
                'note':'Public chart observations; original price units; no authoritative finality'}
    if receipt:
        # Copy only receipt fields, never let caller relabel provenance or authentication.
        provenance.update({key:receipt[key] for key in ('sha256','bytes','server_date') if key in receipt})
    with CandleStore(paths,database) as store:
        stored=[bar for latest in store.latest() for bar in store.history(latest.symbol)]
        if any(bar.source!='dnse_public' or bar.price_basis!='unknown' or bar.volume_basis!='unknown'
               or bar.status=='closed' for bar in stored):
            raise ValueError('Use a separate database for public unknown-basis observations')
        changes=[]
        for bar in bars:
            old=store.get(symbol,bar.trade_date)
            if old:
                if replace(bar,reconciled_at=old.reconciled_at).payload_tuple()==old.payload_tuple():
                    continue
                if old.reconciled_at and fetched_at<=old.reconciled_at:
                    raise ValueError('Older public observation cannot replace newer data')
                bar=replace(bar,revision=old.revision+1)
            changes.append(bar)
        changed=store.upsert_batch(changes)
        all_bars=sorted((bar for latest in store.latest() for bar in store.history(latest.symbol)),
                        key=lambda bar:(bar.symbol,bar.trade_date))
        exported={'version':1,'count':len(all_bars),'bars':[bar.to_dict() for bar in all_bars],
                  'provenance':provenance}
        paths.atomic_json(output,exported)
    chart_snapshot=embed_chart_snapshot(paths,exported)
    return {'symbol':symbol,'received_bars':len(bars),'changed_bars':changed,'total_exported':len(all_bars),
            'first_date':bars[0].trade_date.isoformat(),'last_date':bars[-1].trade_date.isoformat(),
            'database':database,'output':output,'status':'pending_reconciliation',
            'source':'dnse_public','chart_snapshot':chart_snapshot}


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description='Fetch anonymous daily stock history (one request, no retries)')
    parser.add_argument('--symbol',default='FPT')
    parser.add_argument('--exchange',choices=['HOSE','HNX','UPCOM'],default='HOSE')
    parser.add_argument('--start',type=date.fromisoformat)
    parser.add_argument('--end',type=date.fromisoformat)
    parser.add_argument('--db',default=DEFAULT_DB)
    parser.add_argument('--output',default=DEFAULT_OUTPUT)
    args=parser.parse_args(argv)
    try:
        now=datetime.now(VN)
        end=args.end or now.date()
        start=args.start or end-timedelta(days=180)
        url=request_url(args.symbol,args.exchange,start,end,now)
        paths=ProjectPaths()
        # Reject bad output paths before making a network request.
        _output_paths(paths,args.db,args.output)
        raw,server_date=fetch_response(url)
        receipt={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'server_date':server_date}
        report=ingest_response(parse_response(raw),symbol=args.symbol,exchange=args.exchange,start=start,end=end,
                               fetched_at=now,paths=paths,database=args.db,output=args.output,receipt=receipt)
        report['requests']=1
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,RuntimeError,OSError) as error:
        # No source bodies, environment or credentials printed.
        print(f'Public history failed ({type(error).__name__})')
        return 2


if __name__=='__main__':
    raise SystemExit(main())
