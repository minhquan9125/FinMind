"""Per-metric comparison against the available, eligible peer subgroup."""
from collections import Counter
from decimal import Decimal, localcontext

from .health import SIGNATURE, _format, _number, _text

LOWER_BETTER = {'liabilities_to_assets_percent','npl_percent','cost_to_income_percent'}
RATIO_NAMES = {'roe_percent','roa_percent','nim_percent','npl_percent','cost_to_income_percent'}


def _eligible(signal, name):
    if not signal or signal.get('status') not in ('complete','provisional') or signal.get('value') is None:
        return False
    comparison = signal.get('comparison', {})
    fields = SIGNATURE + ('unit',) + (('ratio_definition',) if name in RATIO_NAMES else ())
    return all(_text(comparison.get(field)) for field in fields) and comparison.get('unit')=='PERCENT'


def compare_peers(analyses, *, symbol, minimum_peers=3):
    if type(minimum_peers) is not int or minimum_peers < 3:
        raise ValueError('At least three distinct peers are required')
    counts = Counter(row['symbol'] for row in analyses)
    if counts[symbol] != 1:
        raise ValueError('Target must occur exactly once')
    target = next(row for row in analyses if row['symbol']==symbol)
    metrics = {}
    with localcontext() as context:
        context.prec = 50
        for name, signal in target['signals'].items():
            included, excluded = [], {}
            target_ok = target.get('industry') in ('BANK','TECH') and _eligible(signal,name)
            target_value = _number(signal.get('value')) if target_ok else None
            for row in analyses:
                code = row['symbol']
                if code == symbol:
                    continue
                other = row.get('signals',{}).get(name)
                if counts[code] != 1:
                    excluded[code] = 'duplicate_symbol'
                elif row.get('industry') != target.get('industry') or row.get('period') != target.get('period'):
                    excluded[code] = 'different_industry_or_period'
                elif not target_ok or not _eligible(other,name) or other['comparison'] != signal['comparison']:
                    excluded[code] = 'incomparable_signal'
                else:
                    included.append((code,_number(other['value']),other))
            values = sorted(value for _,value,_ in included)
            result = dict(target_value=_format(target_value) if target_value is not None else None,
                peer_median=None,difference_pp=None,position='insufficient_data',favorable=None,
                peer_symbols=sorted(code for code,_,_ in included),excluded=excluded,
                reasons=['insufficient_comparable_peers'] if target_ok else ['target_signal_unavailable'],
                status='insufficient_data',inputs={symbol:signal.get('inputs',[])})
            result['inputs'].update({code:other.get('inputs',[]) for code,_,other in included})
            if target_ok and len(values)>=minimum_peers:
                middle = len(values)//2
                median = values[middle] if len(values)%2 else (values[middle-1]+values[middle])/2
                delta = target_value-median
                provisional = any(other['status']=='provisional' for _,_,other in included) or signal['status']=='provisional'
                result.update(peer_median=_format(median),difference_pp=_format(delta),
                    position='above' if delta>0 else 'below' if delta<0 else 'equal',
                    favorable=(delta<0 if name in LOWER_BETTER else delta>0) if delta else None,
                    status='provisional' if provisional else 'complete',
                    reasons=['source_or_metric_provisional'] if provisional else [])
            metrics[name] = result
        applicable = [row for name,row in metrics.items() if target['signals'][name]['status']!='not_applicable']
        usable = any(row['peer_median'] is not None for row in applicable)
        status = 'complete' if applicable and all(row['status']=='complete' for row in applicable) else 'provisional' if usable else 'insufficient_data'
        return dict(target=symbol,industry=target.get('industry'),period=target['period'],status=status,
                    scope='available_eligible_database_subgroup',minimum_peers=minimum_peers,metrics=metrics)
