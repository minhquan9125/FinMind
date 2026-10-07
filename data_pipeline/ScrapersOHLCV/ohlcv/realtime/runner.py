"""Bounded, sequential DNSE streaming; every accepted snapshot is persisted."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
import math
import ssl
import time
import uuid
from zoneinfo import ZoneInfo

from ohlcv.providers.dnse import websocket_auth

ENDPOINT = 'wss://ws-openapi.dnse.com.vn/v1/stream?encoding=json'
TZ = ZoneInfo('Asia/Ho_Chi_Minh')


class SocketFailure(Exception):
    """Recoverable transport failure, without upstream error text."""


def decode_message(raw):
    if not isinstance(raw, (str, bytes)) or len(raw) > 1048576:
        raise ValueError('Invalid stream frame')
    try:
        data = json.loads(raw, parse_float=Decimal,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise ValueError('Malformed stream JSON') from None
    if not isinstance(data, dict):
        raise ValueError('Stream message must be an object')
    return data


class LiveRunner:
    def __init__(self, pipeline, api_key, api_secret, universe, *, connector=None,
                 clock=None, monotonic=time.monotonic, sleep=time.sleep):
        # Reuse auth input validation; do not retain an unsigned fallback.
        websocket_auth(api_key, api_secret, 1, 'validation')
        if not universe or (hasattr(pipeline, 'universe') and universe != pipeline.universe):
            raise ValueError('Live universe must match pipeline')
        self.pipeline = pipeline
        self._key, self._secret = api_key, api_secret
        self.universe = dict(universe)
        self._connector = connector
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic, self._sleep = monotonic, sleep
        self._logger = logging.Logger('ohlcv.private.websocket', level=logging.CRITICAL + 1)
        self._logger.addHandler(logging.NullHandler())
        self._logger.propagate = False

    def _now(self):
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError('Live clock must be timezone-aware')
        return now

    def _connect(self, remaining):
        connector = self._connector
        if connector is None:
            try:
                from websockets.sync.client import connect
            except ImportError:
                raise RuntimeError('Install the project live dependency: websockets') from None
            connector = connect
        return connector(ENDPOINT, ssl=ssl.create_default_context(), proxy=None,
                         open_timeout=min(15, remaining), close_timeout=5,
                         ping_interval=20, ping_timeout=20, max_size=1048576,
                         max_queue=16, logger=self._logger)

    def _recover(self, start):
        now = self._now()
        try:
            self.pipeline.recover(start, now.astimezone(TZ).date(), now)
        except Exception:
            raise RuntimeError('Live recovery failed') from None

    def _send(self, socket, data):
        try:
            socket.send(json.dumps(data, allow_nan=False))
        except Exception:
            raise SocketFailure() from None

    def _recv(self, socket, timeout):
        try:
            raw = socket.recv(timeout=timeout)
        except TimeoutError:
            raise
        except Exception:
            raise SocketFailure() from None
        return decode_message(raw)

    def _ended(self, now):
        day = now.astimezone(TZ).date()
        ends = [self.pipeline.calendar.session_end(ex, day) for ex in set(self.universe.values())]
        active_ends = [end for end in ends if end is not None]
        return bool(active_ends) and all(now >= end + timedelta(seconds=60) for end in active_ends)

    def _authenticate(self, socket, deadline):
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            return False
        welcome = self._recv(socket, min(15, remaining))
        if not (welcome.get('sid') or welcome.get('session_id')):
            raise RuntimeError('Invalid stream welcome')
        self._send(socket, websocket_auth(self._key, self._secret, int(self._now().timestamp()), uuid.uuid4().hex))
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            return False
        auth = self._recv(socket, min(15, remaining))
        if (auth.get('action') or auth.get('a')) != 'auth_success':
            raise RuntimeError('Stream authentication failed')
        self._send(socket, {'action':'subscribe', 'channels':[
            {'name':name, 'symbols':sorted(self.universe)}
            for name in ('ohlc.1D.json', 'ohlc_closed.1D.json')]})
        return True

    def _stream(self, socket, start, deadline, counts, stop_event):
        if not self._authenticate(socket, deadline):
            return
        self._recover(start)
        last_ping = self._monotonic()
        awaiting_pong = None
        while self._monotonic() < deadline and not (stop_event and stop_event.is_set()):
            now = self._now()
            if self._ended(now):
                return
            elapsed = self._monotonic()
            if awaiting_pong is not None and elapsed - awaiting_pong >= 40:
                raise SocketFailure()
            if elapsed - last_ping >= 20:
                self._send(socket, {'action':'ping'})
                last_ping = elapsed
                if awaiting_pong is None:
                    awaiting_pong = elapsed
            try:
                message = self._recv(socket, min(1, deadline - elapsed))
            except TimeoutError:
                continue
            action = message.get('action') or message.get('a')
            if action == 'ping':
                self._send(socket, {'action':'pong'})
                counts['heartbeats'] += 1
            elif action == 'pong':
                awaiting_pong = None
                counts['heartbeats'] += 1
            elif action in {'error', 'auth_error', 'subscription_error'}:
                raise RuntimeError('Stream protocol request rejected')
            elif message.get('T') in {'b', 'bc'}:
                counts['messages'] += 1
                try:
                    result = self.pipeline.ingest_stream(message, self._now())
                except Exception:
                    raise RuntimeError('Live pipeline update failed') from None
                counts['accepted' if result is not None and result.accepted else 'rejected'] += 1

    def run(self, start: date, duration=28800, max_reconnects=5, stop_event=None):
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 0 < duration <= 86400:
            raise ValueError('duration must be finite and in (0,86400]')
        if type(max_reconnects) is not int or not 0 <= max_reconnects <= 10:
            raise ValueError('max_reconnects must be an integer in [0,10]')
        now = self._now()
        today = now.astimezone(TZ).date()
        if type(start) is not date or start > today:
            raise ValueError('Invalid live start date')
        self.pipeline.calendar.trading_dates(start, today)
        deadline = self._monotonic() + duration
        counts = dict(messages=0, accepted=0, rejected=0, reconnects=0, heartbeats=0)
        if stop_event and stop_event.is_set():
            return counts
        self._recover(start)
        while self._monotonic() < deadline and not (stop_event and stop_event.is_set()):
            now = self._now()
            if not self.pipeline.calendar.is_known(now.astimezone(TZ).date()):
                raise ValueError('Calendar coverage expired')
            if self._ended(now):
                break
            collecting = any(self.pipeline.calendar.is_collecting(ex, now) for ex in set(self.universe.values()))
            if not collecting:
                delay = min(30, deadline - self._monotonic())
                stop_event.wait(delay) if stop_event else self._sleep(delay)
                continue
            try:
                with self._connect(deadline - self._monotonic()) as socket:
                    self._stream(socket, start, deadline, counts, stop_event)
                break
            except (SocketFailure, OSError, TimeoutError):
                if self._monotonic() >= deadline:
                    break
                if counts['reconnects'] >= max_reconnects:
                    raise RuntimeError('Stream reconnect limit exceeded') from None
                delay = min(2 ** counts['reconnects'], 30, deadline - self._monotonic())
                counts['reconnects'] += 1
                stop_event.wait(delay) if stop_event else self._sleep(delay)
            except RuntimeError:
                raise
            except Exception:
                raise RuntimeError('Stream connection failed') from None
        self._recover(start)
        return counts
