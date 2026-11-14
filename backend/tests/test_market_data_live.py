"""Deterministic batch tests: no SDK, network or locked crawler writes."""
import copy
import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from backend.src.market_data.live import BusyError, LiveCoordinator

VN = timezone(timedelta(hours=7))


def quote(symbol="FPT", **changes):
    return {"symbol": symbol, "exchange": "HOSE", "TD": "08/10/2026",
            "open_price": "60000", "high_price": "62000", "low_price": "59000",
            "close_price": "61000", "volume_accumulated": 100, **changes}


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.seconds = 0
        self.open = True
        self.now = datetime(2026, 10, 8, 10, tzinfo=VN)
        self.saved = {"symbol": "FPT", "interval": "1D", "source": "vnstock_kbs",
                      "fetched_at": None, "bars": []}
        self.repo = Mock()
        self.repo.get_ohlcv.side_effect = lambda symbol, limit: {**copy.deepcopy(self.saved), "symbol": symbol}
        self.fetch = Mock(side_effect=lambda symbols: {
            "fetched_at": self.now.isoformat(), "rows": [quote(symbol) for symbol in symbols]})
        self.service = LiveCoordinator(self.fetch, lambda exchange: self.open, self.repo,
                                       clock=lambda: self.seconds, now=lambda: self.now)

    def test_ten_viewers_produce_one_batch_and_duplicate_is_deduplicated(self):
        symbols = ["FPT", "VCB", "HPG", "MBB", "ACB", "VNM", "SSI", "FTS", "VIC", "VHM"]
        for index, symbol in enumerate(symbols):
            self.service.watch(str(index), symbol)
        self.service.watch("duplicate", "FPT")
        self.service.tick()
        self.assertEqual(self.fetch.call_count, 1)
        self.assertEqual(set(self.fetch.call_args.args[0]), set(symbols))
        self.assertEqual(self.service.read("FPT", 250)["bars"][0]["close"], "61")

    def test_switch_unsubscribe_and_expiry_stop_collection(self):
        self.service.watch("one", "FPT")
        self.service.watch("one", "VCB")
        self.service.tick()
        self.assertEqual(self.fetch.call_args.args[0], ["VCB"])
        self.service.unwatch("one")
        self.seconds = 5
        self.service.tick()
        self.assertEqual(self.fetch.call_count, 1)
        self.service.watch("two", "FPT")
        self.seconds = 26
        self.service.tick()
        self.assertEqual(self.fetch.call_count, 1)

    def test_closed_session_never_automatically_fetches_but_manual_refresh_works(self):
        self.open = False
        self.service.watch("one", "FPT")
        self.service.tick()
        self.fetch.assert_not_called()
        self.service.refresh("FPT")
        self.assertEqual(self.fetch.call_count, 1)
        self.assertEqual(self.service.read("FPT", 250)["bars"][0]["status"], "pending_reconciliation")

    def test_manual_uses_60_second_cache_and_shared_spacing(self):
        self.service.refresh("FPT")
        self.seconds = 59
        self.service.refresh("FPT")
        self.assertEqual(self.fetch.call_count, 1)
        self.seconds = 60
        self.service.refresh("FPT")
        self.assertEqual(self.fetch.call_count, 2)
        with self.assertRaises(BusyError):
            self.service.refresh("VCB")

    def test_invalid_duplicate_and_stale_day_rows_do_not_poison_good_symbol(self):
        for symbol in ("FPT", "VCB", "HPG"):
            self.service.watch(symbol, symbol)
        self.fetch.side_effect = lambda _: {"fetched_at": self.now.isoformat(), "rows": [
            quote("FPT"), quote("FPT"), quote("VCB", TD="07/10/2026"), quote("HPG")]}
        self.service.tick()
        self.assertEqual(self.service.read("FPT", 250)["bars"], [])
        self.assertEqual(self.service.read("VCB", 250)["bars"], [])
        self.assertEqual(len(self.service.read("HPG", 250)["bars"]), 1)

    def test_price_decrease_is_valid_but_regressing_volume_is_rejected(self):
        self.service.watch("one", "FPT")
        self.service.tick()
        self.seconds = 5
        self.fetch.side_effect = lambda _: {"fetched_at": self.now.isoformat(), "rows": [
            quote(close_price="60000", volume_accumulated=110)]}
        self.service.tick()
        self.assertEqual(self.service.read("FPT", 250)["bars"][0]["close"], "60")
        self.seconds = 10
        self.fetch.side_effect = lambda _: {"fetched_at": self.now.isoformat(), "rows": [
            quote(close_price="61500", volume_accumulated=105)]}
        self.service.tick()
        self.assertEqual(self.service.read("FPT", 250)["bars"][0]["volume"], 110)

    def test_saved_same_day_and_history_are_preserved(self):
        self.saved["bars"] = [
            {"date": "2026-10-07", "close": "58"},
            {"date": "2026-10-08", "open": "60", "high": "62", "low": "59", "close": "61",
             "volume": 1000, "source": "vnstock_kbs", "price_basis": "unknown", "volume_basis": "unknown"}]
        original = copy.deepcopy(self.saved)
        self.service.watch("one", "FPT")
        self.service.tick()
        self.assertEqual(self.service.read("FPT", 250)["bars"], self.saved["bars"])
        self.assertEqual(self.saved, original)

    def test_failed_calls_back_off_and_never_replace_good_data(self):
        self.service.watch("one", "FPT")
        self.service.tick()
        self.fetch.side_effect = RuntimeError("private upstream detail")
        self.seconds = 5
        self.service.tick()
        self.seconds = 6
        self.service.tick()
        self.assertEqual(self.fetch.call_count, 2)
        self.assertEqual(self.service.read("FPT", 250)["bars"][0]["close"], "61")
        self.assertNotIn("private upstream", str(self.service.read("FPT", 250)))

    def test_no_overlap_and_unsubscribed_inflight_result_is_ignored(self):
        entered, release = threading.Event(), threading.Event()
        def fetch(symbols):
            entered.set()
            release.wait(3)
            return {"fetched_at": self.now.isoformat(), "rows": [quote()]}
        self.fetch.side_effect = fetch
        self.service.watch("one", "FPT")
        thread = threading.Thread(target=self.service.tick)
        thread.start()
        self.assertTrue(entered.wait(2))
        self.service.tick()
        self.service.unwatch("one")
        release.set()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.fetch.call_count, 1)
        self.assertEqual(self.service.read("FPT", 250)["bars"], [])

    def test_indices_and_invalid_symbols_are_not_sent_to_stock_batch(self):
        for symbol in ("VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX", "../FPT", "FPT$"):
            with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                self.service.watch("one", symbol)
        self.service.tick()
        self.fetch.assert_not_called()

    def test_one_viewer_expiring_does_not_remove_another_live_lease(self):
        self.service.watch("expired", "FPT")
        self.service.watch("active", "VCB")
        self.seconds = 15
        self.service.watch("active", "VCB")
        self.seconds = 21
        self.service.tick()
        self.assertEqual(self.fetch.call_args.args[0], ["VCB"])

    def test_session_closing_inflight_discards_response(self):
        self.service.watch("one", "FPT")
        def fetch(_):
            self.open = False
            return {"fetched_at": self.now.isoformat(), "rows": [quote()]}
        self.fetch.side_effect = fetch
        self.service.tick()
        self.assertEqual(self.service.read("FPT", 250)["bars"], [])

    def test_bad_timestamp_and_empty_rows_cannot_refresh_freshness(self):
        self.service.watch("one", "FPT")
        self.service.tick()
        original = self.service.read("FPT", 250)["fetched_at"]
        for index, payload in enumerate((
            {"fetched_at": "2026-10-08T10:00:00", "rows": [quote()]},
            {"fetched_at": (self.now + timedelta(minutes=5)).isoformat(), "rows": [quote()]},
            {"fetched_at": self.now.isoformat(), "rows": []},
            {"fetched_at": self.now.isoformat(), "rows": "invalid"},
        )):
            self.seconds = 100 * (index + 1)
            self.service.watch("one", "FPT")
            self.fetch.side_effect = None
            self.fetch.return_value = payload
            self.service.tick()
            self.assertEqual(self.service.read("FPT", 250)["fetched_at"], original)
            self.assertTrue(self.service.read("FPT", 250)["live"]["stale"])

    def test_settings_and_symbol_capacity_are_bounded(self):
        for value in (0, 4, float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                LiveCoordinator(self.fetch, lambda _: True, self.repo, poll_seconds=value)
        symbols = ["A" + chr(65 + index // 26) + chr(65 + index % 26) for index in range(101)]
        for index, symbol in enumerate(symbols[:100]):
            self.service.watch(str(index), symbol)
        with self.assertRaises(OverflowError):
            self.service.watch("extra", symbols[100])
        self.service.watch("0", symbols[100])  # Switching the last viewer frees one symbol slot.

    def test_saved_data_overtaking_overlay_wins_on_read(self):
        self.service.watch("one", "FPT")
        self.service.tick()
        saved = self.service.read("FPT", 250)["bars"][0]
        self.saved["bars"] = [{**saved, "volume": 1000}]
        self.assertEqual(self.service.read("FPT", 250)["bars"][0]["volume"], 1000)

    def test_pending_saved_status_is_not_reopened_by_existing_overlay(self):
        self.service.watch("one", "FPT")
        self.service.tick()
        saved = self.service.read("FPT", 250)["bars"][0]
        self.saved["bars"] = [{**saved, "status": "pending_reconciliation"}]
        self.assertEqual(self.service.read("FPT", 250)["bars"][0]["status"], "pending_reconciliation")
        self.seconds = 5
        self.service.tick()
        self.assertEqual(self.service.read("FPT", 250)["bars"][0]["status"], "pending_reconciliation")



if __name__ == "__main__":
    unittest.main()
