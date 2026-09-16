"""One real Gemini request, gated separately from the paid OpenAI smoke test."""

import os

import pytest

from searchrank_ai.config import AppConfig
from searchrank_ai.llm import ProviderUnavailableError, build_llm_provider


@pytest.mark.integration
def test_gemini_analyzes_one_constraint_heavy_request():
    if os.getenv("SEARCHRANK_RUN_GEMINI_INTEGRATION") != "1":
        pytest.skip("SEARCHRANK_RUN_GEMINI_INTEGRATION is not 1")
    config = AppConfig.from_environment()
    if config.llm_provider != "gemini" or not config.gemini_free_tier_confirmed:
        pytest.fail("Explicit Gemini configuration and free-tier confirmation are required")
    try:
        analysis = build_llm_provider(config).analyze_request(
            "Find Samsung phones under INR 30000 with at least 8 GB RAM and 128 GB storage.", ()
        )
    except ProviderUnavailableError as error:
        pytest.fail(str(error), pytrace=False)
    assert analysis.request_type == "search"
    assert analysis.normalized_query
    assert analysis.constraints["max_price_inr"] == 30000
    assert analysis.constraints["min_ram_gb"] == 8
    assert analysis.constraints["min_storage_gb"] == 128
    assert analysis.constraints["included_brands"] == ["Samsung"]
