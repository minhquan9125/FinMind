"""Retention policy for chunks that were superseded (option B of the chunk_id decision).

When a chunk's content changes the old chunk is kept (superseded_at is set) so citations stay
valid. Price and index chunks change every trading day, so their retired rows would pile up.
Policy agreed with the leader:

* PRICE_HISTORY and MARKET_INDEX chunks that were superseded more than N days ago (default 30)
  are deleted;
* NEWS and FINANCIAL_STATEMENT chunks are NEVER deleted by this module;
* a retired chunk that is still cited (a row in ``evidence`` points to it) is never deleted.

The default is a dry run: it only counts what would be removed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

DEFAULT_DAYS = 30
DEFAULT_DOC_TYPES = ("PRICE_HISTORY", "MARKET_INDEX")
# Types that must never be removed by retention, even if someone passes them by mistake.
PROTECTED_DOC_TYPES = frozenset({"NEWS", "FINANCIAL_STATEMENT", "COMPANY_PROFILE"})

_WHERE = """
FROM public.text_chunks t
JOIN public.documents d ON d.document_id = t.document_id
WHERE d.doc_type = ANY($1::text[])
  AND t.superseded_at IS NOT NULL
  AND t.superseded_at < now() - ($2::int * interval '1 day')
  AND NOT EXISTS (SELECT 1 FROM public.evidence e WHERE e.chunk_id = t.chunk_id)
"""

COUNT_SQL = f"""
SELECT d.doc_type AS doc_type, count(*) AS chunks,
       coalesce(sum(pg_column_size(t.embedding) + length(t.chunk_text)), 0) AS bytes
{_WHERE}
GROUP BY d.doc_type
ORDER BY d.doc_type
"""

DELETE_SQL = f"""
DELETE FROM public.text_chunks
WHERE chunk_id IN (SELECT t.chunk_id {_WHERE})
"""


@dataclass
class RetentionReport:
    days: int
    doc_types: tuple[str, ...]
    applied: bool
    candidates: dict[str, int] = field(default_factory=dict)  # doc_type -> chunks
    bytes_total: int = 0
    deleted: int = 0

    @property
    def candidate_total(self) -> int:
        return sum(self.candidates.values())


def validate(days: int, doc_types: Sequence[str]) -> tuple[int, tuple[str, ...]]:
    if days < 1:
        raise ValueError("days must be at least 1")
    cleaned = tuple(dict.fromkeys(t.strip().upper() for t in doc_types if t.strip()))
    if not cleaned:
        raise ValueError("at least one doc_type is required")
    blocked = sorted(set(cleaned) & PROTECTED_DOC_TYPES)
    if blocked:
        raise ValueError(f"refusing to delete protected document types: {', '.join(blocked)}")
    return days, cleaned


def _deleted_count(status: Any) -> int:
    """asyncpg returns a status string such as 'DELETE 12'."""
    try:
        return int(str(status).split()[-1])
    except (ValueError, IndexError):
        return 0


async def run_retention(conn: Any, days: int = DEFAULT_DAYS,
                        doc_types: Sequence[str] = DEFAULT_DOC_TYPES, apply: bool = False) -> RetentionReport:
    days, types = validate(days, doc_types)
    report = RetentionReport(days=days, doc_types=types, applied=apply)
    rows = await conn.fetch(COUNT_SQL, list(types), days)
    for row in rows:
        report.candidates[str(row["doc_type"])] = int(row["chunks"])
        report.bytes_total += int(row["bytes"])
    if apply and report.candidate_total:
        async with conn.transaction():
            report.deleted = _deleted_count(await conn.execute(DELETE_SQL, list(types), days))
    return report
