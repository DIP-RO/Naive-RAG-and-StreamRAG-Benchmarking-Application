from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Assessment Agent"
    environment: Literal["dev", "test", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    sqlite_path: Path = Path("./data/assessment.db")
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "assessment_chunks"
    postgres_dsn: str | None = None

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    google_api_key_fallback: str | None = None
    google_api_key_fallback_2: str | None = None
    openrouter_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OPENROUTER_API_KEY", "API_KEY_OPEN_ROUTER", "GEMMA_API_KEY_OPEN_ROUTER"
        ),
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_name: str = "Applied AI Engineer Assessment"
    openrouter_referer: str | None = None
    langchain_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LANGCHAIN_API_KEY", "LANGSMITH_API_KEY"),
    )
    langchain_project: str = "assessment-agent"
    langchain_tracing_v2: bool = False
    default_llm_provider: Literal["openai", "openrouter", "google"] = "google"
    default_llm_model: str = "gpt-4.1"
    default_embedding_model: str = "text-embedding-3-small"

    max_context_tokens: int = 14_000
    max_output_tokens: int = 2_000
    naive_top_k: int = 30
    stream_initial_top_k: int = 30
    stream_final_top_k: int = 30
    retrieval_timeout_s: float = 8.0
    request_timeout_s: float = 30.0

    benchmark_trials: int = 3


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
