"""Database access for the Vector RAG module.

RAG data uses dedicated ``rag_documents`` and ``rag_document_chunks`` tables
so it does not collide with the financial ``documents``/``text_chunks`` schema.
"""

import uuid

import asyncpg


async def create_document(pool: asyncpg.Pool, filename: str, page_count: int) -> str:
    document_id = str(uuid.uuid4())
    await pool.execute(
        """
        INSERT INTO rag_documents (id, filename, page_count)
        VALUES ($1, $2, $3)
        """,
        document_id,
        filename,
        page_count,
    )
    return document_id


async def insert_chunks(
    pool: asyncpg.Pool,
    document_id: str,
    rows: list[dict],
) -> None:
    """rows: list of dicts with keys chunk_index, page, text, word_count,
    token_count, unique_count, embedding (list[float])."""
    await pool.executemany(
        """
        INSERT INTO rag_document_chunks
            (id, document_id, chunk_index, page, text, word_count, token_count, unique_count, embedding)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        [
            (
                str(uuid.uuid4()),
                document_id,
                row["chunk_index"],
                row["page"],
                row["text"],
                row["word_count"],
                row["token_count"],
                row["unique_count"],
                row["embedding"],
            )
            for row in rows
        ],
    )


async def get_document(pool: asyncpg.Pool, document_id: str) -> asyncpg.Record | None:
    return await pool.fetchrow("SELECT * FROM rag_documents WHERE id = $1", document_id)


async def get_chunks(pool: asyncpg.Pool, document_id: str) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        SELECT chunk_index, page, text, word_count, token_count, unique_count
        FROM rag_document_chunks
        WHERE document_id = $1
        ORDER BY chunk_index
        """,
        document_id,
    )


async def vector_search(
    pool: asyncpg.Pool,
    document_id: str,
    query_embedding: list[float],
    top_k: int,
) -> list[asyncpg.Record]:
    """Nearest-neighbour search using pgvector cosine distance (<=>), scoped
    to one document. Score is reported as 1 - cosine_distance so higher is
    better, matching the "similarity" convention already used by the UI."""
    return await pool.fetch(
        """
        SELECT chunk_index, page, text, 1 - (embedding <=> $2::vector) AS score
        FROM rag_document_chunks
        WHERE document_id = $1
        ORDER BY embedding <=> $2::vector
        LIMIT $3
        """,
        document_id,
        query_embedding,
        top_k,
    )
