"""Validate one-page Document IR against the schema and cross-field rules.

Usage: python src/validate_ir.py path/to/page.ir.json
       python src/validate_ir.py path/to/four-tables.ir.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA = Path(__file__).resolve().parents[1] / "Document IR" / "ir-v1.schema.json"


def semantic_errors(ir: dict) -> list[str]:
    errors: list[str] = []
    width = ir["page_size"]["width"]
    height = ir["page_size"]["height"]
    merged = ir["source"]["engine"] == "MERGED"

    def check_bbox(path: str, box: list[float] | None) -> None:
        if box is None:
            return
        x0, y0, x1, y1 = box
        if x0 > x1 or y0 > y1:
            errors.append(f"{path}: bbox ngược chiều")
        if x1 > width or y1 > height:
            errors.append(f"{path}: bbox ra ngoài trang")

    block_ids: set[str] = set()
    for block in ir["blocks"]:
        block_id = block["id"]
        if block_id in block_ids:
            errors.append(f"{block_id}: trùng id block")
        block_ids.add(block_id)
        check_bbox(block_id, block["bbox"])
        if block["type"] != "table":
            continue
        keys = [column["key"] for column in block["columns"]]
        if len(keys) != len(set(keys)):
            errors.append(f"{block_id}: trùng key cột")
        for column in block["columns"]:
            check_bbox(f"{block_id}/{column['key']}/header", column["bbox"])
        row_ids: set[str] = set()
        for row in block["rows"]:
            row_path = f"{block_id}/{row['id']}"
            if row["id"] in row_ids:
                errors.append(f"{row_path}: trùng id dòng")
            row_ids.add(row["id"])
            check_bbox(row_path, row["bbox"])
            if row.get("indent") is not None and row["indent"] > width:
                errors.append(f"{row_path}: indent ra ngoài trang")
            for key, cell in row["cells"].items():
                cell_path = f"{row_path}/{key}"
                if key not in keys:
                    errors.append(f"{cell_path}: cột không có trong columns")
                check_bbox(cell_path, cell["bbox"])
                if merged and not cell.get("votes"):
                    errors.append(f"{cell_path}: MERGED nhưng thiếu votes")
    return errors


def validate_page(ir: dict, validator: Draft202012Validator) -> list[str]:
    schema_errors = sorted(validator.iter_errors(ir), key=lambda e: list(map(str, e.path)))
    if schema_errors:
        return [f"{'/'.join(map(str, error.path)) or '$'}: {error.message}"
                for error in schema_errors]
    return semantic_errors(ir)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    pages = [("$", document)] if "blocks" in document else [
        (f"tables/{i}/pages/{j}", page)
        for i, table in enumerate(document["tables"])
        for j, page in enumerate(table["pages"])
    ]
    errors = [f"{path}/{error}" for path, page in pages
              for error in validate_page(page, validator)]
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print(f"OK: {len(pages)} page(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
