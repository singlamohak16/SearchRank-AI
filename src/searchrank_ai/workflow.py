"""One bounded LangGraph workflow for search, comparison, and grounded answers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from langgraph.graph import END, START, StateGraph

from searchrank_ai.agent_models import (
    AgentOutcome,
    AnswerDraft,
    FinalStatus,
    SearchToolInput,
    ToolCallRecord,
    WorkflowState,
)
from searchrank_ai.agent_tools import (
    CatalogueSearchTool,
    EvidenceVerificationTool,
    ProductDetailsTool,
)
from searchrank_ai.llm import LLMProvider
from searchrank_ai.retrieval import SearchConstraints

MAX_REFORMULATIONS = 1
MAX_TOOL_CALLS = 4
DEFAULT_RESULT_LIMIT = 5
_FIELD_LABELS = {
    "product_name": "product name",
    "brand": "brand",
    "price_inr": "price",
    "ram_gb": "RAM",
    "storage_gb": "storage",
    "user_rating_5": "user rating",
    "processor": "processor",
    "battery_mah": "battery capacity",
    "charging": "charging",
    "display_inches": "display size",
    "display_type": "display type",
    "rear_camera": "rear camera",
    "front_camera": "front camera",
    "release_date": "release date",
    "release_status": "release status",
}


def _path(state: WorkflowState, node: str) -> tuple[str, ...]:
    return (*state.get("workflow_path", ()), node)


def _format_value(field: str, value: object) -> str:
    if field == "price_inr":
        return f"₹{int(value):,}"
    if field in {"ram_gb", "storage_gb"}:
        return f"{value:g} GB"
    if field == "user_rating_5":
        return f"{value:g}/5"
    if field == "battery_mah":
        return f"{int(value):,} mAh"
    if field == "display_inches":
        return f"{value:g} inches"
    return str(value)


def _render_verified_answer(state: WorkflowState) -> str:
    report = state["verification"]
    products = {product.product_id: product for product in state["product_evidence"]}
    sections: list[str] = []
    if report.verified_facts:
        lines = ["Facts explicitly present in the catalogue:"]
        for claim in report.verified_facts:
            product = products[claim.product_id]
            label = _FIELD_LABELS[claim.field]
            value = _format_value(claim.field, getattr(product, claim.field))
            lines.append(
                f"- {product.product_name}: {label} is {value}. "
                f"[{product.product_id}]({product.source_url})"
            )
        sections.append("\n".join(lines))
    if report.verified_comparisons:
        lines = ["Conclusions derived from those facts:"]
        for claim in report.verified_comparisons:
            preferred = products[claim.preferred_product_id]
            value = _format_value(claim.field, getattr(preferred, claim.field))
            label = _FIELD_LABELS[claim.field]
            citations = ", ".join(
                f"[{citation.product_id}]({citation.source_url})" for citation in claim.citations
            )
            lines.append(
                f"- For {claim.criterion}, {preferred.product_name} has the {claim.preference} "
                f"{label} ({value}) among the compared products. Evidence: {citations}"
            )
        sections.append("\n".join(lines))
    unavailable = state["draft"].unavailable_information
    if unavailable:
        lines = ["Information unavailable in the catalogue:"]
        lines.extend(f"- {value}" for value in unavailable)
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


class AgentWorkflow:
    """Compile and run an auditable graph with fixed routes and call limits."""

    def __init__(
        self,
        provider: LLMProvider,
        catalogue_search: CatalogueSearchTool,
        product_details: ProductDetailsTool,
        evidence_verification: EvidenceVerificationTool,
    ) -> None:
        self.provider = provider
        self.catalogue_search = catalogue_search
        self.product_details = product_details
        self.evidence_verification = evidence_verification
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(WorkflowState)
        builder.add_node("analyze_request", self._analyze_request)
        builder.add_node("clarify", self._clarify)
        builder.add_node("unsupported", self._unsupported)
        builder.add_node("conflicting_constraints", self._conflicting_constraints)
        builder.add_node("catalogue_search", self._catalogue_search)
        builder.add_node("reformulate_query", self._reformulate_query)
        builder.add_node("no_results", self._no_results)
        builder.add_node("product_details", self._product_details)
        builder.add_node("generate_search_answer", self._generate_search_answer)
        builder.add_node("generate_comparison", self._generate_comparison)
        builder.add_node("verify_evidence", self._verify_evidence)

        builder.add_edge(START, "analyze_request")
        builder.add_conditional_edges("analyze_request", self._route_analysis)
        builder.add_conditional_edges("catalogue_search", self._route_search)
        builder.add_edge("reformulate_query", "catalogue_search")
        builder.add_conditional_edges("product_details", self._route_details)
        builder.add_edge("generate_search_answer", "verify_evidence")
        builder.add_edge("generate_comparison", "verify_evidence")
        for node in (
            "clarify",
            "unsupported",
            "conflicting_constraints",
            "no_results",
            "verify_evidence",
        ):
            builder.add_edge(node, END)
        return builder.compile()

    @staticmethod
    def _tool_limit(state: WorkflowState, node: str) -> WorkflowState | None:
        if len(state.get("tool_history", ())) < MAX_TOOL_CALLS:
            return None
        return {
            "final_status": "tool_limit_reached",
            "final_response": "I stopped because the workflow reached its tool-call limit.",
            "workflow_path": _path(state, node),
        }

    def _analyze_request(self, state: WorkflowState) -> WorkflowState:
        analysis = self.provider.analyze_request(
            state["user_request"], state.get("conversation_context", ())
        )
        update: WorkflowState = {
            "request_type": analysis.request_type,
            "normalized_query": analysis.normalized_query,
            "raw_constraints": analysis.constraints,
            "comparison_criteria": analysis.comparison_criteria,
            "clarification_question": analysis.clarification_question,
            "unsupported_reason": analysis.unsupported_reason,
            "workflow_path": _path(state, "analyze_request"),
        }
        try:
            update["constraints"] = SearchConstraints.from_dict(analysis.constraints)
        except ValueError as error:
            update["final_status"] = "conflicting_constraints"
            update["unsupported_reason"] = str(error)
            return update
        if (
            analysis.request_type == "compare"
            and "best" in state["user_request"].casefold()
            and not analysis.comparison_criteria
        ):
            update["clarification_question"] = analysis.clarification_question or (
                "What criteria should define the best phone, such as price, rating, or battery?"
            )
        return update

    @staticmethod
    def _route_analysis(
        state: WorkflowState,
    ) -> Literal["clarify", "unsupported", "conflicting_constraints", "catalogue_search"]:
        if state.get("final_status") == "conflicting_constraints":
            return "conflicting_constraints"
        if state["request_type"] == "unsupported":
            return "unsupported"
        if state.get("clarification_question"):
            return "clarify"
        return "catalogue_search"

    @staticmethod
    def _clarify(state: WorkflowState) -> WorkflowState:
        return {
            "final_status": "clarification_required",
            "final_response": state.get("clarification_question")
            or "Please clarify the essential comparison criteria.",
            "workflow_path": _path(state, "clarify"),
        }

    @staticmethod
    def _unsupported(state: WorkflowState) -> WorkflowState:
        reason = state.get("unsupported_reason") or (
            "This request requires information that is not available in the smartphone catalogue."
        )
        return {
            "final_status": "unsupported",
            "final_response": reason,
            "workflow_path": _path(state, "unsupported"),
        }

    @staticmethod
    def _conflicting_constraints(state: WorkflowState) -> WorkflowState:
        reason = state.get("unsupported_reason") or "The requested constraints conflict."
        return {
            "final_status": "conflicting_constraints",
            "final_response": f"I cannot search until the constraints are corrected: {reason}",
            "workflow_path": _path(state, "conflicting_constraints"),
        }

    def _catalogue_search(self, state: WorkflowState) -> WorkflowState:
        limited = self._tool_limit(state, "catalogue_search")
        if limited is not None:
            return limited
        request = SearchToolInput(
            normalized_query=state["normalized_query"],
            constraints=state["constraints"],
            limit=DEFAULT_RESULT_LIMIT,
        )
        results = self.catalogue_search.invoke(request)
        record = ToolCallRecord("catalogue_search", 1, len(results))
        return {
            "search_evidence": results,
            "retrieved_ids": tuple(result.product_id for result in results),
            "tool_history": (*state.get("tool_history", ()), record),
            "workflow_path": _path(state, "catalogue_search"),
        }

    @staticmethod
    def _route_search(
        state: WorkflowState,
    ) -> Literal["product_details", "reformulate_query", "no_results"]:
        if state.get("final_status") == "tool_limit_reached":
            return "no_results"
        if state.get("retrieved_ids"):
            return "product_details"
        if state.get("retry_count", 0) < MAX_REFORMULATIONS:
            return "reformulate_query"
        return "no_results"

    def _reformulate_query(self, state: WorkflowState) -> WorkflowState:
        query = self.provider.reformulate_query(state["user_request"], state["normalized_query"])
        if not query.strip():
            raise ValueError("the reformulated query must not be empty")
        return {
            "normalized_query": query.strip(),
            "retry_count": state.get("retry_count", 0) + 1,
            "workflow_path": _path(state, "reformulate_query"),
        }

    @staticmethod
    def _no_results(state: WorkflowState) -> WorkflowState:
        if state.get("final_status") == "tool_limit_reached":
            response = state["final_response"]
            status: FinalStatus = "tool_limit_reached"
        else:
            response = (
                "I could not find a catalogue product matching the request and strict constraints "
                "after one bounded search reformulation."
            )
            status = "no_results"
        return {
            "final_status": status,
            "final_response": response,
            "workflow_path": _path(state, "no_results"),
        }

    def _product_details(self, state: WorkflowState) -> WorkflowState:
        limited = self._tool_limit(state, "product_details")
        if limited is not None:
            return limited
        lookup = self.product_details.invoke(state["retrieved_ids"])
        record = ToolCallRecord(
            "product_details", len(state["retrieved_ids"]), len(lookup.products)
        )
        update: WorkflowState = {
            "product_evidence": lookup.products,
            "missing_product_ids": lookup.missing_product_ids,
            "tool_history": (*state.get("tool_history", ()), record),
            "workflow_path": _path(state, "product_details"),
        }
        if state["request_type"] == "compare" and len(lookup.products) < 2:
            update["final_status"] = "clarification_required"
            update["clarification_question"] = (
                "I found fewer than two stored products. Please name other phones or "
                "broaden the request."
            )
        return update

    @staticmethod
    def _route_details(
        state: WorkflowState,
    ) -> Literal["clarify", "no_results", "generate_search_answer", "generate_comparison"]:
        if state.get("final_status") == "tool_limit_reached":
            return "no_results"
        if state.get("final_status") == "clarification_required":
            return "clarify"
        if state["request_type"] == "compare":
            return "generate_comparison"
        return "generate_search_answer"

    def _generate_draft(self, state: WorkflowState, node: str) -> WorkflowState:
        draft = self.provider.draft_answer(
            state["user_request"],
            state["request_type"],
            state["constraints"],
            state.get("comparison_criteria", ()),
            state["product_evidence"],
        )
        return {"draft": draft, "workflow_path": _path(state, node)}

    def _generate_search_answer(self, state: WorkflowState) -> WorkflowState:
        return self._generate_draft(state, "generate_search_answer")

    def _generate_comparison(self, state: WorkflowState) -> WorkflowState:
        return self._generate_draft(state, "generate_comparison")

    def _verify_evidence(self, state: WorkflowState) -> WorkflowState:
        limited = self._tool_limit(state, "verify_evidence")
        if limited is not None:
            return limited
        report = self.evidence_verification.invoke(
            state.get("draft", AnswerDraft()),
            state["product_evidence"],
            comparison_criteria=state.get("comparison_criteria", ()),
        )
        record = ToolCallRecord(
            "evidence_verification",
            len(state.get("draft", AnswerDraft()).facts)
            + len(state.get("draft", AnswerDraft()).comparisons),
            len(report.verified_facts) + len(report.verified_comparisons),
        )
        update: WorkflowState = {
            "verification": report,
            "tool_history": (*state.get("tool_history", ()), record),
            "workflow_path": _path(state, "verify_evidence"),
        }
        if report.passed:
            update["final_status"] = "answered"
            combined = {**state, **update}
            update["final_response"] = _render_verified_answer(combined)
        else:
            codes = ", ".join(dict.fromkeys(issue.code for issue in report.issues))
            update["final_status"] = "verification_failed"
            update["final_response"] = (
                "I did not return the generated product claims because deterministic evidence "
                f"verification failed: {codes}."
            )
        return update

    def invoke(
        self, user_request: str, *, conversation_context: Sequence[str] = ()
    ) -> AgentOutcome:
        """Run one request and return only the final auditable outcome."""
        if not user_request.strip():
            raise ValueError("user request must not be empty")
        if isinstance(conversation_context, str) or not all(
            isinstance(value, str) for value in conversation_context
        ):
            raise ValueError("conversation context must contain only strings")
        result = self.graph.invoke(
            {
                "user_request": user_request.strip(),
                "conversation_context": tuple(conversation_context),
                "tool_history": (),
                "retry_count": 0,
                "workflow_path": (),
            },
            {"recursion_limit": 20},
        )
        return AgentOutcome(
            status=result["final_status"],
            response=result["final_response"],
            request_type=result.get("request_type"),
            constraints=result.get("constraints"),
            retrieved_product_ids=result.get("retrieved_ids", ()),
            missing_product_ids=result.get("missing_product_ids", ()),
            tool_history=result.get("tool_history", ()),
            retry_count=result.get("retry_count", 0),
            workflow_path=result.get("workflow_path", ()),
            verification=result.get("verification"),
        )
