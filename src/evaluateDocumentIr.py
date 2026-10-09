"""Compare every positioned financial IR cell with independent Poppler PDF words.

Usage: python src/evaluateDocumentIr.py "FPT_2024_498332 (1).pdf"
This is a cross-extractor agreement measure, not a human-approved gold set.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from financialContent import expand_page_ranges
from util import hash_file, required_command, save_json


def _poppler_words(pdf: Path, number: int) -> list[dict[str, Any]]:
    result = subprocess.run([required_command("pdftotext"), "-f", str(number), "-l", str(number),
                             "-bbox-layout", str(pdf), "-"], capture_output=True, check=True)
    root = ET.fromstring(result.stdout)
    words: list[dict[str, Any]] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "word":
            continue
        words.append({"text": "".join(element.itertext()),
                      "bbox": [float(element.attrib[name]) for name in
                               ("xMin", "yMin", "xMax", "yMax")]})
    return words


def _value(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text)).replace("−", "-")


def evaluate(pdf: Path, ir_dir: Path) -> dict[str, Any]:
    table_dir = ir_dir / "table"
    index = json.loads((table_dir / "index.json").read_text(encoding="utf-8"))
    digest = hash_file(pdf)
    if index["document_sha256"] != digest:
        raise ValueError("PDF không trùng SHA-256 với table/index.json")
    rows: list[dict[str, Any]] = []
    for number in expand_page_ranges(index["structured_table_ranges"]):
        page = json.loads((table_dir / f"p-{number:03d}.ir.json").read_text(encoding="utf-8"))
        if page["source"]["engine"] != "TEXT_LAYER" or page["page_size"]["unit"] != "pt":
            continue
        words = _poppler_words(pdf, number)
        for block in page["blocks"]:
            if block["type"] != "table":
                continue
            for row in block["rows"]:
                for column, cell in row["cells"].items():
                    bbox = cell.get("bbox")
                    if bbox is None or cell.get("raw") is None:
                        continue
                    x0, y0, x1, y1 = bbox
                    selected = [word for word in words
                                if x0 - 2 <= (word["bbox"][0] + word["bbox"][2]) / 2 <= x1 + 2
                                and y0 - 2 <= (word["bbox"][1] + word["bbox"][3]) / 2 <= y1 + 2]
                    selected.sort(key=lambda word: (round(word["bbox"][1] / 3), word["bbox"][0]))
                    reference = " ".join(word["text"] for word in selected)
                    status = ("no_pdf_word" if not selected else
                              "match" if _value(reference) == _value(cell["raw"]) else "mismatch")
                    rows.append({"page": number, "table_id": block["id"], "row_id": row["id"],
                                 "code": row.get("code"), "column": column, "bbox": bbox,
                                 "ir_raw": cell["raw"], "pdf_raw": reference, "status": status})
    matched = sum(row["status"] == "match" for row in rows)
    candidates_path = ir_dir / "gold_candidates.json"
    if not candidates_path.exists():
        save_json(candidates_path, {
            "document_sha256": digest,
            "source": "Poppler bbox-layout candidate transcribed from the source PDF",
            "instruction": "Review gold_raw against the PDF image; set review_status to approved and record reviewer. Automated matches are not approved gold labels.",
            "items": [{"page": row["page"], "table_id": row["table_id"],
                       "row_id": row["row_id"], "code": row["code"],
                       "column": row["column"], "bbox": row["bbox"],
                       "gold_raw": row["pdf_raw"], "review_status": "pending",
                       "reviewer": None} for row in rows],
        })
    gold = json.loads(candidates_path.read_text(encoding="utf-8"))
    if gold["document_sha256"] != digest:
        raise ValueError("gold_candidates.json không cùng PDF")
    row_by_key = {(row["page"], row["table_id"], row["row_id"], row["column"]): row
                  for row in rows}
    if len(row_by_key) != len(rows):
        raise ValueError("IR có ô trùng định danh")
    for item in gold["items"]:
        if item["review_status"] not in ("approved", "agent_visual_check"):
            continue
        key = item["page"], item["table_id"], item["row_id"], item["column"]
        current = row_by_key.get(key)
        if current is None or current["code"] != item["code"] or current["bbox"] != item["bbox"]:
            raise ValueError(f"Nhãn gold đã duyệt không còn khớp vị trí ô IR: {key}")
    if any(item["review_status"] == "approved" and not item.get("reviewer")
           for item in gold["items"]):
        raise ValueError("Ô gold đã duyệt phải ghi reviewer")
    gold_by_key = {(item["page"], item["table_id"], item["row_id"], item["column"]): item
                   for item in gold["items"] if item["review_status"] == "approved"}
    visual_by_key = {(item["page"], item["table_id"], item["row_id"], item["column"]): item
                     for item in gold["items"] if item["review_status"] == "agent_visual_check"}
    approved = [row for row in rows if (row["page"], row["table_id"], row["row_id"], row["column"])
                in gold_by_key]
    gold_matched = sum(_value(row["ir_raw"]) == _value(gold_by_key[
        row["page"], row["table_id"], row["row_id"], row["column"]]["gold_raw"]) for row in approved)
    visual_checked = [row for row in rows if (row["page"], row["table_id"], row["row_id"], row["column"])
                      in visual_by_key]
    visual_matched = sum(_value(row["ir_raw"]) == _value(visual_by_key[
        row["page"], row["table_id"], row["row_id"], row["column"]]["gold_raw"])
                         for row in visual_checked)
    result = {"method": "independent_poppler_bbox_layout_word_comparison",
              "human_gold_set": bool(approved), "document_sha256": digest,
              "cells_total": len(rows), "cells_matched": matched,
              "cells_mismatched": sum(row["status"] == "mismatch" for row in rows),
              "cells_without_pdf_word": sum(row["status"] == "no_pdf_word" for row in rows),
              "exact_agreement": matched / len(rows) if rows else None,
              "gold_approved_cells": len(approved), "gold_matched_cells": gold_matched,
              "gold_accuracy": gold_matched / len(approved) if approved else None,
              "agent_visual_checked_cells": len(visual_checked),
              "agent_visual_matched_cells": visual_matched,
              "per_cell": rows}
    save_json(ir_dir / "cell_evaluation.json", result)
    return result


def main() -> int:
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--ir-dir", type=Path)
    args = parser.parse_args()
    pdf = args.pdf.resolve()
    ir_dir = args.ir_dir or Path("ocr_router_out") / pdf.stem / "annual_ir"
    result = evaluate(pdf, ir_dir)
    print(json.dumps({key: value for key, value in result.items() if key != "per_cell"},
                     ensure_ascii=False, indent=2))
    return 0 if result["cells_mismatched"] == result["cells_without_pdf_word"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
