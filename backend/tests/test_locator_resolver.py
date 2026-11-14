import asyncio

import pytest

from src.documents.locator_resolver import LocatorError, resolve_locator, verify_chunk


class FakeConn:
    """Answers each lookup with the rows it is given, in call order."""
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return self.answers.pop(0)


def run(coro):
    return asyncio.run(coro)


def loc(table, keys, source_id="s1", **extra):
    return {"source_table": table, "source_id": source_id, "row_keys": keys, **extra}


def test_financial_keys_resolve_to_observations_of_the_report():
    ref = resolve_locator(loc("financial_reports", ["o1", "o2"], "r9"))[0]
    assert "public.observations" in ref.sql and ref.params == ("r9", ["o1", "o2"]) and ref.expected == 2


def test_price_keys_split_into_day_month_and_id():
    refs = resolve_locator(loc("price_bars", ["FPT:2026-10-01", "FPT:2026-10:summary", "123", "124"]))
    assert [r.keys for r in refs] == [("FPT:2026-10-01",), ("FPT:2026-10:summary",), ("123", "124")]
    assert refs[0].params == ("FPT", "2026-10-01") and refs[1].expected == -1 and refs[2].expected == 2


def test_index_keys_use_the_index_table():
    refs = resolve_locator(loc("market_index_bars", ["VNINDEX:2026-10-01"]))
    assert "market_index_bars" in refs[0].sql and refs[0].params == ("VNINDEX", "2026-10-01")


def test_company_keys_must_be_known_columns():
    assert resolve_locator(loc("companies", ["FPT:exchange"]))[0].params == ("FPT",)
    with pytest.raises(LocatorError):
        resolve_locator(loc("companies", ["FPT:Sàn niêm yết"]))


@pytest.mark.parametrize("bad", [loc("news_articles", ["x1"]), loc("unknown", ["a"]), loc("price_bars", [])])
def test_bad_locators_raise(bad):
    with pytest.raises(LocatorError):
        resolve_locator(bad)


def test_locator_can_be_a_json_string():
    assert resolve_locator('{"source_table":"news_articles","source_id":"a","row_keys":["p1"]}')


def test_verify_financial_ok_and_missing_row():
    locator = loc("financial_reports", ["o1", "o2"], "r1")
    text = "Doanh thu (REV): 1.00 triệu VND | Lợi nhuận (NP): 2.00 triệu VND"
    ok = run(verify_chunk(FakeConn([{"key": "o1", "code": "REV"}, {"key": "o2", "code": "NP"}]), locator, text))
    assert ok.ok and ok.checked == 2
    bad = run(verify_chunk(FakeConn([{"key": "o1", "code": "REV"}]), locator, text))
    assert not bad.ok and "expected 2 rows" in bad.problems[0]


def test_verify_price_day_must_appear_in_text():
    locator = loc("price_bars", ["FPT:2026-10-01"])
    assert run(verify_chunk(FakeConn([{"key": "2026-10-01"}]), locator, "2026-10-01: mở 1")).ok
    result = run(verify_chunk(FakeConn([{"key": "2026-10-01"}]), locator, "2026-10-02: mở 1"))
    assert not result.ok and "2026-10-01" in result.problems[0]


def test_verify_price_summary_needs_at_least_one_row():
    locator = loc("price_bars", ["FPT:2026-10:summary"])
    assert not run(verify_chunk(FakeConn([]), locator, "Tổng kết tháng 2026-10")).ok
    assert run(verify_chunk(FakeConn([{"key": "2026-10-01"}]), locator, "Tổng kết tháng 2026-10")).ok


def test_verify_news_checks_url():
    locator = loc("news_articles", ["p1"], "a1", url="https://x/y")
    assert run(verify_chunk(FakeConn([{"key": "a1", "url": "https://x/y"}]), locator, "t")).ok
    assert not run(verify_chunk(FakeConn([{"key": "a1", "url": "https://other"}]), locator, "t")).ok


def test_verify_company_value_must_appear():
    locator = loc("companies", ["FPT:exchange"])
    row = {"symbol": "FPT", "exchange": "HOSE", "company_name": "FPT", "industry_type": None,
           "sector": None, "is_active": True}
    assert run(verify_chunk(FakeConn([row]), locator, "Sàn niêm yết: HOSE")).ok
    assert not run(verify_chunk(FakeConn([row]), locator, "Sàn niêm yết: HNX")).ok


def test_verify_reports_unresolvable_locator_instead_of_raising():
    result = run(verify_chunk(FakeConn(), {"source_table": "x", "row_keys": ["a"]}, ""))
    assert not result.ok and "unsupported" in result.problems[0]


def test_sample_takes_a_few_chunks_of_every_table():
    import importlib.util, pathlib
    path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "verify_locators.py"
    spec = importlib.util.spec_from_file_location("verify_locators", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    chunks = [{"chunk_id": str(i), "locator": {"source_table": "price_bars" if i % 2 else "companies"}}
              for i in range(40)]
    picked = module.sample(chunks, 3)
    tables = [c["locator"]["source_table"] for c in picked]
    assert tables.count("price_bars") == 3 and tables.count("companies") == 3
    assert picked == module.sample(chunks, 3)  # deterministic
