"""Opt-in HTTP checks against the running, ingested Compose demonstration."""

from __future__ import annotations

import os
from urllib.parse import quote

import httpx
import pytest

API_URL = os.getenv("SEARCHRANK_TEST_API_URL", "").strip()
UI_URL = os.getenv("SEARCHRANK_TEST_UI_URL", "").strip()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not API_URL, reason="SEARCHRANK_TEST_API_URL is not set"),
]


@pytest.mark.parametrize("mode", ["bm25", "semantic", "hybrid"])
def test_live_search_filters_and_product_evidence(mode: str) -> None:
    with httpx.Client(base_url=API_URL, timeout=60) as client:
        health = client.get("/health")
        health.raise_for_status()
        assert health.json()["components"]["search"]
        assert health.json()["components"]["products"]
        response = client.post(
            "/search",
            json={
                "query": "Samsung Galaxy",
                "mode": mode,
                "limit": 5,
                "constraints": {
                    "included_brands": ["Samsung"],
                    "max_price_inr": 30000.0,
                    "min_ram_gb": 8.0,
                    "min_storage_gb": 128.0,
                },
            },
        )
        response.raise_for_status()
        results = response.json()["results"]
        assert results, "Expected Samsung products in the adopted catalogue"
        for result in results:
            assert result["brand"].casefold() == "samsung"
            assert result["price_inr"] <= 30000
            assert result["ram_gb"] >= 8
            assert result["storage_gb"] >= 128
            product = client.get("/products/" + quote(result["product_id"], safe=""))
            product.raise_for_status()
            evidence = product.json()
            for field in ("product_id", "product_name", "price_inr", "source_url"):
                assert evidence[field] == result[field]


def test_live_validation_missing_product_and_ui() -> None:
    with httpx.Client(base_url=API_URL, timeout=30) as client:
        assert client.post("/search", json={"query": " "}).status_code == 422
        assert client.get("/products/searchrank-smoke-nonexistent").status_code == 404
    if not UI_URL:
        pytest.skip("SEARCHRANK_TEST_UI_URL is not set")
    response = httpx.get(UI_URL.rstrip("/") + "/_stcore/health", timeout=30)
    response.raise_for_status()
    assert response.text.strip() == "ok"
