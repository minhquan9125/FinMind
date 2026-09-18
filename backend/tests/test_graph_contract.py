"""Contract checks against unchanged crawler datasets and malformed input."""

import copy
import json
from pathlib import Path
import unittest

from backend.src.graph.adapter import to_graph
from backend.src.graph.contract import ContractError, load_dataset


ROOT = Path(__file__).resolve().parents[2]


class GraphContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = load_dataset(ROOT / "data/normalized/FPT.json")

    def test_all_eight_datasets_and_full_value_preservation(self):
        prices = reports = 0
        for path in sorted((ROOT / "data/normalized").glob("*.json")):
            with self.subTest(symbol=path.stem):
                payload = load_dataset(path)
                graph = to_graph(payload, source_file=path.name)
                self.assertEqual(json.loads(graph.dataset["payload_json"]), payload)
                self.assertEqual(graph.company["symbol"], path.stem)
                prices += len(graph.prices)
                reports += len(graph.reports)
                report_rows = {r["id"]: json.loads(r["payload_json"]) for r in graph.reports}
                for observation in graph.observations:
                    self.assertEqual(json.loads(observation["value_json"]),
                                     report_rows[observation["report_id"]][observation["code"]])
        self.assertEqual(prices, 17232)
        self.assertEqual(reports, 1335)

    def test_year_quarter_ttm_and_input_are_preserved(self):
        before = copy.deepcopy(self.payload)
        graph = to_graph(self.payload, source_file="FPT.json")
        annual = next(r for r in graph.reports if r["section"] == "ratios"
                      and r["period_label"] == "2025-YEAR")
        period = next(p for p in graph.periods if p["id"] == "2025-YEAR")
        self.assertIsNone(period["quarter"])
        self.assertEqual(period["year"], 2025)
        self.assertEqual(json.loads(annual["payload_json"])["quarter"], 5)
        self.assertEqual(annual["basis"], "RATIO_YEAR")
        quarterly = next(r for r in graph.reports if r["section"] == "ratios"
                         and r["period_label"] == "2026-Q2")
        self.assertEqual(quarterly["basis"], "RATIO_TTM")
        self.assertEqual(self.payload, before)

    def test_zero_null_nested_values_and_json_pointer(self):
        payload = copy.deepcopy(self.payload)
        payload["financial_data"]["ratios"][0]["future/~field"] = {"items": [0, None]}
        graph = to_graph(payload, source_file="FPT.json")
        report = next(r for r in graph.reports if r["section"] == "ratios"
                      and r["period_label"] == "2026-Q2")
        values = {o["code"]: o for o in graph.observations if o["report_id"] == report["id"]}
        self.assertTrue(values["car"]["is_null"])
        self.assertFalse(values["dividendYield"]["is_null"])
        self.assertEqual(values["dividendYield"]["value"], 0)
        self.assertEqual(values["future/~field"]["value_type"], "object")
        self.assertEqual(values["future/~field"]["json_pointer"],
                         "/financial_data/ratios/0/future~1~0field")
        self.assertEqual(json.loads(values["future/~field"]["value_json"]), {"items": [0, None]})
        self.assertTrue(all(m["unit_status"] == "UNKNOWN" for m in graph.metrics))

    def test_checksum_ignores_object_key_order_and_file_location(self):
        reordered = dict(reversed(list(self.payload.items())))
        first = to_graph(self.payload, source_file="a/FPT.json")
        second = to_graph(reordered, source_file="b/FPT.json")
        self.assertEqual(first.dataset["checksum"], second.dataset["checksum"])
        self.assertEqual(first.dataset["id"], second.dataset["id"])

    def test_invalid_contract_data_is_rejected(self):
        def mutations(payload):
            return [
                lambda: payload.update(schema_version="2.0"),
                lambda: payload["financial_data"].update(ratios=[]),
                lambda: payload["financial_data"]["ratios"].append(payload["financial_data"]["ratios"][0]),
                lambda: payload["financial_data"]["ratios"][0].update(year="wrong"),
                lambda: payload["financial_data"]["ratios"][0].update(quarter=True),
                lambda: payload["financial_data"]["ratios"][0].update(organCode="VNM"),
                lambda: payload["meta"].update(total_price_sessions=0),
                lambda: payload["quality"].update(published_price_records=True),
                lambda: payload["quality"].update(status="FAIL"),
                lambda: payload["price_history"][0].update(close=float("nan")),
                lambda: payload["price_history"][0].update(high=1),
                lambda: payload["price_history"][0].update(source_timestamp=0),
                lambda: payload["price_history"][0].update(volume=-1),
                lambda: payload.update(generated_at="2026-09-15T09:33:41Z"),
            ]
        for index in range(14):
            with self.subTest(case=index):
                payload = copy.deepcopy(self.payload)
                mutations(payload)[index]()
                with self.assertRaises(ContractError):
                    to_graph(payload)

    def test_loader_rejects_duplicate_keys_and_nonfinite_json(self):
        from uuid import uuid4
        # Windows Python 3.14 restricts mkdtemp ACLs under the sandbox token.
        directory = ROOT / "backend/tests" / f"fixture_{uuid4().hex}"
        directory.mkdir()
        path = directory / "invalid.json"
        try:
            for content in ('{"symbol":"FPT","symbol":"VNM"}', '{"value":NaN}'):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ContractError):
                    load_dataset(path)
        finally:
            path.unlink(missing_ok=True)
            directory.rmdir()

    def test_nonstring_period_and_non_json_python_values_are_rejected(self):
        for value in (42, ["2026-Q2"]):
            payload = copy.deepcopy(self.payload)
            payload["financial_data"]["ratios"][0]["period_label"] = value
            with self.assertRaises(ContractError):
                to_graph(payload)
        payload = copy.deepcopy(self.payload)
        payload["future"] = (1, 2)
        with self.assertRaises(ContractError):
            to_graph(payload)

    def test_annual_period_requires_an_explicit_quarter_field(self):
        payload = copy.deepcopy(self.payload)
        annual = next(row for row in payload["financial_data"]["ratios"]
                      if row["period_type"] == "YEAR")
        del annual["quarter"]
        with self.assertRaises(ContractError):
            to_graph(payload)

    def test_large_integer_observation_survives_without_invalid_bolt_integer(self):
        payload = copy.deepcopy(self.payload)
        payload["financial_data"]["ratios"][0]["futureInteger"] = 2**80
        graph = to_graph(payload)
        value = next(o for o in graph.observations if o["code"] == "futureInteger")
        self.assertIsNone(value["value"])
        self.assertFalse(value["is_null"])
        self.assertEqual(json.loads(value["value_json"]), 2**80)


if __name__ == "__main__":
    unittest.main()
