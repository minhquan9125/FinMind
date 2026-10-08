"""Offline regression checks for the Python OCR router migration."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import main


class RouterTest(unittest.TestCase):
    def test_cross_check_matches_existing_poc_output(self) -> None:
        root = Path(__file__).resolve().parents[5] / "bctc_fpt_2026"
        if not (root / "pages.jsonl").is_file():
            self.skipTest("POC sample output not available")
        for line in (root / "pages.jsonl").read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if "crossCheck" not in record:
                continue
            tess = (root / "text" / f"p-{record['page']:03d}.tess.txt").read_text(encoding="utf-8")
            self.assertEqual(main.cross_check(record["text"], tess), record["crossCheck"])

    def test_routes_and_output_shape(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            root = Path(tmp)
            pdf = root / "sample.pdf"
            pdf.write_bytes(b"fixture")
            image = root / "p-002.png"
            image.write_bytes(b"fixture")
            cfg = argparse.Namespace(out=root / "out", pages="1-2", gemini="auto",
                model="gemini-3.8-flash-low", escalate_model=None, batch=4,
                agy_concurrency=2, agy_timeout=300, tess_workers=1,
                min_chars=150, min_conf=90, long_side=3508, tessdata=None)
            layer = {1: {"text": "abc " * 40, "chars": 120 + 40, "badRatio": 0, "usable": True},
                     2: {"text": "", "chars": 0, "badRatio": 0, "usable": False}}
            tess = {"text": "BẢNG CÂN ĐỐI KẾ TOÁN\n100 1.000.000", "chars": 30,
                    "words": 6, "meanConf": 95, "lowConfRatio": 0, "seconds": 1.2}
            gem_page = {"page_type": "table", "text": "BẢNG CÂN ĐỐI KẾ TOÁN\n100 1.000.000",
                        "unreadable": []}
            outcome = {2: {"model": cfg.model, "cached": True, "page": gem_page}}
            with patch.object(main, "page_count", return_value=2), \
                 patch.object(main, "read_text_layer", return_value=layer), \
                 patch.object(main, "upright_page", return_value=(image, 0)), \
                 patch.object(main, "hash_file", return_value="a" * 64), \
                 patch.object(main, "load_json", return_value=tess), \
                 patch.object(main, "gemini_transcribe", return_value=outcome):
                main.process_pdf(pdf, cfg, {})
            doc = cfg.out / "sample"
            pages = [json.loads(line) for line in (doc / "pages.jsonl").read_text(encoding="utf-8").splitlines()]
            summary = json.loads((doc / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual([page["route"] for page in pages], ["text_layer", "tesseract+gemini"])
            self.assertEqual([page["status"] for page in pages], ["OK", "OK"])
            self.assertEqual(summary["routes"], {"text_layer": 1, "tesseract+gemini": 1})
            self.assertEqual(summary["cache"], {"tesseractHits": 1, "geminiHits": 1})
            self.assertEqual(pages[1]["crossCheck"]["numberAgreement"], 1)

    def test_scan_decisions_match_existing_poc_output(self) -> None:
        sample = Path(__file__).resolve().parents[5] / "bctc_fpt_2026"
        if not (sample / "pages.jsonl").is_file():
            self.skipTest("POC sample output not available")
        expected = [json.loads(line) for line in (sample / "pages.jsonl").read_text(encoding="utf-8").splitlines()]
        tesseract_results = []
        gemini_results = {}
        for record in expected:
            tess_text = (sample / "text" / f"p-{record['page']:03d}.tess.txt").read_text(encoding="utf-8")
            tesseract_results.append({**{k: v for k, v in record["tesseract"].items() if k != "cached"},
                                      "text": tess_text})
            gemini_results[record["page"]] = {"model": record["gemini"]["model"], "cached": True,
                "page": {"text": record["text"], "page_type": record["gemini"]["page_type"],
                         "unreadable": record["gemini"]["unreadable"]}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            root = Path(tmp)
            pdf = root / "scan.pdf"
            pdf.write_bytes(b"fixture")
            cfg = argparse.Namespace(out=root / "out", pages="6-9", gemini="auto",
                model="gemini-3.8-flash-low", escalate_model=None, batch=4,
                agy_concurrency=2, agy_timeout=300, tess_workers=1,
                min_chars=150, min_conf=90, long_side=3508, tessdata=None)
            layer = {page: {"text": "", "chars": 0, "badRatio": 0, "usable": False}
                     for page in range(6, 10)}
            with patch.object(main, "page_count", return_value=9), \
                 patch.object(main, "read_text_layer", return_value=layer), \
                 patch.object(main, "upright_page", side_effect=lambda _pdf, page, *_: (root / f"p-{page:03d}.png", 0)), \
                 patch.object(main, "hash_file", return_value="a" * 64), \
                 patch.object(main, "load_json", side_effect=tesseract_results), \
                 patch.object(main, "gemini_transcribe", return_value=gemini_results):
                main.process_pdf(pdf, cfg, {})
            actual = [json.loads(line) for line in (cfg.out / "scan" / "pages.jsonl").read_text(encoding="utf-8").splitlines()]
            for old, new in zip(expected, actual):
                for key in ("page", "route", "status", "flags", "text", "textLayer", "rotation",
                            "tesseract", "crossCheck", "gemini"):
                    self.assertEqual(new.get(key), old.get(key), (old["page"], key))


if __name__ == "__main__":
    unittest.main()
