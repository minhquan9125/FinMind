import json
from datetime import date
from decimal import Decimal

from backend.src.financial.statement_pdf import NoTextLayer, PdfUnreadable
from backend.src.financial.verification import (
    decide,
    fiscal_label_convention,
    quarter_basis,
    same_conclusion,
)

D = Decimal
UNIT = 'Đơn vị tính: triệu đồng\n'
PAGES = [
    UNIT + 'Doanh thu thuần 50.000 45.000\n',
    UNIT + 'Lợi nhuận sau thuế 5.000 4.000\n',
    UNIT + 'Tổng cộng tài sản 270.000 250.000\n',
]
TECH = {'NET_REVENUE': D(50_000_000_000), 'PROFIT_AFTER_TAX': D(5_000_000_000), 'TOTAL_ASSETS': D(270_000_000_000)}
PRIOR = {'NET_REVENUE': D(45_000_000_000), 'PROFIT_AFTER_TAX': D(4_000_000_000), 'TOTAL_ASSETS': D(250_000_000_000)}


def report(**kw):
    base = {'period_code': '2025-YEAR', 'section': 'INCOME', 'industry': 'TECH', 'values': TECH,
            'prior_values': None, 'quarter_basis': None}
    return {**base, **kw}


_FY = ('12-31', 2025)


def evid(pages=PAGES, scope='CONSOLIDATED', fiscal_end=_FY):
    return {'document': {'scope': scope, 'audit_status': 'AUDITED', 'title': 't', 'url': 'u', 'document_id': 7},
            'pages': pages, 'fiscal_end': fiscal_end}


def test_quarter_basis_fpt_like():
    year = {'NET_REVENUE': D(1000), 'PROFIT_AFTER_TAX': D(100)}
    quarters = {q: {'NET_REVENUE': D(250), 'PROFIT_AFTER_TAX': D(25)} for q in (1, 2, 3, 4)}
    assert quarter_basis(year, quarters) == 'STANDALONE_QUARTER'


def test_quarter_basis_ytd_like():
    year = {'NET_REVENUE': D(1000)}
    quarters = {1: {'NET_REVENUE': D(250)}, 2: {'NET_REVENUE': D(500)}, 3: {'NET_REVENUE': D(750)}, 4: {'NET_REVENUE': D(1000)}}
    assert quarter_basis(year, quarters) == 'UNKNOWN'


def test_quarter_basis_missing_quarter_unknown():
    assert quarter_basis({'NET_REVENUE': D(1000)}, {1: {'NET_REVENUE': D(1000)}}) == 'UNKNOWN'


def test_fiscal_label_convention():
    assert fiscal_label_convention(2025, '12-31', 2025) == 'CALENDAR'
    assert fiscal_label_convention(2025, '03-31', 2025) == 'END_YEAR'
    assert fiscal_label_convention(2025, '03-31', 2026) == 'START_YEAR'
    assert fiscal_label_convention(2025, None, None) == 'UNKNOWN'


def test_decide_verified():
    out = decide(report(), evid())
    assert out['status'] == 'VERIFIED'
    assert (out['unit'], out['unit_status'], out['statement_scope']) == ('VND', 'VERIFIED', 'CONSOLIDATED')
    assert [e['page'] for e in out['evidence']] == [1, 2, 3]
    assert out['period_basis'] == 'ANNUAL'
    assert (out['period_start'], out['period_end']) == (date(2025, 1, 1), date(2025, 12, 31))
    assert out['document_id'] == 7 and out['reason_codes'] == []


def test_decide_unit_mismatch_with_page_is_partial():
    pages = [p.replace('triệu đồng', 'đồng') for p in PAGES]
    out = decide(report(), evid(pages))
    assert out['unit_status'] == 'UNKNOWN' and out['status'] == 'PARTIAL'
    assert 'UNIT_UNVERIFIED' in out['reason_codes']


def test_decide_not_found_is_partial_not_mismatch():
    out = decide(report(), evid([UNIT + 'Doanh thu thuần 50.000\n', UNIT + 'nothing here 1\n']))
    assert out['status'] == 'PARTIAL'
    assert 'VALUE_NOT_FOUND' in out['reason_codes']


def test_decide_mismatch_only_when_label_found_with_other_number():
    pages = [PAGES[0], UNIT + 'Lợi nhuận sau thuế 9.999 8.000\n', PAGES[2]]
    out = decide(report(), evid(pages))
    assert out['status'] == 'MISMATCH' and 'VALUE_MISMATCH' in out['reason_codes']
    assert out['checks']['PROFIT_AFTER_TAX']['result'] == 'MISMATCH'


def test_label_without_numbers_and_retained_earnings_are_not_mismatch():
    pages = [PAGES[0], UNIT + 'Lợi nhuận sau thuế\nLợi nhuận sau thuế chưa phân phối 9.999\n', PAGES[2]]
    assert decide(report(), evid(pages))['status'] == 'PARTIAL'


def test_decide_bank_uses_profit_assets_equity():
    pages = [UNIT + 'Lợi nhuận sau thuế 5.000\n', UNIT + 'Tổng cộng tài sản 270.000\n',
             UNIT + 'B. VỐN CHỦ SỞ HỮU 30.000\n']
    values = {'PROFIT_AFTER_TAX': TECH['PROFIT_AFTER_TAX'], 'TOTAL_ASSETS': TECH['TOTAL_ASSETS'],
              'OWNERS_EQUITY': D(30_000_000_000), 'TOTAL_OPERATING_INCOME': D(99_000_000_000)}
    out = decide(report(industry='BANK', values=values), evid(pages))
    assert out['status'] == 'VERIFIED'


def test_decide_no_text_layer_partial():
    out = decide(report(), evid(NoTextLayer('scan'), scope='SEPARATE'))
    assert out['status'] == 'PARTIAL' and 'NO_TEXT_LAYER' in out['reason_codes']
    # final review #7: the title's scope is not evidence when no number was found in the file
    assert out['statement_scope'] == 'UNKNOWN' and out['audit_status'] == 'AUDITED'


def test_quarter_uses_caller_basis_and_cmg_calendar_assumption():
    fe = ('03-31', 2026)
    out = decide(report(period_code='2025-Q2', quarter_basis='STANDALONE_QUARTER'), evid(fiscal_end=fe))
    # final review #8: quarter dates of an off-calendar fiscal year are assumed, so never VERIFIED
    assert out['status'] == 'PARTIAL' and out['fiscal_label_convention'] == 'START_YEAR'
    assert (out['period_start'], out['period_end']) == (date(2025, 4, 1), date(2025, 6, 30))
    assert 'FISCAL_QUARTER_CALENDAR_ASSUMED' in out['reason_codes']
    assert decide(report(period_code='2025-Q2'), evid())['status'] == 'PARTIAL'


def test_fiscal_year_dates_start_year():
    out = decide(report(), evid(fiscal_end=('03-31', 2026)))
    assert (out['period_start'], out['period_end']) == (date(2025, 4, 1), date(2026, 3, 31))


def test_comparison_basis():
    assert decide(report(prior_values=PRIOR), evid())['comparison_basis'] == 'AS_REPORTED'
    restated = [PAGES[0].replace('45.000', '44.000'), PAGES[1], PAGES[2]]
    assert decide(report(prior_values=PRIOR), evid(restated))['comparison_basis'] == 'RESTATED'
    assert decide(report(prior_values=PRIOR), evid(NoTextLayer('x')))['comparison_basis'] == 'UNKNOWN'
    assert decide(report(), evid())['comparison_basis'] == 'UNKNOWN'


def test_same_conclusion_ignores_ids_and_time():
    a = decide(report(), evid())
    b = {**a, 'verified_at': 1, 'verification_id': 2, 'job_id': 3, 'supersedes_id': 4}
    assert same_conclusion(a, b)
    assert not same_conclusion(a, {**a, 'document_id': 8})


def test_decide_verified_json_roundtrip():
    out = decide(report(prior_values=PRIOR), evid())
    assert out['status'] == 'VERIFIED'
    json.loads(json.dumps(out['checks']))
    json.loads(json.dumps(out['evidence']))


def test_no_fiscal_year_end_is_partial():
    out = decide(report(), evid(fiscal_end=None))
    assert out['status'] == 'PARTIAL' and 'FISCAL_YEAR_UNKNOWN' in out['reason_codes']
    assert out['fiscal_label_convention'] == 'UNKNOWN' and out['fiscal_year_end'] is None
    assert (out['statement_scope'], out['unit_status'], out['period_basis']) == ('CONSOLIDATED', 'VERIFIED', 'ANNUAL')


def test_line_codes_on_label_row_are_not_mismatch():
    row = UNIT + 'Lợi nhuận sau thuế thu nhập doanh nghiệp (60 = 50 - 51)\n'
    out = decide(report(), evid([PAGES[0], row, PAGES[2]]))
    assert out['status'] == 'PARTIAL' and 'VALUE_NOT_FOUND' in out['reason_codes']
    assert 'VALUE_MISMATCH' not in out['reason_codes']


def test_unknown_industry_raises():
    import pytest
    with pytest.raises(ValueError):
        decide(report(industry='RETAIL'), evid())


def test_pdf_unreadable_partial():
    out = decide(report(), evid(PdfUnreadable('bad')))
    assert out['status'] == 'PARTIAL' and 'PDF_UNREADABLE' in out['reason_codes']


def test_quarter_basis_negative_profit_year():
    year = {'PROFIT_AFTER_TAX': D(-1000)}
    quarters = {q: {'PROFIT_AFTER_TAX': D(-255)} for q in (1, 2, 3, 4)}
    assert quarter_basis(year, quarters) == 'STANDALONE_QUARTER'


# --- fiscal year end known without its year (quarterly notes, 13/11) ---
def test_calendar_year_end_without_year_is_enough():
    assert fiscal_label_convention(2025, '12-31', None) == 'CALENDAR'
    out = decide(report(), evid(fiscal_end=('12-31', None)))
    assert out['status'] == 'VERIFIED' and out['fiscal_label_convention'] == 'CALENDAR'
    assert 'FISCAL_YEAR_UNKNOWN' not in out['reason_codes']


def test_offset_year_end_without_year():
    assert fiscal_label_convention(2025, '03-31', None) == 'UNKNOWN'
    yearly = decide(report(), evid(fiscal_end=('03-31', None)))
    assert yearly['status'] == 'PARTIAL' and 'FISCAL_YEAR_LABEL_UNKNOWN' in yearly['reason_codes']
    quarterly = decide(report(period_code='2025-Q3', quarter_basis='STANDALONE_QUARTER'), evid(fiscal_end=('03-31', None)))
    assert quarterly['fiscal_year_end'] == '03-31'
    assert 'FISCAL_YEAR_UNKNOWN' not in quarterly['reason_codes']
    assert 'FISCAL_QUARTER_CALENDAR_ASSUMED' in quarterly['reason_codes']
    assert quarterly['period_start'] == date(2025, 7, 1)


def test_dec_31_year_end_is_calendar_whatever_year_was_read():
    assert fiscal_label_convention(2025, '12-31', 2024) == 'CALENDAR'


def test_unit_verified_when_one_hit_per_metric_is_on_a_unit_page():
    # p1: cover letter repeats profit without a unit line; p2-p4: statements with the unit line
    pages = ['Công văn giải trình: lợi nhuận sau thuế 5.000 so với 4.000\n'] + PAGES
    out = decide(report(), evid(pages))
    assert out['unit_status'] == 'VERIFIED' and out['status'] == 'VERIFIED'


def test_unit_not_verified_when_a_hit_contradicts_its_page_unit():
    pages = ['Đơn vị tính: VND\nLợi nhuận sau thuế 5.000\n'] + PAGES[:1] + PAGES[2:]
    out = decide(report(), evid(pages))
    assert out['unit_status'] == 'UNKNOWN'


def test_unit_verified_on_continuation_page():
    pages = ['Đơn vị tính: triệu đồng\nDoanh thu thuần 50.000 45.000\n', '(tiếp theo)\nLợi nhuận sau thuế 5.000 4.000\n',
             'Thuyết minh Triệu VND Triệu VND\nTổng cộng tài sản 270.000 250.000\n']
    out = decide(report(), evid(pages))
    assert out['unit_status'] == 'VERIFIED' and out['status'] == 'VERIFIED'


def test_fake_million_hit_on_continuation_page_does_not_block():
    pages = ['Thuyết minh VND VND\nDoanh thu thuần 50.000.000.000 45.000.000.000\nLợi nhuận sau thuế 5.000.000.000 4.000.000.000\n'
             'Tổng cộng tài sản 270.000.000.000 250.000.000.000\n',
             '(tiếp theo)\nLợi nhuận 5.000 000.000\n']  # OCR split: "5.000" reads as a million-scale hit
    out = decide(report(), evid(pages))
    assert out['unit_status'] == 'VERIFIED'


def test_ocr_garbled_number_on_label_line_is_not_a_mismatch():
    pages = [UNIT + 'Doanh thu thuần 50.000 45.000\n', UNIT + 'Lợi nhuận sau thuế 5.0013.000 4.000\n',
             UNIT + 'Tổng cộng tài sản 270.000 250.000\n']
    out = decide(report(), evid(pages))
    assert out['status'] == 'PARTIAL' and 'VALUE_MISMATCH' not in out['reason_codes']


def test_balance_sheet_metrics_do_not_decide_comparison_basis():
    # balance sheet comparatives are the prior year end, not the prior period: never RESTATED on them
    pages = [UNIT + 'Doanh thu thuần 50.000 45.000\n', UNIT + 'Lợi nhuận sau thuế 5.000 4.000\n',
             UNIT + 'Tổng cộng tài sản 270.000 260.000\n']
    out = decide(report(prior_values=PRIOR), evid(pages))
    assert out['comparison_basis'] == 'AS_REPORTED'


# --- final review fix wave (13/11) ---
def test_scope_needs_a_found_required_metric():
    out = decide(report(), evid(['Đơn vị tính: VND\nkhông có số nào khớp 1.234.567\n'] * 3))
    assert out['statement_scope'] == 'UNKNOWN' and out['status'] == 'PARTIAL'


def test_off_calendar_quarter_is_not_verified():
    q = report(period_code='2025-Q3', quarter_basis='STANDALONE_QUARTER')
    out = decide(q, evid(fiscal_end=('03-31', 2026)))
    assert 'FISCAL_QUARTER_CALENDAR_ASSUMED' in out['reason_codes'] and out['status'] == 'PARTIAL'


def test_bank_optional_metric_mismatch_is_partial():
    pages = [UNIT + 'Tổng thu nhập hoạt động 77.000\n', UNIT + 'Lợi nhuận sau thuế 5.000\n',
             UNIT + 'Tổng cộng tài sản 270.000\n', UNIT + 'B. VỐN CHỦ SỞ HỮU 30.000\n']
    values = {'PROFIT_AFTER_TAX': TECH['PROFIT_AFTER_TAX'], 'TOTAL_ASSETS': TECH['TOTAL_ASSETS'],
              'OWNERS_EQUITY': D(30_000_000_000), 'TOTAL_OPERATING_INCOME': D(99_000_000_000)}
    out = decide(report(industry='BANK', values=values), evid(pages))
    assert out['status'] == 'PARTIAL'
    assert 'OPTIONAL_VALUE_MISMATCH' in out['reason_codes'] and 'VALUE_MISMATCH' not in out['reason_codes']
