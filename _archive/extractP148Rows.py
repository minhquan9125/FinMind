"""Page 148 demonstration: extract table rows from pdftotext output.

Usage: python src/extractP148Rows.py <p-148.txt> <starter-ir.json> <output-ir.json>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


AMOUNT = re.compile(r"^\(?[\d.]+\)?$")
CODE = re.compile(r"(?:^|\s)(1\d{2})\s{2,}")


def extract_rows(text: str) -> list[dict]:
    rows = []
    for index, line in enumerate(text.splitlines(), 1):
        match = CODE.search(line)
        if not match:
            continue
        code = match[1]
        parts = re.split(r"\s{2,}", line[match.end():].strip())
        if len(parts) not in (3, 4) or not AMOUNT.fullmatch(parts[-2]) or not AMOUNT.fullmatch(parts[-1]):
            raise ValueError(f"Cannot parse source line {index}, mã số {code}: {line}")
        has_note = len(parts) == 4
        rows.append({"ma_so": code, "label_raw": parts[0],
                     "note": parts[1] if has_note else None, "bbox": None,
                     "cells": {"c1": {"raw": parts[-2], "bbox": None},
                               "c2": {"raw": parts[-1], "bbox": None}}})
    if not rows:
        raise ValueError("No table rows found")
    return rows


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    text_path, starter_path, output_path = map(Path, sys.argv[1:])
    page = json.loads(starter_path.read_text(encoding="utf-8"))
    tables = [block for block in page["blocks"] if block["type"] == "table"]
    if len(tables) != 1:
        raise ValueError("Starter IR must have exactly one table")
    tables[0]["rows"] = extract_rows(text_path.read_text(encoding="utf-8"))
    output_path.write_text(json.dumps(page, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(tables[0]['rows'])} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
