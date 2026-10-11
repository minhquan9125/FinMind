"""Compare same-period statement values across two already-built annual IR reports.

Usage:
    py src/compareFinancialReports.py
    py src/compareFinancialReports.py --left <annual_ir_dir> --right <annual_ir_dir>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from financialContent import compare_accounting_reports


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEFT = ROOT / "ocr_router_out" / "FPT_2024_498332 (1)" / "annual_ir"
DEFAULT_RIGHT = ROOT / "ocr_router_out" / "BCTN_2025" / "annual_ir"


def _load_report(directory: Path) -> tuple[list[dict[str, Any]], Path, dict[str, Any]]:
    table_dir = directory / "table"
    index_path = table_dir / "index.json"
    if not index_path.is_file():
        raise FileNotFoundError(f"Thiếu table/index.json: {index_path}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    pages = [json.loads(path.read_text(encoding="utf-8"))
             for path in sorted(table_dir.glob("p-*.ir.json"))]
    if not pages:
        raise ValueError(f"Không có IR trang bảng trong {table_dir}")
    return pages, index_path, index


def compare_and_write(left_dir: Path, right_dir: Path) -> dict[str, Any]:
    left_pages, left_index_path, left_index = _load_report(left_dir)
    right_pages, right_index_path, right_index = _load_report(right_dir)
    checks, summary = compare_accounting_reports(left_pages, right_pages)
    if not checks:
        raise ValueError("Hai báo cáo không có ô cùng mã, cùng kỳ để đối chiếu")
    left_name = left_pages[0].get("source", {}).get("file_name") or left_dir.name
    right_name = right_pages[0].get("source", {}).get("file_name") or right_dir.name
    for index, peer in ((left_index, right_name), (right_index, left_name)):
        index["cross_report_peer"] = peer
        index["cross_report_summary"] = summary
        index["cross_report_checks"] = checks
    left_index_path.write_text(json.dumps(left_index, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8", newline="\n")
    right_index_path.write_text(json.dumps(right_index, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8", newline="\n")
    return {"left": left_name, "right": right_name, **summary,
            "mismatches": [check for check in checks if check["status"] != "match"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, default=DEFAULT_LEFT,
                        help="First annual_ir output directory")
    parser.add_argument("--right", type=Path, default=DEFAULT_RIGHT,
                        help="Second annual_ir output directory")
    args = parser.parse_args(argv)
    result = compare_and_write(args.left.resolve(), args.right.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
