"""Trend labels from stored daily prices: fixed rules, exact decimals, never a guessed label."""
from datetime import date, timedelta
from decimal import Decimal
import unittest

from backend.src.market_data.trend import analyze_trend, trend_passage


def weekdays(start, count):
    days, day = [], start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def series(closes, start=date(2025, 1, 2)):
    rows = []
    for day, close in zip(weekdays(start, len(closes)), closes):
        close = Decimal(close).quantize(Decimal(".0001"))
        rows.append({"trade_date": day, "open": close, "high": close * Decimal("1.01"), "low": close * Decimal("0.99"),
                     "close": close, "volume": 1000, "price_scale": 1000, "is_adjusted": False,
                     "source_name": "ENTRADE", "source_id": "s1", "approval_status": "PENDING"})
    return rows


def geometric(count, step, start=Decimal(100)):
    values, value = [], start
    for _ in range(count):
        values.append(value)
        value *= Decimal(1) + Decimal(step)
    return values


def index_for(rows, level=Decimal(1000)):
    return [{"trade_date": row["trade_date"], "close": level + i} for i, row in enumerate(rows)]


def trend(rows, index=None, rsi14=None):
    return analyze_trend(rows, index_for(rows) if index is None else index, exchange="HOSE", rsi14=rsi14)


class TrendLabelTests(unittest.TestCase):
    def test_rising_series_is_up_on_all_horizons(self):
        out = trend(series(geometric(260, "0.003")))
        for h in ("20", "60", "200"):
            self.assertEqual(out["horizons"][h]["label"], "UP", h)
            self.assertTrue({"close_above_sma", "sma_rising", "positive_return"} <= set(out["horizons"][h]["reasons"]))
        self.assertEqual(out["as_of"], series(geometric(260, "0.003"))[-1]["trade_date"].isoformat())

    def test_falling_series_is_down(self):
        out = trend(series(geometric(260, "-0.003")))
        self.assertEqual({h: v["label"] for h, v in out["horizons"].items()}, {"20": "DOWN", "60": "DOWN", "200": "DOWN"})

    def test_flat_band_is_sideways(self):
        out = trend(series([100, 102, 100, 98] * 65))
        self.assertEqual(out["horizons"]["20"]["label"], "SIDEWAYS")
        self.assertIn("narrow_range", out["horizons"]["20"]["reasons"])

    def test_mixed_signals_is_unclear(self):
        closes = geometric(257, "0.005")
        for _ in range(3):
            closes.append(closes[-1] * Decimal("0.97"))
        out = trend(series(closes))
        self.assertEqual(out["horizons"]["20"]["label"], "UNCLEAR")
        self.assertIn("mixed_signals", out["horizons"]["20"]["reasons"])

    def test_insufficient_sessions_boundary(self):
        short = trend(series(geometric(24, "0.003")))["horizons"]
        self.assertEqual(short["20"]["label"], "INSUFFICIENT_DATA")
        self.assertEqual(short["20"]["reasons"], ["not_enough_sessions"])
        self.assertIsNone(short["20"]["return_percent"])
        self.assertNotEqual(trend(series(geometric(25, "0.003")))["horizons"]["20"]["label"], "INSUFFICIENT_DATA")

    def test_corporate_action_day_forces_unclear(self):
        closes = geometric(260, "0.003")
        closes[-5:] = [value * Decimal("0.8") for value in closes[-5:]]
        rows = series(closes)
        out = trend(rows)
        flag = f"possible_corporate_action:{rows[-5]['trade_date'].isoformat()}"
        for h in ("20", "60", "200"):
            self.assertEqual(out["horizons"][h]["label"], "UNCLEAR")
            self.assertIn(flag, out["horizons"][h]["reasons"])
        self.assertIsNone(out["context"]["high_52w"])
        self.assertIn(flag, out["warnings"])

    def test_limit_move_within_band_is_not_flagged(self):
        closes = geometric(260, "0.003")
        closes[-5:] = [value * Decimal("0.93") for value in closes[-5:]]
        out = trend(series(closes))
        self.assertFalse(any(r.startswith("possible_corporate_action") for r in out["horizons"]["20"]["reasons"]))

    def test_corporate_action_at_first_52w_row_keeps_context(self):
        rows = series([200] * 10 + [100] * 250)
        out = trend(rows, rsi14=Decimal("45.1234"))
        self.assertEqual(out["context"], {
            "high_52w": "101.0000", "high_52w_date": rows[-1]["trade_date"].isoformat(),
            "low_52w": "99.0000", "low_52w_date": rows[-1]["trade_date"].isoformat(),
            "from_high_percent": "-0.9901", "from_low_percent": "1.0101",
            "rsi14": "45.1234", "volume20_vs_volume60": "1.0000",
        })
        self.assertFalse(any(reason.startswith("possible_corporate_action:") for reason in out["warnings"]))

    def test_corporate_action_just_inside_52w_window_suppresses_context(self):
        rows = series([200] * 11 + [100] * 249)
        out = trend(rows, rsi14=Decimal("45.1234"))
        for field in ("high_52w", "high_52w_date", "low_52w", "low_52w_date",
                      "from_high_percent", "from_low_percent"):
            self.assertIsNone(out["context"][field], field)
        self.assertEqual(out["context"]["rsi14"], "45.1234")
        self.assertEqual(out["context"]["volume20_vs_volume60"], "1.0000")
        self.assertIn(f"possible_corporate_action:{rows[11]['trade_date'].isoformat()}", out["warnings"])

    def test_corporate_action_hides_distorted_returns_and_ranges_without_changing_reasons(self):
        rows = series([100] * 255 + [80] * 5)
        out = trend(rows)
        flag = f"possible_corporate_action:{rows[-5]['trade_date'].isoformat()}"
        expected_reasons = {
            "20": [flag, "close_below_sma", "sma_falling", "negative_return"],
            "60": [flag, "close_below_sma", "sma_falling", "negative_return"],
            "200": [flag, "close_below_sma", "sma_flat", "negative_return", "narrow_range"],
        }
        for h, reasons in expected_reasons.items():
            with self.subTest(horizon=h):
                item = out["horizons"][h]
                self.assertEqual(item["label"], "UNCLEAR")
                self.assertIsNone(item["return_percent"])
                self.assertIsNone(item["range_percent"])
                self.assertEqual(item["reasons"], reasons)

    def test_corporate_action_keeps_unaffected_horizon_metrics(self):
        out = trend(series([100] * 220 + [80] * 40))
        unaffected = trend(series([80] * 260))["horizons"]["20"]
        self.assertEqual(out["horizons"]["20"], unaffected)
        self.assertEqual(unaffected["return_percent"], "0.0000")
        self.assertEqual(unaffected["range_percent"], "2.0202")
        for h in ("60", "200"):
            self.assertEqual(out["horizons"][h]["label"], "UNCLEAR")
            self.assertIsNone(out["horizons"][h]["return_percent"])
            self.assertIsNone(out["horizons"][h]["range_percent"])

    def test_index_comparison_uses_stock_dates_only(self):
        rows = series(geometric(260, "0.003"))
        full = trend(rows)["horizons"]["20"]
        self.assertEqual(full["index_return_percent"], "1.6142")  # (1259 - 1239) / 1239
        index = index_for(rows)
        del index[-3]
        gap = trend(rows, index)["horizons"]["20"]
        self.assertIsNone(gap["index_return_percent"])
        self.assertIn("index_not_enough_sessions", gap["reasons"])

    def test_malformed_index_row_is_one_missing_day(self):
        rows = series(geometric(260, "0.003"))
        index = index_for(rows)
        invalid_at = len(rows) - 100
        full = trend(rows, index, rsi14=Decimal("45.1234"))
        missing = trend(rows, index[:invalid_at] + index[invalid_at + 1:], rsi14=Decimal("45.1234"))
        self.assertIsNone(missing["horizons"]["200"]["index_return_percent"])
        self.assertIn("index_not_enough_sessions", missing["horizons"]["200"]["reasons"])
        self.assertEqual(missing["context"], full["context"])
        for h in ("20", "60"):
            self.assertEqual(missing["horizons"][h], full["horizons"][h])
        for fields in ({"close": "invalid"}, {"close": None}, {"close": "NaN"}, {"close": 1.0},
                       {"trade_date": "invalid"}, {"date": rows[invalid_at + 1]["trade_date"]}):
            with self.subTest(fields=fields):
                malformed = index[:]
                malformed[invalid_at] = {**index[invalid_at], **fields}
                self.assertEqual(trend(rows, malformed, rsi14=Decimal("45.1234")), missing)

    def test_rsi_and_context_numbers(self):
        rows = series([100] * 230 + [106] + [103] * 29)  # +6% stays inside the HOSE band
        out = trend(rows, rsi14=Decimal("45.1234"))
        context = out["context"]
        self.assertEqual(context["rsi14"], "45.1234")
        self.assertEqual((context["high_52w"], context["high_52w_date"]), ("107.0600", rows[230]["trade_date"].isoformat()))
        self.assertEqual(context["low_52w"], "99.0000")
        self.assertEqual(context["volume20_vs_volume60"], "1.0000")
        self.assertEqual(out["source"], {"name": "ENTRADE", "approval_status": "PENDING", "is_adjusted": False,
                                         "price_scale": 1000})
        self.assertIn("unadjusted_prices", out["warnings"])
        self.assertEqual(out["benchmark"], "VNINDEX")

    def test_inconsistent_input_is_rejected(self):
        rows = series(geometric(30, "0.003"))
        for broken in (rows + [dict(rows[-1])], rows[:-1] + [{**rows[-1], "source_name": "KBS"}]):
            with self.assertRaises(ValueError):
                trend(broken)
        with self.assertRaises(ValueError):
            analyze_trend(rows, [], exchange="NYSE", rsi14=None)

    def test_passage_states_labels_and_disclaimer(self):
        out = trend(series(geometric(260, "0.003")))
        text = trend_passage("FPT", out)
        self.assertIn("Ngắn hạn: Tăng", text)
        self.assertIn(out["as_of"], text)
        self.assertIn("chưa điều chỉnh", text)
        self.assertIn("không phải khuyến nghị", text)

    def test_passage_explains_each_label_from_its_rule(self):
        # The chatbot may only explain a label with reasons that are written in the evidence.
        out = trend(series(geometric(260, "0.003")))
        text = trend_passage("FPT", out)
        short = next(line for line in text.splitlines() if line.startswith("- Ngắn hạn"))
        self.assertIn("Lý do: giá trên SMA20, SMA20 dốc lên hơn 1%, lợi suất dương.", short)
        mixed = dict(out["horizons"]["20"], label="UNCLEAR",
                     reasons=["close_above_sma", "sma_falling", "positive_return", "mixed_signals"])
        out["horizons"]["20"] = mixed
        short = next(line for line in trend_passage("FPT", out).splitlines() if line.startswith("- Ngắn hạn"))
        self.assertIn("Lý do: tín hiệu trái chiều (giá trên SMA20, SMA20 dốc xuống hơn 1%, lợi suất dương).", short)

    def test_passage_numbers_use_two_decimals_with_comma(self):
        out = trend(series(geometric(260, "0.003")))
        out["horizons"]["20"]["return_percent"] = "-14.5690"
        text = trend_passage("FPT", out)
        self.assertIn("Lợi suất -14,57%", text)
        self.assertNotIn("-14.5690", text)


    def test_passage_orders_horizons_by_sessions(self):
        out = trend(series(geometric(260, "0.003")))
        out["horizons"] = {h: out["horizons"][h] for h in ("200", "20", "60")}
        text = trend_passage("FPT", out)
        self.assertLess(text.index("(20 phiên)."), text.index("(60 phiên)."))
        self.assertLess(text.index("(60 phiên)."), text.index("(200 phiên)."))


if __name__ == "__main__":
    unittest.main()
