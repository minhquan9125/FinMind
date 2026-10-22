"""Cached configuration access for the optional immutable source snapshot."""
from functools import lru_cache

from ..core import config
from .source_snapshot import SourceSnapshot, load_source_snapshot


@lru_cache
def configured_source_snapshot() -> SourceSnapshot | None:
    path = config.get_settings().source_snapshot_path
    return load_source_snapshot(path) if path else None
