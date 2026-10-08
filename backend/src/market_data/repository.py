"""Read crawler snapshots. Replace this reader when data moves to Supabase."""

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit


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

    def get_ohlcv(self, symbol: str, limit: int) -> dict:
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

    def get_news(self, symbol: str, limit: int) -> dict:
        folder = self.root / "data_pipeline" / "scrapers" / "data" / "tin_tuc_theo_ma" / symbol / "fireant"
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
                if not isinstance(raw, dict) or symbol not in (raw.get("matched_symbols") or []):
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
