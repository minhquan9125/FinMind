"""Runtime configuration for the FinMind Vector RAG backend.

All values are read from environment variables (see .env.example) so the
same image works locally and inside Docker Compose without code changes.
"""

from functools import lru_cache

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
ENV_FILES = (ENV_PATH.parent.parent / ".env", ENV_PATH)


class Settings(BaseSettings):
    # Read root defaults first; backend-specific values take precedence.
    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore")


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

    # Existing research chat uses a pinned, read-only corpus. Fixture CLI stays separate.
    research_chat_live: bool = True
    research_retrieval_backend: Literal['dense', 'hybrid'] = 'hybrid'
    research_corpus_version_id: str = Field(default='33d33730-0f0a-5274-a7f8-8d32a6be07e8',
        pattern=r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
    research_retrieval_timeout_seconds: float = Field(default=120.0, gt=0, le=600, allow_inf_nan=False)
    research_warmup_enabled: bool = True
    research_warmup_timeout_seconds: float = Field(default=180.0, gt=0, le=600, allow_inf_nan=False)
    gemini_api_key: SecretStr = SecretStr('')
    b1_gemini_free_tier_confirmed: bool = False

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
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""
    frontend_url: str = "http://localhost:5173"

    # Hybrid Router live adapter control (Bước 12)
    hybrid_router_mode: Literal["mock", "shadow", "live"] = "mock"
    hybrid_router_index_id: str = ""  # UUID của index dùng cho LiveContentAdapter

@lru_cache
def get_settings() -> Settings:
    return Settings()
