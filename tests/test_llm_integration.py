"""Optional real-provider smoke test; never runs without an explicit opt-in."""

from __future__ import annotations

import os

import pytest

from searchrank_ai.llm import OpenAIResponsesProvider


@pytest.mark.integration
def test_openai_provider_can_analyze_one_request() -> None:
    if os.getenv("SEARCHRANK_RUN_LLM_INTEGRATION") != "1":
        pytest.skip("SEARCHRANK_RUN_LLM_INTEGRATION is not 1")
    api_key = os.getenv("SEARCHRANK_LLM_API_KEY", "").strip()
    model = os.getenv("SEARCHRANK_LLM_MODEL", "").strip()
    if not api_key or not model:
        pytest.skip("SEARCHRANK_LLM_API_KEY and SEARCHRANK_LLM_MODEL are required")

    analysis = OpenAIResponsesProvider(model, api_key).analyze_request(
        "Find Samsung phones under ₹30,000 with at least 8 GB RAM.", ()
    )

    assert analysis.request_type == "search"
    assert analysis.normalized_query
