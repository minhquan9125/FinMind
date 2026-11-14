"""Crosswalk Registry: Mapping statutory accounting line codes to FinMind metric_ids.

Provides decoupled, two-way bridge between Vietnamese accounting standards
(TT200/TT202, TT99/2025) and canonical FinMind business metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

DEFAULT_MAPPINGS_DIR = Path(__file__).resolve().parents[1] / "mappings"
DEFAULT_CATALOG_DIR = Path(__file__).resolve().parents[3] / "templates"


@dataclass(frozen=True)
class CrosswalkEntry:
    statement: str
    code: str
    metric_id: str
    standard_label: str
    sign_convention: str = "positive_magnitude"
    period_type: str | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrosswalkEntry:
        return cls(
            statement=data["statement"],
            code=str(data["code"]),
            metric_id=data["metric_id"],
            standard_label=data.get("standard_label", ""),
            sign_convention=data.get("sign_convention", "positive_magnitude"),
            period_type=data.get("period_type"),
            notes=data.get("notes"),
        )

    def to_dict(self) -> dict[str, Any]:
        res = {
            "statement": self.statement,
            "code": self.code,
            "metric_id": self.metric_id,
            "standard_label": self.standard_label,
            "sign_convention": self.sign_convention,
        }
        if self.period_type:
            res["period_type"] = self.period_type
        if self.notes:
            res["notes"] = self.notes
        return res


class CrosswalkRegistry:
    """Registry maintaining statutory line code to FinMind metric_id mappings."""

    _STANDARD_FILES = {
        "TT200_NONBANK": "tt200_nonbank_crosswalk.json",
        "LEGACY_NONBANK": "tt200_nonbank_crosswalk.json",
        "TT99_2025": "tt99_2025_crosswalk.json",
    }

    def __init__(self, mappings_dir: Path | None = None) -> None:
        self.mappings_dir = mappings_dir or DEFAULT_MAPPINGS_DIR
        self._cache: dict[str, dict[tuple[str, str], CrosswalkEntry]] = {}

    def get_mapping(self, standard: str) -> dict[tuple[str, str], CrosswalkEntry]:
        """Load and return {(statement, code): CrosswalkEntry} for the given standard."""
        if standard in self._cache:
            return self._cache[standard]

        filename = self._STANDARD_FILES.get(standard)
        if not filename:
            return {}

        file_path = self.mappings_dir / filename
        if not file_path.is_file():
            return {}

        data = json.loads(file_path.read_text(encoding="utf-8"))
        entries: dict[tuple[str, str], CrosswalkEntry] = {}
        for item in data.get("entries", []):
            entry = CrosswalkEntry.from_dict(item)
            entries[(entry.statement, entry.code)] = entry

        self._cache[standard] = entries
        return entries

    def lookup(self, standard: str, statement: str, code: str | None) -> CrosswalkEntry | None:
        """Find the crosswalk entry for a specific (standard, statement, code)."""
        if not code:
            return None
        mapping = self.get_mapping(standard)
        return mapping.get((statement, str(code)))

    def validate_against_catalog(self, catalog_path: Path) -> list[str]:
        """Validate that all metric_ids in loaded crosswalks exist in FinMind catalog."""
        if not catalog_path.is_file():
            return [f"Catalog file not found: {catalog_path}"]

        catalog_data = json.loads(catalog_path.read_text(encoding="utf-8"))
        valid_metric_ids = {m["metric_id"] for m in catalog_data.get("metrics", [])}

        errors: list[str] = []
        for standard, filename in self._STANDARD_FILES.items():
            file_path = self.mappings_dir / filename
            if not file_path.is_file():
                continue
            data = json.loads(file_path.read_text(encoding="utf-8"))
            for entry in data.get("entries", []):
                metric_id = entry.get("metric_id")
                if metric_id not in valid_metric_ids:
                    errors.append(
                        f"[{standard}] metric_id '{metric_id}' (code {entry.get('code')}) "
                        f"not found in catalog {catalog_path.name}"
                    )
        return errors
