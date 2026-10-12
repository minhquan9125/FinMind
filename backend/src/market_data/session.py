"""Read the existing explicit exchange calendar without importing/writing crawler modules."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import runpy


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
        return self.calendar.is_collecting(exchange, self.now())
