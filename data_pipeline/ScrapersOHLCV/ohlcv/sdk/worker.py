"""Bounded vnstock invocation in an isolated child process, no API key required."""
from pathlib import Path
import os
import sys


def serialize_dataframe(frame, action):
    copy = frame.copy()
    if action in ('history','quote'):
        fields = ('open','high','low','close') if action=='history' else ('open_price','high_price','low_price','close_price')
        for field in fields:
            # Pandas JSON with precision=15 reveals binary float tails (60.399999999999999).
            # Python's shortest round-trip spelling preserves the SDK value, without those tails.
            copy[field] = copy[field].map(str)
    return copy.to_json(orient='records',date_format='iso',double_precision=15)


def main():
    from ohlcv.storage.store import ProjectPaths
    from ohlcv.history.vnstock import normalize_symbol
    from ohlcv.core.instruments import INDEXES
    paths = ProjectPaths()
    serving = sys.argv[1:] == ['--serve']
    if not serving and (len(sys.argv) not in (2,3) or sys.argv[1] not in ('catalog','history','quote')):
        return 2
    action = None if serving else sys.argv[1]
    symbol = normalize_symbol(sys.argv[2]) if action in ('history','quote') and len(sys.argv)==3 else None
    if action in ('history','quote') and symbol is None:
        return 2
    scoped_home = paths.output('.agent-state/vnstock-home')
    scoped_home.mkdir(parents=True,exist_ok=True)
    # Scope SDK caches to the project in this child only. Keep its own auth/quota code intact.
    os.environ['USERPROFILE'] = str(scoped_home)
    os.environ['VNSTOCK_DISABLE_AGENT_SETUP'] = '1'
    os.environ['VNSTOCK_AGENT_TARGETS'] = 'none'
    os.environ['VNSTOCK_TELEMETRY'] = 'off'
    os.environ['MPLCONFIGDIR'] = str(scoped_home/'matplotlib')
    os.environ['TEMP'] = str(scoped_home)
    os.environ['TMP'] = str(scoped_home)
    os.environ.pop('VNSTOCK_API_KEY',None)
    sys.dont_write_bytecode = True
    import contextlib
    import hashlib
    import json
    from datetime import datetime, timedelta
    from importlib.metadata import version
    from ohlcv.history.vnstock import VN
    with contextlib.redirect_stdout(sys.stderr):
        from vnstock import Market, Reference
    def request(action, symbol, automatic_exchange=None):
        if action not in ('catalog','history','quote'):
            raise ValueError('Invalid action')
        if action!='catalog':symbol=normalize_symbol(symbol)
        from ohlcv.realtime.session import SessionGate
        gate=SessionGate(paths) if automatic_exchange is not None else None
        if gate and not gate.status(automatic_exchange)['active']:
            return '{"session_closed":true}'
        with contextlib.redirect_stdout(sys.stderr):
            today = datetime.now(VN).date()
            if action == 'catalog':
                df = Reference().equity.list_by_exchange()
            elif action == 'quote' and symbol not in INDEXES:
                equity=Market().equity(symbol)
                if gate and not gate.status(automatic_exchange)['active']:
                    return '{"session_closed":true}'
                df = equity.quote(get_all=True)
            else:
                equity=Market().index(symbol) if symbol in INDEXES else Market().equity(symbol)
                if gate and not gate.status(automatic_exchange)['active']:
                    return '{"session_closed":true}'
                df = equity.ohlcv(start=str(today if action=='quote' else today-timedelta(days=180)),
                                  end=str(today), interval='1D', count=1 if action=='quote' else 400)
            raw = serialize_dataframe(df,'history' if action=='quote' and symbol in INDEXES else action)
        header = json.dumps({'fetched_at':datetime.now(VN).isoformat(), 'vnstock_version':version('vnstock'),
                             'symbol':symbol, 'instrument_type':'index' if symbol in INDEXES else 'stock',
                             'dataframe_sha256':hashlib.sha256(raw.encode()).hexdigest()})
        return header[:-1]+',"rows":'+raw+'}'
    if serving:
        # A closed parent stdin ends this child naturally; SDK auth/quota stays in this process.
        for line in sys.stdin:
            try:
                if len(line)>2048:raise ValueError('Oversized request')
                item=json.loads(line)
                output=request(item['action'],item.get('symbol'),item.get('automatic_exchange'))
            except Exception:
                output='{"error":"vnstock request failed"}'
            sys.stdout.write(output+'\n');sys.stdout.flush()
    else:
        sys.stdout.write(request(action,symbol))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as issue:
        # No traceback with SDK URLs, user/device paths or headers.
        print('vnstock request failed: '+type(issue).__name__,file=sys.stderr)
        raise SystemExit(2)
