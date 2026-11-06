"""Reporting-period SQL shared by dense results and hybrid cache metadata.

Expressions use the existing p (reporting_periods), t (chunks), d (documents)
aliases. A PDF page is a locator, never an annual reporting period. Only the
known annual-title suffix is a fallback; publication dates cannot date a BCTN.
"""

ANNUAL_YEAR_SQL = """CASE WHEN upper(d.doc_type) = 'ANNUAL_REPORT' THEN
    substring(d.title from '(?i)(?:báo cáo thường niên|annual report)[[:space:]]+([12][0-9]{3})[[:space:]]*$')
END"""

EXACT_PERIOD_SQL = f"coalesce(p.period_code, t.locator_json->>'period_code', {ANNUAL_YEAR_SQL})"

PERIOD_SQL = f"""CASE WHEN upper(d.doc_type) = 'ANNUAL_REPORT' THEN {EXACT_PERIOD_SQL}
ELSE coalesce(p.period_code, t.locator_json->>'period_code',
              t.locator_json->>'published_at', t.locator_json->>'section') END"""

# Dense legacy searches also match the title when no period metadata exists.
# Keep that behavior for other document types, without guessing annual years.
FILTER_PERIOD_SQL = f"coalesce({PERIOD_SQL}, CASE WHEN upper(d.doc_type) <> 'ANNUAL_REPORT' THEN d.title END)"
