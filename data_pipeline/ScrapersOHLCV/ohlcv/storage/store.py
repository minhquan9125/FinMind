from __future__ import annotations

import json
import math
import os
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath, PureWindowsPath
import sqlite3
import tempfile
from typing import Any

from ohlcv.core.models import Bar

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open TEXT,
    high TEXT,
    low TEXT,
    close TEXT,
    volume INTEGER NOT NULL,
    source TEXT NOT NULL,
    price_basis TEXT NOT NULL,
    volume_basis TEXT NOT NULL,
    status TEXT NOT NULL,
    quality TEXT NOT NULL,
    source_updated_at TEXT,
    received_at TEXT,
    reconciled_at TEXT,
    revision INTEGER NOT NULL,
    PRIMARY KEY (symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_candles_symbol_trade_date ON candles (symbol, trade_date);
"""


class ProjectPaths:
    def __init__(self, root: str | Path | None = None) -> None:
        self._fixed_boundary = Path(__file__).resolve().parents[2]

        if root is None:
            self._root = self._fixed_boundary
        else:
            candidate_root = Path(root)
            self._check_lexical_path(candidate_root, is_root_check=True)
            resolved_root = candidate_root.resolve()
            if resolved_root != self._fixed_boundary and self._fixed_boundary not in resolved_root.parents:
                raise ValueError(f"Root path {root} is outside allowed boundary {self._fixed_boundary}")
            self._root = resolved_root

    @property
    def root(self) -> Path:
        return self._root

    def _check_lexical_path(self, path: Path, is_root_check: bool = False) -> None:
        # Check for PureWindowsPath characteristics (drive letters, UNC shares, colons)
        s_path = str(path)
        pure_win = PureWindowsPath(s_path)
        if pure_win.drive or pure_win.is_absolute() or pure_win.root:
            if not is_root_check:
                raise ValueError(f"Path has forbidden drive or UNC root: {s_path}")

        parts = list(path.parts)
        if ".." in parts:
            raise ValueError(f"Parent directory traversal '..' is prohibited: {path}")

        for part in (parts[1:] if is_root_check and path.anchor else parts):
            if ":" in part:
                raise ValueError(f"Path component cannot contain colon (ADS / drive): {part}")

        # Traverse lexical ancestors to inspect symlinks / junctions before resolve
        curr = path if path.is_absolute() else (self._root / path if hasattr(self, "_root") else Path.cwd() / path)
        # If relative, walk from root downwards
        if not path.is_absolute() and hasattr(self, "_root"):
            walking = self._root
            for part in path.parts:
                walking = walking / part
                if walking.is_symlink() or (hasattr(walking, "is_junction") and walking.is_junction()):
                    raise ValueError(f"Symlink / junction detected in path component: {walking}")
        else:
            # absolute check
            check_cur = curr
            while check_cur != check_cur.parent:
                if check_cur.is_symlink() or (hasattr(check_cur, "is_junction") and check_cur.is_junction()):
                    raise ValueError(f"Symlink / junction detected in path: {check_cur}")
                check_cur = check_cur.parent

    def output(self, relative_path: str | Path) -> Path:
        rel = Path(relative_path)
        if rel.is_absolute():
            raise ValueError(f"Output path must be relative, got: {relative_path}")
        self._check_lexical_path(rel)

        dest = (self._root / rel).resolve()
        if not dest.is_relative_to(self._root):
            raise ValueError(f"Resolved output path is outside allowed project boundary: {dest}")
        return dest

    def atomic_json(self, relative_path: str | Path, payload: Any) -> Path:
        def _scan_nan(obj: Any) -> None:
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                raise ValueError("NaN or Infinity is not allowed in atomic JSON payload")
            if isinstance(obj, dict):
                for k, v in obj.items():
                    _scan_nan(k)
                    _scan_nan(v)
            elif isinstance(obj, (list, tuple, set)):
                for item in obj:
                    _scan_nan(item)

        _scan_nan(payload)
        encoded = json.dumps(payload, indent=2, allow_nan=False)

        target = self.output(relative_path)
        target_parent = target.parent
        target_parent.mkdir(parents=True, exist_ok=True)

        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            dir=target_parent,
            encoding="utf-8",
            delete=False,
            prefix=".tmp_",
        )
        temp_path = Path(temp_file.name)
        try:
            temp_file.write(encoded)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()
            os.replace(temp_path, target)
        except Exception:
            temp_file.close()
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise
        return target


def _validate_no_dangling_or_symlink(path: Path) -> None:
    sidecars = [path, Path(str(path) + "-wal"), Path(str(path) + "-shm"), Path(str(path) + "-journal")]
    for p in sidecars:
        if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
            raise ValueError(f"SQLite file or sidecar cannot be a symlink/junction: {p}")
        try:
            if os.path.islink(p):
                raise ValueError(f"SQLite file or sidecar cannot be a link: {p}")
        except OSError:
            pass


def _row_to_bar(row: sqlite3.Row) -> Bar:
    trade_date_val = date.fromisoformat(row["trade_date"])
    open_val = Decimal(row["open"]) if row["open"] is not None else None
    high_val = Decimal(row["high"]) if row["high"] is not None else None
    low_val = Decimal(row["low"]) if row["low"] is not None else None
    close_val = Decimal(row["close"]) if row["close"] is not None else None
    source_updated_at = (
        datetime.fromisoformat(row["source_updated_at"]) if row["source_updated_at"] is not None else None
    )
    received_at = datetime.fromisoformat(row["received_at"]) if row["received_at"] is not None else None
    reconciled_at = datetime.fromisoformat(row["reconciled_at"]) if row["reconciled_at"] is not None else None

    return Bar(
        symbol=row["symbol"],
        exchange=row["exchange"],
        trade_date=trade_date_val,
        open=open_val,
        high=high_val,
        low=low_val,
        close=close_val,
        volume=row["volume"],
        source=row["source"],
        price_basis=row["price_basis"],
        volume_basis=row["volume_basis"],
        status=row["status"],
        quality=row["quality"],
        source_updated_at=source_updated_at,
        received_at=received_at,
        reconciled_at=reconciled_at,
        revision=row["revision"],
    )


class CandleStore:
    def __init__(self, paths: ProjectPaths, relative_path: str | Path = "data/runtime/candles.sqlite3") -> None:
        self._paths = paths
        self._db_path = paths.output(relative_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        _validate_no_dangling_or_symlink(self._db_path)

        self._conn = sqlite3.connect(str(self._db_path), timeout=30.0, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=FULL;")
            self._conn.executescript(_SCHEMA)

    def __enter__(self) -> CandleStore:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _ensure_open(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("CandleStore connection is closed")
        return self._conn

    def upsert_batch(self, bars: Iterable[Bar]) -> int:
        conn = self._ensure_open()
        bar_list = list(bars)
        for b in bar_list:
            if not isinstance(b, Bar):
                raise TypeError(f"Expected Bar instance, got {type(b)!r}")

        _validate_no_dangling_or_symlink(self._db_path)

        inserted_or_updated = 0
        conn.execute("BEGIN IMMEDIATE;")
        try:
            for bar in bar_list:
                cursor = conn.execute(
                    """
                    SELECT symbol, exchange, trade_date, open, high, low, close, volume,
                           source, price_basis, volume_basis, status, quality,
                           source_updated_at, received_at, reconciled_at, revision
                    FROM candles WHERE symbol = ? AND trade_date = ?
                    """,
                    (bar.symbol, bar.trade_date.isoformat()),
                )
                existing_row = cursor.fetchone()

                if existing_row is None:
                    conn.execute(
                        """
                        INSERT INTO candles (
                            symbol, exchange, trade_date, open, high, low, close, volume,
                            source, price_basis, volume_basis, status, quality,
                            source_updated_at, received_at, reconciled_at, revision
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            bar.symbol,
                            bar.exchange,
                            bar.trade_date.isoformat(),
                            str(bar.open) if bar.open is not None else None,
                            str(bar.high) if bar.high is not None else None,
                            str(bar.low) if bar.low is not None else None,
                            str(bar.close) if bar.close is not None else None,
                            bar.volume,
                            bar.source,
                            bar.price_basis,
                            bar.volume_basis,
                            bar.status,
                            bar.quality,
                            bar.source_updated_at.isoformat() if bar.source_updated_at is not None else None,
                            bar.received_at.isoformat() if bar.received_at is not None else None,
                            bar.reconciled_at.isoformat() if bar.reconciled_at is not None else None,
                            bar.revision,
                        ),
                    )
                    inserted_or_updated += 1
                else:
                    existing_bar = _row_to_bar(existing_row)
                    # Immutable dimension checks
                    if existing_bar.exchange != bar.exchange:
                        raise ValueError(f"Cannot change exchange for {bar.symbol} on {bar.trade_date}")
                    if existing_bar.source != bar.source:
                        raise ValueError(f"Cannot change source for {bar.symbol} on {bar.trade_date}")
                    if existing_bar.price_basis != bar.price_basis:
                        raise ValueError(f"Cannot change price_basis for {bar.symbol} on {bar.trade_date}")
                    if existing_bar.volume_basis != bar.volume_basis:
                        raise ValueError(f"Cannot change volume_basis for {bar.symbol} on {bar.trade_date}")
                    if existing_bar.status == "closed" and bar.status != "closed":
                        raise ValueError(f"Cannot reopen closed bar for {bar.symbol} on {bar.trade_date}")

                    if bar.revision < existing_bar.revision:
                        raise ValueError("Incoming revision older than stored revision")
                    if existing_bar.payload_tuple() == bar.payload_tuple():
                        # Receipt-only duplicates excluded by payload_tuple(); no writes even if revision is higher
                        continue

                    if bar.revision == existing_bar.revision:
                        raise ValueError(
                            f"Revision {bar.revision} collision with different payload for {bar.symbol} on {bar.trade_date}"
                        )

                    conn.execute(
                        """
                        UPDATE candles SET
                            open = ?,
                            high = ?,
                            low = ?,
                            close = ?,
                            volume = ?,
                            status = ?,
                            quality = ?,
                            source_updated_at = ?,
                            received_at = ?,
                            reconciled_at = ?,
                            revision = ?
                        WHERE symbol = ? AND trade_date = ?
                        """,
                        (
                            str(bar.open) if bar.open is not None else None,
                            str(bar.high) if bar.high is not None else None,
                            str(bar.low) if bar.low is not None else None,
                            str(bar.close) if bar.close is not None else None,
                            bar.volume,
                            bar.status,
                            bar.quality,
                            bar.source_updated_at.isoformat() if bar.source_updated_at is not None else None,
                            bar.received_at.isoformat() if bar.received_at is not None else None,
                            bar.reconciled_at.isoformat() if bar.reconciled_at is not None else None,
                            bar.revision,
                            bar.symbol,
                            bar.trade_date.isoformat(),
                        ),
                    )
                    inserted_or_updated += 1
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        return inserted_or_updated

    def history(
        self,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        closed_only: bool = False,
    ) -> list[Bar]:
        conn = self._ensure_open()
        query = ["SELECT * FROM candles WHERE symbol = ?"]
        params: list[Any] = [symbol]
        if start is not None:
            query.append("AND trade_date >= ?")
            params.append(start.isoformat())
        if end is not None:
            query.append("AND trade_date <= ?")
            params.append(end.isoformat())
        if closed_only:
            query.append("AND status = 'closed'")
        query.append("ORDER BY trade_date ASC")

        cursor = conn.execute(" ".join(query), params)
        return [_row_to_bar(row) for row in cursor.fetchall()]

    def latest(self) -> list[Bar]:
        conn = self._ensure_open()
        cursor = conn.execute(
            """
            SELECT c.*
            FROM candles c
            INNER JOIN (
                SELECT symbol, MAX(trade_date) AS max_date
                FROM candles
                GROUP BY symbol
            ) latest_dates ON c.symbol = latest_dates.symbol AND c.trade_date = latest_dates.max_date
            ORDER BY c.symbol ASC
            """
        )
        return [_row_to_bar(row) for row in cursor.fetchall()]

    def get(self, symbol: str, day: date) -> Bar | None:
        conn = self._ensure_open()
        cursor = conn.execute(
            "SELECT * FROM candles WHERE symbol = ? AND trade_date = ?",
            (symbol, day.isoformat()),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_bar(row)
