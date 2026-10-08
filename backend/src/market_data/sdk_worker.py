"""Persistent guest SDK child. Only this new backend runtime may be written."""
import contextlib
import json
import os
from pathlib import Path
import sys


def main():
    home = Path(os.environ["FINMIND_LIVE_SDK_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    for key in ("HOME", "USERPROFILE", "TEMP", "TMP"):
        os.environ[key] = str(home)
    os.environ.update(VNSTOCK_DISABLE_AGENT_SETUP="1", VNSTOCK_AGENT_TARGETS="none",
                      VNSTOCK_TELEMETRY="off", MPLCONFIGDIR=str(home / "matplotlib"))
    # Honor SDK authentication/quota normally. No monkey-patching or direct provider calls.
    from datetime import datetime, timedelta, timezone
    from .history import INDEX_NAMES
    from .live import stock_symbol
    from .session import SessionGate
    with contextlib.redirect_stdout(sys.stderr):
        from vnstock import Market
        market = Market()
    gate = SessionGate(Path.cwd())
    for line in sys.stdin:
        try:
            if len(line) > 4096:
                raise ValueError("Request too large")
            request = json.loads(line)
            if request.get("action") in ("index_history", "stock_history"):
                symbol = request["symbol"]
                is_index = request["action"] == "index_history"
                if is_index and symbol not in INDEX_NAMES:
                    raise ValueError("Invalid index")
                if not is_index:
                    stock_symbol(symbol)
                today = datetime.now(timezone(timedelta(hours=7))).date()
                with contextlib.redirect_stdout(sys.stderr):
                    instrument = market.index(symbol) if is_index else market.equity(symbol)
                    frame = instrument.ohlcv(start=str(today - timedelta(days=180)),
                                                      end=str(today), interval="1D", count=250).copy()
                    for field in ("open", "high", "low", "close"):
                        frame[field] = frame[field].map(str)
                    rows = json.loads(frame.to_json(orient="records", date_format="iso", double_precision=15))
                result = {"fetched_at": datetime.now(timezone(timedelta(hours=7))).isoformat(), "rows": rows}
                sys.stdout.write(json.dumps(result, allow_nan=False) + "\n")
                sys.stdout.flush()
                continue
            symbols = request["symbols"]
            if not isinstance(symbols, list) or not 1 <= len(symbols) <= 100:
                raise ValueError("Invalid symbols")
            symbols = list(dict.fromkeys(stock_symbol(symbol) for symbol in symbols))
            # SDK import/startup may cross a session boundary; recheck immediately before HTTP.
            if request.get("automatic") and not any(gate(exchange) for exchange in ("HOSE", "HNX", "UPCOM")):
                raise ValueError("Session closed")
            with contextlib.redirect_stdout(sys.stderr):
                frame = market.quote(symbol=symbols, get_all=True).copy()
                for field in ("open_price", "high_price", "low_price", "close_price"):
                    frame[field] = frame[field].map(str)
                rows = json.loads(frame.to_json(orient="records", double_precision=15))
            result = {"fetched_at": datetime.now(timezone(timedelta(hours=7))).isoformat(), "rows": rows}
        except Exception:
            result = {"error": "Nguồn vnstock chưa trả dữ liệu hợp lệ."}
        sys.stdout.write(json.dumps(result, allow_nan=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
