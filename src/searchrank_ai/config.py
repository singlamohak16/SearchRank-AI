"""Environment-backed application configuration.

The project deliberately starts with the standard library. A dedicated settings
framework can be introduced later if nested settings or complex validation make
it worthwhile.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

_VALID_ENVIRONMENTS = frozenset({"development", "test", "production"})
_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def _optional_environment_value(name: str) -> str | None:
    """Return a stripped environment value, treating blanks as unset."""
    value = os.getenv(name, "").strip()
    return value or None


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Validated runtime settings read from ``SEARCHRANK_*`` variables."""

    environment: str = "development"
    log_level: str = "INFO"
    database_url: str | None = None
    llm_provider: str = "mock"
    llm_model: str | None = None
    llm_api_key: str | None = field(default=None, repr=False)

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
        )
