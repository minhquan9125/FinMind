"""Validated KBS day-to-date quotes; never synthesize bars from yesterday's prices."""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
import threading

from ohlcv.core.models import Bar
from ohlcv.history.vnstock import normalize_symbol, indicators, normalize_history, VN
from ohlcv.realtime.session import RateBudget, SessionGate
from ohlcv.core.instruments import INDEXES


def normalize_quote(result, symbol, exchange):
    rows=result.get('rows')
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):
        raise ValueError('Nguồn không trả đúng một mã.')
    row=rows[0]
    if symbol in INDEXES:
        if result.get('symbol')!=symbol or result.get('instrument_type')!='index' or exchange!=INDEXES[symbol]['exchange']:
            raise ValueError('Chỉ số hoặc sàn nguồn không khớp.')
        try:
            stamp=datetime.fromisoformat(result['fetched_at'])
            bar=normalize_history(rows,symbol,exchange,stamp)['bars'][0]
        except (KeyError,TypeError) as issue:
            raise ValueError('Nến chỉ số thiếu trường dữ liệu.') from issue
        return {**bar,'status':'open','reconciled_at':None}
    if row.get('symbol')!=symbol or row.get('exchange')!=exchange:
        raise ValueError('Mã hoặc sàn bảng điện không khớp.')
    try:
        stamp=datetime.fromisoformat(result['fetched_at'])
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError('Thiếu múi giờ nguồn.')
        day=datetime.strptime(row['TD'],'%d/%m/%Y').date()
        prices={}
        for field in ('open','high','low','close'):
            value=row[field+'_price']
            if isinstance(value,(float,bool)) or value is None:
                raise ValueError('Giá không hợp lệ.')
            # SDK KBS history divides equity prices by 1000; price_board does not.
            prices[field]=Decimal(value)/1000
        volume=row['volume_accumulated']
        if type(volume) is not int:
            raise ValueError('Volume không hợp lệ.')
        bar=Bar(symbol=symbol,exchange=exchange,trade_date=day,**prices,volume=volume,
                source='vnstock_kbs',price_basis='unknown',volume_basis='unknown',
                status='open',quality='complete',received_at=stamp)
        return bar.to_dict()
    except (KeyError,TypeError,InvalidOperation) as issue:
        raise ValueError('Bảng điện thiếu trường hoặc sai kiểu dữ liệu.') from issue


class LiveService:
    def __init__(self, paths, *, fetch, gate=None, budget=None, lock=None):
        self.paths=paths
        self.fetch=fetch
        self.gate=gate or SessionGate(paths)
        self.budget=budget or RateBudget()
        self.lock=lock or threading.Lock()

    def _saved(self,symbol):
        path=self.paths.output(f'data/stocks/{symbol}/data.json')
        if not path.is_file():
            raise ValueError('Hãy nhập mã rồi lấy dữ liệu một lần trước khi tự cập nhật.')
        data=json.loads(path.read_text(encoding='utf-8'))
        bars=data.get('bars',[])
        if not bars or any(bar.get('symbol')!=symbol or bar.get('source')!='vnstock_kbs'
                           or bar.get('price_basis')!='unknown' or bar.get('volume_basis')!='unknown' for bar in bars):
            raise ValueError('Bản lưu không phải lịch sử vnstock của mã đang mở.')
        exchange=bars[-1]['exchange']
        if any(bar['exchange']!=exchange for bar in bars):
            raise ValueError('Sàn trong bản lưu không nhất quán.')
        return data,exchange

    def status(self,value):
        symbol=normalize_symbol(value)
        with self.lock:
            _,exchange=self._saved(symbol)
            return {'session':self.gate.status(exchange),'symbol':symbol}

    def quote(self,value):
        symbol=normalize_symbol(value)
        with self.lock:
            data,exchange=self._saved(symbol)
            session=self.gate.status(exchange)
            response={'session':session,'symbol':symbol,'quote':None}
            if not session['active']:
                return response
            current_day=datetime.fromisoformat(session['server_time']).date()
            calendar=self.gate.calendar
            past=calendar.trading_dates(calendar.coverage_start,current_day-timedelta(days=1)) if current_day>calendar.coverage_start else []
            if past and data['bars'][-1]['trade_date'] < str(past[-1]):
                wait=self.budget.reserve(3)
                if wait:return {**response,'wait_seconds':wait,'reason':'Đang chờ tải bù lịch sử.'}
                history=self.fetch('history',symbol)
                response['session']=self.gate.status(exchange)
                if not response['session']['active']:return response
                if history.get('session_closed'):
                    return {**response,'session':{**response['session'],'active':False,'phase':'halted'}}
                stamp=datetime.fromisoformat(history['fetched_at'])
                payload=normalize_history(history['rows'],symbol,exchange,stamp)
                if payload['bars'][-1]['trade_date'] < str(past[-1]):
                    # Do not retry an unavailable history batch every 5 seconds.
                    return {**response,'wait_seconds':60,'reason':'Nguồn chưa có đủ lịch sử gần nhất.'}
                payload['provenance'].update({k:v for k,v in data.get('provenance',{}).items()
                                               if k in ('name','storage')})
                payload['provenance']['vnstock_version']=history.get('vnstock_version','unknown')
                payload['provenance']['dataframe_sha256']=history.get('dataframe_sha256')
                prior={bar['trade_date']:bar for bar in data['bars']}
                for item in payload['bars']:
                    old=prior.get(item['trade_date'])
                    if old:item['revision']=old['revision']+int(any(item[k]!=old[k] for k in ('open','high','low','close','volume')))
                self.paths.atomic_json(f'data/stocks/{symbol}/data.json',payload)
                return {**response,'wait_seconds':5,'reason':'Đã tải bù lịch sử; đang chờ bảng điện.'}
            wait=self.budget.reserve(3 if symbol in INDEXES else 1)
            if wait:
                return {**response,'wait_seconds':wait,'reason':'Đang chờ hạn mức gọi chung.'}
            result=self.fetch('quote',symbol)
            session=self.gate.status(exchange)
            response['session']=session
            if not session['active']:
                return response
            if result.get('session_closed'):
                return {**response,'session':{**session,'active':False,'phase':'halted'}}
            bar=normalize_quote(result,symbol,exchange)
            today=datetime.fromisoformat(session['server_time']).date().isoformat()
            if bar['trade_date']!=today or bar['volume']==0:
                return {**response,'reason':'Nguồn chưa có giao dịch của phiên hiện tại.'}
            old=next((item for item in data['bars'] if item['trade_date']==today),None)
            if old and (bar['volume']<old['volume'] or Decimal(bar['high'])<Decimal(old['high'])
                        or Decimal(bar['low'])>Decimal(old['low'])):
                return {**response,'reason':'Nguồn trả dữ liệu lùi; giữ bản lưu trước.'}
            bar['revision']=old['revision']+int(any(bar[k]!=old[k] for k in ('open','high','low','close','volume','status'))) if old else 1
            bars=[item for item in data['bars'] if item['trade_date']!=today]+[bar]
            bars.sort(key=lambda item:item['trade_date'])
            provenance={**data.get('provenance',{}),'fetched_at':result['fetched_at'],
                'history_fetched_at':data.get('provenance',{}).get('history_fetched_at',data.get('provenance',{}).get('fetched_at')),
                'quote_dataframe_sha256':result.get('dataframe_sha256'),
                'live_method':'vnstock Market.equity.quote(get_all=True)', 'quote_price_divisor':1000,
                'quote_trade_date_field':'TD', 'latency':'Tự lấy bảng điện trong phiên; chưa đo độ trễ nguồn'}
            if symbol in INDEXES:
                provenance.update(live_method='vnstock Market.index.ohlcv(interval=1D,count=1)',
                                  quote_price_divisor=1,quote_trade_date_field='time',
                                  latency='Tự lấy nến chỉ số trong phiên; chưa đo độ trễ nguồn',
                                  instrument_type='index',price_units='points')
            payload={**data,'bars':bars,'count':len(bars),'indicators':indicators(bars),'provenance':provenance}
            # Extra SDK decimal fields (e.g. percent_change) are lossless text in the receipt.
            receipt=json.loads(json.dumps(result,default=str,allow_nan=False))
            receipt['decimal_tokens_stored_as_text']=True
            self.paths.atomic_json(f'data/stocks/{symbol}/live.json',receipt)
            self.paths.atomic_json(f'data/stocks/{symbol}/data.json',payload)
            return {**response,'quote':bar,'data':payload}
