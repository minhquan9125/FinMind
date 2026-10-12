"""Read crawler snapshots. Replace this reader when data moves to Supabase."""

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
import re


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
