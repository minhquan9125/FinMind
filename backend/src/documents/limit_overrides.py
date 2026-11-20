"""Admin overrides of the B1 answering limits, versioned and bounded.

limits.json stays the tracked default. Overrides are stored in the local admin database, validated
against fixed bounds, and applied per request. Never editable here: the model, the config version
and max_cost_usd (the free-tier lock).
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import replace

from ..b1_answering.core.policy import Limits
from .research_metrics import ResearchMetrics, utc_now

# field -> (minimum, maximum)
EDITABLE = {
    'max_input_tokens': (1024, 65536),
    'max_output_tokens': (256, 8192),
    'read_timeout_seconds': (5, 600),
    'max_generation_calls': (1, 50),
    'max_total_tokens': (1024, 262144),
}


class LimitOverrides:
    def __init__(self, root):
        self.metrics = ResearchMetrics(root)
        with self.metrics.connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS limit_versions(
                id TEXT PRIMARY KEY,created_at TEXT NOT NULL,actor TEXT NOT NULL,reason TEXT NOT NULL,values_json TEXT NOT NULL)''')

    def current(self):
        """(version id or None, overrides dict) of the latest saved version."""
        with self.metrics.connect() as conn:
            row = conn.execute('SELECT id,values_json FROM limit_versions ORDER BY rowid DESC LIMIT 1').fetchone()
        return (row['id'], json.loads(row['values_json'])) if row else (None, {})

    def history(self, limit=30):
        with self.metrics.connect() as conn:
            rows = conn.execute('SELECT * FROM limit_versions ORDER BY rowid DESC LIMIT ?', (limit,)).fetchall()
        return [{'id': r['id'], 'created_at': r['created_at'], 'actor': r['actor'], 'reason': r['reason'],
                 'values': json.loads(r['values_json'])} for r in rows]

    def save(self, values, actor, reason, expected_version):
        clean = validate(values)
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500:
            raise ValueError('LIMITS_REASON_REQUIRED')
        with self.metrics.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT id FROM limit_versions ORDER BY rowid DESC LIMIT 1').fetchone()
            if (row[0] if row else None) != expected_version:
                raise ValueError('LIMITS_CONFIG_CHANGED')
            ident = str(uuid.uuid4())
            conn.execute('INSERT INTO limit_versions VALUES(?,?,?,?,?)',
                         (ident, utc_now(), actor, reason.strip(), json.dumps(clean, sort_keys=True)))
        return ident


def validate(values):
    """Keep only known fields with integer values inside their bounds; reject anything else."""
    if not isinstance(values, dict):
        raise ValueError('LIMITS_INVALID')
    clean = {}
    for key, value in values.items():
        if key not in EDITABLE:
            raise ValueError('LIMITS_FIELD_NOT_EDITABLE')
        low, high = EDITABLE[key]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError('LIMITS_OUT_OF_RANGE')
        clean[key] = value
    try:
        apply(Limits.load(), clean)          # the dataclass enforces the cross-field rules
    except (ValueError, TypeError):
        raise ValueError('LIMITS_INCONSISTENT') from None
    return clean


def apply(base, overrides):
    return replace(base, **overrides) if overrides else base


def effective_limits(root, base=None):
    """Tracked defaults plus the latest saved overrides. A broken override never blocks Chat."""
    base = base or Limits.load()
    try:
        return apply(base, LimitOverrides(root).current()[1])
    except Exception:
        return base


class CachedLimits:
    """Callable for the chat service: re-reads the saved overrides at most every `ttl` seconds."""

    def __init__(self, root, ttl=5.0, clock=time.monotonic):
        self.root, self.ttl, self.clock = root, ttl, clock
        self.base = Limits.load()
        self._value, self._at = self.base, None

    def __call__(self):
        now = self.clock()
        if self._at is None or now - self._at >= self.ttl:
            self._value, self._at = effective_limits(self.root, self.base), now
        return self._value
