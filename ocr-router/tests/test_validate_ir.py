"""Regression checks for the IR v1 contract and cross-field rules."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from validate_ir import SCHEMA, validate_page


class DocumentIrContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(schema)
        cls.example = schema["examples"][0]

    def check(self, change, valid: bool) -> None:
        document = copy.deepcopy(self.example)
        change(document)
        errors = validate_page(document, self.validator)
        self.assertEqual(errors == [], valid, errors)

    def test_example(self) -> None:
        self.check(lambda _: None, True)

    def test_unreadable_and_empty_cell(self) -> None:
        self.check(lambda d: d["blocks"][3]["rows"][0]["cells"]["c1"].update(raw=None), True)
        self.check(lambda d: d["blocks"][3]["rows"][0]["cells"]["c1"].update(raw=""), False)

    def test_required_source_and_page_size(self) -> None:
        for field in ("source", "page_size"):
            with self.subTest(field=field):
                self.check(lambda d: d.pop(field), False)

    def test_ocr_source_conditions(self) -> None:
        def ocr(d):
            d["source"]["engine"] = "TESSERACT"
            d["source"]["image_sha256"] = "a" * 64
            d["page_size"]["unit"] = "px"
            d["source"]["render"] = {"dpi": 300, "rotation": 180}
        self.check(ocr, True)
        self.check(lambda d: (ocr(d), d["source"].pop("render")), False)
        self.check(lambda d: (ocr(d), d["source"].pop("image_sha256")), False)

        def gemini(d):
            ocr(d)
            d["source"]["engine"] = "GEMINI"
            d["source"]["prompt_version"] = "v1"
        self.check(gemini, True)
        self.check(lambda d: (gemini(d), d["source"].pop("prompt_version")), False)

    def test_votes_and_column_keys(self) -> None:
        def merged(d):
            d["source"]["engine"] = "MERGED"
            for row in d["blocks"][3]["rows"]:
                for cell in row["cells"].values():
                    cell["votes"] = {"TEXT_LAYER": {"raw": cell["raw"], "conf": None}}
        self.check(merged, True)
        self.check(lambda d: (merged(d), d["blocks"][3]["rows"][0]["cells"]["c1"].pop("votes")), False)
        self.check(lambda d: d["blocks"][3]["rows"][0]["cells"]["c1"].update(votes={"foo": {"raw": "1"}}), False)
        self.check(lambda d: d["blocks"][3]["rows"][0]["cells"].update({"2024": {"raw": "1", "bbox": None}}), False)
        self.check(lambda d: d["blocks"][3]["rows"][0]["cells"].update({"c9": {"raw": "1", "bbox": None}}), False)

    def test_ir_excludes_mapping_and_checks_ids_and_boxes(self) -> None:
        self.check(lambda d: d["blocks"][3]["rows"][0].update(metric_match={}), False)
        self.check(lambda d: d["blocks"][1].update(id=d["blocks"][0]["id"]), False)
        self.check(lambda d: d["blocks"][3]["rows"][1].update(id="r1"), False)
        self.check(lambda d: d["blocks"][3]["columns"][1].update(key="c1"), False)
        self.check(lambda d: d["blocks"][3]["rows"][0].update(bbox=[10, 10, 9, 11]), False)
        self.check(lambda d: d["blocks"][3]["rows"][0].update(bbox=[10, 10, 2000, 11]), False)

    def test_notes_and_roman_printed_page(self) -> None:
        self.check(lambda d: d.update(page_class="notes", printed_page="iv"), True)


if __name__ == "__main__":
    unittest.main()
