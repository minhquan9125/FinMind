import json
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.src.api.routers.market_data import router, get_market_data_repository
from backend.src.market_data.history import normalize_history
from backend.src.market_data.live import LiveCoordinator, VN, BusyError
from backend.src.market_data.news import NewsService, FireAntNews
from backend.src.market_data.repository import FileMarketDataRepository
from backend.tests.test_market_data_live import quote


def history():
    return {"fetched_at": "2026-10-08T10:00:00+07:00", "rows": [
        {"time": "2026-10-07T07:00:00", "open": "60", "high": "62", "low": "59", "close": "60.4", "volume": 50},
        {"time": "2026-10-08T07:00:00", "open": "60", "high": "62", "low": "59", "close": "61", "volume": 100}]}


class CompanyDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = FileMarketDataRepository(self.root)
        self.seconds = [0]
        self.fetch = Mock(return_value=history())
        self.now = datetime(2026, 10, 8, 10, tzinfo=VN)
        self.service = LiveCoordinator(Mock(return_value={"fetched_at": self.now.isoformat(), "rows": [quote("CTR", close_price="61500", volume_accumulated=110)]}),
            lambda _: True, self.repo, history_fetch=self.fetch, clock=lambda: self.seconds[0], now=lambda: self.now)

    def test_new_symbol_history_persists_and_live_overlays_without_losing_past(self):
        data = self.service.stock_history("CTR")
        self.assertEqual(len(data["bars"]), 2)
        self.assertEqual(data["bars"][0]["close"], "60.4")
        self.service.stock_history("CTR")
        self.fetch.assert_called_once()
        self.assertTrue(self.repo.runtime_path("CTR", "history").is_file())
        self.assertFalse((self.root / "data_pipeline").exists())
        self.assertEqual(len(FileMarketDataRepository(self.root).get_ohlcv("CTR", 250)["bars"]), 2)
        self.service.watch("viewer", "CTR")
        self.seconds[0] = 5
        self.service.tick()
        data = self.service.read("CTR", 250)
        self.assertEqual(len(data["bars"]), 2)
        self.assertEqual(data["bars"][-1]["close"], "61.5")
        self.assertEqual(data["bars"][-1]["volume"], 110)

    def test_failure_preserves_history_and_paths_are_scoped(self):
        self.service.stock_history("CTR")
        self.now = datetime(2026, 10, 8, 11, tzinfo=VN)
        self.seconds[0] = 61
        self.fetch.return_value = {"rows": []}
        with self.assertRaises(RuntimeError):
            self.service.stock_history("CTR")
        self.assertEqual(len(self.repo.get_ohlcv("CTR", 250)["bars"]), 2)
        for symbol in ("../CTR", "CTR/.."): 
            with self.assertRaises(ValueError):
                self.repo.runtime_write(symbol, "history", {})
        self.assertIn("symbol-CON", str(self.repo.runtime_path("CON", "history")))

    def test_news_cache_failure_cooldown_and_shared_budget(self):
        article = {"id": "one", "title": "Tin mới", "url": "https://fireant.vn/bai-viet/tin/123",
                   "published_at": "2026-10-08T10:00:00+07:00", "marker": "uncheck"}
        fetch = Mock(return_value=[article])
        service = NewsService(fetch, self.repo, clock=lambda: self.seconds[0])
        self.assertFalse(service.refresh("CTR")["refresh"]["stale"])
        service.refresh("CTR")
        fetch.assert_called_once_with("CTR")
        with self.assertRaises(BusyError):
            service.refresh("FPT")
        self.seconds[0] = 61
        fetch.side_effect = RuntimeError("private upstream data")
        result = service.refresh("CTR")
        self.assertTrue(result["refresh"]["stale"])
        self.assertEqual(result["articles"][0]["title"], "Tin mới")
        self.assertNotIn("private", json.dumps(result))
        service.refresh("CTR")
        self.assertEqual(fetch.call_count, 2)

    def test_http_history_and_news_refresh_contract(self):
        app = FastAPI()
        app.include_router(router)
        app.state.live = self.service
        app.state.news = NewsService(Mock(return_value=[]), self.repo)
        app.dependency_overrides[get_market_data_repository] = lambda: self.repo
        with TestClient(app) as client:
            result = client.post("/api/market-data/stocks/ctr/history")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(len(client.get("/api/market-data/stocks/CTR/ohlcv").json()["bars"]), 2)
            self.assertEqual(client.post("/api/market-data/companies/CTR/news/refresh").status_code, 200)
            self.assertEqual(client.post("/api/market-data/stocks/ABCD/history").status_code, 400)

    def test_atomic_failure_keeps_previous_snapshot(self):
        original = normalize_history("CTR", history())
        self.repo.runtime_write("CTR", "history", original)
        with patch.object(Path, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                self.repo.runtime_write("CTR", "history", {"symbol": "CTR", "bars": []})
        self.assertEqual(self.repo.runtime_read("CTR", "history"), original)
        self.assertEqual(list(self.repo.runtime_path("CTR", "history").parent.glob("*.tmp")), [])

    def test_news_deduplicates_same_post_with_changed_slug(self):
        folder = self.root / "data_pipeline/scrapers/data/tin_tuc_theo_ma/CTR/fireant"
        folder.mkdir(parents=True)
        old = {"id": "old", "title": "old", "url": "https://fireant.vn/bai-viet/old-slug/123",
               "matched_symbols": ["CTR"], "published_at": "2026-10-08T10:00:00+07:00"}
        (folder / "08-10-2026.json").write_text(json.dumps({"articles": [old]}), encoding="utf-8")
        fresh = {**old, "id": "new", "title": "new", "url": "https://fireant.vn/bai-viet/new-slug/123"}
        unsafe = {**fresh, "url": "https://example.com/123"}
        self.repo.runtime_write("CTR", "news", {"symbol": "CTR", "articles": [fresh, unsafe]})
        result = self.repo.get_news("CTR", 10)
        self.assertEqual(len(result["articles"]), 1)
        self.assertEqual(result["articles"][0]["title"], "new")

    def test_news_provider_uses_one_bounded_symbol_page_and_strips_html(self):
        requests = []
        def handle(request):
            requests.append(request)
            if request.url.host == "restv2.fireant.vn":
                return httpx.Response(200, json=[{"type": 1, "postID": 123, "title": "<b>CTR</b> mới",
                                                 "description": "Tin &amp; báo cáo", "date": "2026-10-08T10:00:00+07:00"}])
            if "_app-" in request.url.path:
                return httpx.Response(200, text='ANONYMOUS_ACCESS_TOKEN="public-test"')
            return httpx.Response(200, text='<script src="/_next/static/chunks/pages/_app-abc.js"></script>')
        provider = FireAntNews()
        provider.close()
        provider.client = httpx.Client(transport=httpx.MockTransport(handle))
        self.addCleanup(provider.close)
        rows = provider("CTR")
        self.assertEqual(rows[0]["title"], "CTR mới")
        self.assertEqual(rows[0]["description"], "Tin & báo cáo")
        self.assertEqual(requests[-1].url.params["symbol"], "CTR")
        self.assertEqual(requests[-1].url.params["limit"], "20")
        self.assertEqual(len(requests), 3)


if __name__ == "__main__":
    unittest.main()
