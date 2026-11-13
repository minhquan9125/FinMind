"""Pure, exact-date price and observed-flow analysis, with JSON-safe provenance.

``analyze_series`` returns symbol/requested_as_of/as_of/first_date/session_count,
status/freshness/metrics/activity/benchmark/coverage/warnings/sources. Decimal
metrics are HALF_UP four-place strings, counts/volumes are integers, unavailable
metrics are None. Activity windows contain N stock dates; benchmark windows
contain N+1 exact stock dates. Neither calendar dates nor nearby index quotes
substitute for missing sessions. No configuration, database or provider access.
"""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, DecimalException, ROUND_HALF_UP, localcontext
import json
import re


WINDOWS = (1, 5, 20)
MONEY_FIELDS = ('total_value_vnd', 'foreign_buy_value_vnd', 'foreign_sell_value_vnd')
VOLUME_FIELDS = ('foreign_buy_volume', 'foreign_sell_volume')
FLOW_FIELDS = (*MONEY_FIELDS, *VOLUME_FIELDS, 'foreign_net_volume', 'foreign_net_value_vnd')
METRIC_FIELDS = ('close', 'close_vnd', 'price_scale', 'is_adjusted',
                 'return_1_percent', 'return_5_percent', 'return_20_percent',
                 'sma20', 'close_vs_sma20_percent', 'volume', 'average_volume_prior20',
                 'volume_vs_prior20', 'average_volume_latest5', 'average_volume_prior5',
                 'intraday_range_percent', 'daily_volatility20_percent')


def _day(value):
    if type(value) is date:
        return value
    if type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError('Expected a date or strict ISO date')


def _row_day(row):
    day = _day(row.get('trade_date', row.get('date')))
    if 'date' in row and _day(row['date']) != day:
        raise ValueError('Conflicting date and trade_date')
    return day


def _decimal(value, *, positive=False):
    if type(value) not in (Decimal, str, int) or isinstance(value, str) and len(value) > 128:
        raise ValueError('Expected an exact decimal, never bool or float')
    try:
        result = Decimal(value)
        if not result.is_finite() or result < 0 or positive and result == 0:
            raise ValueError('Expected a finite nonnegative decimal')
        return result
    except DecimalException:
        raise ValueError('Invalid decimal') from None


def _volume(value):
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= 2**63-1:
        raise ValueError('Expected a nonnegative bigint volume')
    return value


def _formatted(value):
    if value is None:
        return None
    try:
        rounded = value.quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)
        return format(abs(rounded) if rounded == 0 else rounded, '.4f')
    except DecimalException:
        raise ValueError('Metric exceeds decimal precision') from None


def _source(row):
    return (str(row['source_id']) if row.get('source_id') is not None else None,
            row.get('source_name', row.get('source')))


def _provenance(row, kind, warnings):
    source_id, source_name = _source(row)
    result = {'trade_date': row['trade_date'].isoformat(), 'source_id': source_id,
              'source_name': source_name, 'approval_status': row.get('approval_status'),
              'payload_id': str(row['payload_id']) if row.get('payload_id') is not None else None}
    if kind != 'activity':
        result['price_id'] = str(row['price_id']) if row.get('price_id') is not None else None
    if kind == 'prices':
        result.update(price_scale=row['price_scale'], is_adjusted=row['is_adjusted'])
    if kind == 'activity':
        result['field_payload_ids'] = row.get('field_payload_ids', {})
    # Index bars are keyed by symbol and date; only stock prices carry a price_id.
    if not (source_id or source_name) or not result['payload_id'] or kind == 'prices' and not result['price_id']:
        warnings.append(f'{kind}_missing_provenance:{result["trade_date"]}')
    if row.get('approval_status') != 'APPROVED':
        warnings.append(f'{kind}_source_not_approved:{result["trade_date"]}')
    return result


def _prices(rows, symbol, requested, today):
    selected = []
    for original in rows:
        row = dict(original)
        row['trade_date'] = _row_day(row)
        if row['trade_date'] > today:
            raise ValueError('Future stock price')
        if row['trade_date'] > requested:
            continue
        if row.get('symbol', symbol) != symbol:
            raise ValueError('Stock symbol mismatch')
        for field in ('open', 'high', 'low', 'close'):
            row[field] = _decimal(row.get(field), positive=True)
        if not row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high']:
            raise ValueError('Invalid OHLC relationships')
        row['volume'] = _volume(row.get('volume'))
        if type(row.get('price_scale')) is not int or row['price_scale'] <= 0:
            raise ValueError('A positive integer price_scale is required')
        if type(row.get('is_adjusted')) is not bool:
            raise ValueError('Explicit boolean adjustment is required')
        selected.append(row)
    selected.sort(key=lambda row: row['trade_date'])
    if len({r['trade_date'] for r in selected}) != len(selected):
        raise ValueError('Duplicate stock date')
    selected = selected[-21:]
    if len({(_source(r), r['price_scale'], r['is_adjusted']) for r in selected}) > 1:
        raise ValueError('Mixed price source, scale or adjustment')
    return selected


def _price_metrics(rows):
    metrics = dict.fromkeys(METRIC_FIELDS)
    if not rows:
        return metrics
    latest, size = rows[-1], len(rows)
    close = latest['close']
    values = {'close': close, 'close_vnd': close * latest['price_scale']}
    for n in WINDOWS:
        values[f'return_{n}_percent'] = 100*(close/rows[-n-1]['close']-1) if size > n else None
    if size >= 20:
        values['sma20'] = sum(r['close'] for r in rows[-20:])/20
        values['close_vs_sma20_percent'] = 100*(close/values['sma20']-1)
    for name, subset, count in (
        ('average_volume_prior20', rows[-21:-1], 20),
        ('average_volume_latest5', rows[-5:], 5),
        ('average_volume_prior5', rows[-10:-5], 5),
    ):
        values[name] = (Decimal(sum(r['volume'] for r in subset))/count
                        if len(subset) == count and all(r['volume'] is not None for r in subset) else None)
    average = values['average_volume_prior20']
    values['volume_vs_prior20'] = (Decimal(latest['volume'])/average
                                   if latest['volume'] is not None and average else None)
    if size >= 2:
        values['intraday_range_percent'] = 100*(latest['high']-latest['low'])/rows[-2]['close']
    if size == 21:
        returns = [100*(rows[i]['close']/rows[i-1]['close']-1) for i in range(1, 21)]
        mean = sum(returns)/20
        values['daily_volatility20_percent'] = (sum((r-mean)**2 for r in returns)/19).sqrt()
    metrics.update({name: _formatted(value) for name, value in values.items()})
    metrics.update(volume=latest['volume'], price_scale=latest['price_scale'], is_adjusted=latest['is_adjusted'])
    return metrics


def _activities(rows, symbol, requested, today, warnings):
    grouped = defaultdict(list)
    latest = None
    for original in rows:
        row = dict(original)
        try:
            day = _row_day(row)
            if day > today:
                raise ValueError('Future activity')
            if day > requested:
                continue
            row['trade_date'] = day
            if row.get('symbol', symbol) != symbol:
                raise ValueError('Activity symbol mismatch')
            for field in MONEY_FIELDS:
                row[field] = _decimal(row[field]) if row.get(field) is not None else None
                if row[field] is not None and row[field] >= Decimal('1e20'):
                    raise ValueError('Activity exceeds numeric(24,4)')
            for field in VOLUME_FIELDS:
                row[field] = _volume(row.get(field))
            origins = row.get('field_payload_ids') or {}
            origins = json.loads(origins) if isinstance(origins, str) else origins
            if not isinstance(origins, dict) or any(not isinstance(k, str) or v is None for k, v in origins.items()):
                raise ValueError('Invalid activity field provenance')
            row['field_payload_ids'] = {k: str(v) for k, v in origins.items()}
            grouped[day].append(row)
            # A duplicate date is ambiguous; never choose one provider silently.
            if latest is None or day > latest['trade_date']:
                latest = row
        except (ValueError, TypeError, KeyError):
            warnings.append('activity_invalid_observation')
            try:
                grouped[_row_day(row)].append(None)
            except ValueError:
                pass
    if latest is not None and len(grouped[latest['trade_date']]) != 1:
        warnings.append('activity_latest_ambiguous')
        latest = None
    return grouped, latest


def _activity_result(activity_rows, stock_rows, symbol, requested, today, warnings):
    grouped, latest = _activities(activity_rows, symbol, requested, today, warnings)
    result = {'latest_observation': None, 'windows': {}}
    used = {}

    def remember(row):
        provenance = _provenance(row, 'activity', warnings)
        used[(row['trade_date'], _source(row), provenance['payload_id'])] = provenance
        return provenance

    if latest is not None:
        observation = {**remember(latest), 'symbol': symbol}
        for field in ('observation_status', 'quality_status', 'volume_basis', 'value_basis'):
            observation[field] = latest.get(field)
        for field in ('fetched_at', 'source_updated_at'):
            value = latest.get(field)
            observation[field] = value.isoformat() if isinstance(value, datetime) else value
        observation.update({field: _formatted(latest[field]) for field in MONEY_FIELDS})
        observation.update({field: latest[field] for field in VOLUME_FIELDS})
        observation['foreign_net_volume'] = (latest['foreign_buy_volume']-latest['foreign_sell_volume']
                                             if all(latest[f] is not None for f in VOLUME_FIELDS) else None)
        observation['foreign_net_value_vnd'] = (_formatted(latest['foreign_buy_value_vnd']-latest['foreign_sell_value_vnd'])
                                                if all(latest[f] is not None for f in MONEY_FIELDS[1:]) else None)
        result['latest_observation'] = observation
        if latest.get('quality_status') != 'validated' or latest.get('observation_status') != 'after_close':
            warnings.append('activity_pending_latest_observation')
    for n in WINDOWS:
        dates = [r['trade_date'] for r in stock_rows[-n:]]
        available, missing = [], []
        for day in dates:
            matches = grouped[day]
            row = matches[0] if len(matches) == 1 else None
            if (row is not None and row.get('quality_status') == 'validated'
                    and row.get('observation_status') == 'after_close'
                    and any(_source(row)) and row.get('payload_id')):
                available.append(row)
            else:
                missing.append(day.isoformat())
        same_source = len({_source(r) for r in available}) == 1
        complete = len(dates) == n and len(available) == n and same_source
        window = dict.fromkeys(FLOW_FIELDS)
        window.update(required_sessions=n, available_sessions=len(available), missing_dates=missing)
        if complete:
            for fields, basis in ((MONEY_FIELDS, 'value_basis'), (VOLUME_FIELDS, 'volume_basis')):
                bases = {r.get(basis) for r in available}
                comparable = len(bases) == 1 and next(iter(bases)) not in (None, '', 'unknown')
                for field in fields:
                    if comparable and all(r[field] is not None for r in available):
                        total = sum(r[field] for r in available)
                        window[field] = _formatted(total) if field in MONEY_FIELDS else total
                        for row in available:
                            remember(row)
            if all(window[f] is not None for f in VOLUME_FIELDS):
                window['foreign_net_volume'] = window['foreign_buy_volume']-window['foreign_sell_volume']
            if all(window[f] is not None for f in MONEY_FIELDS[1:]):
                window['foreign_net_value_vnd'] = _formatted(sum(r['foreign_buy_value_vnd']-r['foreign_sell_value_vnd'] for r in available))
        window['status'] = 'complete' if complete and all(window[f] is not None for f in FLOW_FIELDS) else 'incomplete'
        if window['status'] != 'complete':
            warnings.append(f'activity_incomplete_window:{n}')
        result['windows'][str(n)] = window
    return result, sorted(used.values(), key=lambda r: r['trade_date'])


def _benchmark_result(rows, stock_rows, requested, today, metrics, warnings):
    grouped = defaultdict(list)
    for original in rows:
        row = dict(original)
        try:
            day = _row_day(row)
            if day > requested:
                continue
            if day > today:
                raise ValueError('Future index price')
            row['trade_date'] = day
            row['close'] = _decimal(row.get('close'), positive=True)
            if row.get('index_symbol') != 'VNINDEX':
                raise ValueError('Wrong benchmark')
            grouped[day].append(row)
        except (ValueError, TypeError):
            warnings.append('benchmark_invalid_observation')
            try:
                grouped[_row_day(row)].append(None)
            except ValueError:
                pass
    result, used = {'index_symbol': 'VNINDEX', 'windows': {}}, {}
    for n in WINDOWS:
        dates = [r['trade_date'] for r in stock_rows[-n-1:]]
        available, missing = [], []
        for day in dates:
            matches = grouped[day]
            if len(matches) == 1 and matches[0] is not None:
                available.append(matches[0])
            else:
                missing.append(day.isoformat())
        complete = len(dates) == n+1 and len(available) == n+1 and len({_source(r) for r in available}) == 1
        benchmark_return = 100*(available[-1]['close']/available[0]['close']-1) if complete else None
        stock_return = metrics[f'return_{n}_percent']
        # Calculate the spread from unrounded returns, avoiding double rounding.
        difference = (100*(stock_rows[-1]['close']/stock_rows[-n-1]['close']-1)-benchmark_return
                      if complete else None)
        result['windows'][str(n)] = {
            'required_sessions': n+1, 'available_sessions': len(available), 'missing_dates': missing,
            'return_percent': _formatted(benchmark_return), 'stock_return_percent': stock_return,
            'difference_percentage_points': _formatted(difference), 'status': 'complete' if complete else 'incomplete'}
        if complete:
            for row in available:
                used[row['trade_date']] = _provenance(row, 'benchmark', warnings)
        else:
            warnings.append(f'benchmark_incomplete_window:{n}')
    return result, [used[day] for day in sorted(used)]


def analyze_series(price_rows, activity_rows, benchmark_rows, *, symbol, requested_as_of, today):
    """Validate stock basis, then compute exact stock-session windows and provenance.

    Invalid stock rows raise ValueError. Invalid auxiliary rows suppress affected
    windows with warnings, retaining usable independent windows and observations.
    ``freshness`` measures calendar days from the latest price to ``today``; it
    makes no claim that a calendar gap represents a missed exchange session.
    """
    if type(symbol) is not str or not re.fullmatch('[A-Z]{3}', symbol.upper()):
        raise ValueError('Invalid stock symbol')
    symbol = symbol.upper()
    today, requested = _day(today), _day(requested_as_of)
    if requested > today:
        raise ValueError('Future requested_as_of')
    with localcontext() as context:
        context.prec = 60
        rows = _prices(price_rows, symbol, requested, today)
        warnings = []
        metrics = _price_metrics(rows)
        price_sources = [_provenance(row, 'prices', warnings) for row in rows]
        if rows and not rows[-1]['is_adjusted']:
            warnings.append('unadjusted_prices')
        gaps = any((rows[i]['trade_date']-rows[i-1]['trade_date']).days > 1 for i in range(1, len(rows)))
        if gaps:
            warnings.append('price_calendar_gaps_not_inferred_as_missing_sessions')
        staleness = (today-rows[-1]['trade_date']).days if rows else None
        if staleness:
            warnings.append('stale_prices')
        missing = [name for name, value in metrics.items() if value is None]
        if missing:
            warnings.append('incomplete_price_metrics')
        activity, activity_sources = _activity_result(activity_rows, rows, symbol, requested, today, warnings)
        benchmark, benchmark_sources = _benchmark_result(benchmark_rows, rows, requested, today, metrics, warnings)
        incomplete = (missing or any(w['status'] != 'complete' for w in activity['windows'].values())
                      or any(w['status'] != 'complete' for w in benchmark['windows'].values())
                      or any('not_approved' in w or 'provenance' in w or 'invalid' in w for w in warnings))
        return {
            'symbol': symbol, 'requested_as_of': requested.isoformat(),
            'as_of': rows[-1]['trade_date'].isoformat() if rows else None,
            'first_date': rows[0]['trade_date'].isoformat() if rows else None,
            'session_count': len(rows), 'status': 'no_data' if not rows else 'partial' if incomplete else 'ok',
            'freshness': {'staleness_calendar_days': staleness, 'stale': bool(staleness)},
            'metrics': metrics, 'activity': activity, 'benchmark': benchmark,
            'coverage': {'price_sessions': len(rows), 'required_price_sessions': 21, 'missing_metrics': missing},
            'warnings': list(dict.fromkeys(warnings)),
            'sources': {'prices': price_sources, 'activity': activity_sources, 'benchmark': benchmark_sources},
        }
