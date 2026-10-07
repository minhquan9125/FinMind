from __future__ import annotations

from datetime import date, datetime, time
import re
from typing import Any, Dict, List, Optional, Set
from zoneinfo import ZoneInfo

_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_ALLOWED_PHASES = {"ato", "continuous", "lunch", "atc", "after_hours", "halted"}
_COLLECTING_PHASES = {"ato", "continuous", "atc", "after_hours"}
_VALID_EXCHANGES = {"HOSE", "HNX", "UPCOM"}
_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

_DEFAULT_SESSIONS = {
    "HOSE": [
        {"start": "09:00", "end": "09:15", "phase": "ato"},
        {"start": "09:15", "end": "11:30", "phase": "continuous"},
        {"start": "11:30", "end": "13:00", "phase": "lunch"},
        {"start": "13:00", "end": "14:30", "phase": "continuous"},
        {"start": "14:30", "end": "14:45", "phase": "atc"},
    ],
    "HNX": [
        {"start": "09:00", "end": "11:30", "phase": "continuous"},
        {"start": "11:30", "end": "13:00", "phase": "lunch"},
        {"start": "13:00", "end": "14:30", "phase": "continuous"},
        {"start": "14:30", "end": "14:45", "phase": "atc"},
        {"start": "14:45", "end": "15:00", "phase": "after_hours"},
    ],
    "UPCOM": [
        {"start": "09:00", "end": "11:30", "phase": "continuous"},
        {"start": "11:30", "end": "13:00", "phase": "lunch"},
        {"start": "13:00", "end": "15:00", "phase": "continuous"},
    ],
}


def _parse_time(t_str: str) -> time:
    if not isinstance(t_str, str) or not _TIME_RE.fullmatch(t_str):
        raise ValueError(f"Time must be strict HH:MM: {t_str}")
    h, m = t_str.split(":")
    return time(int(h), int(m))


def _validate_and_sort_sessions(raw_sessions: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not isinstance(raw_sessions, list):
        raise ValueError("Sessions must be a list")

    cleaned = []
    parsed_list = []
    for s in raw_sessions:
        if not isinstance(s, dict) or "start" not in s or "end" not in s or "phase" not in s:
            raise ValueError(f"Session dict missing required keys: {s}")
        start_str = s["start"]
        end_str = s["end"]
        phase = s["phase"]

        st = _parse_time(start_str)
        et = _parse_time(end_str)
        if st >= et:
            raise ValueError(f"Session start {start_str} must be before end {end_str}")
        if not isinstance(phase, str) or phase not in _ALLOWED_PHASES:
            raise ValueError(f"Invalid phase '{phase}'. Allowed: {_ALLOWED_PHASES}")

        parsed_list.append((st, et, start_str, end_str, phase))

    # Sort by start time
    parsed_list.sort(key=lambda x: (x[0], x[1]))

    # Check overlaps
    for i in range(len(parsed_list) - 1):
        curr_end = parsed_list[i][1]
        next_start = parsed_list[i + 1][0]
        if curr_end > next_start:
            raise ValueError(f"Overlapping sessions: {parsed_list[i][3]} > {parsed_list[i+1][2]}")

    for item in parsed_list:
        cleaned.append({"start": item[2], "end": item[3], "phase": item[4]})

    return cleaned


class TradingCalendar:
    """Explicit calendar with bounded date whitelists and safe session phases."""

    def __init__(
        self,
        working_dates: List[date],
        coverage_start: date,
        coverage_end: date,
        source: str,
        overrides: Optional[Dict[str, Dict[str, List[Dict[str, str]]]]] = None,
    ) -> None:
        # Validate types strictly (exclude datetime which inherits from date)
        if type(coverage_start) is not date or type(coverage_end) is not date:
            raise TypeError("Coverage boundaries must be date instances, not datetime")
        if coverage_start > coverage_end:
            raise ValueError("coverage_start must be <= coverage_end")

        if not isinstance(source, str) or not source.strip() or len(source) > 200 or any(ord(c) < 32 for c in source):
            raise ValueError("Source must be a nonempty safe bounded string <= 200 chars")
        self._source = source
        self._coverage_start = coverage_start
        self._coverage_end = coverage_end

        working_dates = tuple(working_dates)
        for d in working_dates:
            if type(d) is not date:
                raise TypeError(f"Working date {d} must be date instance, not datetime")
            if d < coverage_start or d > coverage_end:
                raise ValueError(f"Working date {d} outside coverage range [{coverage_start}, {coverage_end}]")

        self._working_dates: Set[date] = set(working_dates)

        # Clean and freeze overrides
        self._overrides: Dict[date, Dict[str, List[Dict[str, str]]]] = {}
        if overrides:
            for k_date_str, ex_dict in overrides.items():
                if not isinstance(k_date_str, str):
                    raise TypeError("Override key must be ISO date string")
                d = date.fromisoformat(k_date_str)
                if d < coverage_start or d > coverage_end:
                    raise ValueError(f"Override date {d} outside coverage range")
                if d not in self._working_dates:
                    raise ValueError(f"Override date {d} is not a covered working date")
                if not isinstance(ex_dict, dict):
                    raise ValueError("Override value must be a dictionary of exchanges")

                self._overrides[d] = {}
                for ex, sessions in ex_dict.items():
                    if ex not in _VALID_EXCHANGES:
                        raise ValueError(f"Unknown exchange '{ex}' in override")
                    self._overrides[d][ex] = _validate_and_sort_sessions(sessions)

    @property
    def source(self) -> str:
        return self._source

    @property
    def coverage_start(self) -> date:
        return self._coverage_start

    @property
    def coverage_end(self) -> date:
        return self._coverage_end

    def is_known(self, d: date) -> bool:
        if type(d) is not date:
            return False
        return self._coverage_start <= d <= self._coverage_end

    def is_working_day(self, d: date) -> bool:
        if not self.is_known(d):
            raise ValueError("Date outside calendar coverage")
        return d in self._working_dates

    def trading_day(self, exchange: str, d: date) -> bool:
        if exchange not in _VALID_EXCHANGES:
            raise ValueError(f"Unknown exchange: {exchange}")
        if not self.is_known(d) or not self.is_working_day(d):
            return False
        sessions = self.sessions(exchange, d)
        return len(sessions) > 0

    def trading_dates(self, start: date, end: date) -> List[date]:
        if type(start) is not date or type(end) is not date:
            raise TypeError("Dates must be date instances, not datetime")
        if start > end:
            raise ValueError("start must be <= end")
        if start < self._coverage_start or end > self._coverage_end:
            raise ValueError(f"Range [{start}, {end}] outside coverage [{self._coverage_start}, {self._coverage_end}]")
        return sorted([d for d in self._working_dates if start <= d <= end])

    def sessions(self, exchange: str, d: date) -> List[Dict[str, str]]:
        """Return immutable copy of sessions for exchange on date."""
        if exchange not in _VALID_EXCHANGES:
            raise ValueError(f"Unknown exchange: {exchange}")
        if type(d) is not date:
            raise TypeError("Date must be a date instance")
        if not self.is_known(d) or not self.is_working_day(d):
            return []

        if d in self._overrides and exchange in self._overrides[d]:
            return [dict(s) for s in self._overrides[d][exchange]]

        return [dict(s) for s in _DEFAULT_SESSIONS[exchange]]

    def session_end(self, exchange: str, d: date) -> Optional[datetime]:
        """Return aware datetime of final session end for date, or None if no sessions."""
        if exchange not in _VALID_EXCHANGES:
            raise ValueError(f"Unknown exchange: {exchange}")
        if type(d) is not date:
            raise TypeError("Date must be a date instance")
        if not self.is_known(d) or not self.is_working_day(d):
            return None

        s_list = self.sessions(exchange, d)
        if not s_list or not any(s['phase'] in _COLLECTING_PHASES for s in s_list):
            return None
        last_end = s_list[-1]["end"]
        h, m = last_end.split(":")
        return datetime(d.year, d.month, d.day, int(h), int(m), tzinfo=_VN_TZ)

    def phase(self, exchange: str, now: datetime) -> str:
        if exchange not in _VALID_EXCHANGES:
            raise ValueError(f"Unknown exchange: {exchange}")
        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime instance")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")

        local_now = now.astimezone(_VN_TZ)
        d = local_now.date()

        if not self.is_known(d):
            return "unknown_calendar"
        if not self.is_working_day(d):
            return "holiday"

        sessions = self.sessions(exchange, d)
        if not sessions:
            return "holiday"

        cur_t = local_now.time()
        first_start = _parse_time(sessions[0]["start"])
        if cur_t < first_start:
            return "pre_open"

        for i, s in enumerate(sessions):
            st = _parse_time(s["start"])
            et = _parse_time(s["end"])
            if st <= cur_t < et:
                return s["phase"]
            # Check gap between sessions
            if i < len(sessions) - 1:
                next_st = _parse_time(sessions[i + 1]["start"])
                if et <= cur_t < next_st:
                    # Gap between morning and afternoon is lunch or halted
                    return "lunch" if cur_t >= time(11, 30) and cur_t < time(13, 0) else "halted"

        last_end = _parse_time(sessions[-1]["end"])
        if cur_t >= last_end:
            return "ended"

        return "halted"

    def is_collecting(self, exchange: str, now: datetime) -> bool:
        if exchange not in _VALID_EXCHANGES:
            raise ValueError(f"Unknown exchange: {exchange}")
        p = self.phase(exchange, now)
        return p in _COLLECTING_PHASES

    def has_ended(self, exchange: str, now: datetime) -> bool:
        if exchange not in _VALID_EXCHANGES:
            raise ValueError(f"Unknown exchange: {exchange}")
        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime instance")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        local_now = now.astimezone(_VN_TZ)
        d = local_now.date()
        if not self.is_known(d) or not self.is_working_day(d):
            return False
        end_dt = self.session_end(exchange, d)
        if end_dt is None:
            return False
        return local_now >= end_dt

    def to_dict(self) -> Dict[str, Any]:
        overrides_dict = {}
        for d, ex_map in self._overrides.items():
            overrides_dict[d.isoformat()] = {
                ex: [dict(s) for s in sessions]
                for ex, sessions in ex_map.items()
            }
        return {
            "version": 1,
            "coverage_start": self._coverage_start.isoformat(),
            "coverage_end": self._coverage_end.isoformat(),
            "working_dates": sorted([d.isoformat() for d in self._working_dates]),
            "source": self._source,
            "overrides": overrides_dict,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TradingCalendar:
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
        if type(data.get("version")) is not int or data.get("version") != 1:
            raise ValueError(f"Unsupported calendar version: {data.get('version')}")
        cov_start = date.fromisoformat(data["coverage_start"])
        cov_end = date.fromisoformat(data["coverage_end"])
        working = [date.fromisoformat(x) for x in data["working_dates"]]
        source = data["source"]
        overrides = data.get("overrides")
        return cls(working, cov_start, cov_end, source, overrides=overrides)
