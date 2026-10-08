"""HTTP contract, calendar boundaries and singleton lock; never calls the SDK."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.src.api.routers.market_data import get_market_data_repository, router
from backend.src.market_data.live import LiveCoordinator
from backend.src.market_data.repository import FileMarketDataRepository
from backend.src.market_data.sdk import CollectorLock
from backend.src.market_data.session import SessionGate
from backend.tests.test_market_data_live import quote

VN = timezone(timedelta(hours=7))


class LiveApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = FileMarketDataRepository(self.root)
        self.now = datetime(2026, 10, 8, 10, tzinfo=VN)
        self.fetch = Mock(return_value={"fetched_at": self.now.isoformat(), "rows": [quote()]})
        self.service = LiveCoordinator(self.fetch, lambda _: True, self.repo, now=lambda: self.now)
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.state.live = self.service
        self.app.dependency_overrides[get_market_data_repository] = lambda: self.repo
        self.client = TestClient(self.app)
        self.viewer = str(uuid4())

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_lease_overlay_etag_and_unsubscribe(self):
        url = "/api/market-data/stocks/FPT/ohlcv?limit=1"
        before = self.client.get(url)
        self.assertEqual(before.status_code, 200)
        lease = self.client.put(f"/api/market-data/live/viewers/{self.viewer}", json={"symbol": "fpt"})
        self.assertEqual(lease.status_code, 200)
        self.service.tick()
        current = self.client.get(url, headers={"If-None-Match": before.headers["etag"]})
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["bars"][0]["close"], "61")
        self.assertTrue(current.json()["live"]["active"])
        same = self.client.get(url, headers={"If-None-Match": current.headers["etag"]})
        self.assertEqual(same.status_code, 304)
        self.assertEqual(self.client.delete(f"/api/market-data/live/viewers/{self.viewer}").status_code, 200)
        self.assertEqual(self.client.get("/api/market-data/live/status").json()["symbols"], [])
        self.assertFalse((self.root / "data_pipeline").exists())

    def test_validators_and_manual_share_budget(self):
        self.assertEqual(self.client.put("/api/market-data/live/viewers/bad", json={"symbol": "FPT"}).status_code, 422)
        self.assertEqual(self.client.put(f"/api/market-data/live/viewers/{self.viewer}", json={"symbol": "VNINDEX"}).status_code, 400)
        response = self.client.post("/api/market-data/stocks/FPT/refresh")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post("/api/market-data/stocks/FPT/refresh").status_code, 200)
        self.assertEqual(self.fetch.call_count, 1)
        busy = self.client.post("/api/market-data/stocks/VCB/refresh")
        self.assertEqual(busy.status_code, 429)
        self.assertGreater(int(busy.headers["Retry-After"]), 0)

    def test_next_quote_updates_http_candle_and_invalidates_etag(self):
        seconds = [0]
        self.service.clock = lambda: seconds[0]
        lease_url = f"/api/market-data/live/viewers/{self.viewer}"
        self.assertEqual(self.client.put(lease_url, json={"symbol": "FPT"}).status_code, 200)
        self.service.tick()
        url = "/api/market-data/stocks/FPT/ohlcv?limit=250"
        first = self.client.get(url)
        self.assertEqual(first.json()["bars"][0]["close"], "61")
        self.fetch.return_value = {"fetched_at": self.now.isoformat(), "rows": [
            quote(close_price="61500", volume_accumulated=110)]}
        seconds[0] = 5
        self.service.tick()
        second = self.client.get(url, headers={"If-None-Match": first.headers["etag"]})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["bars"][0]["close"], "61.5")
        self.assertEqual(second.json()["bars"][0]["volume"], 110)
        self.assertNotEqual(first.headers["etag"], second.headers["etag"])
        self.assertEqual(self.client.delete(lease_url).status_code, 200)
        seconds[0] = 10
        self.service.tick()
        self.assertEqual(self.fetch.call_count, 2)

    def test_etag_depends_on_requested_limit(self):
        path = self.root / "data_pipeline/ScrapersOHLCV/data/stocks/FPT/data.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"bars": [
            {"symbol": "FPT", "trade_date": "2026-10-06", "close": "60"},
            {"symbol": "FPT", "trade_date": "2026-10-07", "close": "61"}]}), encoding="utf-8")
        first = self.client.get("/api/market-data/stocks/FPT/ohlcv?limit=1")
        second = self.client.get("/api/market-data/stocks/FPT/ohlcv?limit=2", headers={"If-None-Match": first.headers["etag"]})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.json()["bars"]), 2)

    def test_disabled_collector_keeps_saved_api_available(self):
        self.app.state.live = None
        self.assertEqual(self.client.get("/api/market-data/stocks/FPT/ohlcv").status_code, 200)
        self.assertEqual(self.client.put(f"/api/market-data/live/viewers/{self.viewer}", json={"symbol": "FPT"}).status_code, 503)

    def test_index_endpoint_is_explicit_cached_and_validated(self):
        from backend.tests.test_market_indices import snapshot
        self.service.history_fetch = Mock(return_value=snapshot())
        response = self.client.get("/api/market-data/indices/HNXINDEX/ohlcv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["price_unit"], "points")
        self.assertEqual(self.client.get("/api/market-data/indices/HNXINDEX/ohlcv").status_code, 200)
        self.assertEqual(self.service.history_fetch.call_count, 1)
        self.assertEqual(self.client.get("/api/market-data/indices/FPT/ohlcv").status_code, 400)
        self.assertEqual(self.client.get("/api/market-data/indices/UPCOMINDEX/ohlcv").status_code, 429)


class InfrastructureTests(unittest.TestCase):
    def test_calendar_lunch_weekend_and_unknown_year_fail_closed(self):
        root = Path(__file__).resolve().parents[2]
        gate = SessionGate(root, now=lambda: datetime(2026, 10, 8, 10, tzinfo=VN))
        self.assertTrue(gate("HOSE"))
        gate.now = lambda: datetime(2026, 10, 8, 11, 45, tzinfo=VN)
        self.assertFalse(gate("HOSE"))
        gate.now = lambda: datetime(2026, 10, 10, 10, tzinfo=VN)
        self.assertFalse(gate("HOSE"))
        gate.now = lambda: datetime(2027, 10, 8, 10, tzinfo=VN)
        self.assertFalse(gate("HOSE"))
        self.assertFalse(gate("BAD"))
        self.assertFalse(SessionGate(root / "missing")("HOSE"))

    def test_exclusive_collector_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "collector.lock"
            first, second = CollectorLock(path), CollectorLock(path)
            first.acquire()
            try:
                with self.assertRaises(RuntimeError):
                    second.acquire()
            finally:
                first.close()
            second.acquire()
            second.close()


if __name__ == "__main__":
    unittest.main()
