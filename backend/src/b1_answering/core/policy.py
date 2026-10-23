"""Budget and limits management for B1 answering."""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Limits:
    """Configuration limits for B1 answering."""
    version: str = 'b1-limits-v1'
    model: str = 'gemini-3.5-flash-lite'
    max_input_tokens: int = 16384
    max_output_tokens: int = 2048
    read_timeout_seconds: int = 600
    max_generation_calls: int = 20
    max_total_tokens: int = 65536
    max_cost_usd: float = 0.0

    def __post_init__(self) -> None:
        # Validate version and model
        if self.version != 'b1-limits-v1':
            raise ValueError(f'Invalid version: {self.version}')
        if self.model != 'gemini-3.5-flash-lite':
            raise ValueError(f'Invalid model: {self.model}')
        # Validate cost must be 0
        if isinstance(self.max_cost_usd, bool) or type(self.max_cost_usd) not in (int, float) or self.max_cost_usd != 0.0:
            raise ValueError(f'max_cost_usd must be 0.0, got {self.max_cost_usd}')
        # Validate all numeric fields
        self._validate_positive('max_input_tokens', self.max_input_tokens)
        self._validate_positive('max_output_tokens', self.max_output_tokens)
        self._validate_positive('max_generation_calls', self.max_generation_calls)
        self._validate_positive('max_total_tokens', self.max_total_tokens)
        self._validate_timeout(self.read_timeout_seconds)
        # Validate max_total_tokens >= max_output_tokens
        if self.max_total_tokens < self.max_output_tokens:
            raise ValueError(
                f'max_total_tokens ({self.max_total_tokens}) must be >= '
                f'max_output_tokens ({self.max_output_tokens})'
            )

    def _validate_positive(self, name: str, value: int) -> None:
        if type(value) is not int:
            raise TypeError(f'{name} must be int, got {type(value).__name__}')
        if value <= 0:
            raise ValueError(f'{name} must be > 0, got {value}')

    def _validate_timeout(self, value: int) -> None:
        if type(value) is not int:
            raise TypeError(f'read_timeout_seconds must be int, got {type(value).__name__}')
        if value <= 0 or value > 600:
            raise ValueError(f'read_timeout_seconds must be in (0, 600], got {value}')

    @classmethod
    def load(cls, path: Path | None = None) -> 'Limits':
        """Load limits from JSON file next to this module."""
        if path is None:
            path = Path(__file__).resolve().parents[1] / 'config' / 'limits.json'
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Check for missing/extra fields
        expected = {
            'version', 'model', 'max_input_tokens', 'max_output_tokens',
            'read_timeout_seconds', 'max_generation_calls', 'max_total_tokens',
            'max_cost_usd'
        }
        if not isinstance(data, dict):
            raise ValueError('Limits must be an object')
        actual = set(data.keys())
        missing = expected - actual
        extra = actual - expected
        if missing:
            raise ValueError(f'Missing fields: {missing}')
        if extra:
            raise ValueError(f'Extra fields: {extra}')
        # Check bool instead of number
        for key in expected:
            val = data[key]
            if isinstance(val, bool):
                raise TypeError(f'{key} is bool, expected number/string')
        # Check for nonfinite floats
        if isinstance(data.get('max_cost_usd'), float):
            cost = data['max_cost_usd']
            if math.isnan(cost) or math.isinf(cost):
                raise ValueError(f'max_cost_usd is nonfinite: {cost}')
        return cls(**data)


class PolicyError(Exception):
    """Policy violation error."""
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass
class Budget:
    """Thread-safe budget tracker for API calls."""
    limits: Limits
    _calls_used: int = field(default=0, init=False)
    _tokens_reserved: int = field(default=0, init=False)
    _unknown_usage: int = field(default=0, init=False)
    _reservations: dict[int, int] = field(default_factory=dict, init=False)
    _settled: set[int] = field(default_factory=set, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _next_ticket: int = field(default=1, init=False)

    def reserve(self, input_tokens: int) -> int:
        """Reserve tokens for a call. Returns ticket number."""
        with self._lock:
            # Validate input
            if type(input_tokens) is not int or input_tokens < 0:
                raise ValueError(f'input_tokens must be positive int, got {input_tokens}')
            # Check max_input_tokens
            if input_tokens > self.limits.max_input_tokens:
                raise PolicyError('INPUT_LIMIT_EXCEEDED')
            # Check call limit
            if self._calls_used >= self.limits.max_generation_calls:
                raise PolicyError('CALL_LIMIT_EXCEEDED')
            # Check total budget
            reservation = input_tokens + self.limits.max_output_tokens
            remaining = self.limits.max_total_tokens - self._tokens_reserved
            if reservation > remaining:
                raise PolicyError('BUDGET_EXCEEDED')
            # Reserve
            ticket = self._next_ticket
            self._next_ticket += 1
            self._calls_used += 1
            self._tokens_reserved += reservation
            self._reservations[ticket] = reservation
            return ticket

    def settle(self, ticket: int, usage: dict | None) -> None:
        """Retain worst-case reservation whenever usage cannot be trusted."""
        with self._lock:
            if type(ticket) is not int or ticket not in self._reservations:
                raise PolicyError('INVALID_TICKET')
            if ticket in self._settled:
                raise PolicyError('TICKET_ALREADY_SETTLED')
            reservation = self._reservations[ticket]
            self._settled.add(ticket)
            if usage is None:
                self._unknown_usage += 1
                raise PolicyError('USAGE_UNKNOWN')
            values = tuple(usage.get(k) for k in ('input_tokens', 'output_tokens', 'total_tokens')) if isinstance(usage, dict) else ()
            valid = len(values) == 3 and all(type(v) is int and v >= 0 for v in values)
            if valid:
                inp, out, total = values
                valid = (inp <= reservation - self.limits.max_output_tokens
                         and out <= self.limits.max_output_tokens
                         and inp + out <= total <= reservation)
            if not valid:
                self._unknown_usage += 1
                raise PolicyError('USAGE_LIMIT_EXCEEDED')
            self._tokens_reserved -= reservation - values[2]

    def snapshot(self) -> dict[str, Any]:
        """Return current budget state."""
        with self._lock:
            return {
                'calls_used': self._calls_used,
                'tokens_reserved': self._tokens_reserved,
                'unknown_usage': self._unknown_usage,
                'policy_version': self.limits.version,
            }
