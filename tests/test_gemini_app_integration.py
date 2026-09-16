"""Opt-in real model + catalogue + PostgreSQL checks through the API boundary."""

import os
import time

import pytest
from fastapi.testclient import TestClient

from searchrank_ai.api import create_app
from searchrank_ai.config import AppConfig
from searchrank_ai.evidence_policy import COMPARISON_RULES
from searchrank_ai.services import build_application_services


@pytest.fixture(scope="module")
def live_client():
    if os.getenv("SEARCHRANK_RUN_GEMINI_APP_INTEGRATION") != "1":
        pytest.skip("SEARCHRANK_RUN_GEMINI_APP_INTEGRATION is not 1")
    config = AppConfig.from_environment()
    if config.llm_provider != "gemini" or not config.gemini_free_tier_confirmed:
        pytest.fail("Explicit Gemini configuration and free-tier confirmation are required")
    services = build_application_services(config)
    drafts = []
    if services.query is not None:
        original_request = services.query.provider._request_json

        def trace_request(operation, instructions, payload, schema):
            result = original_request(operation, instructions, payload, schema)
            if operation == "grounded_answer_draft":
                drafts.append((payload, result))
            return result

        services.query.provider._request_json = trace_request
    with TestClient(create_app(services)) as client:
        assert all(client.get("/health").json()["components"].values())
        yield client, drafts


@pytest.mark.integration
@pytest.mark.parametrize(
    ("user_query", "expected"),
    [
        (
            "Find Samsung phones under INR 30000 with at least 8 GB RAM and 128 GB storage.",
            "answered",
        ),
        (
            "Compare Samsung phones under INR 30000 with at least 8 GB RAM and 128 GB storage "
            "by lowest price and highest rating.",
            "answered",
        ),
        ("Write a poem about the ocean.", "unsupported"),
    ],
    ids=["search", "comparison", "unsupported"],
)
def test_real_gemini_workflow(live_client, user_query, expected):
    client, drafts = live_client
    started = time.perf_counter()
    response = client.post("/query", json={"request": user_query})
    body = response.json()
    print(
        {
            "expected": expected,
            "http": response.status_code,
            "status": body.get("status"),
            "seconds": round(time.perf_counter() - started, 2),
        }
    )
    assert response.status_code == 200, body
    assert body["status"] == expected, body
    if expected == "answered":
        assert body["response"]
        assert body["verification"]["passed"] is True
        assert len(body["tool_history"]) <= 4
        assert body["constraints"]["max_price_inr"] == 30000
        assert body["constraints"]["min_ram_gb"] == 8
        assert body["constraints"]["min_storage_gb"] == 128
        assert body["constraints"]["included_brands"] == ["samsung"]
        if user_query.startswith("Compare"):
            payload, draft = drafts[-1]
            evidence = payload["catalogue_data"]
            assert set(payload["comparison_criteria"]) == {"lowest price", "highest rating"}
            for criterion in payload["comparison_criteria"]:
                field, direction = COMPARISON_RULES[criterion]
                values = {p["product_id"]: p[field] for p in evidence}
                target = min(values.values()) if direction == "lower" else max(values.values())
                winners = [product_id for product_id, value in values.items() if value == target]
                claims = [c for c in draft["comparisons"] if c["criterion"] == criterion]
                if len(winners) == 1:
                    assert len(claims) == 1
                    assert claims[0]["preferred_product_id"] == winners[0]
                    assert set(claims[0]["product_ids"]) == set(values)
                else:
                    # A sole-winner claim is invalid on ties; require all factual values instead.
                    assert claims == []
                    facts = {
                        f["product_id"]: f["value"] for f in draft["facts"] if f["field"] == field
                    }
                    assert facts == values
