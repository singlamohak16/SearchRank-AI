"""Foundation-level smoke tests."""

import logging

import pytest

from searchrank_ai import __version__
from searchrank_ai.config import AppConfig
from searchrank_ai.logging_config import configure_logging


def test_package_import_and_default_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """The package imports and starts safely without credentials."""
    variable_names = (
        "SEARCHRANK_ENVIRONMENT",
        "SEARCHRANK_LOG_LEVEL",
        "SEARCHRANK_DATABASE_URL",
        "SEARCHRANK_LLM_PROVIDER",
        "SEARCHRANK_LLM_MODEL",
        "SEARCHRANK_LLM_API_KEY",
    )
    for name in variable_names:
        monkeypatch.delenv(name, raising=False)

    config = AppConfig.from_environment()

    assert __version__ == "0.1.0.dev0"
    assert config.environment == "development"
    assert config.log_level == "INFO"
    assert config.llm_provider == "mock"
    assert config.database_url is None
    assert config.llm_api_key is None


def test_configuration_normalizes_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCHRANK_ENVIRONMENT", " TEST ")
    monkeypatch.setenv("SEARCHRANK_LOG_LEVEL", " debug ")
    monkeypatch.setenv("SEARCHRANK_LLM_PROVIDER", " MOCK ")

    config = AppConfig.from_environment()

    assert config.environment == "test"
    assert config.log_level == "DEBUG"
    assert config.llm_provider == "mock"


def test_logging_configuration_returns_application_logger() -> None:
    logger = configure_logging("warning")

    assert logger.name == "searchrank_ai"
    assert logging.getLogger().getEffectiveLevel() == logging.WARNING
