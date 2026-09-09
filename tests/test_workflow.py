"""Route, retry, grounding, and limit tests for the Phase 5 LangGraph."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from searchrank_ai.agent_models import (
    AnswerDraft,
    ComparisonClaim,
    FactualClaim,
    ProductCitation,
    RequestAnalysis,
    SearchEvidence,
    UnavailableInformation,
)
from searchrank_ai.agent_tools import EvidenceVerificationTool, ProductDetailsTool
from searchrank_ai.llm import MockLLMProvider
from searchrank_ai.storage import ProductLookup, StoredProduct
from searchrank_ai.workflow import MAX_REFORMULATIONS, MAX_TOOL_CALLS, AgentWorkflow


def _product(product_id: str, name: str, *, price: int = 20_000) -> StoredProduct:
    return StoredProduct(
        product_id=product_id,
        product_name=name,
        brand="Test",
        price_inr=price,
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


def _hit(product: StoredProduct) -> SearchEvidence:
    return SearchEvidence(
        rank=1,
        product_id=product.product_id,
        product_name=product.product_name,
        brand=product.brand,
        price_inr=product.price_inr,
        ram_gb=product.ram_gb,
        storage_gb=product.storage_gb,
        user_rating_5=product.user_rating_5,
        source_url=product.source_url,
        score=0.9,
    )


def _citation(product: StoredProduct) -> ProductCitation:
    return ProductCitation(product.product_id, product.source_url)


class QueueSearchTool:
    def __init__(self, results):
        self.results = list(results)
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)
        if not self.results:
            raise AssertionError("unexpected extra search call")
        return self.results.pop(0)


class MemoryRepository:
    def __init__(self, products):
        self.products = {product.product_id: product for product in products}

    def get_product_details(self, product_ids):
        found = tuple(self.products[value] for value in product_ids if value in self.products)
        missing = tuple(value for value in product_ids if value not in self.products)
        return ProductLookup(found, missing)


def _workflow(provider, search_results, products):
    return AgentWorkflow(
        provider,
        QueueSearchTool(search_results),
        ProductDetailsTool(MemoryRepository(products)),
        EvidenceVerificationTool(),
    )


def test_search_request_uses_search_specific_route_and_grounded_response() -> None:
    product = _product("phone-a", "Phone A", price=19_999)
    provider = MockLLMProvider(
        (RequestAnalysis("search", "phone a", {"max_price_inr": 25_000}),),
        drafts=(
            AnswerDraft(facts=(FactualClaim("phone-a", "price_inr", 19_999, _citation(product)),)),
        ),
    )
    workflow = _workflow(provider, ((_hit(product),),), (product,))

    outcome = workflow.invoke("Find Phone A under 25000")

    assert outcome.status == "answered"
    assert outcome.workflow_path == (
        "analyze_request",
        "catalogue_search",
        "product_details",
        "generate_search_answer",
        "verify_evidence",
    )
    assert [call.tool for call in outcome.tool_history] == [
        "catalogue_search",
        "product_details",
        "evidence_verification",
    ]
    assert "Facts explicitly present" in outcome.response
    assert "₹19,999" in outcome.response
    assert "[phone-a](https://example.test/phone-a)" in outcome.response


def test_comparison_uses_distinct_route_and_verified_numeric_conclusion() -> None:
    first = _product("phone-a", "Phone A", price=18_000)
    second = _product("phone-b", "Phone B", price=22_000)
    comparison = ComparisonClaim(
        ("phone-a", "phone-b"),
        "price_inr",
        "phone-a",
        "lower",
        "price",
        (_citation(first), _citation(second)),
    )
    provider = MockLLMProvider(
        (RequestAnalysis("compare", "phone a phone b", comparison_criteria=("price",)),),
        drafts=(AnswerDraft(comparisons=(comparison,)),),
    )
    workflow = _workflow(provider, ((_hit(first), _hit(second)),), (first, second))

    outcome = workflow.invoke("Compare Phone A and Phone B by price")

    assert outcome.status == "answered"
    assert "generate_comparison" in outcome.workflow_path
    assert "lower price" in outcome.response
    assert outcome.verification and outcome.verification.passed


def test_best_request_without_criteria_routes_to_essential_clarification() -> None:
    provider = MockLLMProvider((RequestAnalysis("compare", "phones"),))
    workflow = _workflow(provider, (), ())

    outcome = workflow.invoke("Which phone is best?")

    assert outcome.status == "clarification_required"
    assert outcome.workflow_path == ("analyze_request", "clarify")
    assert "criteria" in outcome.response
    assert not outcome.tool_history


def test_explicit_unsupported_request_does_not_call_catalogue_tools() -> None:
    provider = MockLLMProvider(
        (
            RequestAnalysis(
                "unsupported",
                "",
                unsupported_reason="The catalogue does not contain repair instructions.",
            ),
        )
    )
    workflow = _workflow(provider, (), ())

    outcome = workflow.invoke("How do I repair a water-damaged phone?")

    assert outcome.status == "unsupported"
    assert outcome.workflow_path == ("analyze_request", "unsupported")
    assert "repair instructions" in outcome.response
    assert not outcome.tool_history


def test_conflicting_constraints_stop_before_search() -> None:
    provider = MockLLMProvider(
        (
            RequestAnalysis(
                "search",
                "samsung",
                {"included_brands": ["Samsung"], "excluded_brands": ["samsung"]},
            ),
        )
    )
    workflow = _workflow(provider, (), ())

    outcome = workflow.invoke("Show Samsung but exclude Samsung")

    assert outcome.status == "conflicting_constraints"
    assert outcome.workflow_path == ("analyze_request", "conflicting_constraints")
    assert not outcome.tool_history


def test_unsuccessful_search_reformulates_once_then_answers() -> None:
    product = _product("phone-a", "Phone A")
    provider = MockLLMProvider(
        (RequestAnalysis("search", "original query"),),
        reformulations=("bounded replacement",),
        drafts=(
            AnswerDraft(facts=(FactualClaim("phone-a", "brand", "Test", _citation(product)),)),
        ),
    )
    workflow = _workflow(provider, ((), (_hit(product),)), (product,))

    outcome = workflow.invoke("Find a phone")

    assert outcome.status == "answered"
    assert outcome.retry_count == MAX_REFORMULATIONS == 1
    assert outcome.workflow_path.count("reformulate_query") == 1
    assert [call.tool for call in outcome.tool_history].count("catalogue_search") == 2
    assert len(outcome.tool_history) == MAX_TOOL_CALLS


def test_search_stops_after_one_failed_reformulation() -> None:
    provider = MockLLMProvider(
        (RequestAnalysis("search", "original query"),),
        reformulations=("replacement query",),
    )
    workflow = _workflow(provider, ((), ()), ())

    outcome = workflow.invoke("Find a nonexistent phone")

    assert outcome.status == "no_results"
    assert outcome.retry_count == 1
    assert outcome.workflow_path.count("catalogue_search") == 2
    assert outcome.workflow_path.count("reformulate_query") == 1
    assert len(outcome.tool_history) == 2


def test_comparison_with_one_stored_product_requests_clarification() -> None:
    product = _product("phone-a", "Phone A")
    provider = MockLLMProvider(
        (RequestAnalysis("compare", "phone a phone b", comparison_criteria=("price",)),)
    )
    workflow = _workflow(provider, ((_hit(product),),), (product,))

    outcome = workflow.invoke("Compare Phone A and Phone B by price")

    assert outcome.status == "clarification_required"
    assert outcome.workflow_path[-1] == "clarify"
    assert "fewer than two" in outcome.response


def test_hallucinated_value_is_not_returned() -> None:
    product = _product("phone-a", "Phone A", price=20_000)
    provider = MockLLMProvider(
        (RequestAnalysis("search", "phone a"),),
        drafts=(AnswerDraft(facts=(FactualClaim("phone-a", "price_inr", 1, _citation(product)),)),),
    )
    workflow = _workflow(provider, ((_hit(product),),), (product,))

    outcome = workflow.invoke("Find Phone A")

    assert outcome.status == "verification_failed"
    assert "value_mismatch" in outcome.response
    assert "₹1" not in outcome.response


def test_workflow_rejects_empty_requests_and_string_context() -> None:
    provider = MockLLMProvider()
    workflow = _workflow(provider, (), ())

    with pytest.raises(ValueError, match="must not be empty"):
        workflow.invoke("  ")
    with pytest.raises(ValueError, match="only strings"):
        workflow.invoke("phone", conversation_context="not a sequence")


@pytest.mark.parametrize(
    "unavailable",
    [
        "Phone A costs INR 1 and is the best phone.",
        UnavailableInformation("phone-a", "price_inr"),
        UnavailableInformation("phone-a", "Phone A costs INR 1"),
        UnavailableInformation("unknown-phone", "weight_g"),
    ],
)
def test_unavailable_information_cannot_bypass_verification(unavailable) -> None:
    product = _product("phone-a", "Phone A")
    provider = MockLLMProvider(
        (RequestAnalysis("search", "phone a"),),
        drafts=(AnswerDraft(unavailable_information=(unavailable,)),),
    )
    outcome = _workflow(provider, ((_hit(product),),), (product,)).invoke("Tell me about Phone A")
    assert outcome.status == "verification_failed"
    assert not outcome.verification.passed
    assert "INR 1" not in outcome.response
    assert "Information unavailable" not in outcome.response


def test_verified_missing_information_uses_fixed_text_and_stored_citations() -> None:
    product = replace(_product("phone-a", "Phone A"), processor=None)
    missing = (
        UnavailableInformation("phone-a", "processor"),
        UnavailableInformation("phone-a", "weight_g"),
    )
    provider = MockLLMProvider(
        (RequestAnalysis("search", "phone a"),),
        drafts=(AnswerDraft(unavailable_information=missing),),
    )
    outcome = _workflow(provider, ((_hit(product),),), (product,)).invoke(
        "What are the processor and weight of Phone A?"
    )
    assert outcome.status == "answered"
    assert outcome.verification.verified_unavailable == missing
    assert "processor is unavailable in this catalogue" in outcome.response
    assert "weight is unavailable in this catalogue" in outcome.response
    assert outcome.response.count("[phone-a](https://example.test/phone-a)") == 2
    assert outcome.tool_history[-1].input_count == outcome.tool_history[-1].output_count == 2


@pytest.mark.parametrize(
    "constraints, changes",
    [
        ({"max_price_inr": 25000}, {"price_inr": 40000}),
        ({"min_ram_gb": 8}, {"ram_gb": 4}),
        ({"min_storage_gb": 128}, {"storage_gb": 64}),
        ({"min_rating_5": 4}, {"user_rating_5": None}),
        ({"min_rating_5": 4}, {"user_rating_5": 3}),
        ({"included_brands": ["Test"]}, {"brand": "Different"}),
        ({"excluded_brands": ["Different"]}, {"brand": "Different"}),
    ],
)
@pytest.mark.parametrize("request_type", ["search", "compare"])
def test_changed_database_records_fail_constraints_before_generation(
    constraints, changes, request_type
) -> None:
    indexed = _product("phone-a", "Phone A")
    stored = replace(indexed, **changes)
    # No draft is scripted: the workflow must not ask the provider to generate one.
    provider = MockLLMProvider((RequestAnalysis(request_type, "phone a", constraints),))
    outcome = _workflow(provider, ((_hit(indexed),),), (stored,)).invoke("Find matching phones")
    assert outcome.status == "verification_failed"
    assert "constraint_mismatch" in {issue.code for issue in outcome.verification.issues}
    assert provider.call_history == ["analyze_request"]
    assert [call.tool for call in outcome.tool_history] == [
        "catalogue_search",
        "product_details",
        "evidence_verification",
    ]
    assert "40,000" not in outcome.response


def test_changed_database_record_that_still_satisfies_constraints_is_answered() -> None:
    indexed = _product("phone-a", "Phone A")
    stored = replace(indexed, price_inr=24000)
    provider = MockLLMProvider(
        (RequestAnalysis("search", "phone a", {"max_price_inr": 25000}),),
        drafts=(
            AnswerDraft(facts=(FactualClaim("phone-a", "price_inr", 24000, _citation(stored)),)),
        ),
    )
    outcome = _workflow(provider, ((_hit(indexed),),), (stored,)).invoke("Phone A under 25000")
    assert outcome.status == "answered"
    assert "₹24,000" in outcome.response


def test_lowest_price_cannot_approve_the_most_expensive_phone() -> None:
    first = _product("phone-a", "Phone A", price=20000)
    second = _product("phone-b", "Phone B", price=30000)
    claim = ComparisonClaim(
        ("phone-a", "phone-b"),
        "price_inr",
        "phone-b",
        "higher",
        "lowest price",
        (_citation(first), _citation(second)),
    )
    provider = MockLLMProvider(
        (RequestAnalysis("compare", "phone a phone b", comparison_criteria=("lowest price",)),),
        drafts=(AnswerDraft(comparisons=(claim,)),),
    )
    outcome = _workflow(provider, ((_hit(first), _hit(second)),), (first, second)).invoke(
        "Compare Phone A and Phone B and choose the lowest price"
    )
    assert outcome.status == "verification_failed"
    assert "criterion_mismatch" in outcome.response
    assert "30,000" not in outcome.response
