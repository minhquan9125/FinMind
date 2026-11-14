"""Independent-worker cases, corrected contract names, plus acceptance gaps."""
import copy
import unittest

from retrieval_flow.contracts import check_evidence, load_fixtures, validate_pack


class TestContracts(unittest.TestCase):
    def setUp(self):
        self.fixtures = load_fixtures()
        self.pack = self.fixtures["packs"]["valid_metric"]
        self.registry = self.fixtures["registry"]
        self.scope = {"companies": ["BID"], "periods": ["2026-06-30"],
                      "metric_code": "TOTAL_ASSETS", "topic": None,
                      "measure_basis": "POINT_IN_TIME", "reporting_entity": "UNKNOWN", "source_type": "BCTC"}

    def codes(self, errors):
        return {e["code"] for e in errors}

    def test_valid_pack_and_source_contract_field_names(self):
        self.assertEqual(self.pack["schema_version"], "1.0")
        self.assertIn("source_sha256", self.pack["items"][0])
        self.assertEqual(validate_pack(self.pack), [])
        self.assertEqual(check_evidence(self.pack, self.scope, self.registry), [])

    def test_schema_missing_or_unsupported(self):
        for version in (None, "2.0", 1, True):
            pack = copy.deepcopy(self.pack)
            pack["schema_version"] = version
            self.assertIn("E002", self.codes(validate_pack(pack)))

    def test_valid_compare(self):
        scope = {**self.scope, "companies": ["BID", "VCB"], "periods": ["2025-12-31"]}
        self.assertEqual(check_evidence(self.fixtures["packs"]["valid_compare"], scope, self.registry), [])

    def test_company_mismatch(self):
        self.assertIn("E102", self.codes(check_evidence(self.pack, {**self.scope, "companies": ["VCB"]}, self.registry)))

    def test_duplicate_evidence_id(self):
        self.pack["items"].append(copy.deepcopy(self.pack["items"][0]))
        self.assertIn("E011", self.codes(validate_pack(self.pack)))

    def test_all_fixture_packs_validate_and_are_synthetic(self):
        self.assertEqual(self.fixtures["execution_mode"], "FIXTURE")
        for pack in self.fixtures["packs"].values():
            self.assertEqual(validate_pack(pack), [])
            for item in pack["items"]:
                self.assertIn("FIXTURE", item["passage"])

    def test_loader_and_validators_do_not_share_or_mutate(self):
        other = load_fixtures()
        self.pack["items"][0]["passage"] = "changed"
        self.assertNotEqual(other["packs"]["valid_metric"]["items"][0]["passage"], "changed")
        before = copy.deepcopy(other)
        validate_pack(other["packs"]["valid_metric"])
        check_evidence(other["packs"]["valid_metric"], self.scope, other["registry"])
        self.assertEqual(other, before)

    def test_non_objects_missing_fields_and_blank_content_fail(self):
        for value in (None, [], "raw JSON", 3, True):
            self.assertTrue(validate_pack(value))
        for field in ("query_id", "data_version", "items"):
            pack = copy.deepcopy(self.pack)
            del pack[field]
            self.assertTrue(validate_pack(pack))
        for field in ("evidence_id", "chunk_id", "source_id", "passage"):
            pack = copy.deepcopy(self.pack)
            pack["items"][0][field] = " "
            self.assertTrue(validate_pack(pack))

    def test_bad_hash_score_and_version_are_rejected(self):
        for sha in ("abc", "x" * 64, "a" * 65, None, True):
            pack = copy.deepcopy(self.pack)
            pack["items"][0]["source_sha256"] = sha
            self.assertIn("E014", self.codes(validate_pack(pack)))
        for score in (True, "0.8", None, float("nan"), float("inf"), -1.1, 1.1, 10 ** 500):
            pack = copy.deepcopy(self.pack)
            pack["items"][0]["score"]["value"] = score
            self.assertIn("E026", self.codes(validate_pack(pack)))
        self.pack["data_version"]["id"] = "latest"
        self.assertIn("E007", self.codes(validate_pack(self.pack)))

    def test_locator_page_and_table_validation(self):
        for locator in ({}, {"section_label": "Title"}, {"page_number": True}, {"page_number": 0},
                        {"page_number": 1.5}, {"table_id": " "}, {"table_id": "valid", "page_number": -1}):
            pack = copy.deepcopy(self.pack)
            pack["items"][0]["locator"] = locator
            self.assertTrue(validate_pack(pack))
        for locator in ({"page_number": 1}, {"table_id": "fixture-table"}):
            pack = copy.deepcopy(self.pack)
            pack["items"][0]["locator"] = locator
            self.assertEqual(validate_pack(pack), [])

    def test_empty_pack_valid_structure_but_not_complete_evidence(self):
        self.assertEqual(validate_pack(self.fixtures["packs"]["empty"]), [])
        self.assertIn("E114", self.codes(check_evidence(self.fixtures["packs"]["empty"], self.scope, self.registry)))

    def test_registry_binding_and_missing_metadata(self):
        key = self.pack["items"][0]["chunk_id"]
        for field, expected in (("source_id", "E112"), ("source_sha256", "E109"), ("passage", "E111"),
                                ("index_version", "E116"), ("measure_basis", "E105")):
            registry = copy.deepcopy(self.registry)
            registry[key][field] = "wrong"
            self.assertIn(expected, self.codes(check_evidence(self.pack, self.scope, registry)))
        for field in ("unit", "reporting_entity", "company", "value_token"):
            registry = copy.deepcopy(self.registry)
            del registry[key][field]
            self.assertIn("E115", self.codes(check_evidence(self.pack, self.scope, registry)))
        self.assertIn("E101", self.codes(check_evidence(self.pack, self.scope, {})))

    def test_wrong_period_metric_basis_entity_unit_source(self):
        for field, value, expected in (("periods", ["2025-12-31"], "E103"),
                                      ("metric_code", "PROFIT_AFTER_TAX", "E104"),
                                      ("measure_basis", "YTD", "E105"),
                                      ("reporting_entity", "PARENT", "E106"),
                                      ("unit", "OTHER_UNIT", "E107"), ("source_type", "BCTN", "E108")):
            self.assertIn(expected, self.codes(check_evidence(self.pack, {**self.scope, field: value}, self.registry)))

    def test_required_company_period_coverage_and_empty_scope(self):
        for extension in ({"companies": ["BID", "VCB"]}, {"periods": ["2026-06-30", "2025-12-31"]}):
            self.assertIn("E114", self.codes(check_evidence(self.pack, {**self.scope, **extension}, self.registry)))
        for extension in ({"companies": []}, {"periods": []}, {"periods": "2026-06-30"},
                          {"periods": ["2026-02-31"]}, {"metric_code": None}):
            self.assertIn("E115", self.codes(check_evidence(self.pack, {**self.scope, **extension}, self.registry)))

    def test_conflicting_values_and_entity_ambiguity(self):
        item = copy.deepcopy(self.pack["items"][0])
        record = copy.deepcopy(self.registry[item["chunk_id"]])
        item["chunk_id"] = "fixture-conflict"
        item["evidence_id"] = "fixture-conflict"
        self.pack["items"].append(item)
        record["value_token"] = "FIXTURE_CONFLICT"
        self.registry[item["chunk_id"]] = record
        self.assertIn("E113", self.codes(check_evidence(self.pack, self.scope, self.registry)))
        record["reporting_entity"] = "PARENT"
        self.assertIn("E106", self.codes(check_evidence(self.pack, self.scope, self.registry)))

    def test_one_invalid_item_rejects_whole_pack(self):
        self.pack["items"].append(None)
        self.assertIn("E009", self.codes(validate_pack(self.pack)))
        self.assertTrue(check_evidence(self.pack, self.scope, self.registry))

    def test_malformed_record_metric_fails_without_crashing(self):
        self.registry[self.pack["items"][0]["chunk_id"]]["metric_code"] = []
        self.assertIn("E115", self.codes(check_evidence(self.pack, self.scope, self.registry)))
