"""Daily refresh planning: only closed sessions after the stored series, never a silent mismatch."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import unittest

from backend.scripts.refresh_market_prices import (DAILY_INDEXES, closed_through, drop_ambiguous_days, entrade_rows,
                                             fetch_index, is_busy, plan_daily_index, plan_index, plan_index_backfill,
                                             plan_index_or_block)

VN = timezone(timedelta(hours=7))
BASIS = {"source_name": "ENTRADE", "source_id": "s1", "price_scale": 1000, "is_adjusted": False}


def stamp(day, hour=9):
    return int(datetime(2026, 11, day, hour, tzinfo=VN).timestamp())


def entrade(bars):
    """bars: (timestamp, open, high, low, close, volume)"""
    return json.dumps(dict(zip("tohlcv", map(list, zip(*bars))))).encode()


def rows(raw, stored_days=(9, 10), through=11):
    return entrade_rows("FPT", raw, BASIS, {date(2026, 11, d) for d in stored_days},
                        date(2026, 11, 1), date(2026, 11, through), "https://example.invalid")


def index_row(day, close="1700.5", volume=10):
    return {"trade_date": date(2026, 11, day), "open": Decimal("1700"), "high": Decimal("1710"),
            "low": Decimal("1690"), "close": Decimal(close), "volume": volume, "source_name": "vnstock_kbs"}


def index_bar(day, close="1700.5", volume=10):
    return {"date": f"2026-11-{day:02d}", "open": "1700", "high": "1710", "low": "1690", "close": close, "volume": volume}


class RefreshPlanningTests(unittest.TestCase):
    def test_today_is_final_only_after_the_close(self):
        self.assertEqual(closed_through(datetime(2026, 11, 12, 15, 29, tzinfo=VN)), date(2026, 11, 11))
        self.assertEqual(closed_through(datetime(2026, 11, 12, 15, 30, tzinfo=VN)), date(2026, 11, 12))
        # 08:30 UTC is 15:30 in Vietnam.
        self.assertEqual(closed_through(datetime(2026, 11, 12, 8, 30, tzinfo=timezone.utc)), date(2026, 11, 12))

    def test_rows_keep_the_stored_basis_and_drop_the_provisional_day(self):
        raw = entrade([(stamp(10), 51.6, 52.5, 50.9, 50.9, 7268500), (stamp(11), 51.0, 51.1, 50.2, 50.9, 6533000),
                       (stamp(11, 15), 51.0, 51.2, 50.2, 51.0, 6600000), (stamp(12), 51.0, 51.5, 50.8, 51.2, 100)])
        out = rows(raw)
        self.assertEqual([row["trade_date"] for row in out], ["2026-11-10", "2026-11-11"])
        # The later timestamp of the same day wins; 12/11 is still trading and is left out.
        self.assertEqual((out[1]["high"], out[1]["close"], out[1]["volume"]), ("51.2000", "51.0000", 6600000))
        self.assertEqual({key: out[0][key] for key in BASIS}, BASIS)

    def test_a_bad_new_or_stored_bar_stops_the_run_but_an_already_absent_one_is_skipped(self):
        good = (stamp(10), 51.6, 52.5, 50.9, 50.9, 7268500)
        bad = lambda day: (stamp(day), 51.0, 50.0, 52.0, 51.0, 5)  # high below low
        self.assertEqual(len(rows(entrade([bad(6), good]))), 1)
        for day in (9, 11):
            with self.assertRaises(ValueError):
                rows(entrade([good, bad(day)]))
        with self.assertRaises(ValueError):
            rows(json.dumps({"t": [], "o": [], "h": [], "l": [], "c": [], "v": []}).encode())

    def test_index_appends_only_closed_days_after_a_matching_stored_series(self):
        stored, offered = [index_row(10), index_row(11)], [index_bar(d) for d in (10, 11, 12, 13)]
        self.assertEqual([bar["date"] for bar in plan_index(stored, offered, date(2026, 11, 12))], ["2026-11-12"])
        self.assertEqual(plan_index(stored, offered[:2], date(2026, 11, 12)), [])
        for broken in ([index_bar(10), index_bar(11, close="1701")], [index_bar(10), index_bar(11, volume=11)],
                       [index_bar(12)]):
            with self.assertRaises(ValueError):
                plan_index(stored, broken, date(2026, 11, 12))
        with self.assertRaises(ValueError):
            plan_index([{**index_row(11), "source_name": "other"}], offered, date(2026, 11, 12))
        with self.assertRaises(ValueError):
            plan_index([], offered, date(2026, 11, 12))


class DailyIndexBlockTests(unittest.TestCase):
    def test_index_disagreement_blocks_the_index_not_the_daily_refresh(self):
        stored = [index_row(10), index_row(11, volume=99)]
        rows, reason = plan_index_or_block(stored, [index_bar(d) for d in (10, 11, 12)], date(2026, 11, 12))
        self.assertEqual(rows, [])
        self.assertIn("2026-11-11", reason)
        rows, reason = plan_index_or_block([index_row(10), index_row(11)], [index_bar(d) for d in (10, 11, 12)],
                                           date(2026, 11, 12))
        self.assertEqual(([bar["date"] for bar in rows], reason), (["2026-11-12"], None))


class DailyIndexesTests(unittest.TestCase):
    def test_daily_refresh_covers_all_three_indexes(self):
        self.assertEqual(DAILY_INDEXES, ("VNINDEX", "HNXINDEX", "UPCOMINDEX"))

    def test_plan_index_names_the_index_it_refuses(self):
        with self.assertRaisesRegex(ValueError, "HNXINDEX"):
            plan_index([{**index_row(10), "source_name": "other"}], [index_bar(10)], date(2026, 11, 12), symbol="HNXINDEX")

    def test_index_fetch_waits_out_the_shared_quota(self):
        from backend.src.market_data.live import BusyError
        calls, waits = [], []

        def history(symbol):
            calls.append(symbol)
            if len(calls) == 1:
                raise BusyError(3)
            return {"rows": []}

        async def sleep(seconds):
            waits.append(seconds)

        self.assertEqual(asyncio.run(fetch_index(history, "HNXINDEX", sleep=sleep)), {"rows": []})
        self.assertEqual((calls, len(waits)), (["HNXINDEX", "HNXINDEX"], 1))
        self.assertGreaterEqual(waits[0], 3)

        def always_busy(symbol):
            raise BusyError(1)
        with self.assertRaises(BusyError):
            asyncio.run(fetch_index(always_busy, "VNINDEX", sleep=sleep))

    def test_busy_from_the_backend_import_path_is_recognised(self):
        # The backend runs as `src.market_data...`; its BusyError is a different class from `backend.src...`.
        class BusyError(RuntimeError):
            def __init__(self, wait_seconds=5):
                self.wait_seconds = wait_seconds
        calls = []

        def history(symbol):
            calls.append(symbol)
            if len(calls) == 1:
                raise BusyError(1)
            return {"rows": []}

        async def sleep(seconds):
            pass

        self.assertEqual(asyncio.run(fetch_index(history, "HNXINDEX", sleep=sleep)), {"rows": []})
        self.assertTrue(is_busy(BusyError(2)))
        self.assertFalse(is_busy(RuntimeError("other")))


class IndexBackfillPlanningTests(unittest.TestCase):
    def test_backfill_prepends_only_older_days(self):
        stored = [index_row(10), index_row(11)]
        offered = [index_bar(d) for d in (6, 9, 10, 11)]
        plan = plan_index_backfill("VNINDEX", stored, offered)
        self.assertEqual([bar["date"] for bar in plan["rows"]], ["2026-11-06", "2026-11-09"])
        self.assertEqual((plan["matched_overlap"], plan["initial_load"]), (2, False))

    def test_backfill_rejects_mismatch_and_unanchored_series(self):
        stored = [index_row(10), index_row(11)]
        for offered in ([index_bar(9), index_bar(10, close="1701"), index_bar(11)],
                        [index_bar(d) for d in (3, 4, 5)]):
            with self.assertRaises(ValueError):
                plan_index_backfill("VNINDEX", stored, offered)
        with self.assertRaises(ValueError):
            plan_index_backfill("VNINDEX", [{**index_row(10), "source_name": "other"}], [index_bar(9), index_bar(10)])

    def test_backfill_also_catches_up_closed_days_after_the_last_stored(self):
        stored = [index_row(9), index_row(10)]
        offered = [index_bar(d) for d in (6, 9, 10, 11, 12)]
        plan = plan_index_backfill("HNXINDEX", stored, offered, through=date(2026, 11, 11))
        self.assertEqual([bar["date"] for bar in plan["rows"]], ["2026-11-06", "2026-11-11"])

    def test_a_mismatch_blocks_only_the_edge_it_touches(self):
        stored = [index_row(d) for d in (3, 4, 5)] + [index_row(6, close="1699")]
        offered = [index_bar(d) for d in (2, 3, 4, 5, 6, 9)]
        plan = plan_index_backfill("VNINDEX", stored, offered, through=date(2026, 11, 9), anchor=2)
        self.assertEqual([bar["date"] for bar in plan["rows"]], ["2026-11-02"])
        self.assertEqual((plan["mismatched_days"], plan["blocked_edges"]), (["2026-11-06"], ["after"]))

    def test_ambiguous_source_days_are_dropped_not_guessed(self):
        raw = {"fetched_at": "2026-11-12T08:00:00+07:00", "rows": [
            {"time": "2026-11-10T07:00:00.000", "close": "1"}, {"time": "2026-11-11T07:00:00.000", "close": "2"},
            {"time": "2026-11-11T07:00:00.000", "close": "3"}]}
        clean, dropped = drop_ambiguous_days(raw)
        self.assertEqual(([row["close"] for row in clean["rows"]], dropped), (["1"], ["2026-11-11"]))
        self.assertEqual(len(raw["rows"]), 3)

    def test_backfill_initial_load_when_nothing_stored(self):
        offered = [index_bar(d) for d in (9, 10)]
        plan = plan_index_backfill("HNXINDEX", [], offered)
        self.assertEqual((plan["rows"], plan["initial_load"], plan["matched_overlap"]), (offered, True, 0))


if __name__ == "__main__":
    unittest.main()


class ReviewFixTests(unittest.TestCase):
    """Findings of the 12/11 independent review, each reproduced before the fix."""

    def test_an_ambiguous_day_stops_the_append_instead_of_leaving_a_hole(self):
        stored = [index_row(9), index_row(10)]
        offered = [index_bar(d) for d in (9, 10, 12)]
        rows = plan_index(stored, offered, date(2026, 11, 12), ambiguous=["2026-11-11"])
        self.assertEqual(rows, [])
        rows = plan_index(stored, offered, date(2026, 11, 12), ambiguous=["2026-11-03"])
        self.assertEqual([bar["date"] for bar in rows], ["2026-11-12"])

    def test_one_bad_index_payload_blocks_only_that_index(self):
        import tempfile
        from pathlib import Path
        good = {"fetched_at": "2026-11-12T16:00:00+07:00",
                "rows": [{"time": f"2026-11-{d:02d}T07:00:00.000", "open": "1700", "high": "1710", "low": "1690",
                          "close": "1700.5", "volume": 10} for d in (10, 11, 12)]}
        bad = {**good, "rows": [{**good["rows"][0], "close": "0"}]}
        stored = [index_row(10), index_row(11)]

        class Busy(RuntimeError):
            wait_seconds = 1

        def busy(symbol):
            raise type("BusyError", (Busy,), {})()

        async def no_sleep(seconds):
            pass

        with tempfile.TemporaryDirectory() as folder:
            run = lambda history: asyncio.run(plan_daily_index(history, "UPCOMINDEX", stored, date(2026, 11, 12),
                                                                Path(folder), sleep=no_sleep))
            rows, info = run(lambda symbol: good)
            self.assertEqual(([bar["date"] for bar in rows], info["blocked"]), (["2026-11-12"], None))
            for history in (lambda symbol: bad, lambda symbol: (_ for _ in ()).throw(RuntimeError("sdk down"))):
                rows, info = run(history)
                self.assertEqual(rows, [])
                self.assertTrue(info["blocked"])
            rows, info = run(busy)
            self.assertEqual((rows, info.get("deferred")), ([], "sdk_busy"))

    def test_the_run_report_reaches_the_caller_even_when_the_run_fails(self):
        import backend.scripts.refresh_market_prices as refresh
        from types import SimpleNamespace
        from unittest.mock import patch
        import asyncpg
        seen = []

        async def refuse(*args, **kwargs):
            raise OSError("database unreachable")

        with patch.object(refresh, "get_settings", lambda: SimpleNamespace(database_url="postgresql://x@127.0.0.1:1/x")), \
             patch.object(asyncpg, "connect", refuse):
            code = asyncio.run(refresh.run(False, index_history=lambda symbol: {}, symbols=["FPT"], on_report=seen.append))
        self.assertEqual(code, 1)
        self.assertEqual(seen[0]["failure_class"], "OSError")
