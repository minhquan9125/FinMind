"""Apply explicit PDF-review overrides to mapped rows.

Usage: python src/applyPdfReview.py <mapped-ir.json> <review-overrides.json> <output-ir.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    input_path, review_path, output_path = map(Path, sys.argv[1:])
    page = json.loads(input_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if page["page"] != review["physical_page"]:
        raise ValueError("IR and PDF review page do not match")
    page["source"] = {**page.get("source", {}), "document_name": 
    review["pdf_document"],
                      "physical_page": review["physical_page"], "printed_page": review["printed_page"],
                      "form_code": review["form_code"]}
    applied = 0
    for block in page["blocks"]:
        if block["type"] != "table":
            continue
        for row in block.get("rows", []):
            override = review["overrides"].get(row.get("ma_so")) if row.get("ma_so") else None
            if override:
                metric_id = override.get("metric_id")
                row["metric_match"] = {
                    "status": override["status"], "metric_id": metric_id,
                    "candidate_ids": [metric_id] if metric_id else [],
                    "matched_alias": override.get("matched_alias"),
                    "template_schema_version": review["template_schema_version"],
                    "match_method": override["match_method"],
                    "review_evidence": override["review_evidence"],
                    "suggested_metric_id": override.get("suggested_metric_id"),
                }
                applied += 1
            elif row.get("metric_match"):
                row["metric_match"]["match_method"] = "exact_alias"
    output_path.write_text(json.dumps(page, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Applied {applied} PDF review decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
