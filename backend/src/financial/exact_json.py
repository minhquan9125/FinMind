"""JSON numbers remain Decimal from source parsing through payload storage."""
from decimal import Decimal
import json


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def _reject(value):
    raise ValueError(f'Nonfinite JSON number: {value}')


def loads(text):
    return json.loads(text, parse_float=Decimal, parse_constant=_reject, object_pairs_hook=_unique)


def dumps(value):
    """Deterministic compact JSON; Decimal is a number, never a quoted string."""
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError('Nonfinite Decimal')
        return str(value)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError('JSON keys must be strings')
        return '{' + ','.join(json.dumps(k, ensure_ascii=False) + ':' + dumps(value[k]) for k in sorted(value)) + '}'
    if isinstance(value, (list, tuple)):
        return '[' + ','.join(dumps(v) for v in value) + ']'
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
