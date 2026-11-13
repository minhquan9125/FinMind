"""Translate existing financial exports without certifying legacy importer assumptions."""
from .exact_json import loads

MAP = {'INCOME_STATEMENT':{'PROFIT_AFTER_TAX':'profit'},
       'BALANCE_SHEET':{'TOTAL_ASSETS':'assets','OWNERS_EQUITY':'equity','TOTAL_LIABILITIES':'liabilities'},
       'CASH_FLOW':{'CASH_FLOW_OPERATING':'operating_cash_flow'},
       'RATIO':{'ROE':'roe','ROA':'roa','NIM':'nim','NPL_RATIO':'npl','COST_TO_INCOME':'cost_to_income'}}


def canonical_rows(records):
    result = []
    for row in records:
        industry, section = row.get('industry_type'), row.get('section')
        metric = MAP.get(section,{}).get(row.get('code'))
        revenue_code = 'TOTAL_OPERATING_INCOME' if industry=='BANK' else 'NET_REVENUE' if industry=='TECH' else None
        if section=='INCOME_STATEMENT' and row.get('code')==revenue_code:
            metric = 'revenue'
        if metric is None:
            continue
        raw_locator = row.get('locator_json')
        locator = loads(raw_locator) if isinstance(raw_locator,str) else raw_locator or {}
        if not isinstance(locator,dict):
            raise ValueError('Financial locator must be an object')
        verified_unit = locator.get('unit_status')=='VERIFIED'
        source_period = row['period_code']
        period = source_period.removesuffix('-YEAR')
        result.append(dict(symbol=row['symbol'],industry=industry,period=period,source_period=source_period,metric=metric,
            value=row.get('value'),unit=row.get('unit') if verified_unit else 'UNKNOWN',raw_unit=row.get('unit'),
            scale=row.get('scale',1),currency=row.get('currency'),
            basis=locator.get('period_basis','UNKNOWN'),scope=locator.get('statement_scope','UNKNOWN'),
            comparison_basis=locator.get('comparison_basis','UNKNOWN'),
            fiscal_year_end=locator.get('fiscal_year_end'),fiscal_label_convention=locator.get('fiscal_label_convention'),
            period_start=locator.get('period_start'),
            period_end=locator.get('period_end'),ratio_definition=locator.get('ratio_definition'),
            published_at=row.get('published_at'),observation_id=row.get('observation_id'),
            payload_id=row.get('payload_id'),source_name=row.get('source_name'),source_uri=row.get('source_uri'),
            source_sha256=row.get('sha256'),approval_status=row.get('approval_status'),
            source_locator=locator,report_id=row.get('report_id'),report_version=row.get('report_version'),
            restated_from_id=row.get('restated_from_id')))
    return result
