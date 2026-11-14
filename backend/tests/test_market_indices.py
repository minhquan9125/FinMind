import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from backend.src.market_data.history import normalize_index_history
from backend.src.market_data.live import LiveCoordinator, BusyError


def snapshot():
    return {"fetched_at": "2026-10-08T14:00:00+07:00", "rows": [{
        "time": "2026-10-08T07:00:00", "open": "1700", "high": "1720",
        "low": "1690", "close": "1710.5", "volume": 100}]}


class IndexTests(unittest.TestCase):
    def test_points_preserved_and_invalid_rows_rejected(self):
        result = normalize_index_history("VNINDEX", snapshot())
        self.assertEqual(result["bars"][0]["close"], "1710.5")
        for field, value in [("close", "NaN"), ("close", "1800"), ("volume", True)]:
            data = snapshot()
            data["rows"][0][field] = value
            with self.assertRaises(ValueError):
                normalize_index_history("VNINDEX", data)

    def test_normalize_accepts_longer_window(self):
        data = snapshot()
        data["rows"][0]["time"] = "2025-09-13T07:00:00"  # 390 days before fetched_at
        with self.assertRaises(ValueError):
            normalize_index_history("VNINDEX", data)
        result = normalize_index_history("VNINDEX", data, max_age_days=400)
        self.assertEqual(result["bars"][0]["date"], "2025-09-13")

    def test_explicit_history_uses_same_budget_and_cache_as_live(self):
        seconds = [0]
        fetch = Mock(return_value=snapshot())
        service = LiveCoordinator(Mock(), lambda _: False, Mock(), history_fetch=fetch,
                                  clock=lambda: seconds[0])
        self.assertEqual(service.index_history("HNXINDEX")["symbol"], "HNXINDEX")
        service.index_history("HNXINDEX")
        fetch.assert_called_once_with("HNXINDEX")
        with self.assertRaises(BusyError):
            service.index_history("UPCOMINDEX")
        with self.assertRaises(ValueError):
            service.index_history("../FPT")
        seconds[0] = 61
        service.index_history("HNXINDEX")
        self.assertEqual(fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
