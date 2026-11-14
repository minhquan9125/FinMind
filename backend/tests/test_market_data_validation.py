import unittest
from datetime import date
from backend.src.market_data.validation import normalize_quote

# Fixed context for all tests
TODAY = date(2026, 10, 8)
FETCHED_AT = "2026-10-08T10:00:00+07:00"

def base_row():
    """A minimal, valid KBS row."""
    return {
        "symbol": "FPT",
        "exchange": "HOSE",
        "TD": "08/10/2026",
        "open_price": "60000",
        "high_price": "62000",
        "low_price": "59000",
        "close_price": "61000",
        "volume_accumulated": 100,
    }

class TestNormalizeQuote(unittest.TestCase):
    # --------------------------------------------------------------------- #
    #  Valid happy‑path
    # --------------------------------------------------------------------- #
    def test_valid_row_returns_expected_structure(self):
        row = base_row()
        out = normalize_quote(
            row,
            FETCHED_AT,
            today=TODAY,
            automatic=True,
        )
        # check immutable input
        self.assertEqual(row, base_row())
        # basic keys
        self.assertCountEqual(
            out.keys(),
            {
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "status",
                "quality",
                "price_basis",
                "volume_basis",
                "source",
            },
        )
        # values
        self.assertEqual(out["date"], "2026-10-08")
        self.assertEqual(out["status"], "open")
        self.assertEqual(out["price_basis"], "unknown")
        self.assertEqual(out["volume_basis"], "unknown")
        self.assertEqual(out["source"], "vnstock_kbs")
        # price strings are divided by 1000
        self.assertEqual(out["open"], "60")
        self.assertEqual(out["high"], "62")
        self.assertEqual(out["low"], "59")
        self.assertEqual(out["close"], "61")
        self.assertEqual(out["volume"], 100)

    # --------------------------------------------------------------------- #
    #  Simple field validation (table‑driven)
    # --------------------------------------------------------------------- #
    def test_invalid_fields_raise(self):
        cases = [
            ("open_price", "1e999999999", "Bảng điện thiếu trường hoặc sai kiểu dữ liệu."),
            ("open_price", False, "Giá phải là"),
            ("close_price", 61000.0, "Giá phải là"),
            ("volume_accumulated", True, "Khối lượng giao dịch không hợp lệ."),
            ("volume_accumulated", 100.1, "Khối lượng giao dịch không hợp lệ."),
            ("volume_accumulated", "100", "Khối lượng giao dịch không hợp lệ."),
            ("volume_accumulated", 0, "Khối lượng giao dịch không hợp lệ."),
            ("symbol", "FPT1", "Mã cổ phiếu không hợp lệ."),
            ("exchange", "NYSE", "Sàn không hợp lệ."),
            ("TD", "2026-10-08", "Ngày bảng điện không hợp lệ."),
            ("open_price", "-1000", "Giá phải dương và hữu hạn."),
            ("high_price", "nan", "Giá phải dương và hữu hạn."),
            ("low_price", "inf", "Giá phải dương và hữu hạn."),
            ("close_price", "0", "Giá phải dương và hữu hạn."),
            ("volume_accumulated", -5, "Khối lượng giao dịch không hợp lệ."),
            ("volume_accumulated", 1 << 63, "Khối lượng giao dịch không hợp lệ."),
        ]
        for field, bad, msg in cases:
            with self.subTest(field=field, bad=bad):
                row = base_row()
                row[field] = bad
                with self.assertRaisesRegex(ValueError, msg):
                    normalize_quote(
                        row,
                        FETCHED_AT,
                        today=TODAY,
                        automatic=False,
                    )

    # --------------------------------------------------------------------- #
    #  OHLC relationship checks
    # --------------------------------------------------------------------- #
    def test_ohlc_relation_errors(self):
        # low > open
        row = base_row()
        row["low_price"] = "63000"
        with self.assertRaisesRegex(ValueError, "Quan hệ OHLC không hợp lệ."):
            normalize_quote(row, FETCHED_AT, today=TODAY, automatic=False)

        # open > high
        row = base_row()
        row["high_price"] = "59000"
        with self.assertRaisesRegex(ValueError, "Quan hệ OHLC không hợp lệ."):
            normalize_quote(row, FETCHED_AT, today=TODAY, automatic=False)

        # close outside range
        row = base_row()
        row["close_price"] = "63000"
        with self.assertRaisesRegex(ValueError, "Quan hệ OHLC không hợp lệ."):
            normalize_quote(row, FETCHED_AT, today=TODAY, automatic=False)

    # --------------------------------------------------------------------- #
    #  Date & fetch‑time validation
    # --------------------------------------------------------------------- #
    def test_date_and_fetched_at_errors(self):
        # fetched_at with missing tz
        with self.assertRaisesRegex(ValueError, "Thời điểm lấy giá không hợp lệ."):
            normalize_quote(
                base_row(),
                "2026-10-08T10:00:00",
                today=TODAY,
                automatic=False,
            )
        # day in future
        row = base_row()
        row["TD"] = "09/10/2026"
        with self.assertRaisesRegex(ValueError, "Ngày giá không khớp phiên."):
            normalize_quote(row, FETCHED_AT, today=TODAY, automatic=False)

        # automatic mode but row day != today
        row = base_row()
        row["TD"] = "07/10/2026"
        with self.assertRaisesRegex(ValueError, "Ngày giá không khớp phiên."):
            normalize_quote(row, FETCHED_AT, today=TODAY, automatic=True)

    # --------------------------------------------------------------------- #
    #  Previous‑row consistency checks
    # --------------------------------------------------------------------- #
    def test_previous_row_errors(self):
        prev = {
            "date": "2026-10-08",
            "source": "vnstock_kbs",
            "price_basis": "unknown",
            "volume_basis": "unknown",
            "status": "open",
            "volume": 90,
            "high": "62",
            "low": "59",
            "open": "60",
        }

        # older previous date (should be ok) – we test a newer date error
        row = base_row()
        row["TD"] = "07/10/2026"
        with self.assertRaisesRegex(ValueError, "Nguồn trả ngày cũ hơn bản đã lưu."):
            normalize_quote(
                row,
                FETCHED_AT,
                today=TODAY,
                automatic=False,
                previous=prev,
            )

        # source mismatch
        prev_bad = prev.copy()
        prev_bad["source"] = "other"
        row = base_row()
        with self.assertRaisesRegex(ValueError, "Không trộn nguồn hoặc cơ sở giá khác nhau."):
            normalize_quote(row, FETCHED_AT, today=TODAY, automatic=False, previous=prev_bad)

        # closed candle reopened
        prev_closed = prev.copy()
        prev_closed["status"] = "closed"
        row = base_row()
        with self.assertRaisesRegex(ValueError, "Không mở lại nến đã đối soát đóng phiên."):
            normalize_quote(row, FETCHED_AT, today=TODAY, automatic=False, previous=prev_closed)

        # volume regression
        prev_reg = prev.copy()
        prev_reg["volume"] = 150
        row = base_row()
        with self.assertRaisesRegex(ValueError, "Nguồn trả dữ liệu OHLCV lùi."):
            normalize_quote(row, FETCHED_AT, today=TODAY, automatic=False, previous=prev_reg)

        # OHLC regression (high decreased)
        prev_reg = prev.copy()
        prev_reg["high"] = "63"
        row = base_row()
        with self.assertRaisesRegex(ValueError, "Nguồn trả dữ liệu OHLCV lùi."):
            normalize_quote(row, FETCHED_AT, today=TODAY, automatic=False, previous=prev_reg)

        # Open price change
        prev_reg = prev.copy()
        prev_reg["open"] = "61"
        row = base_row()
        with self.assertRaisesRegex(ValueError, "Nguồn trả dữ liệu OHLCV lùi."):
            normalize_quote(row, FETCHED_AT, today=TODAY, automatic=False, previous=prev_reg)

    # --------------------------------------------------------------------- #
    #  Ensure no mutation of the input row
    # --------------------------------------------------------------------- #
    def test_input_not_mutated(self):
        row = base_row()
        row_copy = row.copy()
        normalize_quote(row, FETCHED_AT, today=TODAY, automatic=False)
        self.assertEqual(row, row_copy)

    def test_pending_status_and_lower_close_are_preserved(self):
        row = base_row()
        previous = normalize_quote(row, FETCHED_AT, today=TODAY, automatic=False)
        snapshot = previous.copy()
        row["close_price"] = "60000"
        row["volume_accumulated"] = 110
        result = normalize_quote(row, FETCHED_AT, today=TODAY, automatic=True, previous=previous)
        self.assertEqual(result["status"], "pending_reconciliation")
        self.assertEqual(result["close"], "60")
        self.assertEqual(previous, snapshot)

if __name__ == "__main__":
    unittest.main()
