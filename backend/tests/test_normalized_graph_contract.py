"""Regression checks for the tracked Vietcap/price snapshots at graph ingestion."""

import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import pytest

from src.graph import ContractError, load_dataset, to_graph
from src.graph.contract import validate_dataset


ROOT = Path(__file__).resolve().parents[2] / "data" / "normalized"
SYMBOLS = ("BID", "CMG", "CTG", "ELC", "FPT", "ICT", "ITD", "MBB", "TCB", "VCB")
FIRST_SESSION = "2025-01-01"
LAST_SESSION = "2026-12-31"


@lru_cache(maxsize=len(SYMBOLS))
def snapshot(symbol):
    return json.loads((ROOT / f"{symbol}.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=len(SYMBOLS))
def project(symbol):
    path = ROOT / f"{symbol}.json"
    return to_graph(load_dataset(path), source_file=path.name)


@pytest.fixture(scope="module", autouse=True)
def release_snapshot_cache():
    yield
    project.cache_clear()
    snapshot.cache_clear()


def recent_sessions():
    for symbol in SYMBOLS:
        for index, bar in enumerate(snapshot(symbol)["price_history"]):
            if FIRST_SESSION <= bar["date"] <= LAST_SESSION:
                yield pytest.param(symbol, index, id=f"{symbol}-{bar['date']}")


@pytest.mark.parametrize("symbol,index", list(recent_sessions()))
def test_trading_session_preserves_identity_ohlcv_and_source_pointer(symbol, index):
    source = snapshot(symbol)
    bar = source["price_history"][index]
    graph = project(symbol)
    price = graph.prices[index]
    assert price["id"] == f"{symbol}:{source['dataset_version']}:{bar['date']}"
    assert price["source"] == source["sources"]["prices"]
    assert price["source_file"] == f"{symbol}.json"
    assert price["json_pointer"] == f"/price_history/{index}"
    assert json.loads(price["payload_json"]) == bar
    assert {key: price[key] for key in bar} == bar


@pytest.mark.parametrize("symbol", SYMBOLS)
def test_complete_graph_snapshot_preserves_reporting_periods_and_checksum(symbol):
    source = snapshot(symbol)
    graph = project(symbol)
    expected_reports = {
        (section, row["period_label"]): row
        for section, rows in source["financial_data"].items()
        for row in rows
    }
    assert len(graph.reports) == len(expected_reports)
    assert {item["id"] for item in graph.periods} == {period for _, period in expected_reports}
    for report in graph.reports:
        expected = expected_reports[report["section"], report["period_label"]]
        assert json.loads(report["payload_json"]) == expected
        assert report["source"] == source["sources"]["fundamentals"]
    assert len(graph.prices) == len(source["price_history"])
    payload_json = graph.dataset["payload_json"]
    assert json.loads(payload_json) == source
    assert graph.dataset["checksum"] == hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


@pytest.fixture
def small_snapshot():
    original = snapshot("ICT")
    bar = deepcopy(original["price_history"][0])
    financial = {section: [deepcopy(rows[0])] for section, rows in original["financial_data"].items()}
    return {
        **original,
        "sources": dict(original["sources"]),
        "price_history": [bar],
        "financial_data": financial,
        "meta": {
            **original["meta"], "total_price_sessions": 1, "price_start_date": bar["date"],
            "price_end_date": bar["date"], "total_ratio_periods": 1, "total_income_periods": 1,
            "total_balance_sheet_periods": 1, "total_cash_flow_periods": 1,
        },
        "quality": {"status": "PASS", "issues": [], "raw_price_records": 1,
                    "published_price_records": 1, "rejected_price_records": 0},
    }


@pytest.mark.parametrize("section", ("ratios", "income_statement", "balance_sheet", "cash_flow_statement"))
def test_vietcap_internal_organ_code_preserves_exchange_ticker(small_snapshot, section):
    validate_dataset(small_snapshot)
    assert small_snapshot["financial_data"][section][0]["organCode"] == "CTIN"
    graph = to_graph(small_snapshot)
    assert graph.company == {"symbol": "ICT"}


@pytest.mark.parametrize(
    "provider,symbol,key,value,reason",
    [
        ("VIETCAP_VCI", "ICT", "organCode", "FPT", "organCode mismatch"),
        ("VIETCAP_VCI", "ICT", "organCode", ["ICT"], "organCode mismatch"),
        ("VIETCAP_VCI", "ICT", "ticker", "CTIN", "ticker mismatch"),
        ("OTHER", "ICT", "organCode", "CTIN", "organCode mismatch"),
        ("VIETCAP_VCI", "FPT", "organCode", "CTIN", "organCode mismatch"),
    ],
)
def test_provider_alias_cannot_bind_to_wrong_symbol_or_provider(
    small_snapshot, provider, symbol, key, value, reason
):
    small_snapshot["sources"] = {**small_snapshot["sources"], "fundamentals": provider}
    small_snapshot["symbol"] = symbol
    for rows in small_snapshot["financial_data"].values():
        rows[0]["organCode"] = symbol
        if "ticker" in rows[0]:
            rows[0]["ticker"] = symbol
    small_snapshot["financial_data"]["ratios"][0][key] = value
    with pytest.raises(ContractError, match=reason):
        validate_dataset(small_snapshot)


@pytest.mark.parametrize(
    "path,value,error",
    [
        (("schema_version",), "2.0", "Unsupported normalized"),
        (("symbol",), "ict", "uppercase stock code"),
        (("dataset_version",), "20261301T000000Z", "Invalid generated_at or"),
        (("generated_at",), "2001-01-01T00:00:00+07:00", "must be UTC"),
        (("sources", "fundamentals"), "", "provider code"),
        (("price_history", 0, "date"), "2025-02-30", "Invalid trading date"),
        (("price_history", 0, "open"), True, "Invalid OHLC value"),
        (("price_history", 0, "high"), 0.001, "Invalid OHLC bounds"),
        (("price_history", 0, "volume"), -1, "Invalid volume"),
        (("price_history", 0, "source_timestamp"), -1, "Invalid source_timestamp"),
        (("price_history", 0, "source_timestamp"), 0, "does not match Vietnam"),
        (("meta", "total_price_sessions"), True, "nonnegative integer"),
        (("meta", "total_price_sessions"), 9, "Price count mismatch"),
        (("meta", "price_start_date"), "", "Price bounds mismatch"),
        (("meta", "total_ratio_periods"), 2, "ratios count mismatch"),
        (("financial_data", "ratios", 0, "period_label"), "2026-Q5", "invalid period_label"),
        (("financial_data", "ratios", 0, "period_type"), "OTHER", "inconsistent period_type"),
        (("financial_data", "ratios", 0, "year"), False, "inconsistent year"),
        (("financial_data", "ratios", 0, "yearReport"), 1899, "inconsistent yearReport"),
        (("financial_data", "ratios", 0, "ratioType"), None, "invalid ratioType"),
        (("quality", "issues"), None, "must be a list"),
        (("quality", "issues"), [{"severity": "DEBUG"}], "Invalid quality issue"),
        (("quality", "status"), "PASS_WITH_WARNINGS", "Invalid quality status"),
        (("quality", "raw_price_records"), 2, "Quality count mismatch"),
    ],
)
def test_snapshot_boundary_rejects_invalid_rows(small_snapshot, path, value, error):
    # Keep an otherwise valid baseline for every individual mutation.
    for rows in small_snapshot["financial_data"].values():
        rows[0]["organCode"] = "ICT"
    current = small_snapshot
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value
    with pytest.raises(ContractError, match=error):
        validate_dataset(small_snapshot)


@pytest.mark.parametrize(
    "raw,error",
    [
        (b'{"symbol":"ICT","symbol":"FPT"}', "Duplicate JSON key"),
        (b'{"price":NaN}', "Nonfinite JSON"),
        (b"\xff", "Invalid dataset JSON"),
        (b'{"price":', "Invalid dataset JSON"),
    ],
)
def test_snapshot_parser_rejects_ambiguous_or_broken_json(tmp_path, raw, error):
    path = tmp_path / "invalid.json"
    path.write_bytes(raw)
    with pytest.raises(ContractError, match=error):
        load_dataset(path)
