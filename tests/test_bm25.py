"""Tests for the deterministic BM25 keyword baseline."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from searchrank_ai.bm25 import (
    BM25Index,
    IndexedDocument,
    evaluate,
    load_catalogue,
    load_evaluation_cases,
    main,
    tokenize,
)
from searchrank_ai.mobile_catalogue import FINAL_FIELDS


def catalogue(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FINAL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def row(product_id: str, name: str, **changes: str) -> dict[str, str]:
    values = {field: "" for field in FINAL_FIELDS}
    values.update(
        product_id=product_id,
        product_name=name,
        brand=name.split()[0],
        price_inr="25000",
        ram_gb="8",
        storage_gb="128",
        processor="Test Chip",
        battery_mah="5000",
        source_url=f"https://www.91mobiles.com/{product_id}-price-in-india",
    )
    values.update(changes)
    return values


def index_for(tmp_path: Path, rows: list[dict[str, str]]) -> BM25Index:
    path = catalogue(tmp_path / "catalogue.csv", rows)
    return BM25Index.from_catalogue(path)


def test_tokenizer_is_casefolded_unicode_and_punctuation_safe():
    assert tokenize("  OnePlus NORD-5G, AMOLED! ") == ("oneplus", "nord", "5g", "amoled")
    assert tokenize("MOTO_日本") == ("moto", "日本")


def test_product_name_weighting_and_stable_tie_breaking(tmp_path):
    index = index_for(
        tmp_path,
        [
            row("phone-z", "Zulu Phone", processor="Orchid Chip"),
            row("phone-b", "Beta Orchid", processor="Plain Chip"),
            row("phone-a", "Alpha Orchid", processor="Plain Chip"),
        ],
    )
    results = index.search("ORCHID")
    assert [result.product_id for result in results] == ["phone-a", "phone-b", "phone-z"]
    assert results[0].score == results[1].score
    assert results[1].score > results[2].score
    assert [result.rank for result in results] == [1, 2, 3]


def test_search_handles_unknown_and_empty_queries_and_validates_limit(tmp_path):
    index = index_for(tmp_path, [row("phone-a", "Alpha Phone")])
    assert index.search("unknown-token") == ()
    assert index.search("!!!") == ()
    with pytest.raises(ValueError, match="limit"):
        index.search("alpha", limit=0)


def test_strict_filter_values_are_not_used_as_keyword_terms(tmp_path):
    index = index_for(tmp_path, [row("phone-a", "Alpha Phone")])
    assert index.search("25000 8 128") == ()
    assert index.search("5000 mah")[0].product_id == "phone-a"


def test_repeated_query_terms_increase_score(tmp_path):
    index = index_for(tmp_path, [row("phone-a", "Alpha Phone")])
    one = index.search("alpha")[0].score
    two = index.search("alpha alpha")[0].score
    assert two == pytest.approx(one * 2)


def test_index_round_trip_is_byte_stable_and_refuses_overwrite(tmp_path):
    index = index_for(
        tmp_path,
        [
            row("phone-b", "Beta Phone", display_type="AMOLED"),
            row("phone-a", "Alpha Phone", processor="Snapdragon 8 Gen 3"),
        ],
    )
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    index.save(first)
    loaded = BM25Index.load(first)
    loaded.save(second)
    assert first.read_bytes() == second.read_bytes()
    assert [item.as_dict() for item in loaded.search("snapdragon")] == [
        item.as_dict() for item in index.search("snapdragon")
    ]
    with pytest.raises(FileExistsError):
        index.save(first)


@pytest.mark.parametrize(
    "modifier,error",
    [
        (lambda rows: rows + [rows[0]], "duplicate product IDs"),
        (lambda rows: [{**rows[0], "product_id": ""}], "empty product ID"),
        (
            lambda rows: [
                {
                    **rows[0],
                    "product_name": "",
                    "brand": "",
                    "processor": "",
                    "battery_mah": "",
                }
            ],
            "without searchable text",
        ),
    ],
)
def test_catalogue_validation(tmp_path, modifier, error):
    path = catalogue(tmp_path / "catalogue.csv", modifier([row("phone-a", "Alpha Phone")]))
    with pytest.raises(ValueError, match=error):
        load_catalogue(path)


def test_catalogue_rejects_changed_schema(tmp_path):
    path = tmp_path / "wrong.csv"
    path.write_text("product_id,product_name\na,Alpha\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        load_catalogue(path)


def test_binary_evaluation_metrics_are_calculated_from_judgments(tmp_path):
    index = index_for(
        tmp_path,
        [row("phone-a", "Alpha Phone"), row("phone-b", "Beta Phone")],
    )
    report = evaluate(
        index,
        [
            {
                "case_id": "alpha",
                "query": "alpha",
                "relevant_product_ids": ["phone-a"],
            },
            {
                "case_id": "missing",
                "query": "unknown",
                "relevant_product_ids": ["phone-b"],
            },
        ],
        limit=1,
    )
    assert report["metrics"] == {"recall_at_k": 0.5, "mrr_at_k": 0.5, "ndcg_at_k": 0.5}
    assert report["catalogue_documents"] == 2


def test_evaluation_case_validation(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {"case_id": "same", "query": "a", "relevant_product_ids": ["a"]},
                    {"case_id": "same", "query": "b", "relevant_product_ids": ["b"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unique"):
        load_evaluation_cases(path)


def test_evaluation_rejects_stale_catalogue_or_unknown_product_ids(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            {
                "catalogue_sha256": "old-hash",
                "cases": [
                    {"case_id": "alpha", "query": "alpha", "relevant_product_ids": ["missing"]}
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="different catalogue"):
        load_evaluation_cases(path, expected_catalogue_sha256="new-hash")
    index = index_for(tmp_path, [row("phone-a", "Alpha Phone")])
    with pytest.raises(ValueError, match="unknown product IDs"):
        evaluate(index, load_evaluation_cases(path), limit=10)


def test_cli_build_search_and_evaluate(tmp_path, capsys):
    source = catalogue(tmp_path / "catalogue.csv", [row("phone-a", "Alpha Phone")])
    index_path = tmp_path / "index.json"
    assert main(["build", "--catalogue", str(source), "--output", str(index_path)]) == 0
    assert json.loads(capsys.readouterr().out)["documents"] == 1
    assert main(["search", "--index", str(index_path), "--query", "alpha"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["product_id"] == "phone-a"
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            {"cases": [{"case_id": "alpha", "query": "alpha", "relevant_product_ids": ["phone-a"]}]}
        ),
        encoding="utf-8",
    )
    report = tmp_path / "report.json"
    assert (
        main(
            [
                "evaluate",
                "--index",
                str(index_path),
                "--cases",
                str(cases),
                "--limit",
                "10",
                "--output",
                str(report),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["recall_at_k"] == 1.0
    assert json.loads(report.read_text(encoding="utf-8"))["metrics"]["mrr_at_k"] == 1.0


def test_parameter_and_malformed_index_validation(tmp_path):
    document = IndexedDocument("a", "A", "https://example.test/a", {"a": 1}, 1)
    with pytest.raises(ValueError, match="k1"):
        BM25Index([document], catalogue_sha256="hash", k1=0)
    with pytest.raises(ValueError, match="b"):
        BM25Index([document], catalogue_sha256="hash", b=2)
    wrong_length = IndexedDocument("a", "A", "https://example.test/a", {"a": 1}, 2)
    with pytest.raises(ValueError, match="must match"):
        BM25Index([wrong_length], catalogue_sha256="hash")
    broken = tmp_path / "broken.json"
    broken.write_text('{"format":"other","version":1}', encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        BM25Index.load(broken)
