"""Write chunks produced by ``db_chunking`` into ``documents`` and ``text_chunks``.

Pipeline for one run: source documents -> chunks -> embeddings -> upsert.

Rules:
* ``text_chunks.embedding`` is NOT NULL, so a document is written only when
  every one of its chunks was embedded. A document that fails is reported and
  skipped; it is never written half way.
* Everything is an upsert keyed by stable ids: running twice gives the same
  rows. Chunks of a document that no longer exist are removed.
* One transaction per document, so a failure never leaves a partial document.
* The embedder is injected (``embed_texts(list[str]) -> list[list[float]]``),
  so tests never need the 2.2GB model.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, Sequence

from .db_chunking import CHUNKER_VERSION, DEFAULT_MAX_WORDS, NAMESPACE, DbChunk, SourceDocument, chunk_document

EMBEDDING_DIM = 1024  # text_chunks.embedding is vector(1024)
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


async def write_chunks(conn: Any, doc: SourceDocument, chunks: Sequence[DbChunk],
                       vectors: Sequence[Sequence[float]], index_version_id: str) -> None:
    document_id = uuid.UUID(doc.document_id)
    version_id = uuid.UUID(index_version_id)
    now = datetime.now(timezone.utc)
    # chunks that no longer exist for this document under this index version
    await conn.execute(
        "DELETE FROM text_chunks WHERE document_id = $1 AND index_version_id = $2 AND chunk_index >= $3",
        document_id, version_id, len(chunks),
    )
    await conn.executemany(
        """
        INSERT INTO text_chunks
            (chunk_id, document_id, index_version_id, chunk_index, page_number, section_label,
             chunk_text, token_count, char_start, char_end, content_hash, embedding, created_at)
        VALUES ($1, $2, $3, $4, NULL, $5, $6, $7, $8, $9, $10, $11, $12)
        ON CONFLICT (index_version_id, document_id, chunk_index) DO UPDATE
        SET chunk_id = EXCLUDED.chunk_id, section_label = EXCLUDED.section_label,
            chunk_text = EXCLUDED.chunk_text, token_count = EXCLUDED.token_count,
            char_start = EXCLUDED.char_start, char_end = EXCLUDED.char_end,
            content_hash = EXCLUDED.content_hash, embedding = EXCLUDED.embedding,
            created_at = EXCLUDED.created_at
        """,
        [
            (uuid.UUID(stored_chunk_id(index_version_id, c)), document_id, version_id, c.chunk_index,
             c.section_label[:255], c.text, c.token_count, c.char_start, c.char_end, c.content_hash,
             list(vector), now)
            for c, vector in zip(chunks, vectors)
        ],
    )


def embed_all(embedder: Embedder, chunks: Sequence[DbChunk], batch_size: int = 32) -> list[list[float]]:
    """Embed in batches. Raises on the first failing batch or a wrong vector size."""
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), batch_size):
        batch = [c.text for c in chunks[start:start + batch_size]]
        out = embedder.embed_texts(batch)
        if len(out) != len(batch):
            raise ValueError(f"embedder returned {len(out)} vectors for {len(batch)} texts")
        for vector in out:
            if len(vector) != EMBEDDING_DIM:
                raise ValueError(f"vector has {len(vector)} dimensions, text_chunks needs {EMBEDDING_DIM}")
        vectors.extend(out)
    return vectors


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
