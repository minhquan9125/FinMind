"""Map common-template aliases to extracted rows.

Usage: python src/mapCommonLabels.py <input-ir.json> <common-template.json> <output-ir.json>
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path


def key(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip().lower()


def match_label(label: str, template: dict, index: dict[str, list[tuple[dict, str]]]) -> dict:
    label_key = key(label)
    matches = [(metric, alias) for metric, alias in index.get(label_key, [])
               if not any(key(phrase) in label_key for phrase in metric.get("exclude_patterns", []))]
    ids = sorted({metric["metric_id"] for metric, _ in matches})
    base = {"candidate_ids": ids, "matched_alias": matches[0][1] if matches else None,
            "template_schema_version": template["schema_version"]}
    if not ids:
        return {**base, "status": "no_match", "metric_id": None}
    if len(ids) > 1:
        return {**base, "status": "ambiguous", "metric_id": None}
    requires_context = any(key(alias) == label_key
                           for metric, _ in matches for alias in metric.get("context_required_aliases", []))
    if requires_context:
        return {**base, "status": "context_required", "metric_id": None}
    return {**base, "status": "candidate", "metric_id": ids[0]}


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    input_path, template_path, output_path = map(Path, sys.argv[1:])
    page = json.loads(input_path.read_text(encoding="utf-8"))
    template = json.loads(template_path.read_text(encoding="utf-8"))
    if template.get("sector_id") != "common" or not isinstance(template.get("metrics"), list) or not isinstance(page.get("blocks"), list):
        raise ValueError("Expected a common template and a page IR with blocks")
    index: dict[str, list[tuple[dict, str]]] = {}
    for metric in template["metrics"]:
        for alias in metric.get("aliases", []):
            index.setdefault(key(alias), []).append((metric, alias))
    for block in page["blocks"]:
        if block["type"] != "table":
            continue
        for row in block.get("rows", []):
            row["metric_match"] = match_label(row["label_raw"], template, index)
    output_path.write_text(json.dumps(page, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
