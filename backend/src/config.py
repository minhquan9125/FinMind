"""Runtime configuration for the FinMind Vector RAG backend.

All values are read from environment variables (see .env.example) so the
same image works locally and inside Docker Compose without code changes.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL / pgvector (ADR01)
    database_url: str = "postgresql://finmind:finmind@localhost:5432/finmind"

    # Embedding model (ADR04). Defaults to the model named in the project
    # proposal (Section 9, ADR04). Override with a smaller model for offline
    # unit tests via the EMBEDDING_MODEL environment variable.
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"
    embedding_dim: int = 1024

    # Chunking (same window/overlap as the original browser demo)
    chunk_words: int = 130
    chunk_stride: int = 100

    default_top_k: int = 5

    frontend_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
