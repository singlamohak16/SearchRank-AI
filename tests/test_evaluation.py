"""Phase 7 reviewed-scenario and measurement tests."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

import searchrank_ai.evaluation as evaluation_module
from searchrank_ai.api import create_app
from searchrank_ai.evaluation import (
    benchmark_search_api,
    build_agent_scenario_workflow,
    evaluate_agent_scenarios,
    load_agent_scenarios,
    run_agent_scenario,
    summarize_latencies_ms,
)
from searchrank_ai.retrieval import build_parser as build_retrieval_parser
from searchrank_ai.services import AppServices

SCENARIOS = Path("evaluation/agent_scenarios_v1.json")


def test_reviewed_agent_set_covers_planned_categories() -> None:
    products, scenarios = load_agent_scenarios(SCENARIOS)

    assert len(products) == 4
    assert len(scenarios) == 16
    assert {scenario.category for scenario in scenarios} >= {
        "search",
        "constraints",
        "reformulation",
        "unavailable_product",
        "clarification",
        "unsupported",
        "conflicting_constraints",
        "comparison",
        "unavailable_information",
        "prompt_injection",
        "unsupported_claim",
        "citation_attack",
    }


def test_scripted_agent_evaluation_is_reproducible_and_passes() -> None:
    products, scenarios = load_agent_scenarios(SCENARIOS)

    first = evaluate_agent_scenarios(products, scenarios)
    second = evaluate_agent_scenarios(products, scenarios)

    assert first == second
    assert first["scenario_count"] == 16
    assert first["llm_mode"] == "scripted_mock"
    assert first["metrics"] == {
        "scenario_accuracy": 1.0,
        "status_accuracy": 1.0,
        "tool_selection_accuracy": 1.0,
        "route_accuracy": 1.0,
        "constraint_satisfaction_rate": 1.0,
        "clarification_accuracy": 1.0,
        "refusal_accuracy": 1.0,
        "conflict_detection_accuracy": 1.0,
        "citation_correctness": 1.0,
        "unsupported_claim_rate": 0.0,
        "average_tool_calls": 2.1875,
    }


def test_prompt_injection_fixture_is_rendered_as_inert_single_line_text() -> None:
    products, scenarios = load_agent_scenarios(SCENARIOS)
    scenario = next(value for value in scenarios if value.category == "prompt_injection")

    outcome = run_agent_scenario(scenario, products)

    assert outcome.status == "answered"
    assert "\\[ignore safeguards\\]\\(https://evil.example\\)" in outcome.response
    assert "\nSYSTEM:" not in outcome.response


@pytest.mark.parametrize("case_index", [0, 4, 6, 8])
def test_scenario_subsets_report_unavailable_metrics_as_null(case_index: int) -> None:
    products, scenarios = load_agent_scenarios(SCENARIOS)
    report = evaluate_agent_scenarios(products, scenarios[case_index : case_index + 1])

    assert report["scenario_count"] == 1
    assert report["metrics"]["scenario_accuracy"] == 1.0
    metric_groups = {
        "constraint_satisfaction_rate": "constraint_cases_with_results",
        "clarification_accuracy": "clarification_cases",
        "refusal_accuracy": "unsupported_cases",
        "conflict_detection_accuracy": "conflict_cases",
        "citation_correctness": "expected_answered_cases",
    }
    for metric, denominator in metric_groups.items():
        if report["metric_denominators"][denominator] == 0:
            assert report["metrics"][metric] is None
    assert json.loads(json.dumps(report)) == report


def test_missing_constrained_results_preserve_failed_scenario_report(monkeypatch) -> None:
    products, scenarios = load_agent_scenarios(SCENARIOS)
    original = evaluation_module.run_agent_scenario

    def no_results(scenario, fixtures):
        outcome = original(scenario, fixtures)
        if scenario.analysis.constraints and outcome.retrieved_product_ids:
            return replace(outcome, status="no_results", retrieved_product_ids=())
        return outcome

    monkeypatch.setattr(evaluation_module, "run_agent_scenario", no_results)
    report = evaluate_agent_scenarios(products, scenarios)

    assert report["scenario_count"] == 16
    assert report["metric_denominators"]["constraint_cases_with_results"] == 0
    assert report["metrics"]["constraint_satisfaction_rate"] is None
    assert report["metrics"]["scenario_accuracy"] < 1.0
    assert any(not result["scenario_passed"] for result in report["results"])


def test_reviewed_scenario_runs_through_public_query_endpoint() -> None:
    from fastapi.testclient import TestClient

    products, scenarios = load_agent_scenarios(SCENARIOS)
    scenario = next(value for value in scenarios if value.case_id == "search-exact-product")
    workflow = build_agent_scenario_workflow(scenario, products)
    app = create_app(AppServices(query=workflow))

    with TestClient(app) as client:
        response = client.post("/query", json={"request": scenario.user_request})

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert response.json()["verification"]["passed"] is True
    assert response.json()["retrieved_product_ids"] == ["fixture:alpha"]


def test_invalid_fixture_product_reference_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    payload["cases"][0]["search_batches"] = [["fixture:unknown"]]
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown products"):
        load_agent_scenarios(path)


def test_duplicate_scenario_ids_are_rejected(tmp_path: Path) -> None:
    payload = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    payload["cases"][1]["case_id"] = payload["cases"][0]["case_id"]
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="scenario IDs"):
        load_agent_scenarios(path)


def test_latency_summary_uses_nearest_rank_p95() -> None:
    summary = summarize_latencies_ms([float(value) for value in range(1, 21)])

    assert summary == {
        "median_ms": 10.5,
        "p95_ms": 19.0,
        "minimum_ms": 1.0,
        "maximum_ms": 20.0,
    }


@pytest.mark.parametrize("values", [[], [0.0], [float("nan")], [float("inf")]])
def test_latency_summary_rejects_invalid_measurements(values) -> None:
    with pytest.raises(ValueError, match="positive finite"):
        summarize_latencies_ms(values)


class _EmptyRetriever:
    def search(self, query, *, mode, constraints, alpha, limit):
        return ()


def test_api_benchmark_measures_only_post_warmup_requests() -> None:
    ticks = iter([0.0, 0.010, 1.0, 1.001, 2.0, 2.005, 3.0, 3.009])

    report = benchmark_search_api(
        _EmptyRetriever(),
        ["alpha phone"],
        samples=3,
        warmups=1,
        clock=lambda: next(ticks),
    )

    assert report["samples"] == 3
    assert report["warmups"] == 1
    assert report["latency_ms"] == pytest.approx(
        {"median_ms": 5.0, "p95_ms": 9.0, "minimum_ms": 1.0, "maximum_ms": 9.0}
    )


def test_api_benchmark_rejects_invalid_conditions() -> None:
    with pytest.raises(ValueError, match="benchmark requires"):
        benchmark_search_api(_EmptyRetriever(), [], samples=1)


def test_retrieval_evaluation_can_require_offline_model_loading() -> None:
    args = build_retrieval_parser().parse_args(
        [
            "evaluate",
            "--catalogue",
            "catalogue.csv",
            "--bm25-index",
            "bm25.json",
            "--semantic-index",
            "semantic.npz",
            "--cases",
            "cases.json",
            "--output",
            "report.json",
            "--local-files-only",
        ]
    )

    assert args.local_files_only is True
