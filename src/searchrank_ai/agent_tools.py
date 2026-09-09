"""Deterministic tools used by the bounded Phase 5 workflow."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from searchrank_ai.agent_models import (
    AnswerDraft,
    ComparisonClaim,
    FactualClaim,
    ProductCitation,
    SearchEvidence,
    SearchToolInput,
    VerificationIssue,
    VerificationReport,
)
from searchrank_ai.retrieval import HybridRetriever
from searchrank_ai.storage import ProductLookup, StoredProduct

FACT_FIELDS = frozenset(
    {
        "product_name",
        "brand",
        "price_inr",
        "ram_gb",
        "storage_gb",
        "user_rating_5",
        "processor",
        "battery_mah",
        "charging",
        "display_inches",
        "display_type",
        "rear_camera",
        "front_camera",
        "release_date",
        "release_status",
    }
)
NUMERIC_COMPARISON_FIELDS = frozenset(
    {
        "price_inr",
        "ram_gb",
        "storage_gb",
        "user_rating_5",
        "battery_mah",
        "display_inches",
    }
)


class ProductDetailsRepository(Protocol):
    def get_product_details(self, product_ids: Sequence[str]) -> ProductLookup: ...


class CatalogueSearchTool:
    """Run measured retrieval while keeping strict constraints deterministic."""

    name = "catalogue_search"

    def __init__(self, retriever: HybridRetriever) -> None:
        self._retriever = retriever

    def invoke(self, request: SearchToolInput) -> tuple[SearchEvidence, ...]:
        results = self._retriever.search(
            request.normalized_query,
            mode=request.mode,
            constraints=request.constraints,
            alpha=request.alpha,
            limit=request.limit,
        )
        return tuple(
            SearchEvidence(
                rank=result.rank,
                product_id=result.product_id,
                product_name=result.product_name,
                brand=result.brand,
                price_inr=result.price_inr,
                ram_gb=result.ram_gb,
                storage_gb=result.storage_gb,
                user_rating_5=result.user_rating_5,
                source_url=result.source_url,
                score=result.score,
            )
            for result in results
        )


class ProductDetailsTool:
    """Retrieve complete stored records without filling missing values."""

    name = "product_details"

    def __init__(self, repository: ProductDetailsRepository) -> None:
        self._repository = repository

    def invoke(self, product_ids: Sequence[str]) -> ProductLookup:
        return self._repository.get_product_details(product_ids)


def _comparable(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    return value


def _values_equal(expected: object, actual: object) -> bool:
    expected = _comparable(expected)
    actual = _comparable(actual)
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(float(expected), float(actual), rel_tol=0, abs_tol=1e-9)
    return expected == actual


def _citation_matches(citation: ProductCitation, product: StoredProduct) -> bool:
    return citation.product_id == product.product_id and citation.source_url == product.source_url


class EvidenceVerificationTool:
    """Verify structured claims against records; never interpret catalogue instructions."""

    name = "evidence_verification"

    def invoke(
        self,
        draft: AnswerDraft,
        products: Sequence[StoredProduct],
        *,
        comparison_criteria: Sequence[str] = (),
    ) -> VerificationReport:
        evidence = {product.product_id: product for product in products}
        criteria = {value.strip().casefold() for value in comparison_criteria if value.strip()}
        issues: list[VerificationIssue] = []
        verified_facts: list[FactualClaim] = []
        verified_comparisons: list[ComparisonClaim] = []

        if not draft.facts and not draft.comparisons and not draft.unavailable_information:
            issues.append(
                VerificationIssue("empty_draft", "the proposed answer contains no content")
            )

        for index, claim in enumerate(draft.facts):
            product = evidence.get(claim.product_id)
            if product is None:
                issues.append(
                    VerificationIssue(
                        "unknown_product", f"unknown product ID {claim.product_id!r}", index
                    )
                )
                continue
            if claim.field not in FACT_FIELDS:
                issues.append(
                    VerificationIssue(
                        "unsupported_field", f"field {claim.field!r} is not claimable", index
                    )
                )
                continue
            actual = getattr(product, claim.field)
            if actual is None:
                issues.append(
                    VerificationIssue(
                        "missing_value",
                        f"{claim.field} is unavailable for {claim.product_id}",
                        index,
                    )
                )
                continue
            if not _values_equal(claim.value, actual):
                issues.append(
                    VerificationIssue(
                        "value_mismatch",
                        f"{claim.field} does not match stored evidence for {claim.product_id}",
                        index,
                    )
                )
                continue
            if not _citation_matches(claim.citation, product):
                issues.append(
                    VerificationIssue(
                        "citation_mismatch",
                        f"citation does not match {claim.product_id}",
                        index,
                    )
                )
                continue
            verified_facts.append(claim)

        for index, claim in enumerate(draft.comparisons):
            unique_ids = tuple(dict.fromkeys(claim.product_ids))
            selected = [evidence.get(product_id) for product_id in unique_ids]
            if claim.preference not in {"higher", "lower"}:
                issues.append(
                    VerificationIssue(
                        "invalid_preference",
                        "comparison preference must be higher or lower",
                        index,
                    )
                )
                continue
            if len(unique_ids) < 2 or any(product is None for product in selected):
                issues.append(
                    VerificationIssue(
                        "invalid_comparison_products",
                        "comparisons require at least two retrieved product IDs",
                        index,
                    )
                )
                continue
            comparison_products = tuple(product for product in selected if product is not None)
            if claim.field not in NUMERIC_COMPARISON_FIELDS:
                issues.append(
                    VerificationIssue(
                        "unsupported_comparison_field",
                        f"field {claim.field!r} cannot be compared deterministically",
                        index,
                    )
                )
                continue
            if not criteria or claim.criterion.casefold() not in criteria:
                issues.append(
                    VerificationIssue(
                        "unapproved_criterion",
                        "the comparison criterion was not explicit in the request",
                        index,
                    )
                )
                continue
            values = {
                product.product_id: getattr(product, claim.field) for product in comparison_products
            }
            if any(value is None or isinstance(value, bool) for value in values.values()):
                issues.append(
                    VerificationIssue(
                        "missing_comparison_value",
                        f"not every product has {claim.field} evidence",
                        index,
                    )
                )
                continue
            expected_citations = {
                ProductCitation(product.product_id, product.source_url)
                for product in comparison_products
            }
            if set(claim.citations) != expected_citations:
                issues.append(
                    VerificationIssue(
                        "citation_mismatch",
                        "comparison citations do not match the compared products",
                        index,
                    )
                )
                continue
            numeric = {product_id: float(value) for product_id, value in values.items()}
            target = (
                max(numeric.values()) if claim.preference == "higher" else min(numeric.values())
            )
            winners = [product_id for product_id, value in numeric.items() if value == target]
            if winners != [claim.preferred_product_id]:
                issues.append(
                    VerificationIssue(
                        "comparison_mismatch",
                        "the preferred product does not follow the proposed numeric comparison",
                        index,
                    )
                )
                continue
            verified_comparisons.append(claim)

        return VerificationReport(
            passed=not issues,
            issues=tuple(issues),
            verified_facts=tuple(verified_facts),
            verified_comparisons=tuple(verified_comparisons),
        )
