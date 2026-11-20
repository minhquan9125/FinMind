"""Verified calendar gate and one shared rolling request budget per chart server."""
from collections import deque
from datetime import datetime
import json
import math
import threading
import time
from zoneinfo import ZoneInfo

from ohlcv.core.calendar import TradingCalendar, _COLLECTING_PHASES, _VALID_EXCHANGES

VN = ZoneInfo('Asia/Ho_Chi_Minh')


class RateBudget:
    def __init__(self, *, clock=time.monotonic, max_calls=16, period=60, spacing=5):
        if type(max_calls) is not int or max_calls < 1:
            raise ValueError('Invalid request budget')
        if any(type(v) not in (int,float) or not math.isfinite(v) or v <= 0 for v in (period,spacing)):
            raise ValueError('Invalid request timing')
        self.clock, self.max_calls, self.period, self.spacing = clock,max_calls,period,spacing
        self.calls=deque()
        self.lock=threading.Lock()

    def reserve(self, cost=1):
        """Return wait seconds without consuming; reserve credits only when allowed.

        History/catalog reserve three credits for SDK HTTP retries; quote uses one.
        Failed calls retain their credits. Ticker changes never reset this object.
        """
        if type(cost) is not int or not 1 <= cost <= self.max_calls:
            raise ValueError('Invalid request cost')
        with self.lock:
            now=self.clock()
            while self.calls and self.calls[0] <= now-self.period:
                self.calls.popleft()
            wait=max(0,self.calls[-1]+self.spacing-now) if self.calls else 0
            if len(self.calls)+cost > self.max_calls:
                wait=max(wait,self.calls[len(self.calls)+cost-self.max_calls-1]+self.period-now)
            if wait > 0:
                return wait
            self.calls.extend([now]*cost)
            return 0


class SessionGate:
    def __init__(self, paths, *, now=None):
        self.now=now or (lambda:datetime.now(VN))
        self.calendar=None
        try:
            self.calendar=TradingCalendar.from_dict(json.loads(paths.output('config/calendar.live.json').read_text(encoding='utf-8')))
        except (OSError,ValueError,KeyError,TypeError):
            pass  # Missing/invalid/uncovered calendar always disables automated collection.

    def status(self, exchange):
        if exchange not in _VALID_EXCHANGES:
            raise ValueError('Unknown exchange')
        now=self.now()
        if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError('Session clock must be timezone-aware')
        now=now.astimezone(VN)
        phase=self.calendar.phase(exchange,now) if self.calendar else 'unknown_calendar'
        return {'active':phase in _COLLECTING_PHASES,'phase':phase,'exchange':exchange,
                'server_time':now.isoformat(),'poll_seconds':5,'check_seconds':30,
                'coverage_end':str(self.calendar.coverage_end) if self.calendar else None}
