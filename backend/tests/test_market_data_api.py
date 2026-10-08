"""The market/news API reads snapshots without starting PostgreSQL or a crawler."""

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.src.api.routers.market_data import get_market_data_repository
from backend.src.market_data.app import app
from backend.src.market_data.repository import FileMarketDataRepository


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class MarketDataApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        app.dependency_overrides[get_market_data_repository] = lambda: FileMarketDataRepository(self.root)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.tempdir.cleanup()

    def test_ohlcv_reads_saved_bars_and_limits_response(self):
        path = self.root / "data_pipeline/ScrapersOHLCV/data/stocks/FPT/data.json"
        write_json(path, {
            "provenance": {"provider": "vnstock_kbs", "history_fetched_at": "2026-10-07T10:00:00+07:00"},
            "bars": [
                {"symbol": "FPT", "trade_date": "2026-10-06", "close": "60.1", "volume": 10, "status": "pending_reconciliation"},
                {"symbol": "FPT", "trade_date": "2026-10-07", "close": "60.2", "volume": 20, "status": "open"},
                {"symbol": "VCB", "trade_date": "2026-10-07", "close": "70", "volume": 30},
            ],
        })
        with TestClient(app) as client:
            response = client.get("/api/market-data/stocks/fpt/ohlcv?limit=1")
            assert response.status_code == 200
            body = response.json()
            assert body["symbol"] == "FPT"
            assert body["source"] == "vnstock_kbs"
            assert body["bars"] == [{
                "date": "2026-10-07", "open": None, "high": None, "low": None,
                "close": "60.2", "volume": 20, "status": "open", "quality": None,
                "price_basis": None, "volume_basis": None, "source": None,
            }]
            version = response.headers["etag"]
            unchanged = client.get("/api/market-data/stocks/FPT/ohlcv?limit=1", headers={"If-None-Match": version})
            assert unchanged.status_code == 304
            assert unchanged.content == b""
            assert unchanged.headers["etag"] == version
            write_json(path, {"provenance": {"provider": "vnstock_kbs"}, "bars": [
                {"symbol": "FPT", "trade_date": "2026-10-08", "close": "61.5", "volume": 100},
            ]})
            changed = client.get("/api/market-data/stocks/FPT/ohlcv?limit=1", headers={"If-None-Match": version})
            assert changed.status_code == 200
            assert changed.headers["etag"] != version
            assert changed.json()["bars"][0]["close"] == "61.5"
            assert client.get("/api/market-data/stocks/AAA/ohlcv").json()["bars"] == []
            assert client.get("/api/market-data/stocks/FPT$/ohlcv").status_code == 400
            assert client.get("/api/market-data/stocks/FPT/ohlcv?limit=251").status_code == 422


    def test_news_filters_symbol_deduplicates_and_keeps_marker(self):
        folder = self.root / "data_pipeline/scrapers/data/tin_tuc_theo_ma/FPT/fireant"
        first = {"id": "one", "title": "Tin FPT", "url": "https://fireant.vn/bai-viet/one",
                 "published_at": "2026-10-01T10:00:00+07:00", "matched_symbols": ["FPT"], "marker": "uncheck"}
        newer = {**first, "description": "Bản mới"}
        other = {"id": "two", "title": "Tin VCB", "matched_symbols": ["VCB"]}
        unsafe = {"id": "three", "title": "Tin khác", "url": "javascript:alert(1)",
                  "matched_symbols": ["FPT"], "marker": "check", "published_at": "2026-10-02T10:00:00+07:00"}
        write_json(folder / "01-10-2026.json", {"articles": [first, other]})
        write_json(folder / "02-10-2026.json", {"articles": [newer, unsafe]})
        with TestClient(app) as client:
            response = client.get("/api/market-data/companies/FPT/news")
            assert response.status_code == 200
            articles = response.json()["articles"]
            assert [article["id"] for article in articles] == ["three", "one"]
            assert articles[0]["url"] is None
            assert articles[0]["marker"] == "check"
            assert articles[1]["description"] == "Bản mới"
            assert articles[1]["marker"] == "uncheck"
            assert client.get("/api/market-data/companies/MBB/news").json()["articles"] == []


if __name__ == "__main__":
    unittest.main()
