"""Reproducible Phase 7 agent and API evaluation utilities.

The agent benchmark intentionally uses reviewed, scripted LLM outputs. It measures
the deterministic workflow around the model; it does not claim real-model quality.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from searchrank_ai.agent_models import (
    AgentOutcome,
    AnswerDraft,
    RequestAnalysis,
    SearchEvidence,
)
from searchrank_ai.agent_tools import EvidenceVerificationTool, ProductDetailsTool
from searchrank_ai.api import create_app
from searchrank_ai.llm import MockLLMProvider
from searchrank_ai.retrieval import HybridRetriever, load_evaluation_cases
from searchrank_ai.semantic import (
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
    SentenceTransformerEncoder,
)
from searchrank_ai.services import AppServices
from searchrank_ai.storage import PRODUCT_COLUMNS, ProductLookup, StoredProduct
from searchrank_ai.workflow import AgentWorkflow

_FINAL_STATUSES = frozenset(
    {
        "answered",
        "clarification_required",
        "unsupported",
        "conflicting_constraints",
        "no_results",
        "verification_failed",
        "tool_limit_reached",
    }
)


@dataclass(frozen=True, slots=True)
class AgentScenario:
    case_id: str
    category: str
    user_request: str
    analysis: RequestAnalysis
    search_batches: tuple[tuple[str, ...], ...]
    reformulations: tuple[str, ...]
    draft: AnswerDraft | None
    expected_status: str
    expected_tools: tuple[str, ...]
    expected_path: tuple[str, ...]
    expected_retry_count: int


class _MemoryRepository:
    def __init__(self, products: Mapping[str, StoredProduct]) -> None:
        self._products = products

    def get_product_details(self, product_ids: Sequence[str]) -> ProductLookup:
        products = tuple(self._products[value] for value in product_ids if value in self._products)
        missing = tuple(value for value in product_ids if value not in self._products)
        return ProductLookup(products, missing)


class _ScenarioSearchTool:
    """Return reviewed product batches while recording the workflow's requests."""

    def __init__(
        self, products: Mapping[str, StoredProduct], batches: Sequence[Sequence[str]]
    ) -> None:
        self._products = products
        self._batches = [tuple(batch) for batch in batches]

    def invoke(self, request: Any) -> tuple[SearchEvidence, ...]:
        if not self._batches:
            raise AssertionError("scenario made an unexpected catalogue-search call")
        product_ids = self._batches.pop(0)
        return tuple(
            SearchEvidence(
                rank=rank,
                product_id=product.product_id,
                product_name=product.product_name,
                brand=product.brand,
                price_inr=product.price_inr,
                ram_gb=product.ram_gb,
                storage_gb=product.storage_gb,
                user_rating_5=product.user_rating_5,
                source_url=product.source_url,
                score=max(0.0, 1.0 - (rank - 1) * 0.1),
            )
            for rank, product in enumerate(
                (self._products[product_id] for product_id in product_ids), start=1
            )
        )


def _stored_product(value: Mapping[str, object]) -> StoredProduct:
    unknown = set(value) - set(PRODUCT_COLUMNS)
    missing = set(PRODUCT_COLUMNS) - set(value)
    if unknown or missing:
        raise ValueError(
            f"fixture product fields differ from the catalogue schema; missing={sorted(missing)}, "
            f"unknown={sorted(unknown)}"
        )
    payload = dict(value)
    release_date = payload["release_date"]
    if release_date is not None:
        if not isinstance(release_date, str):
            raise ValueError("fixture release_date must be an ISO string or null")
        payload["release_date"] = date.fromisoformat(release_date)
    try:
        return StoredProduct(**payload)
    except TypeError as error:
        raise ValueError("fixture product has invalid values") from error


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return tuple(value)


def load_agent_scenarios(
    path: Path,
) -> tuple[dict[str, StoredProduct], tuple[AgentScenario, ...]]:
    """Load reviewed mock-agent cases and reject ambiguous fixture data."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("llm_mode") != "scripted_mock":
        raise ValueError("agent evaluation must declare llm_mode as scripted_mock")
    raw_products = payload.get("products")
    raw_cases = payload.get("cases")
    if not isinstance(raw_products, list) or not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("agent evaluation requires product fixtures and cases")
    products = tuple(_stored_product(value) for value in raw_products)
    product_by_id = {product.product_id: product for product in products}
    if len(products) != len(product_by_id) or any(not value for value in product_by_id):
        raise ValueError("fixture product IDs must be non-empty and unique")

    scenarios: list[AgentScenario] = []
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise ValueError("each agent scenario must be an object")
        case_id = str(raw.get("case_id", "")).strip()
        category = str(raw.get("category", "")).strip()
        user_request = str(raw.get("user_request", "")).strip()
        if not case_id or not category or not user_request:
            raise ValueError("each scenario requires a case ID, category, and request")
        analysis_value = raw.get("analysis")
        if not isinstance(analysis_value, dict):
            raise ValueError(f"scenario {case_id!r} requires an analysis object")
        batches_value = raw.get("search_batches", [])
        if not isinstance(batches_value, list) or not all(
            isinstance(batch, list) for batch in batches_value
        ):
            raise ValueError(f"scenario {case_id!r} search_batches must be lists")
        batches = tuple(
            _string_tuple(batch, f"scenario {case_id!r} search batch") if batch else ()
            for batch in batches_value
        )
        referenced = {product_id for batch in batches for product_id in batch}
        unknown = referenced - product_by_id.keys()
        if unknown:
            raise ValueError(f"scenario {case_id!r} references unknown products: {sorted(unknown)}")
        draft_value = raw.get("draft")
        if draft_value is not None and not isinstance(draft_value, dict):
            raise ValueError(f"scenario {case_id!r} draft must be an object or null")
        expected_status = str(raw.get("expected_status", ""))
        expected_tools = (
            _string_tuple(raw.get("expected_tools", []), f"scenario {case_id!r} expected_tools")
            if raw.get("expected_tools")
            else ()
        )
        expected_path = _string_tuple(
            raw.get("expected_path", []), f"scenario {case_id!r} expected_path"
        )
        retry_count = int(raw.get("expected_retry_count", 0))
        if expected_status not in _FINAL_STATUSES:
            raise ValueError(f"scenario {case_id!r} has an unsupported expected status")
        if len(batches) != expected_tools.count("catalogue_search"):
            raise ValueError(f"scenario {case_id!r} search batches do not match expected tools")
        if retry_count < 0:
            raise ValueError(f"scenario {case_id!r} retry count must not be negative")
        scenarios.append(
            AgentScenario(
                case_id=case_id,
                category=category,
                user_request=user_request,
                analysis=RequestAnalysis.from_mapping(analysis_value),
                search_batches=batches,
                reformulations=_string_tuple(
                    raw.get("reformulations", []), f"scenario {case_id!r} reformulations"
                )
                if raw.get("reformulations")
                else (),
                draft=AnswerDraft.from_mapping(draft_value) if draft_value is not None else None,
                expected_status=expected_status,
                expected_tools=expected_tools,
                expected_path=expected_path,
                expected_retry_count=retry_count,
            )
        )
    ids = [scenario.case_id for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("agent scenario IDs must be unique")
    return product_by_id, tuple(scenarios)


def build_agent_scenario_workflow(
    scenario: AgentScenario, products: Mapping[str, StoredProduct]
) -> AgentWorkflow:
    """Assemble the real graph and deterministic tools around one scripted model case."""
    provider = MockLLMProvider(
        (scenario.analysis,),
        reformulations=scenario.reformulations,
        drafts=() if scenario.draft is None else (scenario.draft,),
    )
    return AgentWorkflow(
        provider,
        _ScenarioSearchTool(products, scenario.search_batches),
        ProductDetailsTool(_MemoryRepository(products)),
        EvidenceVerificationTool(),
    )


def run_agent_scenario(
    scenario: AgentScenario, products: Mapping[str, StoredProduct]
) -> AgentOutcome:
    return build_agent_scenario_workflow(scenario, products).invoke(scenario.user_request)


def _rate(values: Sequence[bool]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def evaluate_agent_scenarios(
    products: Mapping[str, StoredProduct], scenarios: Sequence[AgentScenario]
) -> dict[str, object]:
    """Run reviewed cases and report explicit, denominator-aware agent metrics."""
    if not scenarios:
        raise ValueError("agent evaluation requires at least one scenario")
    results: list[dict[str, object]] = []
    for scenario in scenarios:
        outcome = run_agent_scenario(scenario, products)
        actual_tools = tuple(call.tool for call in outcome.tool_history)
        constraint_satisfied: bool | None = None
        if scenario.analysis.constraints and outcome.retrieved_product_ids:
            constraint_satisfied = outcome.constraints is not None and all(
                outcome.constraints.matches(products[product_id])
                for product_id in outcome.retrieved_product_ids
                if product_id in products
            )
        status_correct = outcome.status == scenario.expected_status
        tools_correct = actual_tools == scenario.expected_tools
        path_correct = outcome.workflow_path == scenario.expected_path
        retry_correct = outcome.retry_count == scenario.expected_retry_count
        results.append(
            {
                "case_id": scenario.case_id,
                "category": scenario.category,
                "expected_status": scenario.expected_status,
                "actual_status": outcome.status,
                "expected_tools": list(scenario.expected_tools),
                "actual_tools": list(actual_tools),
                "expected_path": list(scenario.expected_path),
                "actual_path": list(outcome.workflow_path),
                "retry_count": outcome.retry_count,
                "status_correct": status_correct,
                "tool_selection_correct": tools_correct,
                "route_correct": path_correct,
                "retry_correct": retry_correct,
                "constraint_case": bool(scenario.analysis.constraints),
                "constraint_satisfied": constraint_satisfied,
                "verification_passed": (
                    None if outcome.verification is None else outcome.verification.passed
                ),
                "scenario_passed": status_correct
                and tools_correct
                and path_correct
                and retry_correct
                and constraint_satisfied is not False,
                "tool_calls": len(outcome.tool_history),
            }
        )

    clarification = [
        result for result in results if result["expected_status"] == "clarification_required"
    ]
    refusals = [result for result in results if result["expected_status"] == "unsupported"]
    conflicts = [
        result for result in results if result["expected_status"] == "conflicting_constraints"
    ]
    answered = [result for result in results if result["expected_status"] == "answered"]
    constrained = [result for result in results if result["constraint_satisfied"] is not None]
    return {
        "benchmark": "SearchRank-AI reviewed agent scenarios v1",
        "llm_mode": "scripted_mock",
        "scenario_count": len(results),
        "product_fixture_count": len(products),
        "category_counts": {
            category: sum(result["category"] == category for result in results)
            for category in sorted({str(result["category"]) for result in results})
        },
        "metrics": {
            "scenario_accuracy": _rate([bool(result["scenario_passed"]) for result in results]),
            "status_accuracy": _rate([bool(result["status_correct"]) for result in results]),
            "tool_selection_accuracy": _rate(
                [bool(result["tool_selection_correct"]) for result in results]
            ),
            "route_accuracy": _rate([bool(result["route_correct"]) for result in results]),
            "constraint_satisfaction_rate": _rate(
                [bool(result["constraint_satisfied"]) for result in constrained]
            ),
            "clarification_accuracy": _rate(
                [result["actual_status"] == "clarification_required" for result in clarification]
            ),
            "refusal_accuracy": _rate(
                [result["actual_status"] == "unsupported" for result in refusals]
            ),
            "conflict_detection_accuracy": _rate(
                [result["actual_status"] == "conflicting_constraints" for result in conflicts]
            ),
            "citation_correctness": _rate(
                [result["verification_passed"] is True for result in answered]
            ),
            "unsupported_claim_rate": _rate(
                [
                    result["actual_status"] == "answered" and result["verification_passed"] is False
                    for result in results
                ]
            ),
            "average_tool_calls": sum(int(result["tool_calls"]) for result in results)
            / len(results),
        },
        "metric_denominators": {
            "all_scenarios": len(results),
            "constraint_cases_with_results": len(constrained),
            "clarification_cases": len(clarification),
            "unsupported_cases": len(refusals),
            "conflict_cases": len(conflicts),
            "expected_answered_cases": len(answered),
        },
        "results": results,
    }


def summarize_latencies_ms(values: Sequence[float]) -> dict[str, float]:
    """Summarize positive durations using median and nearest-rank p95."""
    if not values or any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("latencies must be positive finite values")
    ordered = sorted(float(value) for value in values)
    p95_index = math.ceil(0.95 * len(ordered)) - 1
    return {
        "median_ms": statistics.median(ordered),
        "p95_ms": ordered[p95_index],
        "minimum_ms": ordered[0],
        "maximum_ms": ordered[-1],
    }


def benchmark_search_api(
    retriever: HybridRetriever,
    queries: Sequence[str],
    *,
    samples: int = 50,
    warmups: int = 5,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, object]:
    """Measure warmed, in-process POST /search latency with the real retriever."""
    if samples <= 0 or warmups < 0 or not queries or any(not query.strip() for query in queries):
        raise ValueError("benchmark requires queries, positive samples, and non-negative warmups")
    try:
        from fastapi.testclient import TestClient
    except ImportError as error:
        raise RuntimeError("install the dev dependencies to run the API benchmark") from error

    app = create_app(AppServices(search=retriever))
    payloads = [{"query": query, "mode": "hybrid", "alpha": 0.25, "limit": 10} for query in queries]
    durations: list[float] = []
    with TestClient(app) as client:
        for index in range(warmups + samples):
            payload = payloads[index % len(payloads)]
            started = clock()
            response = client.post("/search", json=payload)
            finished = clock()
            if response.status_code != 200:
                raise RuntimeError(f"API benchmark request failed with HTTP {response.status_code}")
            if index >= warmups:
                durations.append((finished - started) * 1000)
    return {
        "endpoint": "POST /search",
        "transport": "FastAPI TestClient (in-process ASGI; no network socket)",
        "retrieval": "hybrid",
        "alpha": 0.25,
        "result_limit": 10,
        "warmups": warmups,
        "samples": samples,
        "query_count": len(queries),
        "latency_ms": summarize_latencies_ms(durations),
    }


def _write_json(path: Path, payload: object) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _retriever(args: argparse.Namespace) -> HybridRetriever:
    encoder = SentenceTransformerEncoder(
        args.model,
        revision=args.revision,
        device=args.device,
        local_files_only=True,
    )
    return HybridRetriever.from_paths(args.catalogue, args.bm25_index, args.semantic_index, encoder)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    agent = commands.add_parser("agent", help="run the reviewed scripted-agent benchmark")
    agent.add_argument("--cases", required=True, type=Path)
    agent.add_argument("--output", required=True, type=Path)

    latency = commands.add_parser("api-latency", help="measure local search endpoint latency")
    latency.add_argument("--catalogue", required=True, type=Path)
    latency.add_argument("--bm25-index", required=True, type=Path)
    latency.add_argument("--semantic-index", required=True, type=Path)
    latency.add_argument("--cases", required=True, type=Path)
    latency.add_argument("--output", required=True, type=Path)
    latency.add_argument("--model", default=DEFAULT_MODEL_NAME)
    latency.add_argument("--revision", default=DEFAULT_MODEL_REVISION)
    latency.add_argument("--device", default="cpu")
    latency.add_argument("--samples", type=int, default=50)
    latency.add_argument("--warmups", type=int, default=5)
    latency.add_argument("--hardware", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "agent":
        products, scenarios = load_agent_scenarios(args.cases)
        report = evaluate_agent_scenarios(products, scenarios)
    else:
        retriever = _retriever(args)
        cases = load_evaluation_cases(
            args.cases, expected_catalogue_sha256=retriever.catalogue_sha256
        )
        report = {
            "benchmark": benchmark_search_api(
                retriever,
                [str(case["query"]) for case in cases],
                samples=args.samples,
                warmups=args.warmups,
            ),
            "environment": {
                "hardware": args.hardware,
                "platform": platform.platform(),
                "python": sys.version.split()[0],
                "catalogue_documents": len(retriever.products),
                "encoder_identifier": retriever.semantic_index.encoder_identifier,
                "model_cache": "cached locally; network disabled",
                "llm": "not used",
            },
        }
    _write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
