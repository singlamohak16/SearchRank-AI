"""Offline Gemini contract, credential isolation, and fail-closed transport tests."""

import io
import json
from urllib.error import HTTPError, URLError

import pytest
from fastapi.testclient import TestClient

from searchrank_ai.api import create_app
from searchrank_ai.config import AppConfig
from searchrank_ai.gemini import MAX_RESPONSE_BYTES, GeminiProvider, _NoRedirect, _unique_winner
from searchrank_ai.llm import ProviderUnavailableError, build_llm_provider
from searchrank_ai.retrieval import SearchConstraints
from searchrank_ai.services import AppServices


def envelope(value):
    return {
        "candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(value)}]}}
        ]
    }


class FakeOpener:
    def __init__(self, value=None, *, raw=None, error=None):
        self.raw = raw if raw is not None else json.dumps(envelope(value)).encode()
        self.error = error
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return io.BytesIO(self.raw)


def provider(opener):
    return GeminiProvider("gemini-3.1-flash-lite", "synthetic-secret", opener=opener)


def test_request_analysis_preserves_contract_and_secure_transport():
    opener = FakeOpener(
        {
            "request_type": "search",
            "normalized_query": "Samsung",
            "constraints": {"max_price_inr": 30000, "min_ram_gb": 8},
            "comparison_criteria": [],
            "clarification_question": None,
            "unsupported_reason": None,
        }
    )
    analysis = provider(opener).analyze_request("Samsung under 30000 with 8GB RAM", ())
    assert analysis.constraints["max_price_inr"] == 30000
    assert analysis.constraints["min_ram_gb"] == 8
    request, timeout = opener.calls[0]
    body = json.loads(request.data)
    assert request.full_url == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.1-flash-lite:generateContent"
    )
    assert request.get_header("X-goog-api-key") == "synthetic-secret"
    assert "synthetic-secret" not in request.full_url
    assert "synthetic-secret" not in request.data.decode()
    assert timeout == 25
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["responseJsonSchema"]["additionalProperties"] is False
    criteria = body["generationConfig"]["responseJsonSchema"]["properties"]["comparison_criteria"]
    assert "lowest price" in criteria["items"]["enum"]
    assert "price_inr_lower" not in criteria["items"]["enum"]
    assert "unsupported" in body["systemInstruction"]["parts"][0]["text"]
    assert body["generationConfig"]["candidateCount"] == 1
    assert body["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "minimal"
    assert "tools" not in body
    assert len(opener.calls) == 1


def test_answer_and_reformulation_use_shared_prompts():
    opener = FakeOpener({"facts": [], "comparisons": [], "unavailable_information": []})
    assert not provider(opener).draft_answer("phone", "search", SearchConstraints(), (), ()).facts
    body = json.loads(opener.calls[0][0].data)
    assert "untrusted" in body["systemInstruction"]["parts"][0]["text"]
    payload = json.loads(body["contents"][0]["parts"][0]["text"])
    assert payload["catalogue_data"] == []
    assert payload["comparison_rules"]["lowest price"] == ["price_inr", "lower"]
    assert (
        body["generationConfig"]["responseJsonSchema"]["properties"]["comparisons"]["maxItems"] == 0
    )
    assert (
        provider(FakeOpener({"normalized_query": "Samsung"})).reformulate_query(
            "Samsung phones", "no match"
        )
        == "Samsung"
    )


def test_comparison_schema_binds_exact_requested_criteria_without_mutating_shared_schema():
    from searchrank_ai.llm import ANSWER_DRAFT_SCHEMA

    opener = FakeOpener({"facts": [], "comparisons": [], "unavailable_information": []})
    provider(opener).draft_answer(
        "Compare prices", "compare", SearchConstraints(), ("lowest price",), ()
    )
    schema = json.loads(opener.calls[0][0].data)["generationConfig"]["responseJsonSchema"]
    properties = schema["properties"]["comparisons"]["items"]["anyOf"][0]["properties"]
    assert properties["criterion"]["enum"] == ["lowest price"]
    assert properties["field"]["enum"] == ["price_inr"]
    assert properties["preference"]["enum"] == ["lower"]
    instructions = json.loads(opener.calls[0][0].data)["systemInstruction"]["parts"][0]["text"]
    assert "EVERY product in its product_ids, exactly once" in instructions
    assert "citation.product_id must equal that fact's product_id" in instructions
    assert "for ties report the factual values" in instructions
    assert (
        "enum"
        not in ANSWER_DRAFT_SCHEMA["properties"]["comparisons"]["items"]["properties"]["criterion"]
    )
    assert "maxItems" not in ANSWER_DRAFT_SCHEMA["properties"]["comparisons"]


def test_generation_schema_binds_catalogue_ids_and_exact_source_pairs():
    from searchrank_ai.llm import ANSWER_DRAFT_SCHEMA

    opener = FakeOpener({"facts": [], "comparisons": [], "unavailable_information": []})
    provider(opener)._request_json(
        "grounded_answer_draft",
        "test",
        {
            "catalogue_data": [{"product_id": "phone-a", "source_url": "https://example.test/a"}],
            "request_type": "search",
            "comparison_criteria": [],
            "comparison_rules": {},
        },
        ANSWER_DRAFT_SCHEMA,
    )
    schema = json.loads(opener.calls[0][0].data)["generationConfig"]["responseJsonSchema"]
    facts = schema["properties"]["facts"]["items"]["properties"]
    assert facts["product_id"]["enum"] == ["phone-a"]
    pair = facts["citation"]["anyOf"][0]["properties"]
    assert pair["product_id"]["enum"] == ["phone-a"]
    assert pair["source_url"]["enum"] == ["https://example.test/a"]
    assert (
        "enum"
        not in ANSWER_DRAFT_SCHEMA["properties"]["facts"]["items"]["properties"]["product_id"]
    )


@pytest.mark.parametrize(
    ("values", "direction", "expected"),
    [
        ([10, 20], "lower", "a"),
        ([10, 20], "higher", "b"),
        ([4.3, 4.3], "higher", None),
        ([10, None], "lower", None),
        ([10, True], "lower", None),
        ([10], "lower", None),
    ],
)
def test_unique_comparison_winner(values, direction, expected):
    evidence = [
        {"product_id": product_id, "value": value}
        for product_id, value in zip(("a", "b"), values, strict=False)
    ]
    assert _unique_winner(evidence, "value", direction) == expected


def test_tied_criterion_is_excluded_without_changing_evidence_or_shared_schema():
    from copy import deepcopy

    from searchrank_ai.llm import ANSWER_DRAFT_SCHEMA

    payload = {
        "catalogue_data": [
            {"product_id": "a", "source_url": "https://example.test/a", "user_rating_5": 4.3},
            {"product_id": "b", "source_url": "https://example.test/b", "user_rating_5": 4.3},
        ],
        "request_type": "compare",
        "comparison_criteria": ["highest rating"],
        "comparison_rules": {"highest rating": ("user_rating_5", "higher")},
    }
    original = deepcopy(payload)
    opener = FakeOpener({"facts": [], "comparisons": [], "unavailable_information": []})
    provider(opener)._request_json("grounded_answer_draft", "test", payload, ANSWER_DRAFT_SCHEMA)
    body = json.loads(opener.calls[0][0].data)
    assert (
        body["generationConfig"]["responseJsonSchema"]["properties"]["comparisons"]["maxItems"] == 0
    )
    sent_payload = json.loads(body["contents"][0]["parts"][0]["text"])
    assert "no sole winner" in sent_payload["comparison_notes"][0]
    assert payload == original
    assert "maxItems" not in ANSWER_DRAFT_SCHEMA["properties"]["comparisons"]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 302])
def test_http_errors_are_safe_and_never_retried(status):
    error = HTTPError("https://example.test", status, "synthetic-secret", {}, io.BytesIO(b"secret"))
    opener = FakeOpener(error=error)
    with pytest.raises(ProviderUnavailableError) as caught:
        provider(opener).reformulate_query("phone", "none")
    assert "secret" not in str(caught.value)
    assert len(opener.calls) == 1
    assert caught.value.__suppress_context__


@pytest.mark.parametrize("error", [URLError("synthetic-secret"), TimeoutError("synthetic-secret")])
def test_transport_failures_are_safe(error):
    with pytest.raises(ProviderUnavailableError, match="timed out"):
        provider(FakeOpener(error=error)).reformulate_query("phone", "none")


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b"[]",
        b"null",
        b"{}",
        b"\xff",
        json.dumps({"promptFeedback": {"blockReason": "SAFETY"}}).encode(),
        json.dumps({"candidates": [{"finishReason": "MAX_TOKENS"}]}).encode(),
        json.dumps(envelope([])).encode(),
        json.dumps({"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]}).encode(),
        b"x" * (MAX_RESPONSE_BYTES + 1),
    ],
    ids=[
        "text",
        "array",
        "null",
        "empty",
        "encoding",
        "blocked",
        "truncated",
        "list-output",
        "no-parts",
        "oversized",
    ],
)
def test_invalid_blocked_and_incomplete_responses_fail_closed(raw):
    with pytest.raises(ProviderUnavailableError):
        provider(FakeOpener(raw=raw)).reformulate_query("phone", "none")


def test_redirects_are_rejected():
    assert _NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test") is None


@pytest.mark.parametrize("model", ["", "gemini-paid", "../other?key=secret", "https://other.test"])
def test_unreviewed_models_rejected(model):
    with pytest.raises(ValueError, match="allowlist"):
        GeminiProvider(model, "synthetic-secret")


@pytest.mark.parametrize(
    "key", ["", "secret\nheader", "secret\rheader", "secret key", "secret\u2603"]
)
def test_invalid_header_credentials_are_rejected_without_echoing(key):
    with pytest.raises(ValueError) as caught:
        GeminiProvider("gemini-3.1-flash-lite", key)
    assert str(caught.value) == "Gemini requires GEMINI_API_KEY"


def test_environment_keeps_provider_keys_separate_and_private(monkeypatch):
    monkeypatch.setenv("SEARCHRANK_LLM_API_KEY", "openai-synthetic-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-synthetic-secret")
    monkeypatch.setenv("SEARCHRANK_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("SEARCHRANK_LLM_MODEL", "gemini-3.1-flash-lite")
    monkeypatch.delenv("SEARCHRANK_GEMINI_FREE_TIER_CONFIRMED", raising=False)
    config = AppConfig.from_environment()
    assert config.llm_api_key == "gemini-synthetic-secret"
    assert "secret" not in repr(config)
    with pytest.raises(ValueError, match="free tier"):
        build_llm_provider(config)
    monkeypatch.setenv("SEARCHRANK_GEMINI_FREE_TIER_CONFIRMED", "1")
    assert isinstance(build_llm_provider(AppConfig.from_environment()), GeminiProvider)
    monkeypatch.setenv("SEARCHRANK_LLM_PROVIDER", "openai")
    assert AppConfig.from_environment().llm_api_key == "openai-synthetic-secret"
    monkeypatch.setenv("SEARCHRANK_LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        build_llm_provider(AppConfig.from_environment())


def test_quota_failure_returns_actionable_503():
    class UnavailableQuery:
        def invoke(self, *_args, **_kwargs):
            raise ProviderUnavailableError("Gemini quota/rate limit reached. Do not upgrade.")

    with TestClient(create_app(AppServices(query=UnavailableQuery()))) as client:
        response = client.post("/query", json={"request": "Find Samsung phones"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert "Do not upgrade" in response.text
