"""Offline contract and error-handling tests for the Phase 6 FastAPI app."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from searchrank_ai.agent_models import AgentOutcome, ToolCallRecord, VerificationReport
from searchrank_ai.api import create_app
from searchrank_ai.retrieval import RetrievalResult, SearchConstraints
from searchrank_ai.services import AppServices
from searchrank_ai.storage import ProductLookup, StoredProduct


def _product(product_id: str = "phone-a") -> StoredProduct:
    return StoredProduct(
        product_id=product_id,
        product_name="Phone A",
        brand="Test",
        price_inr=19_999,
        ram_gb=8,
        storage_gb=128,
        user_rating_5=4.2,
        processor="Test Chip",
        battery_mah=5000,
        charging="45W",
        display_inches=6.5,
        display_type="AMOLED",
        rear_camera="50 MP",
        front_camera="16 MP",
        release_date=date(2025, 1, 2),
        release_status="Released",
        source_url=f"https://example.test/{product_id}",
        image_url=None,
    )


def _result(product: StoredProduct) -> RetrievalResult:
    return RetrievalResult(
        rank=1,
        product_id=product.product_id,
        product_name=product.product_name,
        brand=product.brand,
        price_inr=product.price_inr,
        ram_gb=product.ram_gb,
        storage_gb=product.storage_gb,
        user_rating_5=product.user_rating_5,
        source_url=product.source_url,
        score=0.91,
        bm25_raw_score=3.5,
        bm25_normalized_score=1.0,
        semantic_cosine_score=0.82,
        semantic_normalized_score=0.91,
    )


class FakeSearch:
    def __init__(self, results=()) -> None:
        self.results = results
        self.calls = []

    def search(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return self.results


class FakeQuery:
    def __init__(self, outcome: AgentOutcome) -> None:
        self.outcome = outcome
        self.calls = []

    def invoke(self, request, *, conversation_context=()):
        self.calls.append((request, conversation_context))
        return self.outcome


class MemoryProducts:
    def __init__(self, products) -> None:
        self.products = {product.product_id: product for product in products}

    def get_product_details(self, product_ids):
        found = tuple(self.products[value] for value in product_ids if value in self.products)
        missing = tuple(value for value in product_ids if value not in self.products)
        return ProductLookup(found, missing)


def _outcome() -> AgentOutcome:
    return AgentOutcome(
        status="answered",
        response="Facts explicitly present in the catalogue:\n- Phone A costs ₹19,999.",
        request_type="search",
        constraints=SearchConstraints(max_price_inr=25_000),
        retrieved_product_ids=("phone-a",),
        missing_product_ids=(),
        tool_history=(ToolCallRecord("catalogue_search", 1, 1),),
        retry_count=0,
        workflow_path=("analyze_request", "catalogue_search", "verify_evidence"),
        verification=VerificationReport(True, (), (), (), ()),
    )


def _client():
    product = _product()
    search = FakeSearch((_result(product),))
    query = FakeQuery(_outcome())
    services = AppServices(search=search, query=query, products=MemoryProducts((product,)))
    return TestClient(create_app(services)), search, query


def test_health_reports_all_injected_components_ready() -> None:
    client, _, _ = _client()

    with client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "components": {"search": True, "query": True, "products": True},
        "errors": {},
    }


def test_search_validates_and_delegates_strict_constraints() -> None:
    client, search, _ = _client()

    with client:
        response = client.post(
            "/search",
            json={
                "query": "  test phone  ",
                "mode": "hybrid",
                "alpha": 0.25,
                "limit": 5,
                "constraints": {
                    "max_price_inr": 25_000,
                    "min_ram_gb": 8,
                    "included_brands": ["Test"],
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "test phone"
    assert payload["results"][0]["product_id"] == "phone-a"
    assert payload["results"][0]["source_url"] == "https://example.test/phone-a"
    query, options = search.calls[0]
    assert query == "test phone"
    assert options["constraints"] == SearchConstraints(
        max_price_inr=25_000,
        min_ram_gb=8,
        included_brands=("test",),
    )


def test_query_returns_auditable_workflow_fields() -> None:
    client, _, query = _client()

    with client:
        response = client.post(
            "/query",
            json={"request": " Find Phone A ", "conversation_context": [" Under ₹25,000 "]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "answered"
    assert payload["constraints"]["max_price_inr"] == 25_000
    assert payload["retrieved_product_ids"] == ["phone-a"]
    assert payload["tool_history"][0]["tool"] == "catalogue_search"
    assert payload["verification"]["passed"] is True
    assert query.calls == [("Find Phone A", ("Under ₹25,000",))]


def test_product_endpoint_returns_complete_record_and_404() -> None:
    client, _, _ = _client()

    with client:
        found = client.get("/products/phone-a")
        missing = client.get("/products/unknown")

    assert found.status_code == 200
    assert found.json()["release_date"] == "2025-01-02"
    assert found.json()["processor"] == "Test Chip"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "product_not_found"


def test_invalid_requests_use_stable_error_shape() -> None:
    client, _, _ = _client()

    with client:
        blank = client.post("/search", json={"query": "   "})
        conflict = client.post(
            "/search",
            json={
                "query": "phone",
                "constraints": {
                    "included_brands": ["Test"],
                    "excluded_brands": ["test"],
                },
            },
        )
        extra = client.post("/query", json={"request": "phone", "secret": "not allowed"})

    for response in (blank, conflict, extra):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert response.json()["error"]["details"]


def test_search_rejects_boolean_numeric_fields() -> None:
    client, _, _ = _client()
    invalid_payloads = (
        {"query": "phone", "alpha": False},
        {"query": "phone", "limit": True},
        {"query": "phone", "constraints": {"max_price_inr": True}},
        {"query": "phone", "constraints": {"min_ram_gb": False}},
        {"query": "phone", "constraints": {"min_storage_gb": True}},
        {"query": "phone", "constraints": {"min_rating_5": False}},
    )

    with client:
        responses = [client.post("/search", json=payload) for payload in invalid_payloads]

    assert all(response.status_code == 422 for response in responses)
    assert all(response.json()["error"]["code"] == "validation_error" for response in responses)


def test_unavailable_components_keep_health_but_return_503() -> None:
    services = AppServices(
        errors={
            "search": "Search is not configured.",
            "query": "Query is not configured.",
            "products": "Products are not configured.",
        }
    )

    with TestClient(create_app(services)) as client:
        health = client.get("/health")
        search = client.post("/search", json={"query": "phone"})

    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert search.status_code == 503
    assert search.json()["error"] == {
        "code": "service_unavailable",
        "message": "Search is not configured.",
        "details": [],
    }


def test_openapi_lists_the_four_phase_six_routes() -> None:
    client, _, _ = _client()

    with client:
        schema = client.get("/openapi.json").json()

    assert set(schema["paths"]) == {"/health", "/search", "/query", "/products/{product_id}"}
