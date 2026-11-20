from decimal import Decimal
from io import BytesIO

import pypdf
import pytest

from backend.src.financial.statement_pdf import (
    NoTextLayer,
    PdfUnreadable,
    fiscal_year_end,
    find_value,
    numbers_in,
    page_unit,
    prior_column_value,
    read_pages,
)


def test_find_value_vnd():
    hits = find_value(["Tổng tài sản 23.259.126.277.266 100"], Decimal("23259126277266"))
    assert [(h["page"], h["unit"]) for h in hits] == [(1, "VND")]
    assert "23.259.126.277.266" in hits[0]["snippet"]
    assert len(hits[0]["snippet"]) <= 160


def test_find_value_page_numbers_are_one_based():
    hits = find_value(["trống", "x 23.259.126.277.266"], Decimal("23259126277266"))
    assert [h["page"] for h in hits] == [2]


@pytest.mark.parametrize("written", ["23.259.127", "23.259.126"])
def test_find_value_million_rounded(written):
    hits = find_value([f"Tổng tài sản {written}"], Decimal("23259126777266"))
    assert [(h["page"], h["unit"]) for h in hits] == [(1, "MILLION_VND")]


@pytest.mark.parametrize("written", ["(212.582.739.626)", "(212.583)"])
def test_find_value_negative_parentheses(written):
    assert find_value([f"Lỗ {written}"], Decimal("-212582739626"))


def test_find_value_no_false_hit():
    assert find_value(["123.259.126.277.2660"], Decimal("23259126277266")) == []
    assert find_value(["x 123.259.126.277.266"], Decimal("23259126277266")) == []


def test_find_value_small_value_never_matches_in_millions():
    assert find_value(["Ghi chú 1"], Decimal("600000")) == []


def test_numbers_in():
    assert numbers_in("Lợi nhuận sau thuế 8.294.916 (212.583) 1,5") == [
        Decimal("8294916"),
        Decimal("-212583"),
        Decimal("1.5"),
    ]
    assert numbers_in("trừ -5.000 hết") == [Decimal("-5000")]


def test_numbers_in_year_kept_note_reference_skipped():
    # years are plain numbers; "V.12" is a note reference, not a figure
    assert numbers_in("năm 2025 thuyết minh V.12") == [Decimal("2025")]


def test_page_unit():
    assert page_unit("Đơn vị tính: VND") == "VND"
    assert page_unit("Đơn vị: triệu đồng") == "MILLION_VND"
    assert page_unit("Đơn vị tính: Đồng Việt Nam") == "VND"
    assert page_unit("Đơn vị tính: triệu VND") == "MILLION_VND"
    assert page_unit("không có gì") is None


def test_fiscal_year_end():
    expected = ("03-31", 2026)
    assert fiscal_year_end(["cho năm tài chính kết thúc ngày 31 tháng 3 năm 2026"]) == expected
    assert fiscal_year_end(["x", "năm tài chính kết thúc vào ngày 31/03/2026"]) == expected
    assert fiscal_year_end(["nothing here"]) is None


def test_fiscal_year_end_ignores_quarter_period():
    assert fiscal_year_end(["cho kỳ kế toán 3 tháng kết thúc ngày 31 tháng 12 năm 2025"]) is None
    page = (
        "cho kỳ kế toán 3 tháng kết thúc ngày 31 tháng 12 năm 2025\n"
        "và năm tài chính kết thúc ngày 31 tháng 3 năm 2026"
    )
    assert fiscal_year_end([page]) == ("03-31", 2026)


def test_fiscal_year_end_across_line_break():
    assert fiscal_year_end(["năm tài chính  kết thúc ngày 31 tháng 3\nnăm 2026"]) == ("03-31", 2026)


def test_find_value_million_scale_ignores_line_codes():
    assert find_value(["Mã số 120"], Decimal("120000000")) == []


def test_prior_column_value():
    cur, pri = Decimal("23259126277266"), Decimal("30100000000000")
    assert prior_column_value(["Tổng tài sản 23.259.126 30.100.000\n"], cur, pri)
    assert not prior_column_value(["Tổng tài sản 30.100.000\n"], cur, pri)
    assert not prior_column_value(["Tổng tài sản 30.100.000 23.259.126\n"], cur, pri)
    assert not prior_column_value(["a 23.259.126\nb 30.100.000\n"], cur, pri)
    row = ["LNST 8.294.916 7.100.000 24.000.000 20.000.000\n"]
    assert prior_column_value(row, Decimal("8294916000000"), Decimal("7100000000000"))


def test_no_text_layer_raises():
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    with pytest.raises(NoTextLayer):
        read_pages(buf.getvalue())


def test_garbage_raises():
    with pytest.raises(PdfUnreadable):
        read_pages(b"not a pdf")


# --- OCR fallback and fiscal year without a year (real Vietstock PDFs, 13/11) ---
import backend.src.financial.statement_pdf as sp


def _blank_pdf(pages=1):
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


VI_PAGE = "Đơn vị tính: VND\nTổng cộng tài sản 82.738.304.930.449\nLợi nhuận sau thuế 2.901.545.752.650\n" * 3


def test_scan_is_read_through_ocr(monkeypatch):
    calls = []
    monkeypatch.setattr(sp, "_ocr_tools", lambda: ("tess", "ppm"))
    monkeypatch.setattr(sp, "_ocr_page", lambda pdf, n, tools: calls.append(n) or VI_PAGE)
    pages = read_pages(_blank_pdf(2))
    assert calls == [1, 2] and pages == [VI_PAGE, VI_PAGE]


def test_garbled_text_layer_is_replaced_by_ocr(monkeypatch):
    garbled = "Ngan hang ThU'O'ng m�i C6 phan Lgi nhu�n 5.800.441 TONG THU NHAP HO�T OQNG " * 20
    assert not sp._usable([garbled])
    assert sp._usable([VI_PAGE])
    monkeypatch.setattr(sp, "_native_pages", lambda data: [garbled])
    monkeypatch.setattr(sp, "_ocr_tools", lambda: ("tess", "ppm"))
    monkeypatch.setattr(sp, "_ocr_page", lambda pdf, n, tools: VI_PAGE)
    assert read_pages(b"%PDF-fake") == [VI_PAGE]


def test_ocr_limited_to_first_pages(monkeypatch):
    # The fiscal-year note is inside the first pages, so OCR stops at OCR_MAX_PAGES.
    page = VI_PAGE + "Năm tài chính bắt đầu từ ngày 01 tháng 01 và kết thúc vào ngày 31 tháng 12."
    calls = []
    monkeypatch.setattr(sp, "_ocr_tools", lambda: ("tess", "ppm"))
    monkeypatch.setattr(sp, "_ocr_page", lambda pdf, n, tools: calls.append(n) or page)
    pages = read_pages(_blank_pdf(sp.OCR_MAX_PAGES + 5))
    assert calls == list(range(1, sp.OCR_MAX_PAGES + 1))
    assert len(pages) == sp.OCR_MAX_PAGES + 5 and pages[-1] == ""


def test_scan_without_ocr_tools_raises(monkeypatch):
    monkeypatch.setattr(sp, "_ocr_tools", lambda: None)
    with pytest.raises(NoTextLayer):
        read_pages(_blank_pdf())


def test_ocr_returning_nothing_raises(monkeypatch):
    monkeypatch.setattr(sp, "_ocr_tools", lambda: ("tess", "ppm"))
    monkeypatch.setattr(sp, "_ocr_page", lambda pdf, n, tools: "")
    with pytest.raises(NoTextLayer):
        read_pages(_blank_pdf())


def test_fiscal_year_end_without_year():
    text = "Năm tài chính của Tập đoàn bắt đầu từ ngày 01 tháng 01 và kết thúc vào ngày 31 tháng 12. Báo cáo"
    assert fiscal_year_end([text]) == ("12-31", None)
    cmg = "Năm tài chính của Công ty bắt đầu từ ngày 01 tháng 4 và kết thúc vào ngày 31 tháng 3 năm sau."
    assert fiscal_year_end([cmg]) == ("03-31", None)
    assert fiscal_year_end(["cho kỳ kế toán kết thúc vào ngày 30 tháng 9. Năm tài chính khác"]) is None


def test_fiscal_year_end_prefers_dated_clause():
    pages = ["Năm tài chính bắt đầu từ ngày 01 tháng 4 và kết thúc vào ngày 31 tháng 3.",
             "cho năm tài chính kết thúc ngày 31 tháng 3 năm 2026"]
    assert fiscal_year_end(pages) == ("03-31", 2026)


def test_bank_accounting_year_clause():
    text = "Kỳ kế toán năm của Ngân hàng bắt đầu từ ngày 1 tháng 1 và kết thúc vào ngày 31 tháng 12."
    assert fiscal_year_end([text]) == ("12-31", None)


def test_image_pages_inside_a_text_pdf_are_ocrd(monkeypatch):
    narrative = "Đơn vị tính: VND. Tổng cộng tài sản, lợi nhuận sau thuế, doanh thu thuần của công ty " * 5
    native = [narrative, "", "   ", narrative]
    calls = []
    monkeypatch.setattr(sp, "_native_pages", lambda data: list(native))
    monkeypatch.setattr(sp, "_ocr_tools", lambda: ("tess", "ppm"))
    monkeypatch.setattr(sp, "_ocr_page", lambda pdf, n, tools: calls.append(n) or VI_PAGE)
    pages = read_pages(b"%PDF-fake")
    assert calls == [2, 3]
    assert pages == [narrative, VI_PAGE, VI_PAGE, narrative]


def test_text_pdf_without_ocr_tools_keeps_native_pages(monkeypatch):
    narrative = "Đơn vị tính: VND. Tổng cộng tài sản, lợi nhuận sau thuế, doanh thu thuần " * 5
    monkeypatch.setattr(sp, "_native_pages", lambda data: [narrative, ""])
    monkeypatch.setattr(sp, "_ocr_tools", lambda: None)
    assert read_pages(b"%PDF-fake") == [narrative, ""]


def test_unit_from_column_headers():
    assert page_unit("Mã Thuyết 2025 2024\nsố minh VND VND\n01 Doanh thu 70.207.688.944.553") == "VND"
    assert page_unit("Thuyết minh Triệu VND Triệu VND\nTổng tài sản 1.328.560.306") == "MILLION_VND"
    assert page_unit("minh triệu đồng triệu đồng") == "MILLION_VND"
    assert page_unit("Giá trị giao dịch 5.000 VND một cổ phiếu") is None


def test_unit_carries_over_to_continuation_pages():
    from backend.src.financial.statement_pdf import unit_for_page
    pages = ["Đơn vị tính: VND\nTài sản", "(tiếp theo)\nNợ phải trả", "(tiếp theo)\nVốn", "(tiếp theo)\nKhác"]
    assert unit_for_page(pages, 1) == "VND" and unit_for_page(pages, 2) == "VND" and unit_for_page(pages, 3) is None
    assert unit_for_page(["Đơn vị tính: VND", "", "", "", "x"], 4) is None
    assert unit_for_page(["minh Triệu VND Triệu VND", "(tiếp theo)"], 1) == "MILLION_VND"


def test_ocr_continues_until_the_fiscal_year_note(monkeypatch):
    note = "Kỳ kế toán năm của Ngân hàng bắt đầu từ ngày 1 tháng 1 và kết thúc vào ngày 31 tháng 12."
    calls = []
    monkeypatch.setattr(sp, "_ocr_tools", lambda: ("tess", "ppm"))
    monkeypatch.setattr(sp, "_ocr_page", lambda pdf, n, tools: calls.append(n) or (note if n == 18 else VI_PAGE))
    pages = read_pages(_blank_pdf(40))
    assert calls == list(range(1, 19))
    assert fiscal_year_end(pages) == ("12-31", None)


def test_ocr_extra_pages_are_capped(monkeypatch):
    calls = []
    monkeypatch.setattr(sp, "_ocr_tools", lambda: ("tess", "ppm"))
    monkeypatch.setattr(sp, "_ocr_page", lambda pdf, n, tools: calls.append(n) or VI_PAGE)
    read_pages(_blank_pdf(60))
    assert calls[-1] == sp.OCR_FISCAL_MAX_PAGES


# --- final review fix wave (13/11) ---
import subprocess as _sp


@pytest.mark.parametrize("error", [_sp.CalledProcessError(1, "tesseract"), _sp.TimeoutExpired("tesseract", 300), OSError("vie.traineddata missing")])
def test_ocr_failures_become_pdf_unreadable(monkeypatch, error):
    def boom(pdf, n, tools):
        raise error
    monkeypatch.setattr(sp, "_ocr_tools", lambda: ("tess", "ppm"))
    monkeypatch.setattr(sp, "_ocr_page", boom)
    with pytest.raises(PdfUnreadable):
        read_pages(_blank_pdf())


def test_ocr_subprocess_limits_threads(monkeypatch, tmp_path):
    seen = []
    def fake_run(cmd, **kw):
        seen.append(kw.get("env", {}).get("OMP_THREAD_LIMIT"))
        return _sp.CompletedProcess(cmd, 0, stdout=b"x", stderr=b"")
    monkeypatch.setattr(sp.subprocess, "run", fake_run)
    sp._ocr_page(tmp_path / "s.pdf", 1, ("tess", "ppm"))
    assert seen == ["1", "1"]


def test_snippet_has_no_nul():
    hits = find_value(["Tổng tài sản\x00 23.259.126.277.266"], Decimal("23259126277266"))
    assert hits and "\x00" not in hits[0]["snippet"]


def test_environment_failures_are_distinguishable(monkeypatch):
    # Machine problems (no OCR tools, OCR crash/timeout) must not be cached as facts about the PDF.
    monkeypatch.setattr(sp, "_ocr_tools", lambda: None)
    with pytest.raises(sp.OcrUnavailable):
        read_pages(_blank_pdf())
    monkeypatch.setattr(sp, "_ocr_tools", lambda: ("tess", "ppm"))
    monkeypatch.setattr(sp, "_ocr_page", lambda pdf, n, tools: (_ for _ in ()).throw(_sp.TimeoutExpired("t", 1)))
    with pytest.raises(sp.OcrUnavailable):
        read_pages(_blank_pdf())
    with pytest.raises(PdfUnreadable) as info:
        read_pages(b"not a pdf")
    assert not isinstance(info.value, sp.OcrUnavailable)
