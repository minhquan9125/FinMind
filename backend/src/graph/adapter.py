"""Project normalized JSON into versioned graph records without mutation."""

from __future__ import annotations

import hashlib

from .contract import (GRAPH_VERSION, REPORT_METADATA, SECTIONS, GraphDataset,
                       canonical_json, period_from_row, validate_dataset)


def _pointer_key(key):
    return key.replace("~", "~0").replace("/", "~1")


def _value_type(value):
    if value is None:
        return "null"
    return {bool: "boolean", int: "integer", float: "number", str: "string",
            list: "array", dict: "object"}[type(value)]


def to_graph(payload: dict, *, source_file: str = "") -> GraphDataset:
    """Validate and adapt a normalized snapshot, retaining every provider value."""
    validate_dataset(payload)
    payload_json = canonical_json(payload)
    symbol = payload["symbol"]
    dataset_id = f"{symbol}:{payload['dataset_version']}"
    dataset = {
        "id": dataset_id, "symbol": symbol,
        "dataset_version": payload["dataset_version"],
        "schema_version": payload["schema_version"], "graph_version": GRAPH_VERSION,
        "generated_at": payload["generated_at"], "source_file": str(source_file),
        "checksum": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "payload_json": payload_json, "quality_json": canonical_json(payload["quality"]),
        "sources_json": canonical_json(payload["sources"]),
        "meta_json": canonical_json(payload["meta"]),
    }
    periods, metrics = {}, {}
    reports, observations, prices = [], [], []
    source = payload["sources"]["fundamentals"]
    for section in SECTIONS:
        for index, row in enumerate(payload["financial_data"][section]):
            period = period_from_row(row, section)
            periods[period["id"]] = period
            report_id = f"{dataset_id}:{section}:{period['id']}"
            pointer = f"/financial_data/{section}/{index}"
            reports.append({
                "id": report_id, "section": section, "period_label": period["id"],
                "source": source, "basis": row.get("ratioType", "UNSPECIFIED"),
                "payload_json": canonical_json(row), "source_file": str(source_file),
                "json_pointer": pointer,
            })
            for code, value in row.items():
                if code in REPORT_METADATA:
                    continue
                metric_id = f"{source}:{section}:{code}"
                metrics[metric_id] = {"id": metric_id, "code": code, "section": section,
                                      "source": source, "unit_status": "UNKNOWN"}
                numeric = None
                if type(value) is float or (type(value) is int and -2**63 <= value < 2**63):
                    numeric = value
                observations.append({
                    "id": f"{report_id}:{code}", "report_id": report_id,
                    "metric_id": metric_id, "code": code, "value": numeric,
                    "value_json": canonical_json(value), "value_type": _value_type(value),
                    "is_null": value is None, "json_pointer": f"{pointer}/{_pointer_key(code)}",
                })
    for index, row in enumerate(payload["price_history"]):
        prices.append({
            **{key: row[key] for key in
               ("date", "open", "high", "low", "close", "volume", "source_timestamp")},
            "id": f"{dataset_id}:{row['date']}", "source": payload["sources"]["prices"],
            "source_file": str(source_file), "json_pointer": f"/price_history/{index}",
            "payload_json": canonical_json(row),
        })
    return GraphDataset({"symbol": symbol}, dataset, tuple(periods.values()),
                        tuple(reports), tuple(metrics.values()), tuple(observations), tuple(prices))
