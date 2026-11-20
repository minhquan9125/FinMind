"""Typed daily observations from the installed KBS quote contract."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException, ROUND_HALF_UP
import re

VN = timezone(timedelta(hours=7))
MAX_VOLUME = 2**63 - 1
MONEY_LIMIT = Decimal('1e20')


def _number(value, field, *, money=False):
    if type(value) not in (str, int, Decimal) or isinstance(value, str) and len(value) > 128:
        raise ValueError(f'{field}: invalid decimal type or length')
    try:
        number = Decimal(value)
        if not number.is_finite() or number < 0 or not money and number == 0:
            raise ValueError(f'{field}: invalid decimal value')
        if money:
            if number >= MONEY_LIMIT:
                raise ValueError(f'{field}: exceeds numeric(24,4)')
            number = number.quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)
            if number >= MONEY_LIMIT:
                raise ValueError(f'{field}: exceeds numeric(24,4) after rounding')
        return number
    except DecimalException:
        raise ValueError(f'{field}: invalid decimal') from None


def _volume(value, field, *, optional=False):
    if value is None and optional:
        return None
    if type(value) is not int or not 0 <= value <= MAX_VOLUME:
        raise ValueError(f'{field}: expected nonnegative bigint')
    return value


def normalize_activity(envelope, *, symbol, source_name, now, session_status):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now: timezone-aware datetime required')
    if type(symbol) is not str or not re.fullmatch('[A-Z]{3}', symbol.upper()):
        raise ValueError('symbol: invalid stock symbol')
    symbol = symbol.upper()
    if type(source_name) is not str or not re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,63}', source_name):
        raise ValueError('source_name: invalid source identifier')
    if type(session_status) is not str or session_status not in ('intraday', 'after_close', 'unknown'):
        raise ValueError('session_status: closed or invalid session')
    if not isinstance(envelope, dict) or type(envelope.get('fetched_at')) is not str:
        raise ValueError('envelope: fetched_at string required')
    try:
        fetched = datetime.fromisoformat(envelope['fetched_at'])
    except ValueError:
        raise ValueError('fetched_at: invalid ISO timestamp') from None
    if fetched.tzinfo is None or fetched.utcoffset() is None or fetched > now + timedelta(seconds=30):
        raise ValueError('fetched_at: naive or future timestamp')
    rows = envelope.get('rows')
    if not isinstance(rows, list):
        raise ValueError('rows: list required')
    matches = [row for row in rows if isinstance(row, dict) and row.get('symbol') == symbol]
    if len(matches) != 1:
        raise ValueError('rows: exactly one matching symbol required')
    row = matches[0]
    if row.get('exchange') not in ('HOSE', 'HNX', 'UPCOM'):
        raise ValueError('exchange: unsupported exchange')
    raw_day = row.get('TD')
    if type(raw_day) is not str or not re.fullmatch(r'\d{2}/\d{2}/\d{4}', raw_day):
        raise ValueError('TD: exact dd/mm/YYYY required')
    try:
        trade_date = datetime.strptime(raw_day, '%d/%m/%Y').date()
    except ValueError:
        raise ValueError('TD: invalid calendar date') from None
    if trade_date > fetched.astimezone(VN).date():
        raise ValueError('TD: after observation date')
    prices = {key: _number(row.get(key+'_price'), key+'_price') for key in ('open', 'high', 'low', 'close')}
    if not prices['low'] <= min(prices['open'], prices['close']) <= max(prices['open'], prices['close']) <= prices['high']:
        raise ValueError('OHLC: invalid price relationships')
    total = row.get('total_value')
    return {
        'symbol': symbol, 'source_name': source_name, 'exchange': row['exchange'],
        'trade_date': trade_date, 'fetched_at': fetched, 'source_updated_at': None,
        'volume': _volume(row.get('volume_accumulated'), 'volume_accumulated'),
        'total_value_vnd': _number(total, 'total_value', money=True) if total is not None else None,
        'foreign_buy_volume': _volume(row.get('foreign_buy_volume'), 'foreign_buy_volume', optional=True),
        'foreign_sell_volume': _volume(row.get('foreign_sell_volume'), 'foreign_sell_volume', optional=True),
        'foreign_buy_value_vnd': None, 'foreign_sell_value_vnd': None,
        'volume_basis': 'unknown', 'value_basis': 'unknown',
        'observation_status': 'after_close' if session_status == 'after_close' else 'intraday',
        'quality_status': 'pending_reconciliation',
        'warnings': ['session_unconfirmed'] if session_status == 'unknown' else [],
    }


def classify_activity_session(envelope, root):
    """Historical observation time and explicit exchange calendar, never weekday guesses."""
    from .session import SessionGate
    try:
        row = envelope['rows'][0]
        stamp = datetime.fromisoformat(envelope['fetched_at']).astimezone(VN)
        day = datetime.strptime(row['TD'],'%d/%m/%Y').date()
        if stamp.date()!=day:
            return 'unknown'
        calendar = SessionGate(root).calendar
        if calendar is None:return 'unknown'
        sessions = calendar.sessions(row['exchange'],day)
        if not sessions:return 'closed'
        if stamp.time()<datetime.strptime(sessions[0]['start'],'%H:%M').time():return 'closed'
        end = datetime.strptime(sessions[-1]['end'],'%H:%M').time()
        return 'after_close' if stamp.time()>=end else 'intraday'
    except (KeyError,ValueError,TypeError,IndexError):
        return 'unknown'
