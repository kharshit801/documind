"""Application configuration loaded from environment variables.

All secrets and tunable parameters live here. Nothing else in the codebase
should read environment variables directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Values are loaded (in order of precedence) from:
      1. Real environment variables (e.g. Lambda env, docker-compose env_file)
      2. A local `.env` file at the project root, if present
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- LLM & Embeddings -------------------------------------------------
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")
    LLM_MODEL: str = Field(default="gpt-4o-mini")

    # ---- Pinecone ---------------------------------------------------------
    PINECONE_API_KEY: str = Field(default="", description="Pinecone API key")
    PINECONE_INDEX_NAME: str = Field(default="documind")
    PINECONE_ENVIRONMENT: str = Field(default="us-east-1-aws")

    # ---- App --------------------------------------------------------------
    APP_ENV: str = Field(default="development")
    MAX_FILE_SIZE_MB: int = Field(default=20, ge=1, le=200)
    CHUNK_SIZE: int = Field(default=500, ge=100, le=4000)
    CHUNK_OVERLAP: int = Field(default=50, ge=0, le=1000)
    TOP_K_RESULTS: int = Field(default=5, ge=1, le=50)

    # Embedding dimension for `text-embedding-3-small`. Override if you swap
    # the embedding model for one with a different output size.
    EMBEDDING_DIMENSION: int = Field(default=1536)

    # ---- AWS / Deployment -------------------------------------------------
    AWS_REGION: str = Field(default="us-east-1")
    S3_BUCKET_NAME: str = Field(default="documind-uploads")

    # ---- CORS -------------------------------------------------------------
    CORS_ALLOW_ORIGINS: str = Field(
        default="*",
        description="Comma-separated list of allowed origins, or '*' for all.",
    )

    @field_validator("CHUNK_OVERLAP")
    @classmethod
    def _overlap_lt_chunk(cls, v: int, info) -> int:
        chunk_size = info.data.get("CHUNK_SIZE", 500)
        if v >= chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return v

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def cors_origins(self) -> List[str]:
        if self.CORS_ALLOW_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Use this everywhere instead of constructing
    `Settings()` directly so values are loaded once per process (Lambda-safe).
    """
    return Settings()
