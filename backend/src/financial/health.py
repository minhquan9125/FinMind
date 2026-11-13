"""Comparable financial signals; absent evidence never becomes a zero or a verdict."""
import calendar
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re

RATIOS = ('roe', 'roa', 'nim', 'npl', 'cost_to_income')
SIGNALS = ('revenue_yoy_percent', 'profit_yoy_percent', 'operating_cash_flow_yoy_percent',
           'net_margin_percent', 'liabilities_to_assets_percent',
           *(name + '_percent' for name in RATIOS))
SIGNATURE = ('basis', 'scope', 'comparison_basis', 'fiscal_year_end', 'fiscal_label_convention', 'period_start', 'period_end')


def _text(value):
    return isinstance(value,str) and bool(value.strip()) and value.strip() != 'UNKNOWN'


def _number(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError('Expected an exact financial number')
    try:
        value = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('Invalid financial number') from exc
    if not value.is_finite():
        raise ValueError('Nonfinite financial number')
    return value


def _format(value):
    return format(value.quantize(Decimal('.0001'), rounding=ROUND_HALF_UP), 'f')


def _period(value):
    if not isinstance(value, str) or not re.fullmatch(r'[12]\d{3}(?:-Q[1-4])?', value):
        raise ValueError('Invalid reporting period')
    return int(value[:4]), int(value[-1]) if '-Q' in value else None


def _day(value):
    if value is None or value == 'UNKNOWN':
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid financial date') from exc


def _window_ok(row):
    start, end = _day(row.get('period_start')), _day(row.get('period_end'))
    fiscal = row.get('fiscal_year_end')
    if not start or not end or not isinstance(fiscal, str) or not re.fullmatch(r'\d{2}-\d{2}', fiscal):
        return False
    try:
        fiscal_date = date.fromisoformat('2000-' + fiscal)
    except ValueError:
        return False
    year, quarter = _period(row['period'])
    convention = row.get('fiscal_label_convention')
    if fiscal == '12-31':
        first_year = year
    elif convention in ('START_YEAR','END_YEAR'):
        first_year = year if convention == 'START_YEAR' else year - 1
    else:
        return False
    fiscal_end_year = first_year + (fiscal_date.month != 12)
    if fiscal_date.day != calendar.monthrange(fiscal_end_year,fiscal_date.month)[1]:
        return False
    first_month = fiscal_date.month % 12 + 1
    end_year, end_month = divmod(first_year*12+first_month-1+(quarter*3 if quarter else 12)-1,12)
    expected_end = date(end_year,end_month+1,calendar.monthrange(end_year,end_month+1)[1])
    if end != expected_end:
        return False
    basis = row.get('basis')
    if basis == 'INSTANT':
        return start == end
    months = {'QUARTER': 3 if quarter else None, 'YTD': 3 * quarter if quarter else None,
              'YEAR': 12 if quarter is None else None, 'TTM': 12}.get(basis)
    if months is None:
        return False
    first_year, first_month = divmod(end.year * 12 + end.month - months, 12)
    return start == date(first_year, first_month + 1, 1)


def _issues(row):
    if row is None:
        return ['missing_observation']
    reasons = []
    if row.get('value') is None:
        reasons.append('missing_value')
    if row.get('industry') not in ('BANK', 'TECH'):
        reasons.append('unknown_industry')
    if row.get('scope') not in ('CONSOLIDATED', 'SEPARATE'):
        reasons.append('unverified_scope')
    if not _text(row.get('comparison_basis')):
        reasons.append('unverified_comparison_basis')
    if not _window_ok(row):
        reasons.append('unverified_or_invalid_period_window')
    if row.get('metric') in ('assets','equity','liabilities') and row.get('basis') != 'INSTANT':
        reasons.append('balance_sheet_requires_instant')
    if row.get('metric') in ('revenue','profit','operating_cash_flow') and row.get('basis') not in ('QUARTER','YTD','YEAR','TTM'):
        reasons.append('income_or_cashflow_requires_duration')
    if row.get('metric') in RATIOS:
        if row.get('unit') != 'PERCENT':
            reasons.append('unverified_ratio_unit')
        if not _text(row.get('ratio_definition')):
            reasons.append('unverified_ratio_definition')
    elif row.get('unit') != 'VND' or row.get('currency') != 'VND':
        reasons.append('unverified_money_unit')
    for field in ('observation_id', 'payload_id', 'source_name', 'source_uri'):
        if not _text(row.get(field)):
            reasons.append('missing_' + field)
    value = row.get('value')
    if value is not None and (row.get('metric')=='liabilities' and value<0 or row.get('metric')=='npl' and not 0<=value<=100):
        reasons.append('invalid_metric_domain')
    if not isinstance(row.get('source_sha256'), str) or not re.fullmatch(r'[a-fA-F0-9]{64}', row['source_sha256']):
        reasons.append('missing_source_sha256')
    return reasons


def _shift_year(value):
    return date(value.year - 1, value.month, min(value.day, calendar.monthrange(value.year - 1, value.month)[1]))


def _signal(rows, operation, *, yoy=False, denominator=False):
    facts = [row for row in rows if row is not None]
    ids = [row['observation_id'] for row in facts if _text(row.get('observation_id'))]
    reasons = sorted({reason for row in rows for reason in _issues(row)})
    if not reasons and len(facts) == 2:
        a, b = facts
        fields = ('industry', 'currency', 'unit', 'basis', 'scope', 'comparison_basis', 'fiscal_year_end', 'fiscal_label_convention')
        if any(a.get(field) != b.get(field) for field in fields):
            reasons.append('incompatible_financial_basis')
        if yoy:
            if a['basis'] not in ('QUARTER', 'YTD', 'YEAR') or any(
                    _shift_year(_day(a[field])) != _day(b[field]) for field in ('period_start', 'period_end')):
                reasons.append('incompatible_yoy_window')
        elif any(a.get(field) != b.get(field) for field in ('period_start', 'period_end', 'period')):
            reasons.append('incompatible_same_period_window')
        if (yoy or denominator) and b['value'] is not None and b['value'] <= 0:
            reasons.append('non_positive_base')
    comparison = {field: facts[0].get(field) for field in SIGNATURE} if facts else {}
    comparison['unit'] = 'PERCENT'
    if facts and facts[0]['metric'] in RATIOS:
        comparison['ratio_definition'] = facts[0].get('ratio_definition')
    if reasons:
        return dict(value=None,status='insufficient_data',reasons=reasons,inputs=ids,comparison=comparison)
    value = operation(*[row['value'] for row in facts])
    status = 'complete' if all(row.get('approval_status') == 'APPROVED' for row in facts) else 'provisional'
    return dict(value=_format(value),status=status,reasons=[] if status=='complete' else ['source_not_approved'],
                inputs=ids,comparison=comparison)


def analyze_company(rows, *, symbol, period):
    """Return per-metric evidence and quality; no synthetic overall health score."""
    if not isinstance(symbol, str) or not re.fullmatch(r'[A-Z][A-Z0-9]{2,9}', symbol):
        raise ValueError('Invalid company symbol')
    year, _ = _period(period)
    prior = str(year - 1) + period[4:]
    selected = {}
    with localcontext() as context:
        context.prec = 50
        for source in rows:
            if source.get('symbol') != symbol or source.get('period') not in (period, prior):
                continue
            row = dict(source)
            if row.get('fiscal_year_end')=='12-31':
                row['fiscal_label_convention'] = 'CALENDAR'
            value = _number(row.get('value'))
            scale = row.get('scale', 1)
            if type(scale) is not int or scale <= 0:
                raise ValueError('Scale must be a positive integer')
            row['raw_value'] = str(value) if value is not None else None
            with localcontext() as normalization:
                normalization.prec = max(50,len(value.as_tuple().digits)+len(str(scale))) if value is not None else 50
                row['value'] = value * scale if value is not None else None
            start, end = _day(row.get('period_start')), _day(row.get('period_end'))
            if start and end and start > end:
                raise ValueError('Reversed financial window')
            identity = (row['period'], row.get('metric'))
            if identity in selected:
                raise ValueError('Ambiguous financial observation or revision')
            selected[identity] = row
        current = [row for (p, _), row in selected.items() if p == period]
        industries = {row.get('industry') for row in current}
        industry = next(iter(industries)) if len(industries) == 1 else None
        get = lambda metric, p=period: selected.get((p, metric))
        signals = {}
        for metric in ('revenue', 'profit', 'operating_cash_flow'):
            signals[metric + '_yoy_percent'] = _signal([get(metric),get(metric,prior)],
                lambda a,b:(a-b)/b*100,yoy=True)
        signals['net_margin_percent'] = _signal([get('profit'),get('revenue')],lambda a,b:a/b*100,denominator=True)
        signals['liabilities_to_assets_percent'] = _signal([get('liabilities'),get('assets')],lambda a,b:a/b*100,denominator=True)
        for metric in RATIOS:
            signals[metric + '_percent'] = _signal([get(metric)],lambda value:value)
        irrelevant = ('operating_cash_flow_yoy_percent','net_margin_percent','liabilities_to_assets_percent') if industry=='BANK' else (
            'nim_percent','npl_percent','cost_to_income_percent') if industry=='TECH' else ()
        for name in irrelevant:
            signals[name] = dict(value=None,status='not_applicable',reasons=['industry_profile'],inputs=[],comparison={})
        if industry not in ('BANK','TECH'):
            for signal in signals.values():
                signal.update(value=None,status='insufficient_data',reasons=signal['reasons']+['ambiguous_or_missing_industry'])
        statuses = [value['status'] for value in signals.values() if value['status'] != 'not_applicable']
        usable = any(value['value'] is not None for value in signals.values())
        status = 'complete' if statuses and all(s=='complete' for s in statuses) else 'provisional' if usable else 'insufficient_data'
        evidence = [{**row,'value':str(row['value']) if row['value'] is not None else None} for row in selected.values()]
        return dict(symbol=symbol,industry=industry,period=period,status=status,signals=signals,
                    warnings=sorted({r for signal in signals.values() for r in signal['reasons']}),evidence=evidence)
