from src.json_ingest import (
    financial_json_to_pages,
    generic_json_to_pages,
    is_normalized_financial_payload,
)


def _sample_financial_payload():
    return {
        "symbol": "SSI",
        "price_history": [
            {"date": "2024-01-02", "open": 30.0, "high": 31.0, "low": 29.5, "close": 30.5, "volume": 1000},
            {"date": "2024-01-03", "open": 30.5, "high": 32.0, "low": 30.0, "close": 31.5, "volume": 2000},
            {"date": "2024-02-01", "open": 31.5, "high": 33.0, "low": 31.0, "close": 32.0, "volume": 1500},
        ],
        "financial_data": {
            "ratios": [
                {"period_label": "2024-Q1", "period_type": "QUARTER", "year": 2024, "quarter": 1,
                 "pe": 11.5, "roe": 0.13, "organCode": "SSI", "ratioTTMId": 1},
            ],
            "income_statement": [
                {"period_label": "2024-Q1", "period_type": "QUARTER", "organCode": "SSI",
                 "isa1": 123456.0, "isa2": None},
            ],
            "balance_sheet": [
                {"period_label": "2024-Q1", "period_type": "QUARTER", "bsa53": 999.0},
            ],
            "cash_flow_statement": [
                {"period_label": "2024-Q1", "period_type": "QUARTER", "cfa1": 42.0},
            ],
        },
    }


def test_is_normalized_financial_payload_detects_schema():
    assert is_normalized_financial_payload(_sample_financial_payload())
    assert not is_normalized_financial_payload({"foo": "bar"})
    assert not is_normalized_financial_payload([1, 2, 3])


def test_financial_json_to_pages_groups_prices_by_month():
    pages = financial_json_to_pages("SSI", _sample_financial_payload())
    price_pages = [p for p in pages if p.page == 0]
    assert len(price_pages) == 1
    text = price_pages[0].text
    assert "tháng 2024-01" in text
    assert "tháng 2024-02" in text
    assert "SSI" in text


def test_financial_json_to_pages_one_page_per_period_per_section():
    pages = financial_json_to_pages("SSI", _sample_financial_payload())
    by_section = {1: 0, 2: 0, 3: 0, 4: 0}
    for p in pages:
        if p.page in by_section:
            by_section[p.page] += 1
    assert by_section == {1: 1, 2: 1, 3: 1, 4: 1}


def test_financial_json_to_pages_ratio_uses_readable_label_and_drops_meta():
    pages = financial_json_to_pages("SSI", _sample_financial_payload())
    ratio_page = next(p for p in pages if p.page == 1)
    assert "P/E" in ratio_page.text
    assert "ROE" in ratio_page.text
    assert "ratioTTMId" not in ratio_page.text


def test_financial_json_to_pages_statement_drops_none_values():
    pages = financial_json_to_pages("SSI", _sample_financial_payload())
    income_page = next(p for p in pages if p.page == 2)
    assert "isa1:" in income_page.text
    assert "isa2" not in income_page.text  # value was None


def test_generic_json_to_pages_top_level_list():
    data = [{"name": "a", "value": 1}, {"name": "b", "value": 2}]
    pages = generic_json_to_pages(data)
    assert len(pages) == 2
    assert "name: a" in pages[0].text


def test_generic_json_to_pages_finds_nested_record_list():
    data = {"meta": "x", "rows": [{"a": 1}, {"a": 2}]}
    pages = generic_json_to_pages(data)
    assert len(pages) == 2
    assert all("rows #" in p.text for p in pages)


def test_generic_json_to_pages_fallback_dumps_whole_payload():
    data = {"a": {"nested": True}}
    pages = generic_json_to_pages(data)
    assert len(pages) == 1
    assert "nested" in pages[0].text
