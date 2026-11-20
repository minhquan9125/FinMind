"""Guest vnstock/KBS daily snapshots, stored separately for each equity ticker."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
import json
import re
import subprocess
import threading
import time
from zoneinfo import ZoneInfo

from ohlcv.core.models import Bar
from ohlcv.storage.store import ProjectPaths
from ohlcv.core.instruments import INDEXES, INDEX_ALIASES

VN = ZoneInfo('Asia/Ho_Chi_Minh')
RESERVED = {'CON','PRN','AUX','NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}


def normalize_symbol(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError('Mã chứng khoán phải là chữ hoặc số.')
    symbol = value.strip().upper()
    symbol = INDEX_ALIASES.get(symbol, symbol)
    if not re.fullmatch(r'[A-Z0-9]{1,10}', symbol) or symbol in RESERVED:
        raise ValueError('Mã chứng khoán không hợp lệ; ví dụ FPT, VCB, HPG.')
    return symbol


def indicators(bars: list[dict]) -> list[dict]:
    """Close-based SMA and Wilder RSI; unavailable warm-up values stay null."""
    output = []
    closes = [Decimal(bar['close']) for bar in bars]
    gain = loss = None
    with localcontext() as ctx:
        ctx.prec = 34
        for i, close in enumerate(closes):
            row = {'trade_date':bars[i]['trade_date'], 'sma20':None, 'sma50':None, 'rsi14':None}
            for window in (20,50):
                if i+1 >= window:
                    row[f'sma{window}'] = str(sum(closes[i+1-window:i+1])/window)
            if i == 14:
                changes = [closes[j]-closes[j-1] for j in range(1,15)]
                gain = sum(max(change,Decimal(0)) for change in changes)/14
                loss = sum(max(-change,Decimal(0)) for change in changes)/14
            elif i > 14:
                change = close-closes[i-1]
                gain = (gain*13+max(change,Decimal(0)))/14
                loss = (loss*13+max(-change,Decimal(0)))/14
            if gain is not None:
                rsi = Decimal(50) if gain == loss == 0 else Decimal(100) if loss == 0 else 100-100/(1+gain/loss)
                row['rsi14'] = str(rsi)
            output.append(row)
    return output


def normalize_history(rows: list[dict], symbol: str, exchange: str, fetched_at: datetime) -> dict:
    symbol = normalize_symbol(symbol)
    if not isinstance(fetched_at,datetime) or fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise ValueError('Thiếu thời điểm lấy dữ liệu có múi giờ.')
    if not isinstance(rows,list) or not 1 <= len(rows) <= 400:
        raise ValueError('Nguồn không trả dữ liệu hợp lệ; giữ bản lưu trước đó.')
    bars = []
    seen = set()
    today = fetched_at.astimezone(VN).date()
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError('Dòng OHLCV không hợp lệ.')
        try:
            # vnstock labels daily candles with a local, usually naive 07:00 timestamp.
            # Use its daily date label, never present that label as a source freshness timestamp.
            trade_date = datetime.fromisoformat(row['time']).date()
            if trade_date in seen or not today-timedelta(days=366) <= trade_date <= today:
                raise ValueError('Ngày bị trùng hoặc ngoài khoảng thu thập.')
            seen.add(trade_date)
            prices = {}
            for field in ('open','high','low','close'):
                value = row[field]
                if type(value) is bool or isinstance(value,float) or value is None:
                    raise ValueError('Giá thiếu hoặc không hợp lệ.')
                prices[field] = Decimal(value)
            volume = row['volume']
            if type(volume) is not int:
                raise ValueError('Volume phải là số nguyên.')
            bar = Bar(symbol=symbol, exchange=exchange, trade_date=trade_date,
                      **prices, volume=volume, source='vnstock_kbs', price_basis='unknown',
                      volume_basis='unknown', status='pending_reconciliation', quality='complete',
                      received_at=fetched_at, reconciled_at=fetched_at)
        except (KeyError,TypeError,InvalidOperation) as issue:
            raise ValueError('Dòng OHLCV thiếu trường hoặc sai kiểu.') from issue
        bars.append(bar.to_dict())
    bars.sort(key=lambda bar:bar['trade_date'])
    payload = {'version':1, 'count':len(bars), 'bars':bars,
               'provenance':{'library':'vnstock', 'provider':'KBS', 'authentication':'guest',
                             'fetched_at':fetched_at.isoformat(), 'interval':'1D',
                             'price_units':'Giữ nguyên đơn vị DataFrame vnstock/KBS',
                             'precision':'Giá dùng chuỗi thập phân ngắn nhất của số SDK; không phải JSON gốc của nguồn',
                             'latency':'Chưa đo độ trễ nguồn; bản lưu, không phải feed realtime'},
               'indicators':indicators(bars)}
    if symbol in INDEXES:
        payload['provenance'].update(instrument_type='index', price_units='points')
    return payload


def sdk_fetch(paths: ProjectPaths, action: str, symbol: str | None = None) -> dict:
    executable = paths.output('.agent-state/vnstock-venv/Scripts/python.exe')
    if not executable.is_file():
        raise RuntimeError('Chưa có môi trường vnstock. Xem hướng dẫn trong README.md.')
    command = [str(executable), '-B', '-m', 'ohlcv.sdk.worker', action]
    if symbol is not None:
        command.append(normalize_symbol(symbol))
    try:
        result = subprocess.run(command, cwd=paths.root, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=90)
    except subprocess.TimeoutExpired:
        raise RuntimeError('Nguồn vnstock phản hồi quá lâu; giữ dữ liệu cũ, thử lại sau.') from None
    # SDK messages go to stderr. Never expose arbitrary SDK output, URLs or device details to UI.
    if result.returncode != 0:
        raise RuntimeError('Không lấy được dữ liệu vnstock/KBS. Nguồn có thể lỗi hoặc giới hạn lượt gọi; thử lại sau.')
    if len(result.stdout) > 5*1024*1024:
        raise ValueError('Phản hồi vnstock quá lớn.')
    try:
        payload = json.loads(result.stdout, parse_float=Decimal)
        if not isinstance(payload,dict):
            raise ValueError('Invalid SDK result')
        return payload
    except (ValueError,RecursionError):
        raise RuntimeError('Không đọc được dữ liệu vnstock; giữ bản lưu trước đó.') from None


class StockService:
    def __init__(self, paths: ProjectPaths, *, fetch=None, clock=time.monotonic):
        self.paths = paths
        self.fetch = fetch or (lambda action,symbol=None:sdk_fetch(paths,action,symbol))
        self.clock = clock
        self.lock = threading.Lock()
        self.last_fetch = float('-inf')
        self.last_catalog_fetch = float('-inf')
        self.cache = {}
        self.catalog = None

    def _catalog(self):
        if self.catalog is not None:
            return self.catalog
        target = self.paths.output('.agent-state/vnstock-catalog.json')
        result = None
        if target.is_file():
            try:
                candidate = json.loads(target.read_text(encoding='utf-8'))
                stamp = datetime.fromisoformat(candidate['fetched_at'])
                age = (datetime.now(VN)-stamp).total_seconds()
                if 0 <= age <= 86400:
                    result = candidate
            except (ValueError,KeyError,TypeError):
                pass
        if result is None:
            if self.clock()-self.last_catalog_fetch < 10:
                raise RuntimeError('Chờ 10 giây trước khi lấy lại danh sách mã.')
            try:
                result = self.fetch('catalog')
            finally:
                self.last_catalog_fetch = self.clock()
        catalog = {}
        for row in result.get('rows',[]):
            if row.get('type') != 'stock' or row.get('exchange') not in ('HOSE','HNX','UPCOM'):
                continue
            try:
                symbol = normalize_symbol(row.get('symbol'))
            except ValueError:
                continue
            catalog[symbol] = {'exchange':row['exchange'], 'name':row.get('organ_name',symbol)}
        if not catalog:
            raise ValueError('Không lấy được danh sách mã và sàn từ vnstock.')
        self.paths.atomic_json('.agent-state/vnstock-catalog.json', result)
        self.catalog = catalog
        return catalog

    def load(self, value: str, *, refresh: bool = False) -> dict:
        symbol = normalize_symbol(value)
        with self.lock:
            now = self.clock()
            instrument = INDEXES.get(symbol)
            if instrument is None:
                instrument = self._catalog().get(symbol)
            if instrument is None:
                raise ValueError('Không tìm thấy mã cổ phiếu này trong danh sách vnstock/KBS.')
            folder = f'data/stocks/{symbol}'
            path = self.paths.output(folder+'/data.json')
            previous = None
            if path.is_file():
                previous = json.loads(path.read_text(encoding='utf-8'), parse_float=Decimal)
                # Reload saved data after restart, without changing its real fetched_at.
                stamp = datetime.fromisoformat(previous['provenance']['fetched_at'])
                age = (datetime.now(VN)-stamp).total_seconds()
                if (not refresh and age >= 0 and age < 60) or now-self.cache.get(symbol,float('-inf')) < 60:
                    return {**previous, 'cached':True}
            if now-self.last_fetch < 10:
                raise RuntimeError('Chờ 10 giây giữa hai lần lấy dữ liệu để giảm tải nguồn.')
            self.last_fetch = now
            try:
                result = self.fetch('history',symbol)
            finally:
                self.last_fetch = self.clock()
            stamp = datetime.fromisoformat(result['fetched_at'])
            payload = normalize_history(result['rows'],symbol,instrument['exchange'],stamp)
            payload['provenance']['name'] = instrument['name']
            payload['provenance']['storage'] = folder+'/data.json'
            payload['provenance']['vnstock_version'] = result.get('vnstock_version','unknown')
            payload['provenance']['dataframe_sha256'] = result.get('dataframe_sha256')
            if previous is not None:
                old = {bar['trade_date']:bar for bar in previous['bars']}
                for bar in payload['bars']:
                    prior = old.get(bar['trade_date'])
                    if prior:
                        equal = all(bar[field]==prior[field] for field in ('open','high','low','close','volume','source','exchange'))
                        bar['revision'] = prior['revision']+(not equal)
            # One atomic file per ticker keeps bars, indicators and provenance consistent.
            self.paths.atomic_json(folder+'/data.json',payload)
            self.cache[symbol] = now
            return {**payload, 'cached':False}
