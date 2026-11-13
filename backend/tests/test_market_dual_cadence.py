"""Dual-cadence contract tests; fake time/providers, no network or database."""
import copy
import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from backend.src.market_data.live import BusyError, LiveCoordinator


VN = timezone(timedelta(hours=7))
TRACKED = dict.fromkeys(
    "ACB BID BSR CTG FPT GAS GVR HDB HPG LPB MBB MCH MSN MWG SAB SHB SSB SSI "
    "STB TCB TCX VCB VHM VIB VIC VJC VNM VPB VPL VRE".split(), "HOSE"
)


def quote(symbol="FPT", **changes):
    return {
        "symbol": symbol, "exchange": "HOSE", "TD": "08/10/2026",
        "open_price": "60000", "high_price": "62000", "low_price": "59000",
        "close_price": "61000", "volume_accumulated": 100, **changes,
    }


class FakeClock:
    def __init__(self):
        self.seconds = 0
        self.start = datetime(2026, 10, 8, 10, tzinfo=VN)

    def __call__(self):
        return self.seconds

    def now(self):
        return self.start + timedelta(seconds=self.seconds)


class DualCadenceTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.open = True
        self.saved = {}
        self.repo = Mock()
        self.repo.get_ohlcv.side_effect = self.saved_data
        self.repo.runtime_read.return_value = None
        self.request_times = []
        self.fetch = Mock(side_effect=self.fetch_quotes)
        self.manual = Mock(side_effect=self.envelope)
        self.raw_history = {
            "symbol": "FPT", "fetched_at": self.clock.now().isoformat(),
            "rows": [{"date": "2026-10-07", "close": "60.125"}],
            "provider_metadata": {"price_basis": "unadjusted", "opaque": [1, "2"]},
        }
        self.history = Mock(return_value=self.raw_history)
        self.sink = Mock()

    def saved_data(self, symbol, limit):
        return copy.deepcopy(self.saved.get(symbol, {
            "symbol": symbol, "interval": "1D", "source": "vnstock_kbs",
            "fetched_at": None, "bars": [],
        }))

    def envelope(self, symbols):
        return {"fetched_at": self.clock.now().isoformat(),
                "rows": [quote(symbol) for symbol in symbols]}

    def fetch_quotes(self, symbols):
        self.request_times.append(self.clock.seconds)
        return self.envelope(symbols)

    def service(self, tracked_symbols=(), **kwargs):
        # Most tests also exercise the new default, so baseline failures show behavior.
        return LiveCoordinator(
            self.fetch, lambda exchange: self.open, self.repo,
            clock=self.clock, now=self.clock.now, tracked_symbols=tracked_symbols,
            manual_fetch=self.manual, history_fetch=self.history,
            snapshot_sink=self.sink, **kwargs,
        )

    def renew(self, service, symbols):
        for index, symbol in enumerate(symbols):
            service.watch(str(index), symbol)

    def test_background_only_at_zero_and_sixty_including_half_open_boundary(self):
        service = self.service(TRACKED)
        self.assertEqual(service.tick()["accepted"], 30)
        self.assertEqual(self.fetch.call_args.args[0], sorted(TRACKED))
        for second in (0, 5, 30, 59.999):
            self.clock.seconds = second
            service.tick()
        self.assertEqual(self.fetch.call_count, 1)
        self.clock.seconds = 60
        self.assertEqual(service.tick()["accepted"], 30)
        self.assertEqual(self.request_times, [0, 60])

    def test_one_watched_symbol_is_five_seconds_and_background_is_merged(self):
        service = self.service(TRACKED)
        for second in range(0, 61, 5):
            self.clock.seconds = second
            service.watch("viewer", "CMG")
            self.assertEqual(service.tick()["status"], "ok")
            expected = sorted(set(TRACKED) | {"CMG"}) if second in (0, 60) else ["CMG"]
            self.assertEqual(self.fetch.call_args.args[0], expected)
        self.assertEqual(self.request_times, list(range(0, 61, 5)))

    def test_thirty_watched_symbols_make_twelve_batches_in_half_open_minute(self):
        service = self.service(TRACKED)
        for second in range(0, 60, 5):
            self.clock.seconds = second
            self.renew(service, TRACKED)
            self.assertEqual(service.tick()["accepted"], 30)
            service.tick()
        self.assertEqual(self.request_times, list(range(0, 60, 5)))
        self.clock.seconds = 59.999
        self.renew(service, TRACKED)
        service.tick()
        self.assertEqual(self.fetch.call_count, 12)
        self.clock.seconds = 60
        self.renew(service, TRACKED)
        service.tick()
        self.assertEqual(self.request_times, list(range(0, 61, 5)))

    def test_hundred_viewers_share_one_symbol_and_one_background_collision(self):
        service = self.service(TRACKED)
        for viewer in range(100):
            service.watch(str(viewer), "FPT")
        service.tick()
        self.assertEqual(self.fetch.call_args.args[0], sorted(TRACKED))
        self.clock.seconds = 5
        service.tick()
        self.assertEqual(self.fetch.call_args.args[0], ["FPT"])
        self.assertEqual(self.fetch.call_count, 2)
        self.assertEqual(service.status()["viewers"], 100)
        self.assertEqual(service.status()["symbols"], ["FPT"])

    def test_last_watcher_expiry_returns_to_existing_background_deadline(self):
        service = self.service({"FPT": "HOSE"})
        service.watch("viewer", "HPG")
        service.tick()
        self.clock.seconds = 5
        service.tick()
        self.assertEqual(self.fetch.call_args.args[0], ["HPG"])
        for second in (20, 30, 59.999):
            self.clock.seconds = second
            service.tick()
        self.assertEqual(service.status()["viewers"], 0)
        self.assertEqual(self.fetch.call_count, 2)
        self.clock.seconds = 60
        service.tick()
        self.assertEqual(self.fetch.call_args.args[0], ["FPT"])
        self.assertEqual(self.request_times, [0, 5, 60])

    def test_slow_background_request_is_singleflight_and_does_not_catch_up(self):
        service = self.service({"FPT": "HOSE"})
        entered, release = threading.Event(), threading.Event()

        def delayed(symbols):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test release timed out")
            return self.envelope(symbols)

        self.fetch.side_effect = delayed
        result = []
        worker = threading.Thread(target=lambda: result.append(service.tick()))
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            self.clock.seconds = 12
            self.assertEqual(service.tick()["status"], "busy")
            self.assertEqual(self.fetch.call_count, 1)
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result[0]["status"], "ok")
        self.fetch.side_effect = self.fetch_quotes
        for second in (12, 12, 17, 59.999):
            self.clock.seconds = second
            service.tick()
        self.assertEqual(self.fetch.call_count, 1)
        self.clock.seconds = 60
        service.tick()
        self.assertEqual(self.fetch.call_count, 2)

    def test_scheduler_pause_dispatches_one_background_batch_then_waits_sixty(self):
        service = self.service({"FPT": "HOSE"})
        service.tick()
        self.clock.seconds = 180
        service.tick()
        for second in (180, 185, 239.999):
            self.clock.seconds = second
            service.tick()
        self.assertEqual(self.request_times, [0, 180])
        self.clock.seconds = 240
        service.tick()
        self.assertEqual(self.request_times, [0, 180, 240])

    def test_failure_cooldown_is_shared_and_symbol_switch_does_not_reset_it(self):
        service = self.service({"FPT": "HOSE"})
        service.watch("viewer", "HPG")
        service.tick()
        self.fetch.side_effect = RuntimeError("private upstream credential")
        self.clock.seconds = 5
        self.assertEqual(service.tick()["status"], "error")
        self.clock.seconds = 6
        service.watch("viewer", "VCB")
        with self.assertRaises(BusyError):
            service.refresh("MBB")
        self.clock.seconds = 9.999
        service.tick()
        self.assertEqual(self.fetch.call_count, 2)
        self.clock.seconds = 10
        self.assertEqual(service.tick()["status"], "error")
        service.unwatch("viewer")
        self.clock.seconds = 15
        with self.assertRaises(BusyError):
            service.history_for_refresh("VIC")
        with self.assertRaises(BusyError):
            service.capture_tracked()
        self.assertEqual(self.fetch.call_count, 3)
        self.manual.assert_not_called()
        self.history.assert_not_called()
        self.assertNotIn("private upstream", str(service.status()))
        self.assertEqual(service.read("HPG", 250)["bars"][0]["close"], "61")
        self.clock.seconds = 20
        service.refresh("MBB")
        self.assertEqual(self.manual.call_count, 1)
        with self.assertRaises(BusyError):
            service.history_for_refresh("VIC")

    def test_open_watched_manual_refresh_uses_cache_or_waits_without_hidden_call(self):
        service = self.service()
        service.watch("viewer", "FPT")
        with self.assertRaises(BusyError):
            service.refresh("FPT")
        self.fetch.assert_not_called()
        self.manual.assert_not_called()
        service.tick()
        self.assertEqual(service.refresh("FPT")["bars"][0]["close"], "61")
        self.clock.seconds = 61
        service.watch("viewer", "FPT")
        with self.assertRaises(BusyError):
            service.refresh("FPT")
        self.manual.assert_not_called()
        service.tick()
        self.assertEqual(service.refresh("FPT")["bars"][0]["close"], "61")
        self.assertEqual(self.fetch.call_count, 2)
        self.manual.assert_not_called()

    def test_history_defers_for_open_watchers_but_is_usable_outside_session(self):
        service = self.service()
        service.watch("viewer", "FPT")
        with self.assertRaises(BusyError):
            service.history_for_refresh("VCB")
        self.history.assert_not_called()
        service.tick()
        self.clock.seconds = 5
        with self.assertRaises(BusyError):
            service.history_for_refresh("VCB")
        self.history.assert_not_called()
        self.open = False
        self.assertEqual(service.history_for_refresh("VCB"), self.raw_history)
        self.history.assert_called_once_with("VCB")

    def test_raw_history_and_quotes_share_admission_without_normalizing_envelope(self):
        service = self.service({"FPT": "HOSE"})
        original = copy.deepcopy(self.raw_history)
        self.assertEqual(service.history_for_refresh("FPT"), original)
        self.assertEqual(self.raw_history, original)
        self.history.assert_called_once_with("FPT")
        self.clock.seconds = 1
        service.tick()
        self.fetch.assert_not_called()
        self.clock.seconds = 5
        self.assertEqual(service.tick()["status"], "ok")
        self.clock.seconds = 6
        with self.assertRaises(BusyError):
            service.history_for_refresh("VCB")
        self.assertEqual(self.history.call_count, 1)
        self.clock.seconds = 10
        self.assertEqual(service.history_for_refresh("VCB"), original)
        self.assertEqual(self.history.call_count, 2)
        self.manual.assert_not_called()

    def test_failed_history_keeps_common_spacing_and_cooldown_without_secret(self):
        service = self.service({"FPT": "HOSE"})
        self.history.side_effect = RuntimeError("private history credential")
        with self.assertRaises(RuntimeError) as error:
            service.history_for_refresh("FPT")
        self.assertNotIn("private history", str(error.exception))
        self.clock.seconds = 1
        service.tick()
        with self.assertRaises(BusyError):
            service.refresh("VCB")
        self.fetch.assert_not_called()
        self.manual.assert_not_called()
        self.assertEqual(self.history.call_count, 1)
        self.clock.seconds = 5
        self.assertEqual(service.tick()["status"], "ok")
        self.assertEqual(self.fetch.call_count, 1)

    def test_history_and_manual_refresh_obey_the_same_singleflight_lock(self):
        service = self.service({"FPT": "HOSE"})
        entered, release = threading.Event(), threading.Event()
        result, errors = [], []

        def delayed(symbol):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test release timed out")
            return self.raw_history

        def run_history():
            try:
                result.append(service.history_for_refresh("FPT"))
            except Exception as exc:
                errors.append(exc)

        self.history.side_effect = delayed
        worker = threading.Thread(target=run_history)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            self.clock.seconds = 5
            self.assertEqual(service.tick()["status"], "busy")
            with self.assertRaises(BusyError):
                service.refresh("VCB")
            self.fetch.assert_not_called()
            self.manual.assert_not_called()
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(result, [self.raw_history])

    def test_partial_background_reports_missing_even_when_old_overlay_exists(self):
        service = self.service(TRACKED)
        service.tick()
        self.clock.seconds = 60
        self.fetch.side_effect = lambda symbols: {
            "fetched_at": self.clock.now().isoformat(),
            "rows": [quote(symbol) for symbol in symbols if symbol != "VRE"],
        }
        self.assertEqual(service.tick()["accepted"], 29)
        self.assertEqual(service.status()["missing_tracked_symbols"], ["VRE"])
        self.assertEqual(len(service.read("VRE", 250)["bars"]), 1)
        self.clock.seconds = 65
        service.tick()
        self.assertEqual(self.fetch.call_count, 2)
        self.assertEqual(service.status()["missing_tracked_symbols"], ["VRE"])
        self.clock.seconds = 120
        self.fetch.side_effect = self.fetch_quotes
        self.assertEqual(service.tick()["accepted"], 30)
        self.assertEqual(service.status()["missing_tracked_symbols"], [])

    def test_closed_and_lunch_gates_do_not_consume_background_dispatch(self):
        service = self.service(TRACKED)
        self.open = False
        for second in (0, 60):
            self.clock.seconds = second
            self.assertEqual(service.tick()["status"], "idle")
        self.fetch.assert_not_called()
        self.clock.seconds = 90
        self.open = True
        service.tick()
        self.clock.seconds = 95
        service.tick()
        self.assertEqual(self.request_times, [90])
        self.clock.seconds = 150
        self.open = False
        service.tick()
        self.clock.seconds = 170
        self.open = True
        service.tick()
        self.assertEqual(self.request_times, [90, 170])

    def test_late_tracked_mapping_joins_the_next_background_batch(self):
        service = self.service({"FPT": "HOSE"})
        service.tick()
        self.clock.seconds = 30
        service.set_tracked_symbols({"FPT": "HOSE", "VCB": "HOSE"})
        self.clock.seconds = 60
        service.tick()
        self.assertEqual(self.fetch.call_args.args[0], ["FPT", "VCB"])
        self.assertEqual(service.status()["tracked_symbols"], ["FPT", "VCB"])

    def test_status_reports_background_period_and_monotonic_due_time(self):
        service = self.service({"FPT": "HOSE"})
        before = service.status()
        self.assertEqual(before["poll_seconds"], 5)
        self.assertEqual(before["background_seconds"], 60)
        self.assertEqual(before["background_due_in"], 0)
        service.tick()
        self.assertEqual(service.status()["background_due_in"], 60)
        self.clock.seconds = 59.999
        remaining = service.status()["background_due_in"]
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 1)
        self.clock.seconds = 60
        self.assertEqual(service.status()["background_due_in"], 0)
        service.tick()
        self.assertEqual(service.status()["background_due_in"], 60)

    def test_background_configuration_is_finite_and_not_faster_than_poll(self):
        self.assertEqual(self.service(background_seconds=60).status()["background_seconds"], 60)
        for value in (0, 4, float("nan"), float("inf"), True):
            with self.subTest(background_seconds=value), self.assertRaises(ValueError):
                self.service(background_seconds=value)
        with self.assertRaises(ValueError):
            self.service(poll_seconds=10, background_seconds=5)
        self.assertEqual(self.service(background_seconds=5).status()["background_seconds"], 5)

    def test_tracked_archive_and_price_provenance_remain_unchanged(self):
        service = self.service({"FPT": "HOSE"})
        service.watch("viewer", "HPG")
        payload = self.envelope(["FPT", "HPG"])
        payload["rows"][0]["raw_vendor_field"] = "keep-exactly"
        original = copy.deepcopy(payload)
        self.fetch.side_effect = lambda symbols: payload
        self.assertEqual(service.tick()["accepted"], 2)
        self.assertEqual(self.sink.call_count, 1)
        self.assertEqual(self.sink.call_args.args[0], {
            "symbol": "FPT", "fetched_at": payload["fetched_at"], "rows": [payload["rows"][0]],
        })
        bar = service.read("FPT", 250)["bars"][0]
        self.assertEqual({key: bar[key] for key in (
            "open", "high", "low", "close", "volume", "source", "status", "quality",
            "price_basis", "volume_basis",
        )}, {
            "open": "60", "high": "62", "low": "59", "close": "61", "volume": 100,
            "source": "vnstock_kbs", "status": "open", "quality": "complete",
            "price_basis": "unknown", "volume_basis": "unknown",
        })
        self.assertEqual(payload, original)
        self.assertEqual(self.saved, {})
        self.repo.runtime_write.assert_not_called()

    def test_sink_failure_is_reported_without_delaying_next_watched_batch(self):
        service = self.service({"FPT": "HOSE"})
        service.watch("viewer", "FPT")
        self.sink.side_effect = OSError("private disk detail")
        self.assertEqual(service.tick()["status"], "ok")
        self.assertTrue(service.status()["persistence_error"])
        self.assertNotIn("private disk", str(service.status()))
        self.clock.seconds = 5
        self.assertEqual(service.tick()["status"], "ok")
        self.assertEqual(self.fetch.call_count, 2)

    def test_incompatible_saved_source_is_not_replaced_or_archived(self):
        self.saved["FPT"] = {
            "symbol": "FPT", "interval": "1D", "source": "ENTRADE", "fetched_at": None,
            "bars": [{"date": "2026-10-08", "open": "60", "high": "62", "low": "59",
                      "close": "60.5", "volume": 50, "source": "ENTRADE",
                      "price_basis": "unknown", "volume_basis": "unknown"}],
        }
        original = copy.deepcopy(self.saved)
        service = self.service({"FPT": "HOSE"})
        self.assertEqual(service.tick()["status"], "error")
        self.assertEqual(service.read("FPT", 250)["source"], "ENTRADE")
        self.assertEqual(service.read("FPT", 250)["bars"], original["FPT"]["bars"])
        self.sink.assert_not_called()
        self.assertEqual(self.saved, original)


if __name__ == "__main__":
    unittest.main()
