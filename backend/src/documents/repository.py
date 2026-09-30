"""Database access for ERD-backed documents, chunks, and index versions."""

import uuid
from datetime import datetime, timezone

import asyncpg


def index_version_id_for(chunk_size: int, chunk_overlap: int, embedding_model: str) -> str:
    version_key = f"word-window-v1:{chunk_size}:{chunk_overlap}:{embedding_model}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"finmind:index:{version_key}"))


async def ensure_index_version(
    pool: asyncpg.Pool,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
) -> str:
    index_version_id = uuid.UUID(index_version_id_for(chunk_size, chunk_overlap, embedding_model))
    await pool.execute(
        """
        INSERT INTO index_versions
            (index_version_id, chunker_version, chunk_size, chunk_overlap,
             embedding_model, built_at, status)
        VALUES ($1, 'word-window-v1', $2, $3, $4, $5, 'ACTIVE')
        ON CONFLICT (index_version_id) DO NOTHING
        """,
        index_version_id,
        chunk_size,
        chunk_overlap,
        embedding_model,
        datetime.now(timezone.utc),
    )
    return str(index_version_id)


async def create_document(
    pool: asyncpg.Pool,
    filename: str,
    page_count: int,
    file_type: str,
    file_size: int,
    sha256: str,
    doc_type: str = "USER_UPLOAD",
) -> str:
    document_id = uuid.uuid5(uuid.NAMESPACE_URL, f"finmind:document:{sha256}")
    stored_document_id = await pool.fetchval(
        """
        INSERT INTO documents
            (document_id, doc_type, file_type, title, page_count, file_size,
             sha256, parse_status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'PARSED', $8)
        ON CONFLICT (sha256) DO UPDATE
        SET parse_status = EXCLUDED.parse_status
        RETURNING document_id
        """,
        document_id,
        doc_type,
        file_type.upper(),
        filename,
        page_count,
        file_size,
        sha256,
        datetime.now(timezone.utc),
    )
    return str(stored_document_id)


async def insert_chunks(
    pool: asyncpg.Pool,
    document_id: str,
    index_version_id: str,
    rows: list[dict],
) -> None:
    """Insert ERD-shaped chunks for one document and index version."""
    await pool.executemany(
        """
        INSERT INTO text_chunks
            (chunk_id, document_id, index_version_id, chunk_index, page_number,
             chunk_text, token_count, char_start, char_end, content_hash, embedding, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        ON CONFLICT (index_version_id, document_id, chunk_index) DO UPDATE
        SET page_number = EXCLUDED.page_number,
            chunk_text = EXCLUDED.chunk_text,
            token_count = EXCLUDED.token_count,
            char_start = EXCLUDED.char_start,
            char_end = EXCLUDED.char_end,
            content_hash = EXCLUDED.content_hash,
            embedding = EXCLUDED.embedding,
            created_at = EXCLUDED.created_at
        """,
        [
            (
                uuid.uuid4(),
                uuid.UUID(document_id),
                uuid.UUID(index_version_id),
                row["chunk_index"],
                row["page"],
                row["text"],
                row["token_count"],
                row["char_start"],
                row["char_end"],
                row["content_hash"],
                row["embedding"],
                datetime.now(timezone.utc),
            )
            for row in rows
        ],
    )


async def get_document(pool: asyncpg.Pool, document_id: str) -> asyncpg.Record | None:
    return await pool.fetchrow(
        "SELECT document_id AS id, title AS filename, page_count FROM documents WHERE document_id = $1",
        uuid.UUID(document_id),
    )


async def get_chunks(
    pool: asyncpg.Pool,
    document_id: str,
    index_version_id: str,
) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        SELECT chunk_index, page_number AS page, chunk_text AS text, token_count
        FROM text_chunks
        WHERE document_id = $1 AND index_version_id = $2
        ORDER BY chunk_index
        """,
        uuid.UUID(document_id),
        uuid.UUID(index_version_id),
    )


async def vector_search(
    pool: asyncpg.Pool,
    document_id: str,
    index_version_id: str,
    query_embedding: list[float],
    top_k: int,
) -> list[asyncpg.Record]:
    """Nearest-neighbour search using pgvector cosine distance (<=>), scoped
    to one document. Score is reported as 1 - cosine_distance so higher is
    better, matching the "similarity" convention already used by the UI."""
    return await pool.fetch(
        """
        SELECT chunk_index, page_number AS page, chunk_text AS text,
               1 - (embedding <=> $3::vector) AS score
        FROM text_chunks
        WHERE document_id = $1 AND index_version_id = $2
        ORDER BY embedding <=> $3::vector
        LIMIT $4
        """,
        uuid.UUID(document_id),
        uuid.UUID(index_version_id),
        query_embedding,
        top_k,
    )
