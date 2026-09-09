"""Typed contracts shared by the Phase 5 workflow, providers, and tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias, TypedDict

from searchrank_ai.retrieval import RetrievalMode, SearchConstraints
from searchrank_ai.storage import StoredProduct

RequestType: TypeAlias = Literal["search", "compare", "unsupported"]
FinalStatus: TypeAlias = Literal[
    "answered",
    "clarification_required",
    "unsupported",
    "conflicting_constraints",
    "no_results",
    "verification_failed",
    "tool_limit_reached",
]
ScalarValue: TypeAlias = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class RequestAnalysis:
    """Structured request interpretation proposed by an LLM provider."""

    request_type: RequestType
    normalized_query: str
    constraints: dict[str, object] = field(default_factory=dict)
    comparison_criteria: tuple[str, ...] = ()
    clarification_question: str | None = None
    unsupported_reason: str | None = None

    def __post_init__(self) -> None:
        if self.request_type not in {"search", "compare", "unsupported"}:
            raise ValueError(f"unsupported request type: {self.request_type}")
        if self.request_type != "unsupported" and not self.normalized_query.strip():
            raise ValueError("supported requests require a normalized search query")
        criteria = tuple(dict.fromkeys(value.strip() for value in self.comparison_criteria))
        if any(not value for value in criteria):
            raise ValueError("comparison criteria must not contain blanks")
        object.__setattr__(self, "normalized_query", self.normalized_query.strip())
        object.__setattr__(self, "comparison_criteria", criteria)
        object.__setattr__(
            self,
            "clarification_question",
            self.clarification_question.strip() if self.clarification_question else None,
        )
        object.__setattr__(
            self,
            "unsupported_reason",
            self.unsupported_reason.strip() if self.unsupported_reason else None,
        )

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> RequestAnalysis:
        constraints = value.get("constraints", {})
        criteria = value.get("comparison_criteria", [])
        if not isinstance(constraints, dict):
            raise ValueError("constraints must be an object")
        if not isinstance(criteria, list) or not all(isinstance(item, str) for item in criteria):
            raise ValueError("comparison criteria must be a list of strings")
        return cls(
            request_type=value.get("request_type"),
            normalized_query=str(value.get("normalized_query", "")),
            constraints=constraints,
            comparison_criteria=tuple(criteria),
            clarification_question=value.get("clarification_question"),
            unsupported_reason=value.get("unsupported_reason"),
        )


@dataclass(frozen=True, slots=True)
class ProductCitation:
    product_id: str
    source_url: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> ProductCitation:
        return cls(
            product_id=str(value.get("product_id", "")),
            source_url=str(value.get("source_url", "")),
        )


@dataclass(frozen=True, slots=True)
class FactualClaim:
    """A proposed catalogue value and its proposed product citation."""

    product_id: str
    field: str
    value: ScalarValue
    citation: ProductCitation

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> FactualClaim:
        citation = value.get("citation")
        if not isinstance(citation, dict):
            raise ValueError("a factual claim requires a citation object")
        return cls(
            product_id=str(value.get("product_id", "")),
            field=str(value.get("field", "")),
            value=value.get("value"),
            citation=ProductCitation.from_mapping(citation),
        )


@dataclass(frozen=True, slots=True)
class ComparisonClaim:
    """A proposed deterministic numeric comparison between stored products."""

    product_ids: tuple[str, ...]
    field: str
    preferred_product_id: str
    preference: Literal["higher", "lower"]
    criterion: str
    citations: tuple[ProductCitation, ...]

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> ComparisonClaim:
        product_ids = value.get("product_ids")
        citations = value.get("citations")
        if not isinstance(product_ids, list) or not all(
            isinstance(item, str) for item in product_ids
        ):
            raise ValueError("comparison product IDs must be a list of strings")
        if not isinstance(citations, list) or not all(isinstance(item, dict) for item in citations):
            raise ValueError("comparison citations must be a list of objects")
        return cls(
            product_ids=tuple(product_ids),
            field=str(value.get("field", "")),
            preferred_product_id=str(value.get("preferred_product_id", "")),
            preference=value.get("preference"),
            criterion=str(value.get("criterion", "")).strip(),
            citations=tuple(ProductCitation.from_mapping(item) for item in citations),
        )


@dataclass(frozen=True, slots=True)
class AnswerDraft:
    """Structured answer content proposed by the configured LLM provider."""

    facts: tuple[FactualClaim, ...] = ()
    comparisons: tuple[ComparisonClaim, ...] = ()
    unavailable_information: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> AnswerDraft:
        facts = value.get("facts", [])
        comparisons = value.get("comparisons", [])
        unavailable = value.get("unavailable_information", [])
        if not isinstance(facts, list) or not all(isinstance(item, dict) for item in facts):
            raise ValueError("facts must be a list of objects")
        if not isinstance(comparisons, list) or not all(
            isinstance(item, dict) for item in comparisons
        ):
            raise ValueError("comparisons must be a list of objects")
        if not isinstance(unavailable, list) or not all(
            isinstance(item, str) for item in unavailable
        ):
            raise ValueError("unavailable information must be a list of strings")
        return cls(
            facts=tuple(FactualClaim.from_mapping(item) for item in facts),
            comparisons=tuple(ComparisonClaim.from_mapping(item) for item in comparisons),
            unavailable_information=tuple(item.strip() for item in unavailable if item.strip()),
        )


@dataclass(frozen=True, slots=True)
class SearchToolInput:
    normalized_query: str
    constraints: SearchConstraints
    mode: RetrievalMode = "hybrid"
    alpha: float = 0.25
    limit: int = 5


@dataclass(frozen=True, slots=True)
class SearchEvidence:
    rank: int
    product_id: str
    product_name: str
    brand: str
    price_inr: int
    ram_gb: float
    storage_gb: float
    user_rating_5: float | None
    source_url: str
    score: float


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    tool: Literal["catalogue_search", "product_details", "evidence_verification"]
    input_count: int
    output_count: int


@dataclass(frozen=True, slots=True)
class VerificationIssue:
    code: str
    message: str
    claim_index: int | None = None


@dataclass(frozen=True, slots=True)
class VerificationReport:
    passed: bool
    issues: tuple[VerificationIssue, ...]
    verified_facts: tuple[FactualClaim, ...]
    verified_comparisons: tuple[ComparisonClaim, ...]


class WorkflowState(TypedDict, total=False):
    """Useful, serializable state passed between LangGraph nodes."""

    user_request: str
    conversation_context: tuple[str, ...]
    request_type: RequestType
    normalized_query: str
    raw_constraints: dict[str, object]
    constraints: SearchConstraints
    comparison_criteria: tuple[str, ...]
    clarification_question: str | None
    unsupported_reason: str | None
    retrieved_ids: tuple[str, ...]
    search_evidence: tuple[SearchEvidence, ...]
    product_evidence: tuple[StoredProduct, ...]
    missing_product_ids: tuple[str, ...]
    tool_history: tuple[ToolCallRecord, ...]
    retry_count: int
    draft: AnswerDraft
    verification: VerificationReport
    final_status: FinalStatus
    final_response: str
    workflow_path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AgentOutcome:
    status: FinalStatus
    response: str
    request_type: RequestType | None
    constraints: SearchConstraints | None
    retrieved_product_ids: tuple[str, ...]
    missing_product_ids: tuple[str, ...]
    tool_history: tuple[ToolCallRecord, ...]
    retry_count: int
    workflow_path: tuple[str, ...]
    verification: VerificationReport | None
