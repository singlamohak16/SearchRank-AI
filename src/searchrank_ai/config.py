"""Environment-backed application configuration.

The project deliberately starts with the standard library. A dedicated settings
framework can be introduced later if nested settings or complex validation make
it worthwhile.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_VALID_ENVIRONMENTS = frozenset({"development", "test", "production"})
_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def _optional_environment_value(name: str) -> str | None:
    """Return a stripped environment value, treating blanks as unset."""
    value = os.getenv(name, "").strip()
    return value or None


def _environment_path(name: str, default: str) -> Path:
    value = os.getenv(name, default).strip()
    if not value:
        raise ValueError(f"{name} must not be empty")
    return Path(value)


def _environment_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().casefold()
    if value in {"1", "true", "yes"}:
        return True
    if value in {"0", "false", "no"}:
        return False
    raise ValueError(f"{name} must be one of: 1, 0, true, false, yes, no")


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Validated runtime settings read from ``SEARCHRANK_*`` variables."""

    environment: str = "development"
    log_level: str = "INFO"
    database_url: str | None = None
    llm_provider: str = "mock"
    llm_model: str | None = None
    llm_api_key: str | None = field(default=None, repr=False)
    catalogue_path: Path = Path("data/processed/suresh_91mobiles_2008_2026/catalogue.csv")
    bm25_index_path: Path = Path("artifacts/bm25/phase2-index.json")
    semantic_index_path: Path = Path("artifacts/semantic/phase3-index.npz")
    embedding_device: str = "cpu"
    embedding_local_only: bool = True

    def __post_init__(self) -> None:
        if self.environment not in _VALID_ENVIRONMENTS:
            allowed = ", ".join(sorted(_VALID_ENVIRONMENTS))
            raise ValueError(
                f"Invalid environment {self.environment!r}; expected one of: {allowed}"
            )

        if self.log_level not in _VALID_LOG_LEVELS:
            allowed = ", ".join(sorted(_VALID_LOG_LEVELS))
            raise ValueError(f"Invalid log level {self.log_level!r}; expected one of: {allowed}")

        if not self.llm_provider:
            raise ValueError("LLM provider must not be empty")

        if not self.embedding_device.strip():
            raise ValueError("embedding device must not be empty")

    @classmethod
    def from_environment(cls) -> AppConfig:
        """Build configuration from the process environment using safe defaults."""
        return cls(
            environment=os.getenv("SEARCHRANK_ENVIRONMENT", "development").strip().lower(),
            log_level=os.getenv("SEARCHRANK_LOG_LEVEL", "INFO").strip().upper(),
            database_url=_optional_environment_value("SEARCHRANK_DATABASE_URL"),
            llm_provider=os.getenv("SEARCHRANK_LLM_PROVIDER", "mock").strip().lower(),
            llm_model=_optional_environment_value("SEARCHRANK_LLM_MODEL"),
            llm_api_key=_optional_environment_value("SEARCHRANK_LLM_API_KEY"),
            catalogue_path=_environment_path(
                "SEARCHRANK_CATALOGUE_PATH",
                "data/processed/suresh_91mobiles_2008_2026/catalogue.csv",
            ),
            bm25_index_path=_environment_path(
                "SEARCHRANK_BM25_INDEX_PATH", "artifacts/bm25/phase2-index.json"
            ),
            semantic_index_path=_environment_path(
                "SEARCHRANK_SEMANTIC_INDEX_PATH", "artifacts/semantic/phase3-index.npz"
            ),
            embedding_device=os.getenv("SEARCHRANK_EMBEDDING_DEVICE", "cpu").strip(),
            embedding_local_only=_environment_bool("SEARCHRANK_EMBEDDING_LOCAL_ONLY", True),
        )
