"""Logging setup shared by future command-line, API, and UI entry points."""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure application logging and return the package logger.

    Configuration values and credentials are intentionally not written to logs.
    Application entry points should call this function once during startup.
    """
    normalized_level = level.strip().upper()
    if normalized_level not in _VALID_LOG_LEVELS:
        allowed = ", ".join(sorted(_VALID_LOG_LEVELS))
        raise ValueError(f"Invalid log level {level!r}; expected one of: {allowed}")

    logging.basicConfig(
        level=getattr(logging, normalized_level),
        format=_LOG_FORMAT,
    )
    return logging.getLogger("searchrank_ai")
