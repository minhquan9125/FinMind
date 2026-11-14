"""Read crawler snapshots. Replace this reader when data moves to Supabase."""

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
import re
import hashlib
from datetime import date


class FileMarketDataRepository:
    def __init__(self, root: Path | None = None):
        # FINMIND_DATA_ROOT points to the repository root (or an equivalent mount).
        self.root = Path(root or os.getenv("FINMIND_DATA_ROOT") or Path(__file__).resolve().parents[3])

    def ohlcv_version(self, symbol: str) -> str | None:
        """A cheap validator for the atomically replaced crawler snapshot."""
        path = self.root / "data_pipeline" / "ScrapersOHLCV" / "data" / "stocks" / symbol / "data.json"
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        return f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'

    def runtime_path(self, symbol, kind):
        if not re.fullmatch(r"[A-Z]{3}", symbol) or kind not in ("history", "news"):
            raise ValueError("Invalid runtime snapshot")
        # Prefix avoids reserved Windows device names such as CON/PRN.
        path = self.root / ".agent-state/market-data/stocks" / ("symbol-" + symbol) / (kind + ".json")
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Runtime path escaped project")
        return path

    def runtime_read(self, symbol, kind):
        path = self.runtime_path(symbol, kind)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) and data.get("symbol") == symbol else None
        except (OSError, ValueError):
            return None

    def runtime_write(self, symbol, kind, data):
        path = self.runtime_path(symbol, kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def _activity_path(self, symbol, day):
        if not re.fullmatch(r'[A-Z]{3}',symbol) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',day):
            raise ValueError('Invalid activity archive identity')
        date.fromisoformat(day)
        base=self.root.resolve()
        path=base/'.agent-state/market-data/daily-quotes'/('symbol-'+symbol)/(day+'.json')
        self._check_activity_path(path)
        return path

    def _check_activity_path(self,path):
        base=self.root.resolve()
        if not path.resolve().is_relative_to(base):raise ValueError('Activity archive escaped root')
        for item in (path,*path.parents):
            if item==base:break
            if item.is_symlink() or item.is_junction():raise ValueError('Activity archive links are forbidden')

    @staticmethod
    def _activity_identity(envelope):
        rows=envelope.get('rows')
        if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):
            raise ValueError('Archive expects one quote')
        row=rows[0]
        if not isinstance(row.get('TD'),str) or not re.fullmatch(r'\d{2}/\d{2}/\d{4}',row['TD']):
            raise ValueError('Invalid quote date')
        stamp=datetime.fromisoformat(envelope['fetched_at'])
        if stamp.utcoffset() is None:raise ValueError('Observation requires timezone')
        return row.get('symbol',''),datetime.strptime(row['TD'],'%d/%m/%Y').date().isoformat(),stamp

    @staticmethod
    def _atomic_activity(path,data):
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
        try:
            temporary.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,allow_nan=False),encoding='utf-8')
            temporary.replace(path)
        finally:temporary.unlink(missing_ok=True)

    def save_daily_quote(self,envelope):
        symbol,day,stamp=self._activity_identity(envelope)
        path=self._activity_path(symbol,day)
        raw=json.dumps(envelope,ensure_ascii=False,sort_keys=True,allow_nan=False).encode('utf-8')
        if len(raw)>1024*1024:raise ValueError('Activity quote too large')
        if path.exists():
            old=json.loads(path.read_text(encoding='utf-8'))
            if self._activity_identity(old)[2]>stamp:return False
        self._atomic_activity(path,envelope)
        return True

    def pending_activity(self,limit=100):
        base=self.root.resolve()/'.agent-state/market-data/daily-quotes'
        result=[]
        for path in sorted(base.glob('symbol-*/*.json')):
            if path.name.endswith('.ack.json'):continue
            symbol=path.parent.name.removeprefix('symbol-')
            self._activity_path(symbol,path.stem)
            raw=path.read_bytes()
            if len(raw)>1024*1024:raise ValueError('Activity archive too large')
            digest=hashlib.sha256(raw).hexdigest()
            ack=path.with_suffix('.ack.json');self._check_activity_path(ack)
            if ack.exists() and json.loads(ack.read_text(encoding='utf-8')).get('sha256')==digest:continue
            envelope=json.loads(raw)
            actual=self._activity_identity(envelope)
            if actual[:2]!=(symbol,path.stem):raise ValueError('Activity archive identity mismatch')
            result.append({'path':path,'symbol':symbol,'sha256':digest,'envelope':envelope})
            if len(result)>=limit:break
        return result

    def ack_activity(self,item,status):
        if status not in ('inserted','updated','unchanged','rejected','needs_reconciliation','not_tracked'):
            raise ValueError('Unknown activity outcome')
        symbol,day,_=self._activity_identity(item['envelope'])
        path=self._activity_path(symbol,day)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:return False
        ack=path.with_suffix('.ack.json');self._check_activity_path(ack)
        self._atomic_activity(ack,{'sha256':item['sha256'],'status':status})
        return True

    def get_ohlcv(self, symbol: str, limit: int) -> dict:
        data = self._get_saved_ohlcv(symbol, 250)
        runtime = self.runtime_read(symbol, "history") if re.fullmatch(r"[A-Z]{3}", symbol) else None
        if runtime:
            bars = {bar["date"]: bar for bar in data["bars"]}
            for bar in runtime.get("bars", []):
                if bars.get(bar["date"], {}).get("status") != "closed":
                    bars[bar["date"]] = bar
            data = {**data, "bars": sorted(bars.values(), key=lambda bar: bar["date"]),
                    "fetched_at": runtime.get("fetched_at"), "source": runtime.get("source")}
        return {**data, "bars": data["bars"][-limit:]}

    def index_history_path(self, symbol):
        from .history import INDEX_NAMES
        if symbol not in INDEX_NAMES:raise ValueError('Chỉ số không được hỗ trợ.')
        return self.root/'.agent-state/market-data/indices'/('index-'+symbol)/'history.json'

    def write_index_history(self, symbol, data):
        path=self.index_history_path(symbol);path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
        try:
            temporary.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf-8')
            temporary.replace(path)
        finally:temporary.unlink(missing_ok=True)

    def read_index_history(self, symbol):
        from .history import normalize_index_history
        path=self.index_history_path(symbol)
        sources=[path,self.root/'data_pipeline/ScrapersOHLCV/data/stocks'/symbol/'data.json']
        for source in sources:
            try:
                data=json.loads(source.read_text(encoding='utf-8'))
                provenance=data.get('provenance') or {}
                if source==path:
                    if data.get('symbol')!=symbol or data.get('price_unit')!='points':continue
                    stamp=data['fetched_at'];rows=[{**r,'time':r['date']} for r in data['bars']]
                else:
                    if provenance.get('instrument_type')!='index' or provenance.get('price_units')!='points':continue
                    stamp=provenance.get('fetched_at') or provenance.get('history_fetched_at')
                    rows=[{**r,'time':r['trade_date']} for r in data['bars'] if r.get('symbol')==symbol]
                return normalize_index_history(symbol,{'fetched_at':stamp,'rows':rows})
            except (OSError,ValueError,KeyError,TypeError,AttributeError):continue
        return {'symbol':symbol,'interval':'1D','source':None,'fetched_at':None,'price_unit':'points','bars':[]}

    def _get_saved_ohlcv(self, symbol: str, limit: int) -> dict:
        path = self.root / "data_pipeline" / "ScrapersOHLCV" / "data" / "stocks" / symbol / "data.json"
        if not path.is_file():
            return {"symbol": symbol, "interval": "1D", "source": None, "fetched_at": None, "bars": []}

        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(snapshot, dict):
            raise ValueError("OHLCV snapshot must be an object")
        provenance = snapshot.get("provenance") or {}
        if not isinstance(provenance, dict) or not isinstance(snapshot.get("bars"), list):
            raise ValueError("Invalid OHLCV snapshot")
        bars = []
        for raw in snapshot.get("bars", []):
            if not isinstance(raw, dict) or raw.get("symbol") != symbol or not raw.get("trade_date"):
                continue
            bars.append({
                "date": raw["trade_date"],
                "open": raw.get("open"),
                "high": raw.get("high"),
                "low": raw.get("low"),
                "close": raw.get("close"),
                "volume": raw.get("volume"),
                "status": raw.get("status"),
                "quality": raw.get("quality"),
                "price_basis": raw.get("price_basis"),
                "volume_basis": raw.get("volume_basis"),
                "source": raw.get("source"),
            })
        bars.sort(key=lambda bar: bar["date"])
        return {
            "symbol": symbol,
            "interval": "1D",
            "source": provenance.get("provider"),
            "fetched_at": provenance.get("fetched_at") or provenance.get("history_fetched_at"),
            "bars": bars[-limit:],
        }

    def get_news(self, symbol: str | None, limit: int) -> dict:
        saved = self._get_saved_news(symbol, limit)
        runtime = self.runtime_read(symbol, "news") if symbol and re.fullmatch(r"[A-Z]{3}", symbol) else None
        if not runtime:
            return saved
        def key(article):
            url = article.get("url") or ""
            tail = urlsplit(url).path.rstrip("/").split("/")[-1]
            return "fireant:" + tail if tail.isdigit() else url or article["id"]
        by_id = {key(article): article for article in saved["articles"]}
        for article in runtime.get("articles", []):
            parsed = urlsplit(article.get("url") or "")
            if parsed.scheme == "https" and parsed.hostname in ("fireant.vn", "www.fireant.vn"):
                by_id[key(article)] = article
        def published(article):
            try:
                return datetime.fromisoformat(article["published_at"]).timestamp()
            except (ValueError, TypeError, KeyError):
                return 0
        return {**saved, "fetched_at": runtime.get("fetched_at"),
                "articles": sorted(by_id.values(), key=published, reverse=True)[:limit]}

    def _get_saved_news(self, symbol: str | None, limit: int) -> dict:
        news_root = self.root / "data_pipeline" / "scrapers" / "data"
        folder = news_root / "tin_tuc_theo_ma" / symbol / "fireant" if symbol else news_root / "tin_tuc_chung" / "fireant"
        if not folder.is_dir():
            return {"symbol": symbol, "source": "fireant", "articles": []}

        # Newer crawl files win when the same article appears on multiple days.
        by_id = {}
        paths = []
        for path in folder.glob("*.json"):
            try:
                paths.append((datetime.strptime(path.stem, "%d-%m-%Y"), path))
            except ValueError:
                continue
        for _, path in sorted(paths):
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get("articles"), list):
                raise ValueError("Invalid news snapshot")
            for raw in snapshot.get("articles", []):
                if not isinstance(raw, dict) or (symbol is not None and symbol not in (raw.get("matched_symbols") or [])):
                    continue
                url = raw.get("url") or ""
                parsed = urlsplit(url)
                safe_url = url if parsed.scheme == "https" and parsed.hostname in ("fireant.vn", "www.fireant.vn") else None
                article_id = raw.get("id") or safe_url
                if not article_id or not raw.get("title"):
                    continue
                by_id[safe_url or article_id] = {
                    "id": article_id,
                    "title": raw["title"],
                    "description": raw.get("description") or "",
                    "url": safe_url,
                    "published_at": raw.get("published_at"),
                    "category": raw.get("category"),
                    "marker": raw.get("marker") if raw.get("marker") in ("check", "uncheck") else "uncheck",
                    "source": "fireant",
                }
        articles = sorted(by_id.values(), key=lambda article: article["published_at"] or "", reverse=True)
        return {"symbol": symbol, "source": "fireant", "articles": articles[:limit]}
