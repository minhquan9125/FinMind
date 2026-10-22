"""Explicitly approved workbook unit mappings for controlled financial reads."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class InferredUnitError(ValueError):
    pass


def load_inferred_unit_overrides(path: Path) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "financial-unit-inference-v1":
        raise InferredUnitError("INVALID_INFERENCE_SCHEMA")
    if data.get("status") != "WORKBOOK_APPROVED":
        raise InferredUnitError("INVALID_WORKBOOK_APPROVAL_STATUS")
    if data.get("database_writes") is not False:
        raise InferredUnitError("WORKBOOK_APPROVAL_CANNOT_WRITE_DATABASE")
    overrides: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for item in data.get("overrides", []):
        if item.get("status") != "WORKBOOK_APPROVED":
            raise InferredUnitError("INVALID_WORKBOOK_APPROVAL")
        key = (
            str(item["symbol"]).upper(),
            item["period"],
            item["section"],
            item["code"],
        )
        if key in overrides:
            raise InferredUnitError("DUPLICATE_INFERENCE")
        if item.get("inferred_unit") != "VND" or item.get("inferred_currency") != "VND":
            raise InferredUnitError("UNSUPPORTED_INFERENCE_UNIT")
        if item.get("inferred_scale") != 1:
            raise InferredUnitError("UNSUPPORTED_INFERENCE_SCALE")
        overrides[key] = item
    return overrides
