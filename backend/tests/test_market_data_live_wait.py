"""User lookups may queue for the shared price source instead of failing at once.

The per-source spacing and failure back-off must stay exactly as strict as before.
No SDK, network or real sleeping: time.sleep is replaced by a fake clock advance.
"""
import copy
import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from backend.src.market_data.live import BusyError, LiveCoordinator

VN = timezone(timedelta(hours=7))


def quote(symbol):
    return {"symbol": symbol, "exchange": "HOSE", "TD": "08/10/2026",
            "open_price": "60000", "high_price": "62000", "low_price": "59000",
            "close_price": "61000", "volume_accumulated": 100}


class WaitingLookupTests(unittest.TestCase):
    def setUp(self):
        self.seconds = 0.0
        self.now = datetime(2026, 10, 8, 10, tzinfo=VN)
        self.fetch_times = []
        self.repo = Mock()
        self.repo.get_ohlcv.side_effect = lambda symbol, limit: {
            "symbol": symbol, "interval": "1D", "source": "vnstock_kbs", "fetched_at": None, "bars": []}

        def fetch(symbols):
            self.fetch_times.append(self.seconds)
            return {"fetched_at": self.now.isoformat(), "rows": [quote(s) for s in symbols]}

        self.fetch = Mock(side_effect=fetch)

    def service(self, max_wait):
        return LiveCoordinator(self.fetch, lambda exchange: True, self.repo, clock=lambda: self.seconds,
                               now=lambda: self.now, max_wait_seconds=max_wait)

    def advance(self, wait):
        self.seconds += wait

    def test_waits_out_the_spacing_instead_of_reporting_busy(self):
        service = self.service(max_wait=8)
        with patch("backend.src.market_data.live.time.sleep", side_effect=self.advance) as sleep:
            service.refresh("FPT")
            service.refresh("VCB")
        sleep.assert_called()
        self.assertEqual(self.fetch.call_count, 2)
        self.assertGreaterEqual(self.fetch_times[1] - self.fetch_times[0], 5, "source spacing must not be relaxed")

    def test_default_still_fails_fast(self):
        service = self.service(max_wait=0)
        service.refresh("FPT")
        with self.assertRaises(BusyError):
            service.refresh("VCB")
        self.assertEqual(self.fetch.call_count, 1)

    def test_never_waits_past_the_budget_or_a_failure_backoff(self):
        service = self.service(max_wait=8)
        service._next_attempt = 100  # e.g. after repeated source failures
        with patch("backend.src.market_data.live.time.sleep") as sleep:
            with self.assertRaises(BusyError):
                service.refresh("FPT")
        sleep.assert_not_called()
        self.fetch.assert_not_called()

    def test_queued_lookup_for_same_symbol_reuses_the_fetch_in_flight(self):
        service = self.service(max_wait=8)
        entered, release = threading.Event(), threading.Event()

        def slow_fetch(symbols):
            entered.set()
            release.wait(5)
            return {"fetched_at": self.now.isoformat(), "rows": [quote(s) for s in symbols]}

        self.fetch.side_effect = slow_fetch
        first = threading.Thread(target=service.refresh, args=("FPT",))
        first.start()
        self.assertTrue(entered.wait(5))
        results = []
        second = threading.Thread(target=lambda: results.append(service.refresh("FPT")))
        second.start()
        release.set()
        first.join(5)
        second.join(5)
        self.assertEqual(self.fetch.call_count, 1, "second lookup must not call the source again")
        self.assertEqual(len(results), 1)

    def test_rejects_negative_wait(self):
        with self.assertRaises(ValueError):
            self.service(max_wait=-1)


if __name__ == "__main__":
    unittest.main()
