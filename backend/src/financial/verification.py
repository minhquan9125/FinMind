"""Turns evidence from a BCTC PDF into one verification conclusion. Pure: no I/O, no DB."""
import calendar
from datetime import date, timedelta
from decimal import Decimal
import re

from .statement_pdf import (
    NoTextLayer,
    _fold,
    find_value,
    fiscal_year_end,
    numbers_in,
    page_unit,
    prior_column_value,
    unit_for_page,
)

_QUARTER_TOLERANCE = Decimal('0.03')
_PERIOD = re.compile(r'^(\d{4})-(?:YEAR|Q([1-4]))$')
_ROW_PREFIX = re.compile(r'^(?:(?:[ivx]+|[a-d]|\d+)[.)]\s+)+')
_IGNORED = frozenset({'verified_at', 'verification_id', 'job_id', 'supersedes_id', 'reason_codes'})

# Folded labels; a row counts only when it starts with one (after "I." / "B." style prefixes).
LABELS = {
    'NET_REVENUE': ('doanh thu thuan',),
    'TOTAL_OPERATING_INCOME': ('tong thu nhap hoat dong',),
    'PROFIT_AFTER_TAX': ('loi nhuan sau thue',),
    'TOTAL_ASSETS': ('tong cong tai san', 'tong tai san'),
    'OWNERS_EQUITY': ('von chu so huu', 'tong von chu so huu'),
}
# "Lợi nhuận sau thuế chưa phân phối" is a balance-sheet row, not the P&L profit.
_LABEL_EXCLUDE = ('chua phan phoi',)
_METRICS = {
    'BANK': ('TOTAL_OPERATING_INCOME', 'PROFIT_AFTER_TAX', 'TOTAL_ASSETS', 'OWNERS_EQUITY'),
    'TECH': ('NET_REVENUE', 'PROFIT_AFTER_TAX', 'TOTAL_ASSETS'),
}
_REQUIRED = {
    'BANK': ('PROFIT_AFTER_TAX', 'TOTAL_ASSETS', 'OWNERS_EQUITY'),
    'TECH': ('NET_REVENUE', 'PROFIT_AFTER_TAX', 'TOTAL_ASSETS'),
}


def quarter_basis(year: dict[str, Decimal], quarters: dict[int, dict[str, Decimal]]) -> str:
    if not year or any(q not in quarters for q in (1, 2, 3, 4)):
        return 'UNKNOWN'
    for metric, total in year.items():
        parts = [quarters[q].get(metric) for q in (1, 2, 3, 4)]
        if any(p is None for p in parts):
            return 'UNKNOWN'
        if abs(sum(parts) - total) > _QUARTER_TOLERANCE * abs(total):
            return 'UNKNOWN'
    return 'STANDALONE_QUARTER'


def fiscal_label_convention(year_report: int, end_month_day: str | None, end_year: int | None) -> str:
    if end_month_day == '12-31':  # a 31/12 year end is the calendar year; the year read may be a comparative's
        return 'CALENDAR'
    if end_month_day is None or end_year is None:
        return 'UNKNOWN'
    if end_year == year_report:
        return 'CALENDAR' if end_month_day == '12-31' else 'END_YEAR'
    if end_year == year_report + 1:
        return 'START_YEAR'
    return 'UNKNOWN'


def _label_lines(pages: list[str], metric: str):
    for text in pages:
        for line in text.splitlines():
            folded = _ROW_PREFIX.sub('', _fold(line).strip())
            if any(x in folded for x in _LABEL_EXCLUDE):
                continue
            if folded.startswith(LABELS[metric]):
                yield line


def _period_dates(year: int, quarter: int | None, convention: str, fiscal_end: str | None):
    if quarter is not None:  # quarters stay on calendar dates
        first = 3 * (quarter - 1) + 1
        return date(year, first, 1), date(year, first + 2, calendar.monthrange(year, first + 2)[1])
    if convention in ('START_YEAR', 'END_YEAR') and fiscal_end:
        month, day = (int(x) for x in fiscal_end.split('-'))
        end = date(year + (convention == 'START_YEAR'), month, day)
        try:
            prev = date(end.year - 1, month, day)
        except ValueError:  # 29 Feb
            prev = date(end.year - 1, month, 28)
        return prev + timedelta(days=1), end
    return date(year, 1, 1), date(year, 12, 31)


# Balance-sheet comparatives are the prior year end, not the prior period, so only flow metrics
# (same period last year sits in the next column) can show a restatement.
_FLOW = frozenset({'NET_REVENUE', 'TOTAL_OPERATING_INCOME', 'PROFIT_AFTER_TAX'})
# OCR damage inside a figure ("6.6813.525", "82.738,A04"): such a line proves nothing either way.
_GARBLED = re.compile(r'\d[.,]\d{4,}|\d{4,}[.,]\d{3}|\d[A-Za-zÀ-ỹ]\d|\d[.,][A-Za-z]')


def _mismatch_lines(pages, metric):
    return [line for line in _label_lines(pages, metric) if not _GARBLED.search(line)]


def _comparison_basis(pages, values, prior_values, found) -> tuple[str, dict]:
    detail, restated, as_reported = {}, False, True
    for metric, current in values.items():
        if metric not in _FLOW:
            continue
        prior = (prior_values or {}).get(metric)
        if prior is None or metric not in found:
            continue
        if prior_column_value(pages, current, prior):
            detail[metric] = 'AS_REPORTED'
            continue
        as_reported = False
        on_label = [line for line in _mismatch_lines(pages, metric) if find_value([line], current)]
        if on_label and not any(find_value([line], prior) for line in on_label):
            detail[metric] = 'RESTATED'
            restated = True
        else:
            detail[metric] = 'UNKNOWN'
    if restated:
        return 'RESTATED', detail
    if detail and as_reported:
        return 'AS_REPORTED', detail
    return 'UNKNOWN', detail


def decide(report: dict, evidence: dict) -> dict:
    m = _PERIOD.match(report['period_code'])
    if not m:
        raise ValueError(f"bad period_code {report['period_code']!r}")
    year = int(m.group(1))
    quarter = int(m.group(2)) if m.group(2) else None
    industry = str(report.get('industry', '')).upper()
    if industry not in _METRICS:
        raise ValueError(f"unknown industry {report.get('industry')!r}")
    doc = evidence['document']
    pages = evidence['pages']
    reasons: list[str] = []
    checks: dict = {}
    found_evidence: list[dict] = []
    found: set = set()
    status = 'PARTIAL'
    unit_status = 'UNKNOWN'
    comparison, fiscal_end = 'UNKNOWN', None
    readable = isinstance(pages, list)

    if not readable:
        reasons.append('NO_TEXT_LAYER' if isinstance(pages, NoTextLayer) else 'PDF_UNREADABLE')
        fiscal_end = evidence.get('fiscal_end')
    else:
        fiscal_end = evidence.get('fiscal_end') or fiscal_year_end(pages)
        values = report.get('values') or {}
        found, mismatched, unit_ok, any_hit = set(), [], True, False
        for metric in _METRICS[industry]:
            value = values.get(metric)
            if value is None:
                checks[metric] = {'result': 'NOT_PROVIDED'}
                continue
            hits = find_value(pages, value)
            if hits:
                found.add(metric)
                any_hit = True
                first = hits[0]
                found_evidence.append({'metric': metric, 'page': first['page'], 'unit': first['unit'],
                                       'snippet': first['snippet']})
                # A hit verifies when its page (or the table it continues) states the same unit. Only a
                # page that itself states another unit blocks: OCR splits "2.901.545 752.650" into a fake
                # million-scale hit on continuation pages, which must not veto the real VND hit.
                carried = [unit_for_page(pages, h['page'] - 1) for h in hits]
                own = [page_unit(pages[h['page'] - 1]) for h in hits]
                metric_unit_ok = (any(u == h['unit'] for u, h in zip(carried, hits))
                                  and not any(u is not None and u != h['unit'] for u, h in zip(own, hits)))
                unit_ok = unit_ok and metric_unit_ok
                checks[metric] = {'result': 'FOUND', 'value': str(value),
                                  'pages': sorted({h['page'] for h in hits}), 'unit_matches_page': metric_unit_ok}
            # shortcut: only |n| >= 1000 counts as an amount; line codes like (60 = 50 - 51) are not.
            elif any(abs(n) >= 1000 for line in _mismatch_lines(pages, metric) for n in numbers_in(line)):
                mismatched.append(metric)
                checks[metric] = {'result': 'MISMATCH', 'value': str(value)}
            else:
                checks[metric] = {'result': 'NOT_FOUND', 'value': str(value)}
        unit_status = 'VERIFIED' if any_hit and unit_ok else 'UNKNOWN'
        comparison, checks['comparison'] = _comparison_basis(
            pages, {k: v for k, v in values.items() if k in _METRICS[industry]},
            report.get('prior_values'), found)
        missing = [x for x in _REQUIRED[industry] if x not in found]
        if any(m in _REQUIRED[industry] for m in mismatched):
            reasons.append('VALUE_MISMATCH')
        elif mismatched:  # e.g. a bank's total operating income: not required, so never a MISMATCH
            reasons.append('OPTIONAL_VALUE_MISMATCH')
        if missing:
            reasons.append('VALUE_NOT_FOUND')
        if not mismatched and not missing and unit_status != 'VERIFIED':
            reasons.append('UNIT_UNVERIFIED')

    # The catalog title only names the file; it is evidence of scope once a required number is found in it.
    scope = (doc.get('scope') or 'UNKNOWN') if found & set(_REQUIRED[industry]) else 'UNKNOWN'
    if scope == 'UNKNOWN':
        reasons.append('SCOPE_UNKNOWN')
    if quarter is None:
        period_basis = 'ANNUAL'
    else:
        period_basis = report.get('quarter_basis') or 'UNKNOWN'
    if period_basis == 'UNKNOWN':
        reasons.append('PERIOD_BASIS_UNKNOWN')

    md, end_year = fiscal_end if fiscal_end else (None, None)
    convention = fiscal_label_convention(year, md, end_year)
    if not fiscal_end:
        reasons.append('FISCAL_YEAR_UNKNOWN')
    elif quarter is None and convention == 'UNKNOWN':
        reasons.append('FISCAL_YEAR_LABEL_UNKNOWN')  # off-calendar year end without its year: the label could shift
    if quarter is not None and md and md != '12-31':
        reasons.append('FISCAL_QUARTER_CALENDAR_ASSUMED')
    start, end = _period_dates(year, quarter, convention, md)

    if readable and 'VALUE_MISMATCH' in reasons:
        status = 'MISMATCH'
    elif readable and not any(r in reasons for r in (
            'VALUE_NOT_FOUND', 'UNIT_UNVERIFIED', 'SCOPE_UNKNOWN', 'PERIOD_BASIS_UNKNOWN', 'FISCAL_YEAR_UNKNOWN',
            'FISCAL_YEAR_LABEL_UNKNOWN', 'FISCAL_QUARTER_CALENDAR_ASSUMED', 'OPTIONAL_VALUE_MISMATCH')):
        status = 'VERIFIED'

    return {
        'document_id': doc.get('document_id'),
        'statement_scope': scope,
        'audit_status': doc.get('audit_status') or 'UNKNOWN',
        'unit': 'VND',
        'unit_status': unit_status,
        'period_basis': period_basis,
        'period_start': start,
        'period_end': end,
        'fiscal_year_end': md,
        'fiscal_label_convention': convention,
        'comparison_basis': comparison,
        'checks': checks,
        'evidence': found_evidence,
        'status': status,
        'reason_codes': reasons,
    }


def same_conclusion(a: dict, b: dict) -> bool:
    return {k: v for k, v in a.items() if k not in _IGNORED} == {k: v for k, v in b.items() if k not in _IGNORED}
