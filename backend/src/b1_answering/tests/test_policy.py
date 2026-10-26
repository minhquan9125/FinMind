import json
import unittest
import tempfile
from pathlib import Path

# Add the project root (backend) to sys.path so imports resolve
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.b1_answering.policy import Limits, Budget, PolicyError


class TestLimitsLoad(unittest.TestCase):
    def setUp(self) -> None:
        # Base correct JSON derived from the shipped limits.json
        self.base_data = {
            "version": "b1-limits-v1",
            "model": "gemini-3.5-flash-lite",
            "max_input_tokens": 16384,
            "max_output_tokens": 2048,
            "read_timeout_seconds": 600,
            "max_generation_calls": 20,
            "max_total_tokens": 65536,
            "max_cost_usd": 0.0,
        }

    def _write_tmp(self, data: dict) -> Path:
        tmp = Path(tempfile.mkdtemp()) / "limits.json"
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f)
        return tmp

    def test_load_valid(self):
        path = self._write_tmp(self.base_data)
        limits = Limits.load(path)
        for k, v in self.base_data.items():
            self.assertEqual(getattr(limits, k), v)

    def test_missing_field(self):
        data = self.base_data.copy()
        data.pop("max_input_tokens")
        path = self._write_tmp(data)
        with self.assertRaises(ValueError) as cm:
            Limits.load(path)
        self.assertIn("Missing fields", str(cm.exception))

    def test_extra_field(self):
        data = self.base_data.copy()
        data["unexpected"] = 1
        path = self._write_tmp(data)
        with self.assertRaises(ValueError) as cm:
            Limits.load(path)
        self.assertIn("Extra fields", str(cm.exception))

    def test_bool_instead_of_number(self):
        data = self.base_data.copy()
        data["max_input_tokens"] = True
        path = self._write_tmp(data)
        with self.assertRaises(TypeError) as cm:
            Limits.load(path)
        self.assertIn("bool", str(cm.exception))

    def test_nonfinite_cost(self):
        data = self.base_data.copy()
        data["max_cost_usd"] = float("nan")
        path = self._write_tmp(data)
        with self.assertRaises(ValueError) as cm:
            Limits.load(path)
        self.assertIn("nonfinite", str(cm.exception))

    def test_invalid_version(self):
        with self.assertRaises(ValueError) as cm:
            Limits(version="bad-version")
        self.assertIn("Invalid version", str(cm.exception))

    def test_invalid_model(self):
        with self.assertRaises(ValueError) as cm:
            Limits(model="bad-model")
        self.assertIn("Invalid model", str(cm.exception))

    def test_total_less_than_output(self):
        with self.assertRaises(ValueError) as cm:
            Limits(max_total_tokens=1000, max_output_tokens=2000)
        self.assertIn("must be >= max_output_tokens", str(cm.exception))


class TestBudgetBehaviour(unittest.TestCase):
    def setUp(self) -> None:
        # Use a small, easy‑to‑reason limits configuration
        self.limits = Limits(
            max_input_tokens=10,
            max_output_tokens=5,
            max_total_tokens=30,
            max_generation_calls=2,
            read_timeout_seconds=10,
            max_cost_usd=0.0,
        )
        self.budget = Budget(self.limits)

    def test_reserve_success(self):
        ticket = self.budget.reserve(8)
        self.assertIsInstance(ticket, int)
        snap = self.budget.snapshot()
        self.assertEqual(snap["calls_used"], 1)
        # reservation = input + max_output_tokens = 8 + 5 = 13
        self.assertEqual(snap["tokens_reserved"], 13)

    def test_reserve_input_exceeds_limit(self):
        with self.assertRaises(PolicyError) as cm:
            self.budget.reserve(20)
        self.assertEqual(cm.exception.code, "INPUT_LIMIT_EXCEEDED")

    def test_reserve_call_limit_exceeded(self):
        # First two reservations succeed
        self.budget.reserve(5)
        self.budget.reserve(5)
        # Third should hit call limit (max_generation_calls = 2)
        with self.assertRaises(PolicyError) as cm:
            self.budget.reserve(5)
        self.assertEqual(cm.exception.code, "CALL_LIMIT_EXCEEDED")

    def test_reserve_budget_exceeded(self):
        # Reserve near the total token budget
        self.budget = Budget(Limits(max_input_tokens=20, max_output_tokens=5, max_total_tokens=30))
        self.budget.reserve(10)  # reserves 15 tokens (10+5)
        # Remaining tokens = 30 - 15 = 15
        # Next reservation of 12 input would need 17 total > 15
        with self.assertRaises(PolicyError) as cm:
            self.budget.reserve(12)
        self.assertEqual(cm.exception.code, "BUDGET_EXCEEDED")

    def test_settle_none_usage_marks_unknown(self):
        ticket = self.budget.reserve(5)
        with self.assertRaises(PolicyError) as cm:
            self.budget.settle(ticket, None)
        self.assertEqual(cm.exception.code, "USAGE_UNKNOWN")
        snap = self.budget.snapshot()
        self.assertEqual(snap["unknown_usage"], 1)
        # tokens_reserved stays unchanged because reservation not refunded
        self.assertEqual(snap["tokens_reserved"], 10)  # 5+5

    def test_settle_invalid_usage(self):
        ticket = self.budget.reserve(5)
        bad_usage = {"input_tokens": -1, "output_tokens": 0, "total_tokens": 0}
        with self.assertRaises(PolicyError) as cm:
            self.budget.settle(ticket, bad_usage)
        self.assertEqual(cm.exception.code, "USAGE_LIMIT_EXCEEDED")
        snap = self.budget.snapshot()
        self.assertEqual(snap["unknown_usage"], 1)
        # reservation still counted as used (no refund)
        self.assertEqual(snap["tokens_reserved"], 10)

    def test_settle_valid_usage_refunds(self):
        ticket = self.budget.reserve(8)  # reservation = 13
        usage = {"input_tokens": 8, "output_tokens": 3, "total_tokens": 11}
        # Should not raise
        self.budget.settle(ticket, usage)
        snap = self.budget.snapshot()
        self.assertEqual(snap["tokens_reserved"], 11)  # keep actual usage, refund unused2
        self.assertEqual(snap["unknown_usage"], 0)

    def test_settle_twice_raises(self):
        ticket = self.budget.reserve(5)
        usage = {"input_tokens": 5, "output_tokens": 5, "total_tokens": 10}
        self.budget.settle(ticket, usage)
        with self.assertRaises(PolicyError) as cm:
            self.budget.settle(ticket, usage)
        self.assertEqual(cm.exception.code, "TICKET_ALREADY_SETTLED")

    def test_settle_invalid_ticket(self):
        with self.assertRaises(PolicyError) as cm:
            self.budget.settle(999, {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})
        self.assertEqual(cm.exception.code, "INVALID_TICKET")

    def test_snapshot_reflects_state(self):
        self.assertEqual(self.budget.snapshot()["calls_used"], 0)
        t1 = self.budget.reserve(3)
        t2 = self.budget.reserve(4)
        snap = self.budget.snapshot()
        self.assertEqual(snap["calls_used"], 2)
        self.assertEqual(snap["tokens_reserved"], (3+5)+(4+5))
        # settle one with None -> unknown usage
        with self.assertRaises(PolicyError):
            self.budget.settle(t1, None)
        snap2 = self.budget.snapshot()
        self.assertEqual(snap2["unknown_usage"], 1)
        # tokens_reserved unchanged after unknown usage
        self.assertEqual(snap2["tokens_reserved"], (3+5)+(4+5))


class TestCoordinatorBoundaries(unittest.TestCase):
    def test_direct_bool_fields_rejected(self):
        for name in ('max_input_tokens', 'max_output_tokens', 'max_generation_calls', 'max_total_tokens', 'read_timeout_seconds', 'max_cost_usd'):
            with self.subTest(name=name), self.assertRaises((ValueError, TypeError)):
                Limits(**{name: False if name == 'max_cost_usd' else True})

    def test_usage_above_reserved_input_retains_budget(self):
        budget = Budget(Limits(max_input_tokens=100, max_output_tokens=10))
        ticket = budget.reserve(3)
        with self.assertRaises(PolicyError):
            budget.settle(ticket, {'input_tokens': 4, 'output_tokens': 1, 'total_tokens': 5})
        self.assertEqual(budget.snapshot()['tokens_reserved'], 13)
        self.assertEqual(budget.snapshot()['unknown_usage'], 1)
        with self.assertRaises(PolicyError):
            budget.settle(ticket, {'input_tokens': 3, 'output_tokens': 1, 'total_tokens': 4})

    def test_reserve_bool_rejected(self):
        with self.assertRaises((ValueError, PolicyError)):
            Budget(Limits()).reserve(True)

    def test_concurrent_reservations_respect_call_limit(self):
        from concurrent.futures import ThreadPoolExecutor
        budget = Budget(Limits(max_generation_calls=3))
        def attempt(_):
            try:
                budget.reserve(1)
                return True
            except PolicyError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(attempt, range(20)))
        self.assertEqual(sum(outcomes), 3)
        self.assertEqual(budget.snapshot()['calls_used'], 3)
