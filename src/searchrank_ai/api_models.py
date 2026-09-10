"""Validated HTTP contracts for the SearchRank-AI Phase 6 API."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from searchrank_ai.agent_models import AgentOutcome
from searchrank_ai.retrieval import RetrievalResult, SearchConstraints
from searchrank_ai.storage import StoredProduct

NonEmptyText = Annotated[str, Field(min_length=1, max_length=2_000)]


class APIModel(BaseModel):
    """Base model with strict fields and predictable serialization."""

    model_config = ConfigDict(extra="forbid")


class SearchConstraintsPayload(APIModel):
    max_price_inr: float | None = Field(default=None, gt=0)
    min_ram_gb: float | None = Field(default=None, ge=0)
    included_brands: list[str] = Field(default_factory=list, max_length=20)
    excluded_brands: list[str] = Field(default_factory=list, max_length=20)
    min_rating_5: float | None = Field(default=None, ge=0, le=5)
    min_storage_gb: float | None = Field(default=None, ge=0)

    @field_validator("included_brands", "excluded_brands")
    @classmethod
    def validate_brands(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip() for value in values))
        if any(not value for value in normalized):
            raise ValueError("brand names must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_combination(self) -> SearchConstraintsPayload:
        self.to_domain()
        return self

    def to_domain(self) -> SearchConstraints:
        return SearchConstraints.from_dict(self.model_dump())

    @classmethod
    def from_domain(cls, value: SearchConstraints | None) -> SearchConstraintsPayload | None:
        return None if value is None else cls.model_validate(asdict(value))


class SearchRequest(APIModel):
    query: NonEmptyText
    mode: Literal["bm25", "semantic", "hybrid"] = "hybrid"
    alpha: float = Field(default=0.25, ge=0, le=1)
    limit: int = Field(default=10, ge=1, le=50)
    constraints: SearchConstraintsPayload = Field(default_factory=SearchConstraintsPayload)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value.strip()


class SearchResultResponse(APIModel):
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
    bm25_raw_score: float
    bm25_normalized_score: float
    semantic_cosine_score: float
    semantic_normalized_score: float

    @classmethod
    def from_domain(cls, value: RetrievalResult) -> SearchResultResponse:
        return cls.model_validate(value.as_dict())


class SearchResponse(APIModel):
    query: str
    mode: Literal["bm25", "semantic", "hybrid"]
    alpha: float
    constraints: SearchConstraintsPayload
    results: list[SearchResultResponse]


class QueryRequest(APIModel):
    request: NonEmptyText
    conversation_context: list[NonEmptyText] = Field(default_factory=list, max_length=10)

    @field_validator("request")
    @classmethod
    def strip_request(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("request must not be blank")
        return value.strip()

    @field_validator("conversation_context")
    @classmethod
    def strip_context(cls, values: list[str]) -> list[str]:
        stripped = [value.strip() for value in values]
        if any(not value for value in stripped):
            raise ValueError("conversation context must not contain blank messages")
        return stripped


class ToolCallResponse(APIModel):
    tool: str
    input_count: int
    output_count: int


class VerificationIssueResponse(APIModel):
    code: str
    message: str
    claim_index: int | None


class VerificationResponse(APIModel):
    passed: bool
    issues: list[VerificationIssueResponse]
    verified_fact_count: int
    verified_comparison_count: int
    verified_unavailable_count: int


class QueryResponse(APIModel):
    status: str
    response: str
    request_type: str | None
    constraints: SearchConstraintsPayload | None
    retrieved_product_ids: list[str]
    missing_product_ids: list[str]
    tool_history: list[ToolCallResponse]
    retry_count: int
    workflow_path: list[str]
    verification: VerificationResponse | None

    @classmethod
    def from_domain(cls, value: AgentOutcome) -> QueryResponse:
        verification = None
        if value.verification is not None:
            verification = VerificationResponse(
                passed=value.verification.passed,
                issues=[
                    VerificationIssueResponse.model_validate(asdict(issue))
                    for issue in value.verification.issues
                ],
                verified_fact_count=len(value.verification.verified_facts),
                verified_comparison_count=len(value.verification.verified_comparisons),
                verified_unavailable_count=len(value.verification.verified_unavailable),
            )
        return cls(
            status=value.status,
            response=value.response,
            request_type=value.request_type,
            constraints=SearchConstraintsPayload.from_domain(value.constraints),
            retrieved_product_ids=list(value.retrieved_product_ids),
            missing_product_ids=list(value.missing_product_ids),
            tool_history=[
                ToolCallResponse.model_validate(asdict(call)) for call in value.tool_history
            ],
            retry_count=value.retry_count,
            workflow_path=list(value.workflow_path),
            verification=verification,
        )


class ProductResponse(APIModel):
    product_id: str
    product_name: str
    brand: str
    price_inr: int
    ram_gb: float
    storage_gb: float
    user_rating_5: float | None
    processor: str | None
    battery_mah: int | None
    charging: str | None
    display_inches: float | None
    display_type: str | None
    rear_camera: str | None
    front_camera: str | None
    release_date: date | None
    release_status: str | None
    source_url: str
    image_url: str | None

    @classmethod
    def from_domain(cls, value: StoredProduct) -> ProductResponse:
        return cls.model_validate(asdict(value))


class HealthResponse(APIModel):
    status: Literal["ok", "degraded"]
    components: dict[str, bool]
    errors: dict[str, str]


class ErrorDetail(APIModel):
    location: list[str | int]
    message: str
    type: str


class ErrorBody(APIModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(APIModel):
    error: ErrorBody
