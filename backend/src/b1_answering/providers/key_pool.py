"""Round-robin pool of Gemini API keys with per-key cooldowns.

Purpose: stay available when one key of the team runs out of quota, is revoked or is rejected.
Every key must be a legitimate key of this project's team; the pool never shares a key's budget
and never reveals a key (status only exposes positions, labels and a state).

Failover is only used for rejections that happen BEFORE any generation ran (quota or credentials),
never after a timeout or a partial response, so a request cannot be billed twice.

State is kept per key value, so the key list can change while requests are running (keys added or
removed from the admin page) without shifting anyone's cooldown or position.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional, Sequence

QUOTA_COOLDOWN = 90.0           # first quota rejection; doubles on consecutive rejections
MAX_QUOTA_COOLDOWN = 3600.0
INVALID_COOLDOWN = 6 * 3600.0   # revoked / invalid / forbidden key


def parse_keys(*values: Optional[str]) -> List[str]:
    """Split comma/newline/semicolon separated text into unique, valid keys, keeping first-seen order."""
    keys: List[str] = []
    for value in values:
        for part in (value or "").replace("\r", "\n").replace(";", ",").replace("\n", ",").split(","):
            key = part.strip()
            if key and key not in keys:
                keys.append(key)
    return keys


def _pairs(keys, meta):
    """Unique (key, meta) pairs in order. `meta` is a list aligned with `keys`, or None."""
    seen, pairs = set(), []
    for index, key in enumerate(keys):
        if not isinstance(key, str) or not key.strip() or key in seen:
            continue
        seen.add(key)
        pairs.append((key, dict(meta[index]) if meta and index < len(meta) and meta[index] else {}))
    return pairs


def _fresh():
    return {"until": 0.0, "strikes": 0, "state": "ready"}


class KeyPool:
    def __init__(self, keys: Sequence[str], *, clock: Callable[[], float] = time.monotonic, meta=None):
        pairs = _pairs(keys, meta)
        if not pairs:
            raise ValueError("EMPTY_KEY_POOL")
        self._clock = clock
        self._lock = threading.Lock()
        self._order: List[str] = [k for k, _ in pairs]
        self._meta = {k: m for k, m in pairs}
        self._state = {k: _fresh() for k in self._order}
        self._next = 0

    def __len__(self) -> int:
        return len(self._order)

    def __repr__(self) -> str:  # never include key material
        return f"KeyPool(keys={len(self._order)})"

    def sync(self, keys: Sequence[str], meta=None) -> bool:
        """Adopt a new key list. Keys that stay keep their cooldown; an empty list is ignored.
        Returns True when the set of keys changed."""
        pairs = _pairs(keys, meta)
        if not pairs:
            return False
        with self._lock:
            order = [k for k, _ in pairs]
            changed = order != self._order
            self._meta = {k: m for k, m in pairs}
            self._state = {k: self._state.get(k) or _fresh() for k in order}
            self._order = order
            self._next %= len(order)
            return changed

    def position(self, key: str) -> int:
        """1-based position of a key in the rotation, 0 when it is no longer in the pool."""
        with self._lock:
            return self._order.index(key) + 1 if key in self._state else 0

    def acquire(self, exclude: Sequence[str] = ()) -> Optional[str]:
        """Next available key in round-robin order, or None when every key is cooling or excluded."""
        with self._lock:
            now = self._clock()
            total = len(self._order)
            for step in range(total):
                index = (self._next + step) % total
                key = self._order[index]
                if key in exclude or self._state[key]["until"] > now:
                    continue
                self._next = (index + 1) % total
                return key
            return None

    def success(self, key: str) -> None:
        with self._lock:
            if key in self._state:
                self._state[key] = _fresh()

    def quota_exhausted(self, key: str) -> None:
        with self._lock:
            state = self._state.get(key)
            if state is None:
                return
            state["strikes"] += 1
            state["until"] = self._clock() + min(MAX_QUOTA_COOLDOWN, QUOTA_COOLDOWN * 2 ** (state["strikes"] - 1))
            state["state"] = "quota"

    def invalid(self, key: str) -> None:
        with self._lock:
            state = self._state.get(key)
            if state is not None:
                state["until"] = self._clock() + INVALID_COOLDOWN
                state["state"] = "invalid"

    def status(self) -> List[dict]:
        """Safe summary for the admin page: position, label, source, state and seconds until retry."""
        with self._lock:
            now = self._clock()
            result = []
            for index, key in enumerate(self._order):
                state, meta = self._state[key], self._meta.get(key, {})
                cooling = state["until"] > now
                result.append({"key": f"key {index + 1}", "label": meta.get("label"), "source": meta.get("source", "env"),
                               "id": meta.get("id"), "state": state["state"] if cooling else "ready",
                               "retry_in_seconds": max(0, round(state["until"] - now))})
            return result


_ACTIVE: Optional[KeyPool] = None


def set_active(pool: Optional[KeyPool]) -> None:
    """Remember the pool the chat provider uses so the admin page can show its state."""
    global _ACTIVE
    _ACTIVE = pool


def active_status() -> dict:
    return {"keys": _ACTIVE.status() if _ACTIVE else [], "configured": _ACTIVE is not None}
