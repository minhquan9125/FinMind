"""Financial Observation Generator: Bridges Document IR tables to FinMind metrics.

Constructs verified financial observations from statement table cells,
mapping statutory line codes to canonical FinMind metric_ids and attaching
arithmetic verification status.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any

from crosswalk import CrosswalkRegistry

_ACCOUNTING_STATEMENTS = {"balance_sheet", "income_statement", "cash_flow"}


def _detect_unit_multiplier(text: str | None) -> tuple[int, str]:
    """Detect monetary unit multiplier and currency from header or unit text."""
    if not text:
        return 1, "VND"
    lower = text.lower()
    currency = "USD" if re.search(r"\b(?:usd|đô la|dollar)\b", lower) else "VND"

    # If the text is long (e.g. page context with company names), only inspect the 'đơn vị' section
    if len(text) > 80:
        m = re.search(r"(?:đơn vị(?: tính)?|đvt)\s*:\s*([^,;\n\.]+)", lower)
        target = m.group(1) if m else ""
    else:
        target = lower

    if re.search(r"\b(?:tỷ|billion|ty\s*(?:đồng|dong|vnd))\b", target):
        return 1_000_000_000, currency
    if re.search(r"\b(?:triệu|trieu|million)\b", target):
        return 1_000_000, currency
    if re.search(r"\b(?:nghìn|nghin|thousand)\b", target):
        return 1_000, currency
    return 1, currency


def _extract_equation_cells_from_template(
    template_data: dict[str, Any],
) -> dict[str, list[str]]:
    """Map equation name -> list of child codes involved."""
    eq_children: dict[str, list[str]] = defaultdict(list)
    for line in template_data.get("template_lines", []):
        if not line.get("is_memo", False):
            eq_name = f"{line['statement']}:{line['parent']}"
            eq_children[eq_name].append(str(line["code"]))
    for rule in template_data.get("arithmetic_rules", []):
        eq_name = rule["name"]
        for child in rule.get("children", []):
            eq_children[eq_name].append(str(child["code"]))
    return eq_children


def build_financial_observations(
    documents: list[dict[str, Any]],
    accounting_standard: str | None,
    checks: list[dict[str, Any]],
    skipped_checks: list[dict[str, Any]],
    template_data: dict[str, Any] | None = None,
    crosswalk: CrosswalkRegistry | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Transform financial table cells into canonical FinMind observations.

    Returns:
        (observations_list, summary_statistics)
    """
    if not accounting_standard:
        return [], {
            "total_observations": 0,
            "verified_observations": 0,
            "unverified_observations": 0,
            "failed_observations": 0,
            "needs_review_observations": 0,
            "mapped_metrics_count": 0,
        }

    registry = crosswalk or CrosswalkRegistry()
    eq_children = _extract_equation_cells_from_template(template_data or {})

    # Build maps of verified vs failed (statement, period_end, code) from checks
    passed_cells: set[tuple[str, str, str]] = set()
    failed_cells: set[tuple[str, str, str]] = set()

    for check in checks:
        name = check["name"]
        p_end = check.get("period_end", "")
        p_passed = check.get("passed", False)
        target_set = passed_cells if p_passed else failed_cells

        # Result code (parent)
        res_code = check.get("result_code")
        if res_code:
            # name format is typically "{statement}:{parent}"
            stmt = name.split(":", 1)[0] if ":" in name else "balance_sheet"
            target_set.add((stmt, p_end, str(res_code)))

        # Child codes in this equation
        for child_code in eq_children.get(name, []):
            stmt = name.split(":", 1)[0] if ":" in name else "balance_sheet"
            target_set.add((stmt, p_end, child_code))

        # Cross statement rules
        if check.get("source") == "cross_statement" and template_data:
            for rule in template_data.get("cross_statement_rules", []):
                if rule["name"] == name:
                    target_set.add((rule["left"]["statement"], p_end, str(rule["left"]["code"])))
                    target_set.add((rule["right"]["statement"], p_end, str(rule["right"]["code"])))

    # Import parsing functions from financialContent
    from financialContent import _accounting_period, _parse_accounting_number

    observations_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    mapped_metric_ids: set[str] = set()

    for page in documents:
        kind = page.get("page_class")
        if kind not in _ACCOUNTING_STATEMENTS:
            continue

        context = "\n".join(
            str(item.get("text", ""))
            for item in page.get("blocks", [])
            if item.get("type") in ("heading", "paragraph")
        )

        for block in page.get("blocks", []):
            if block.get("type") != "table":
                continue

            # Unit multiplier for this table
            table_unit_multiplier, table_currency = _detect_unit_multiplier(
                block.get("unit_text") or context
            )

            columns = block.get("columns", [])
            col_periods = {
                col["key"]: _accounting_period(col.get("header_lines", []), kind, context)
                for col in columns
            }

            for row in block.get("rows", []):
                code = row.get("code")
                if not code:
                    continue

                entry = registry.lookup(accounting_standard, kind, str(code))
                if not entry:
                    continue

                mapped_metric_ids.add(entry.metric_id)

                for col_key, cell in row.get("cells", {}).items():
                    period = col_periods.get(col_key)
                    if not period:
                        continue

                    period_end, period_type, period_role = period
                    raw_val = cell.get("raw")
                    parsed_num = _parse_accounting_number(raw_val)

                    # Determine cell-specific unit multiplier if specified in column header
                    col_headers = " ".join(
                        next((c.get("header_lines", []) for c in columns if c["key"] == col_key), [])
                    )
                    col_multiplier, col_currency = _detect_unit_multiplier(col_headers)
                    multiplier = col_multiplier if col_multiplier > 1 else table_unit_multiplier
                    currency = col_currency if col_currency != "VND" else table_currency

                    # Verification status determination
                    cell_key = (kind, period_end, str(code))
                    if (
                        cell.get("needs_review", False)
                        or (parsed_num is None and raw_val is not None)
                    ):
                        v_status = "needs_review"
                    elif cell_key in failed_cells:
                        v_status = "arithmetic_failed"
                    elif cell_key in passed_cells:
                        v_status = "arithmetic_verified"
                    else:
                        v_status = "unverified_optional"

                    # Normalize numeric value with sign convention
                    norm_value: int | float | None = None
                    if parsed_num is not None:
                        val = parsed_num * multiplier
                        if entry.sign_convention == "positive_magnitude":
                            val = abs(val)
                        norm_value = int(val) if val % 1 == 0 else float(val)

                    obs_key = (entry.metric_id, period_end, period_role)
                    if obs_key in observations_by_key:
                        # Merge pages if observation already registered
                        existing = observations_by_key[obs_key]
                        if page["page"] not in existing["pdf_pages"]:
                            existing["pdf_pages"].append(page["page"])
                            existing["pdf_pages"].sort()
                        continue

                    obs = {
                        "metric_id": entry.metric_id,
                        "statement": kind,
                        "accounting_standard": accounting_standard,
                        "code": str(code),
                        "label_raw": str(row.get("label_raw", "")).strip(),
                        "standard_label": entry.standard_label,
                        "period_end": period_end,
                        "period_type": period_type,
                        "period_role": period_role,
                        "raw": raw_val,
                        "numeric_value": norm_value,
                        "currency": currency,
                        "unit_multiplier": multiplier,
                        "sign_convention": entry.sign_convention,
                        "verification_status": v_status,
                        "pdf_pages": [page["page"]],
                        "table_id": block.get("id"),
                        "row_id": row.get("id"),
                        "column_key": col_key,
                        "cell_bbox": cell.get("bbox"),
                    }
                    observations_by_key[obs_key] = obs

    observations = list(observations_by_key.values())
    observations.sort(key=lambda o: (o["statement"], o["code"], o["period_end"]))

    summary = {
        "total_observations": len(observations),
        "verified_observations": sum(
            1 for o in observations if o["verification_status"] == "arithmetic_verified"
        ),
        "unverified_observations": sum(
            1 for o in observations if o["verification_status"] == "unverified_optional"
        ),
        "failed_observations": sum(
            1 for o in observations if o["verification_status"] == "arithmetic_failed"
        ),
        "needs_review_observations": sum(
            1 for o in observations if o["verification_status"] == "needs_review"
        ),
        "mapped_metrics_count": len(mapped_metric_ids),
    }

    return observations, summary
