"""Collection cutoff tests with the real read-only calendar and a fake quote source."""
from datetime import datetime
from pathlib import Path
import unittest
from unittest.mock import Mock

from backend.src.market_data.session import SessionGate
from backend.src.market_data.live import LiveCoordinator

ROOT = Path(__file__).resolve().parents[2]


class SessionTests(unittest.TestCase):
    def gate(self, stamp):
        return SessionGate(ROOT, now=lambda: datetime.fromisoformat(stamp))

    def test_all_exchanges_collect_until_1501(self):
        for exchange in ("HOSE", "HNX", "UPCOM"):
            for clock, expected in (("14:45:00", True), ("14:50:00", True),
                                    ("15:00:00", True), ("15:00:59", True),
                                    ("15:01:00", False), ("15:10:00", False)):
                with self.subTest(exchange=exchange, clock=clock):
                    self.assertEqual(self.gate(f"2026-10-12T{clock}+07:00")(exchange), expected)

    def test_calendar_and_lunch_remain_closed(self):
        for stamp in ("2026-10-12T08:59:00+07:00", "2026-10-12T11:30:00+07:00",
                      "2026-10-12T12:30:00+07:00", "2026-10-11T14:50:00+07:00",
                      "2026-01-01T14:50:00+07:00", "2027-10-12T14:50:00+07:00"):
            for exchange in ("HOSE", "HNX", "UPCOM"):
                with self.subTest(stamp=stamp, exchange=exchange):
                    self.assertFalse(self.gate(stamp)(exchange))
        self.assertTrue(self.gate("2026-10-12T10:00:00+07:00")("HOSE"))
        self.assertTrue(self.gate("2026-10-12T13:00:00+07:00")("HOSE"))

    def test_timezone_uses_vietnam_clock(self):
        self.assertTrue(self.gate("2026-10-12T08:00:59+00:00")("HOSE"))
        self.assertFalse(self.gate("2026-10-12T08:01:00+00:00")("HOSE"))

    def test_unknown_exchange_and_missing_calendar_fail_closed(self):
        gate = self.gate("2026-10-12T14:50:00+07:00")
        self.assertFalse(gate("INVALID"))
        gate.calendar = None
        self.assertFalse(gate("HOSE"))

    def test_closed_and_special_override_not_extended(self):
        gate = self.gate("2026-10-12T14:50:00+07:00")
        calendar_type = type(gate.calendar)
        for sessions in ([], [{"start": "09:00", "end": "11:30", "phase": "continuous"}],
                         [{"start": "09:00", "end": "14:45", "phase": "halted"}]):
            gate.calendar = calendar_type.from_dict({"version": 1, "coverage_start": "2026-10-12",
                "coverage_end": "2026-10-12", "working_dates": ["2026-10-12"], "source": "test fixture",
                "overrides": {"2026-10-12": {"HOSE": sessions}}})
            self.assertFalse(gate("HOSE"))

    def test_collector_updates_quote_after_1445_and_stops_at_1501(self):
        now = datetime.fromisoformat("2026-10-12T14:50:00+07:00")
        elapsed = 0
        gate = SessionGate(ROOT, now=lambda: now)
        repo = Mock()
        repo.get_ohlcv.return_value = {"symbol": "MSN", "bars": []}
        fetch = Mock(side_effect=lambda _: {"fetched_at": now.isoformat(), "rows": [{
            "symbol": "MSN", "exchange": "HOSE", "TD": "12/10/2026", "open_price": "74400",
            "high_price": "74500", "low_price": "73000", "close_price": "73100", "volume_accumulated": 100}]})
        collector = LiveCoordinator(fetch, gate, repo, now=lambda: now, clock=lambda: elapsed)
        collector.watch("test", "MSN")
        self.assertEqual(collector.tick()["status"], "ok")
        self.assertEqual(collector.read("MSN", 250)["bars"][-1]["close"], "73.1")
        now = datetime.fromisoformat("2026-10-12T15:01:00+07:00")
        elapsed = 5
        self.assertEqual(collector.tick()["status"], "idle")
        self.assertEqual(fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
