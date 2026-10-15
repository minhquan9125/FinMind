"""Runtime configuration for the FinMind Vector RAG backend.

All values are read from environment variables (see .env.example) so the
same image works locally and inside Docker Compose without code changes.
"""

from functools import lru_cache

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_PATH, extra="ignore")


    # PostgreSQL / pgvector (ADR01)
    database_url: str = "postgresql://finmind:finmind@localhost:5432/finmind"

    # Embedding model (ADR04). Defaults to the model named in the project
    # proposal (Section 9, ADR04). Override with a smaller model for offline
    # unit tests via the EMBEDDING_MODEL environment variable.
    embedding_model: str = "BAAI/bge-m3"
    # Pin the Hugging Face repository commit so every worker uses identical weights.
    embedding_model_revision: str = "5617a9f61b028005a4858fdac845db406aefb181"
    embedding_device: str = "cpu"
    embedding_dim: int = 1024
    embedding_batch_size: int = 8

    @property
    def embedding_model_ref(self) -> str:
        """Stable model identity stored with each vector index version.

        Uses the first 12 characters of the pinned commit: index_versions.embedding_model
        is varchar(50) and the full 40-character SHA does not fit (52 characters in total).
        """
        return f"{self.embedding_model}@{self.embedding_model_revision[:12]}"

    # Chunking (same window/overlap as the original browser demo)
    chunk_words: int = 130
    chunk_stride: int = 100

    default_top_k: int = 5

    frontend_origin: str = "http://localhost:5173"

    # Folder holding data_pipeline's normalized financial JSON
    # (data/normalized/{SYMBOL}.json), read by POST /api/documents/import-symbol/{symbol}.
    # Default is relative to the backend's working directory (matches how the
    # other defaults above assume a local `cd backend && uvicorn ...` run);
    # docker-compose overrides this to the path where it mounts ../data.
    financial_data_dir: str = "../data/normalized"



    # Cấu hình Auth / JWT (Tự phát triển - Custom Auth)
    jwt_secret_key: SecretStr = SecretStr("cadcf6b6010185805672e56de43183706ab20fe8d6d25f383d3111fceb4e36d1")
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # Rate limiting & Account Lockout
    auth_max_failed_attempts: int = 5
    auth_lockout_minutes: int = 15
@lru_cache
def get_settings() -> Settings:
    return Settings()
