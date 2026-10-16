"""Read the existing explicit exchange calendar without importing/writing crawler modules."""
from datetime import datetime, time, timedelta, timezone
import json
from pathlib import Path
import runpy

VN = timezone(timedelta(hours=7))
AUTO_COLLECTION_END = time(15, 1)


class SessionGate:
    def __init__(self, root, *, now=None):
        root = Path(root)
        self.now = now or (lambda: datetime.now(timezone(timedelta(hours=7))))
        self.calendar = None
        try:
            # run_path compiles the source in memory, with no __pycache__ in the locked folder.
            folder = root / "data_pipeline/ScrapersOHLCV"
            calendar_class = runpy.run_path(str(folder / "ohlcv/core/calendar.py"))["TradingCalendar"]
            self.calendar = calendar_class.from_dict(json.loads((folder / "config/calendar.live.json").read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def __call__(self, exchange):
        if exchange not in ("HOSE", "HNX", "UPCOM") or self.calendar is None:
            return False
        now = self.now().astimezone(VN)
        if now.time() >= AUTO_COLLECTION_END:
            return False
        if self.calendar.is_collecting(exchange, now):
            return True
        # Keep fetching closing quotes after the exchange's regular session.
        # An explicit holiday, halt or special early close stays authoritative.
        sessions = self.calendar.sessions(exchange, now.date())
        if not sessions:
            return False
        last = sessions[-1]
        regular_end = {"HOSE": "14:45", "HNX": "15:00", "UPCOM": "15:00"}[exchange]
        return (last["end"] == regular_end
                and last["phase"] in ("ato", "continuous", "atc", "after_hours")
                and time.fromisoformat(regular_end) <= now.time())
