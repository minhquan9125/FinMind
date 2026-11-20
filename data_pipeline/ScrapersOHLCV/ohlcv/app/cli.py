"""Command-line interface for the standalone OHLCV pipeline."""

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
import re
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from ohlcv.core.calendar import TradingCalendar
from ohlcv.storage.store import ProjectPaths
from ohlcv.core.pipeline import DailyPipeline
from ohlcv.providers.dnse import DNSEProvider
from ohlcv.storage.store import CandleStore

MAX_CONFIG_SIZE = 2 * 1024 * 1024  # 2 MiB
MAX_STREAM_LINE_SIZE = 1 * 1024 * 1024  # 1 MiB
MAX_STREAM_FILE_SIZE = 20 * 1024 * 1024  # 20 MiB


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=_json_default, allow_nan=False))


def _parse_iso_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError("Datetime must be timezone-aware")
    return dt


def _parse_date_or_datetime(value: str) -> Any:
    return date.fromisoformat(value)


def _load_json_file(file_path: Path, max_size: int = MAX_CONFIG_SIZE) -> Any:
    if not file_path.is_file():
        raise FileNotFoundError("Config file not found")
    size = file_path.stat().st_size
    if size > max_size:
        raise ValueError(f"File exceeds maximum size limit of {max_size} bytes")
    with open(file_path, "rb") as f:
        content = f.read(max_size + 1)
    if len(content) > max_size:
        raise ValueError('Config too large')
    return json.loads(content.decode("utf-8"), parse_float=Decimal,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def _load_calendar(paths: ProjectPaths, calendar_rel: str) -> TradingCalendar:
    cal_path = paths.output(calendar_rel)
    data = _load_json_file(cal_path, MAX_CONFIG_SIZE)
    if not isinstance(data, dict):
        raise ValueError("Calendar config must be a JSON object")
    return TradingCalendar.from_dict(data)


def _load_universe(paths: ProjectPaths, universe_rel: str) -> Dict[str, str]:
    uni_path = paths.output(universe_rel)
    data = _load_json_file(uni_path, MAX_CONFIG_SIZE)
    if not isinstance(data, dict):
        raise ValueError("Universe config must be a JSON object")
    universe: Dict[str, str] = {}
    for sym, exch in data.items():
        sym_str = sym
        exch_str = exch
        if not isinstance(sym_str, str) or not re.fullmatch(r'[A-Z0-9]{1,10}', sym_str):
            raise ValueError("Invalid symbol in universe")
        if not isinstance(exch_str, str) or exch_str not in {"HOSE", "HNX", "UPCOM"}:
            raise ValueError("Invalid exchange in universe")
        universe[sym_str] = exch_str
    if not universe:
        raise ValueError('Universe must not be empty')
    return universe


def _get_credentials() -> tuple[str, str]:
    key = os.environ.get("DNSE_API_KEY")
    secret = os.environ.get("DNSE_API_SECRET")
    if not key or not secret:
        raise ValueError("Missing required DNSE_API_KEY or DNSE_API_SECRET in environment")
    return key, secret


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ohlcv",
        description="Standalone OHLCV daily candle pipeline",
    )
    parser.add_argument("--root", type=str, default=None, help="Optional project root directory")
    parser.add_argument("--calendar", type=str, default="config/calendar.json", help="Path to calendar config")
    parser.add_argument("--universe", type=str, default="config/universe.json", help="Path to universe config")
    parser.add_argument("--db", type=str, default="data/runtime/candles.sqlite3", help="Path to SQLite database")
    parser.add_argument("--now", type=str, default=None, help="Override current time (ISO-8601 aware datetime)")
    parser.add_argument("--price-multiplier", type=str, default=None, help="Multiplier for raw price conversion")
    parser.add_argument(
        "--price-basis",
        type=str,
        choices=["raw", "adjusted", "unknown"],
        default="unknown",
        help="Price basis",
    )
    parser.add_argument(
        "--volume-basis",
        type=str,
        choices=["matched", "total", "unknown"],
        default="unknown",
        help="Volume basis",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate-calendar
    subparsers.add_parser("validate-calendar", help="Validate calendar configuration file")

    # status
    subparsers.add_parser("status", help="Report database status and coverage")

    # export
    export_parser = subparsers.add_parser("export", help="Export candles to JSON")
    export_parser.add_argument("--output", type=str, default="data/runtime/ohlcv.json", help="Output JSON file path")
    export_parser.add_argument("--include-open", action="store_true", help="Include unfinalized/open candles")
    export_parser.add_argument("--start", type=str, default=None, help="Start date or datetime")
    export_parser.add_argument("--end", type=str, default=None, help="End date or datetime")

    # recover
    recover_parser = subparsers.add_parser("recover", help="Recover historical candles from provider")
    recover_parser.add_argument("--start", type=str, required=True, help="Start date (YYYY-MM-DD)")
    recover_parser.add_argument("--end", type=str, required=True, help="End date (YYYY-MM-DD)")

    # replay
    replay_parser = subparsers.add_parser("replay", help="Replay recorded stream messages")
    replay_parser.add_argument("--input", type=str, default="fixtures/stream.jsonl", help="Input jsonl path")

    # live
    live_parser = subparsers.add_parser("live", help="Run live streaming ingestion")
    live_parser.add_argument("--start", type=str, required=True, help="Start date or time")
    live_parser.add_argument("--duration", type=int, default=28800, help="Duration in seconds (default 28800)")
    live_parser.add_argument("--max-reconnects", type=int, default=5, help="Max reconnect attempts (default 5)")

    return parser


def _parse_price_multiplier(raw_val: Optional[str]) -> Decimal:
    if raw_val is None:
        raise ValueError("--price-multiplier is required for recover, replay, and live commands")
    try:
        multiplier = Decimal(str(raw_val))
        if not multiplier.is_finite() or multiplier <= Decimal("0"):
            raise ValueError("Price multiplier must be positive")
        return multiplier
    except InvalidOperation:
        raise ValueError("Invalid decimal format for --price-multiplier")


def handle_validate_calendar(paths: ProjectPaths, calendar_rel: str) -> int:
    cal = _load_calendar(paths, calendar_rel)
    summary = {
        "valid": True,
        "coverage_start": cal.coverage_start,
        "coverage_end": cal.coverage_end,
        "total_working_dates": len(cal.to_dict()['working_dates']),
        "source": cal.source,
    }
    _print_json(summary)
    return 0


def handle_status(paths: ProjectPaths, calendar_rel: str, universe_rel: str, db_rel: str, now: datetime) -> int:
    calendar = _load_calendar(paths, calendar_rel)
    universe = _load_universe(paths, universe_rel)
    dummy_provider = None
    with CandleStore(paths, relative_path=db_rel) as store:
        pipeline = DailyPipeline(store, calendar, dummy_provider, universe, paths=paths)
        status_data = pipeline.status(now)
        _print_json(status_data)
    return 0


def handle_export(
    paths: ProjectPaths,
    calendar_rel: str,
    universe_rel: str,
    db_rel: str,
    output_rel: str,
    include_open: bool,
    start_str: Optional[str],
    end_str: Optional[str],
) -> int:
    calendar = _load_calendar(paths, calendar_rel)
    universe = _load_universe(paths, universe_rel)
    dummy_provider = None
    start_val = _parse_date_or_datetime(start_str) if start_str else None
    end_val = _parse_date_or_datetime(end_str) if end_str else None
    with CandleStore(paths, relative_path=db_rel) as store:
        pipeline = DailyPipeline(store, calendar, dummy_provider, universe, paths=paths)
        count = pipeline.export(output_rel, closed_only=not include_open, start=start_val, end=end_val)
        _print_json({"exported_count": count, "output": output_rel})
    return 0


def handle_recover(
    paths: ProjectPaths,
    calendar_rel: str,
    universe_rel: str,
    db_rel: str,
    multiplier: Decimal,
    price_basis: str,
    volume_basis: str,
    start_str: str,
    end_str: str,
    now: datetime,
) -> int:
    key, secret = _get_credentials()
    calendar = _load_calendar(paths, calendar_rel)
    universe = _load_universe(paths, universe_rel)
    provider = DNSEProvider(key, secret, price_multiplier=multiplier, price_basis=price_basis, volume_basis=volume_basis)
    start_date = date.fromisoformat(start_str)
    end_date = date.fromisoformat(end_str)
    with CandleStore(paths, relative_path=db_rel) as store:
        pipeline = DailyPipeline(store, calendar, provider, universe, paths=paths)
        summary = pipeline.recover(start_date, end_date, now)
        _print_json(summary)
    return 0


def handle_replay(
    paths: ProjectPaths,
    calendar_rel: str,
    universe_rel: str,
    db_rel: str,
    multiplier: Decimal,
    price_basis: str,
    volume_basis: str,
    input_rel: str,
    now: datetime,
) -> int:
    calendar = _load_calendar(paths, calendar_rel)
    universe = _load_universe(paths, universe_rel)
    provider = DNSEProvider(
        "dummy_key",
        "dummy_secret",
        price_multiplier=multiplier,
        price_basis=price_basis,
        volume_basis=volume_basis,
    )
    input_path = paths.output(input_rel)
    if not input_path.is_file():
        raise FileNotFoundError("Replay input file not found")
    total_file_size = input_path.stat().st_size
    if total_file_size > MAX_STREAM_FILE_SIZE:
        raise ValueError(f"Replay file exceeds maximum allowed size of {MAX_STREAM_FILE_SIZE} bytes")

    accepted = 0
    rejected = 0
    with CandleStore(paths, relative_path=db_rel) as store:
        pipeline = DailyPipeline(store, calendar, provider, universe, paths=paths)
        with open(input_path, "rb") as f:
            while True:
                line = f.readline(MAX_STREAM_LINE_SIZE + 1)
                if not line:
                    break
                if len(line) > MAX_STREAM_LINE_SIZE:
                    raise ValueError(f"Stream line exceeds maximum line length of {MAX_STREAM_LINE_SIZE} bytes")
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    payload = json.loads(line_str.decode("utf-8"), parse_float=Decimal,
                                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
                except (ValueError, UnicodeError):
                    raise ValueError('Malformed replay JSON') from None
                res = pipeline.ingest_stream(payload, now)
                if res is not None and res.accepted:
                    accepted += 1
                else:
                    rejected += 1

        status_data = pipeline.status(now)
        _print_json({"accepted": accepted, "rejected": rejected, "status": status_data})
    return 0


def handle_live(
    paths: ProjectPaths,
    calendar_rel: str,
    universe_rel: str,
    db_rel: str,
    multiplier: Decimal,
    price_basis: str,
    volume_basis: str,
    start_str: str,
    duration: int,
    max_reconnects: int,
) -> int:
    from ohlcv.realtime.runner import LiveRunner

    key, secret = _get_credentials()
    calendar = _load_calendar(paths, calendar_rel)
    universe = _load_universe(paths, universe_rel)
    provider = DNSEProvider(key, secret, price_multiplier=multiplier, price_basis=price_basis, volume_basis=volume_basis)
    start_val = _parse_date_or_datetime(start_str)
    with CandleStore(paths, relative_path=db_rel) as store:
        pipeline = DailyPipeline(store, calendar, provider, universe, paths=paths)
        runner = LiveRunner(pipeline, key, secret, universe)
        summary = runner.run(start_val, duration=duration, max_reconnects=max_reconnects)
        _print_json(summary)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2

    try:
        paths = ProjectPaths(root=args.root)

        now: datetime
        if args.now:
            now = _parse_iso_datetime(args.now)
        else:
            now = datetime.now(timezone.utc)

        cmd = args.command
        if cmd == "validate-calendar":
            return handle_validate_calendar(paths, args.calendar)

        if cmd == "status":
            return handle_status(paths, args.calendar, args.universe, args.db, now)

        if cmd == "export":
            return handle_export(
                paths,
                args.calendar,
                args.universe,
                args.db,
                args.output,
                args.include_open,
                args.start,
                args.end,
            )

        if cmd == "recover":
            multiplier = _parse_price_multiplier(args.price_multiplier)
            return handle_recover(
                paths,
                args.calendar,
                args.universe,
                args.db,
                multiplier,
                args.price_basis,
                args.volume_basis,
                args.start,
                args.end,
                now,
            )

        if cmd == "replay":
            multiplier = _parse_price_multiplier(args.price_multiplier)
            return handle_replay(
                paths,
                args.calendar,
                args.universe,
                args.db,
                multiplier,
                args.price_basis,
                args.volume_basis,
                args.input,
                now,
            )

        if cmd == "live":
            if args.now is not None:
                raise ValueError("--now is not permitted for live command; real clock only")
            multiplier = _parse_price_multiplier(args.price_multiplier)
            return handle_live(
                paths,
                args.calendar,
                args.universe,
                args.db,
                multiplier,
                args.price_basis,
                args.volume_basis,
                args.start,
                args.duration,
                args.max_reconnects,
            )

        sys.stderr.write(f"Error: UnknownCommand\n")
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        error_type = type(exc).__name__
        sys.stderr.write(f"Error: {error_type}\n")
        return 2
