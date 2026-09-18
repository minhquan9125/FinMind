"""Driver-boundary tests; these do not substitute for a live Neo4j check."""

import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from backend.src.graph.adapter import to_graph
from backend.src.graph.contract import ContractError, SECTIONS, load_dataset
from backend.src.graph.graph_store import DatasetConflictError, GraphStore
from backend.src.graph.ingest import main


ROOT = Path(__file__).resolve().parents[2]


def small_payload():
    payload = load_dataset(ROOT / "data/normalized/FPT.json")
    payload["price_history"] = payload["price_history"][:1]
    payload["meta"].update(total_price_sessions=1, price_end_date=payload["price_history"][0]["date"])
    payload["quality"] = {"status": "PASS", "raw_price_records": 1,
                          "published_price_records": 1, "rejected_price_records": 0, "issues": []}
    for section, count_key in SECTIONS.items():
        payload["financial_data"][section] = payload["financial_data"][section][:1]
        payload["meta"][count_key] = 1
    return payload


class GraphStoreTests(unittest.TestCase):
    def setUp(self):
        self.payload = small_payload()
        self.graph = to_graph(self.payload)
        self.driver = MagicMock()
        self.session = self.driver.session.return_value.__enter__.return_value
        self.tx = MagicMock()
        self.session.execute_write.side_effect = lambda callback, *args: callback(self.tx, *args)
        self.session.execute_read.side_effect = lambda callback, *args: callback(self.tx, *args)
        self.store = GraphStore(self.driver, batch_size=100)
        self.claim = {"checksum": self.graph.dataset["checksum"], "graph_version": "1.0",
                      "status": "IMPORTING"}
        self.fail_reports = False

        def run(query, **parameters):
            result = MagicMock()
            if "claim_token AS claim_token" in query:
                result.single.return_value = {**self.claim, "claim_token": parameters["claim_token"]}
            if self.fail_reports and "HAS_REPORT" in query:
                raise RuntimeError("write failed")
            return result
        self.tx.run.side_effect = run

    def test_ingests_one_snapshot_and_batches_observations(self):
        result = self.store.ingest(self.payload, source_file="FPT.json")
        self.assertTrue(result.created)
        self.assertEqual(result.dataset_id, self.graph.dataset["id"])
        self.assertEqual(result.counts, self.graph.counts())
        self.session.execute_write.assert_called_once()
        observation_batches = [c.kwargs["rows"] for c in self.tx.run.call_args_list
                               if "HAS_OBSERVATION" in c.args[0]]
        self.assertEqual(sum(map(len, observation_batches)), len(self.graph.observations))
        self.assertTrue(all(len(batch) <= 100 for batch in observation_batches))
        self.assertIn("COMPLETE", self.tx.run.call_args_list[-1].args[0])

    def test_repeat_returns_unchanged_without_writing_reports(self):
        self.claim["status"] = "COMPLETE"
        result = self.store.ingest(self.payload)
        self.assertFalse(result.created)
        self.assertEqual(self.tx.run.call_count, 1)

    def test_same_identity_with_changed_content_is_a_conflict(self):
        changed = copy.deepcopy(self.payload)
        changed["financial_data"]["ratios"][0]["pe"] += 1
        with self.assertRaises(DatasetConflictError):
            self.store.ingest(changed)
        self.assertEqual(self.tx.run.call_count, 1)

    def test_graph_version_mismatch_is_a_conflict(self):
        self.claim["graph_version"] = "2.0"
        with self.assertRaises(DatasetConflictError):
            self.store.ingest(self.payload)

    def test_failed_write_escapes_transaction_and_never_marks_complete(self):
        self.fail_reports = True
        with self.assertRaisesRegex(RuntimeError, "write failed"):
            self.store.ingest(self.payload)
        self.assertFalse(any("status = 'COMPLETE'" in c.args[0]
                             for c in self.tx.run.call_args_list))

    def test_invalid_input_never_connects(self):
        self.payload["schema_version"] = "wrong"
        with self.assertRaises(ContractError):
            self.store.ingest(self.payload)
        self.driver.session.assert_not_called()

    def test_payload_read_roundtrip_and_unknown_symbol(self):
        self.tx.run.side_effect = None
        self.tx.run.return_value.single.return_value = {"payload_json": self.graph.dataset["payload_json"]}
        self.assertEqual(self.store.get_dataset("FPT"), self.payload)
        self.tx.run.return_value.single.return_value = None
        self.assertIsNone(self.store.get_dataset("UNKNOWN"))

    def test_observations_read_values_and_provenance_with_parameters(self):
        self.tx.run.side_effect = None
        self.tx.run.return_value.__iter__.return_value = iter([
            {"value_json": "null", "code": "car", "source_file": "FPT.json",
             "json_pointer": "/financial_data/ratios/0/car", "basis": "RATIO_TTM"},
            {"value_json": "0", "code": "dividendYield"},
        ])
        code = "field' RETURN 1 //"
        rows = self.store.get_observations("FPT", "2026-Q2", "ratios", code=code, offset=2)
        self.assertIsNone(rows[0]["value"])
        self.assertEqual(rows[1]["value"], 0)
        self.assertEqual(rows[0]["basis"], "RATIO_TTM")
        query = self.tx.run.call_args.args[0]
        self.assertNotIn(code, query)
        self.assertEqual(self.tx.run.call_args.kwargs["code"], code)
        self.assertEqual(self.tx.run.call_args.kwargs["offset"], 2)

    def test_pagination_and_batch_size_are_bounded(self):
        for limit, offset in ((0, 0), (1001, 0), (True, 0), (1, -1), (1, False), (1, 2**80)):
            with self.assertRaises(ContractError):
                self.store.get_observations("FPT", "2026-Q2", "ratios", limit=limit, offset=offset)
        for size in (0, -1, True, 10001):
            with self.assertRaises(ContractError):
                GraphStore(self.driver, batch_size=size)

    def test_schema_is_applied_once_with_seven_unique_constraints(self):
        self.store.ensure_schema()
        self.store.ensure_schema()
        self.assertEqual(self.session.run.call_count, 7)
        self.assertTrue(all("IS UNIQUE" in call.args[0] for call in self.session.run.call_args_list))

    def test_cli_does_not_expose_driver_exception_credentials(self):
        with patch("backend.src.graph.ingest.load_dataset", return_value=self.payload), \
                patch.object(GraphStore, "from_environment", side_effect=RuntimeError("secret-password")), \
                patch("sys.stderr", new_callable=io.StringIO) as output:
            self.assertEqual(main(["--input", "FPT.json"]), 1)
        self.assertNotIn("secret-password", output.getvalue())

    def test_connection_configuration_requires_credentials_and_rejects_uri_credentials(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ContractError):
                GraphStore.from_environment()
        with patch.dict("os.environ", {"NEO4J_URI": "bolt://user:secret@localhost:7687",
                                       "NEO4J_USER": "neo4j", "NEO4J_PASSWORD": "secret"}, clear=True):
            with self.assertRaises(ContractError):
                GraphStore.from_environment()

    def test_context_manager_closes_driver(self):
        with self.store:
            pass
        self.driver.close.assert_called_once()


class GraphCliTests(unittest.TestCase):
    def test_dry_run_all_real_datasets_without_database(self):
        with patch.object(GraphStore, "from_environment") as connect, patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(main(["--dry-run"]), 0)
        lines = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(lines), 8)
        self.assertEqual(sum(line["counts"]["prices"] for line in lines), 17232)
        connect.assert_not_called()

    def test_bad_input_is_reported_before_connecting(self):
        with patch.object(GraphStore, "from_environment") as connect, patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(main(["--input", str(ROOT / "backend/src/main.py")]), 1)
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
