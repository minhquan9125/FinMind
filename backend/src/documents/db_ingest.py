"""Write chunks produced by ``db_chunking`` into ``documents`` and ``text_chunks``.

OWNERSHIP: storing vectors in pgvector is WBS12/WBS17 (Nhan). This module is a
REFERENCE implementation provided with the chunker so Nhan can reuse or replace
it; it is not run by default (chunk_from_supabase.py needs --confirmed-with-nhan).
It already settles: stable document/chunk ids, model label <= 50 characters
(index_versions.embedding_model is varchar(50)), one transaction per document,
and removal of chunks that no longer exist.

Pipeline for one run: source documents -> chunks -> embeddings -> upsert.

Rules:
* ``text_chunks.embedding`` is NOT NULL, so a document is written only when
  every one of its chunks was embedded. A document that fails is reported and
  skipped; it is never written half way.
* Everything is keyed by stable ids: running twice gives the same rows. A chunk
  whose content changed is NOT overwritten: the old chunk is retired
  (superseded_at) and a new chunk is inserted, so citations stay valid.
* One transaction per document, so a failure never leaves a partial document.
* The embedder is injected (``embed_texts(list[str]) -> list[list[float]]``),
  so tests never need the 2.2GB model.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, Sequence

from .batch_embeddings import EMBEDDING_DIM, embed_chunks  # noqa: F401 - EMBEDDING_DIM re-exported
from .db_chunking import CHUNKER_VERSION, DEFAULT_MAX_WORDS, NAMESPACE, DbChunk, SourceDocument, chunk_document

FILE_TYPE = "DB"  # documents.file_type is NOT NULL; these documents come from tables, not files


class Embedder(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class IngestResult:
    documents_ok: int = 0
    documents_failed: int = 0
    chunks_written: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


def index_version_id_for(max_words: int, embedding_model: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"index:{CHUNKER_VERSION}:{max_words}:{embedding_model}"))


def stored_chunk_id(index_version_id: str, chunk: DbChunk) -> str:
    """Primary key in text_chunks: the same chunk under another index version is a different row."""
    return str(uuid.uuid5(NAMESPACE, f"text_chunk:{index_version_id}:{chunk.chunk_id}"))


def document_sha256(doc: SourceDocument, chunks: Sequence[DbChunk]) -> str:
    """documents.sha256 is unique: derive it from the source identity plus the content."""
    digest = hashlib.sha256()
    digest.update(f"{doc.source_table}:{doc.source_id}".encode("utf-8"))
    for chunk in chunks:
        digest.update(chunk.content_hash.encode("ascii"))
    return digest.hexdigest()


async def ensure_index_version(conn: Any, max_words: int, embedding_model: str) -> str:
    index_version_id = index_version_id_for(max_words, embedding_model)
    await conn.execute(
        """
        INSERT INTO index_versions
            (index_version_id, chunker_version, chunk_size, chunk_overlap, embedding_model, built_at, status)
        VALUES ($1, $2, $3, 0, $4, $5, 'ACTIVE')
        ON CONFLICT (index_version_id) DO NOTHING
        """,
        uuid.UUID(index_version_id), CHUNKER_VERSION, max_words, embedding_model, datetime.now(timezone.utc),
    )
    return index_version_id


async def _lookup_ids(conn: Any, doc: SourceDocument) -> tuple[Any, Any]:
    company_id = None
    if doc.symbol:
        company_id = await conn.fetchval(
            "SELECT company_id FROM companies WHERE symbol = $1 ORDER BY company_id LIMIT 1", doc.symbol)
    period_id = None
    period_code = doc.meta.get("period_code")
    if period_code:
        period_id = await conn.fetchval(
            "SELECT period_id FROM reporting_periods WHERE period_code = $1 LIMIT 1", period_code)
    return company_id, period_id


def _published(doc: SourceDocument) -> datetime | None:
    day = doc.meta.get("published_at")
    try:
        return datetime.fromisoformat(str(day)).replace(tzinfo=timezone.utc) if day else None
    except ValueError:
        return None


async def upsert_document(conn: Any, doc: SourceDocument, chunks: Sequence[DbChunk]) -> None:
    company_id, period_id = await _lookup_ids(conn, doc)
    await conn.execute(
        """
        INSERT INTO documents
            (document_id, company_id, period_id, doc_type, file_type, title, source_url, external_id,
             language, published_at, sha256, parse_status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'PARSED', $12)
        ON CONFLICT (document_id) DO UPDATE
        SET title = EXCLUDED.title, source_url = EXCLUDED.source_url, sha256 = EXCLUDED.sha256,
            company_id = EXCLUDED.company_id, period_id = EXCLUDED.period_id, parse_status = 'PARSED'
        """,
        uuid.UUID(doc.document_id), company_id, period_id, doc.doc_type, FILE_TYPE, doc.title[:500],
        doc.meta.get("url"), doc.source_id[:100], doc.language[:2], _published(doc),
        document_sha256(doc, chunks), datetime.now(timezone.utc),
    )


_INSERT_CHUNK_SQL = """
INSERT INTO text_chunks
    (chunk_id, document_id, index_version_id, chunk_index, page_number, section_label,
     chunk_text, token_count, char_start, char_end, content_hash, embedding, locator_json, created_at)
VALUES ($1, $2, $3, $4, NULL, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13)
"""


async def write_chunks(conn: Any, doc: SourceDocument, chunks: Sequence[DbChunk],
                       vectors: Sequence[Sequence[float]], index_version_id: str) -> None:
    """Write chunks without ever changing an existing chunk_id (leader decision, option B).

    * same position, same content  -> left untouched;
    * same position, content changed -> the old chunk is retired (superseded_at) and a NEW
      chunk is inserted, so evidence/citations keep pointing at the text they quoted;
    * position no longer exists     -> retired, never deleted;
    * content returns to an older text -> the retired chunk with that id is revived.
    """
    if len(chunks) != len(vectors):
        raise ValueError(f"expected {len(chunks)} vectors, got {len(vectors)}")
    document_id = uuid.UUID(doc.document_id)
    version_id = uuid.UUID(index_version_id)
    now = datetime.now(timezone.utc)

    current = await conn.fetch(
        "SELECT chunk_id, chunk_index, content_hash FROM text_chunks "
        "WHERE document_id = $1 AND index_version_id = $2 AND superseded_at IS NULL",
        document_id, version_id,
    )
    current_by_position = {row["chunk_index"]: row for row in current}

    retire: list[Any] = []
    links: list[tuple[Any, Any]] = []  # (old chunk_id, new chunk_id)
    pending: list[tuple[DbChunk, Sequence[float], uuid.UUID]] = []
    for chunk, vector in zip(chunks, vectors):
        new_id = uuid.UUID(stored_chunk_id(index_version_id, chunk))
        old = current_by_position.get(chunk.chunk_index)
        if old is not None:
            if str(old["content_hash"]).strip() == chunk.content_hash:
                continue  # nothing changed
            retire.append(old["chunk_id"])
            links.append((old["chunk_id"], new_id))
        pending.append((chunk, vector, new_id))
    retire.extend(row["chunk_id"] for position, row in current_by_position.items() if position >= len(chunks))

    if retire:
        await conn.execute(
            "UPDATE text_chunks SET superseded_at = $2 WHERE chunk_id = ANY($1::uuid[]) AND superseded_at IS NULL",
            retire, now,
        )

    # a text that came back: its old (retired) row already has this id, so revive it instead of inserting
    revived: set[Any] = set()
    if pending:
        existing = await conn.fetch(
            "SELECT chunk_id FROM text_chunks WHERE chunk_id = ANY($1::uuid[])",
            [new_id for _, _, new_id in pending],
        )
        revived = {row["chunk_id"] for row in existing}
        if revived:
            await conn.execute(
                "UPDATE text_chunks SET superseded_at = NULL, superseded_by_chunk_id = NULL "
                "WHERE chunk_id = ANY($1::uuid[])",
                list(revived),
            )

    rows = [
        (new_id, document_id, version_id, c.chunk_index, c.section_label[:255], c.text, c.token_count,
         c.char_start, c.char_end, c.content_hash, list(vector),
         json.dumps(c.locator, ensure_ascii=False, default=str), now)
        for c, vector, new_id in pending if new_id not in revived
    ]
    if rows:
        await conn.executemany(_INSERT_CHUNK_SQL, rows)
    if links:
        await conn.executemany(
            "UPDATE text_chunks SET superseded_by_chunk_id = $2 WHERE chunk_id = $1",
            [pair for pair in links if pair[1] not in revived],
        )


def embed_all(embedder: Embedder, chunks: Sequence[DbChunk], batch_size: int = 32,
              max_retries: int = 2) -> list[list[float]]:
    """Embed through batch_embeddings.embed_chunks (per-chunk retry and validation).

    A document is written only when every chunk got a valid vector, so any failure raises.
    """
    result = embed_chunks([{"chunk_id": c.chunk_id, "text": c.text} for c in chunks], embedder,
                          batch_size=batch_size, max_retries=max_retries)
    if result.failed:
        first = result.failed[0]
        raise ValueError(f"{len(result.failed)} chunk khong nhung duoc vector; dau tien "
                         f"{first['chunk_id']}: {first['error']}")
    by_id = {item["chunk"]["chunk_id"]: item["embedding"] for item in result.succeeded}
    return [by_id[c.chunk_id] for c in chunks]


async def ingest_documents(conn: Any, docs: Sequence[SourceDocument], embedder: Embedder,
                           embedding_model: str, max_words: int = DEFAULT_MAX_WORDS,
                           batch_size: int = 32) -> IngestResult:
    result = IngestResult()
    index_version_id = await ensure_index_version(conn, max_words, embedding_model)
    for doc in docs:
        chunks = chunk_document(doc, max_words)
        if not chunks:
            continue
        try:
            vectors = embed_all(embedder, chunks, batch_size)
            async with conn.transaction():
                await upsert_document(conn, doc, chunks)
                await write_chunks(conn, doc, chunks, vectors, index_version_id)
        except Exception as exc:  # noqa: BLE001 - one bad document must not stop the run
            result.documents_failed += 1
            result.errors.append({
                "source_table": doc.source_table, "source_id": doc.source_id,
                "chunks": len(chunks), "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        result.documents_ok += 1
        result.chunks_written += len(chunks)
    return result
