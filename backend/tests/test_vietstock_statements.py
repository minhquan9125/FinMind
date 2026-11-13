"""Offline tests for the Vietstock BCTC catalog reader."""
import json
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.annual_reports.vietstock_download_annual import VietstockAnnualClient
from data_pipeline.financial_data import vietstock_statements as vs

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "vietstock_fpt_2025_statements.json").read_text(encoding="utf-8")
)


def row(title, url="https://static2.vietstock.vn/a.pdf", ms=1000, fid=1):
    return {"Title": title, "Url": url, "LastUpdate": f"/Date({ms})/", "FileInfoID": fid}


def test_parse_title():
    assert vs.parse_title("BCTC Hợp nhất Kiểm toán năm 2025") == {"scope": "CONSOLIDATED", "audit_status": "AUDITED"}
    assert vs.parse_title("BCTC Công ty mẹ quý 1 năm 2025") == {"scope": "SEPARATE", "audit_status": "NOT_STATED"}
    assert vs.parse_title("BCTC Riêng lẻ Soát xét 6 tháng") == {"scope": "SEPARATE", "audit_status": "REVIEWED"}
    assert vs.parse_title("Financial statements Q3") == {"scope": "UNKNOWN", "audit_status": "NOT_STATED"}
    assert vs.parse_title("BCTC Riêng quý 2")["scope"] == "SEPARATE"


def test_catalog_entries_from_fixture():
    out = vs.catalog_entries(FIXTURE["by_term"]["4"], symbol="FPT", year=2025, term_id=4)
    assert {e["scope"] for e in out} == {"CONSOLIDATED", "SEPARATE"} and len(out) == 2
    for e in out:
        assert e["period_code"] == "2025-Q3"
        assert e["url"] in {r["Url"] for r in FIXTURE["by_term"]["4"]}
    cons = next(e for e in out if e["scope"] == "CONSOLIDATED")
    assert cons["last_update"] == datetime.fromtimestamp(1761275715.630, tz=timezone.utc)
    assert cons["external_id"] == "522622" and cons["symbol"] == "FPT"


def test_year_period_and_skipped_terms():
    out = vs.catalog_entries(FIXTURE["by_term"]["1"], symbol="FPT", year=2025, term_id=1)
    assert {e["period_code"] for e in out} == {"2025-YEAR"}
    assert vs.catalog_entries(FIXTURE["by_term"]["9"], symbol="FPT", year=2025, term_id=9) == []


def test_duplicate_scope_keeps_latest():
    rows = [row("BCTC Hợp nhất quý 1", ms=1000, fid=1), row("BCTC Hợp nhất quý 1", ms=5000, fid=2)]
    out = vs.catalog_entries(rows, symbol="X", year=2025, term_id=2)
    assert len(out) == 1 and out[0]["external_id"] == "2"


def test_rejects_non_vietstock_url():
    rows = [row("BCTC Hợp nhất quý 1", url="https://evil.example.com/a.pdf")]
    assert vs.catalog_entries(rows, symbol="X", year=2025, term_id=2) == []


def test_unknown_scopes_not_merged_when_titles_odd():
    rows = [row("Something", fid=1), row("Hợp nhất", fid=2, ms=2)]
    out = vs.catalog_entries(rows, symbol="X", year=2025, term_id=2)
    assert sorted(e["scope"] for e in out) == ["CONSOLIDATED", "UNKNOWN"]


class FakeClient:
    def __init__(self, delay=1.0):
        self.calls = []
        self.delay = delay

    def document_type(self, vi, en, *, exact=False):
        assert exact and vi == "Báo cáo tài chính"
        return 7

    def reports_for(self, symbol, year, *, document_type_id, term_id):
        self.calls.append((symbol, year, document_type_id, term_id))
        return FIXTURE["by_term"].get(str(term_id), [])


def test_fetch_catalog():
    c = FakeClient()
    out = vs.fetch_catalog(c, "FPT", [2025])
    assert [x[3] for x in c.calls] == [1, 2, 3, 4, 5] and all(x[2] == 7 for x in c.calls)
    assert len(out) == 10


def test_annual_report_type_unchanged():
    client = VietstockAnnualClient(delay=0)
    client.post = lambda path, body: [
        {"DocumentTypeID": 1, "DocumentName": "Báo cáo tài chính", "DocumentNameEN": "Financial statements"},
        {"DocumentTypeID": 2, "DocumentName": "Báo cáo thường niên", "DocumentNameEN": "Annual report"},
    ]
    assert client.annual_report_type() == 2
    client.document_type_id = None
    assert client.document_type("tài chính", "financial statement") == 1


def test_fetch_catalog_requires_pacing():
    import pytest
    with pytest.raises(ValueError):
        vs.fetch_catalog(FakeClient(delay=0.6), "FPT", [2025])


def test_foreign_url_logged(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger=vs.__name__):
        vs.catalog_entries([row("BCTC Hợp nhất", url="https://evil.example.com/a.pdf", fid=9)],
                           symbol="X", year=2025, term_id=2)
    assert "X" in caplog.text and "2025-Q1" in caplog.text and "9" in caplog.text


def test_bad_date_kept_and_loses_to_real_date(caplog):
    import logging
    bad = {"Title": "BCTC Hợp nhất", "Url": "https://static2.vietstock.vn/a.pdf", "LastUpdate": None, "FileInfoID": 1}
    with caplog.at_level(logging.WARNING, logger=vs.__name__):
        out = vs.catalog_entries([bad], symbol="X", year=2025, term_id=2)
    assert len(out) == 1 and out[0]["last_update"] is None and caplog.text
    good = row("BCTC Hợp nhất", fid=2, ms=5)
    for rows in ([bad, good], [good, bad]):
        out = vs.catalog_entries(rows, symbol="X", year=2025, term_id=2)
        assert [e["external_id"] for e in out] == ["2"]


def test_document_type_exact_skips_explanation_type():
    client = VietstockAnnualClient(delay=0)
    client.post = lambda path, body: [
        {"DocumentTypeID": 8, "DocumentName": "Giải trình KQKD", "DocumentNameEN": "Explanation for Financial Statement"},
        {"DocumentTypeID": 1, "DocumentName": "Báo cáo tài chính", "DocumentNameEN": "Financial Statement"},
        {"DocumentTypeID": 2, "DocumentName": "Báo cáo thường niên", "DocumentNameEN": "Annual report"},
    ]
    assert client.document_type("Báo cáo tài chính", "Financial Statement", exact=True) == 1
    assert client.annual_report_type() == 2
