"""Phase 3 semantic, hybrid, normalization, and strict-filter tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from searchrank_ai.bm25 import BM25Index
from searchrank_ai.mobile_catalogue import FINAL_FIELDS
from searchrank_ai.retrieval import (
    CatalogueProduct,
    HybridRetriever,
    SearchConstraints,
    compare_configurations,
    evaluate_retriever,
    load_evaluation_cases,
    load_products,
    normalize_bm25_scores,
    normalize_cosine_score,
)
from searchrank_ai.semantic import SemanticIndex, build_search_text


class FakeEncoder:
    """Small deterministic semantic space; no model or network is used by tests."""

    identifier = "fake-meaning-encoder@1"

    @staticmethod
    def _vector(text: str) -> np.ndarray:
        folded = text.casefold()
        if any(term in folded for term in ("battery", "endurance", "long lasting")):
            return np.asarray([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        if any(term in folded for term in ("camera", "photo", "photography")):
            return np.asarray([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        if any(term in folded for term in ("gaming", "performance", "snapdragon")):
            return np.asarray([0.0, 0.0, 1.0, 0.0], dtype=np.float32)
        return np.asarray([0.0, 0.0, 0.0, 1.0], dtype=np.float32)

    def encode_documents(self, texts):
        return np.stack([self._vector(text) for text in texts])

    def encode_query(self, text):
        return self._vector(text)


class OtherEncoder(FakeEncoder):
    identifier = "different-encoder@1"


class QueryFailingEncoder(FakeEncoder):
    def encode_query(self, text):
        raise AssertionError("BM25-only search must not call the semantic encoder")


def row(product_id: str, name: str, **changes: str) -> dict[str, str]:
    values = {field: "" for field in FINAL_FIELDS}
    values.update(
        product_id=product_id,
        product_name=name,
        brand=name.split()[0],
        price_inr="25000",
        ram_gb="8",
        storage_gb="128",
        user_rating_5="4.2",
        processor="Test Chip",
        source_url=f"https://www.91mobiles.com/{product_id}-price-in-india",
    )
    values.update(changes)
    return values


def catalogue(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FINAL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def retriever_for(tmp_path: Path, rows: list[dict[str, str]]) -> HybridRetriever:
    path = catalogue(tmp_path / "catalogue.csv", rows)
    encoder = FakeEncoder()
    return HybridRetriever(
        load_products(path),
        BM25Index.from_catalogue(path),
        SemanticIndex.from_catalogue(path, encoder),
        encoder,
        catalogue_sha256=BM25Index.from_catalogue(path).catalogue_sha256,
    )


def test_search_text_uses_stored_retrieval_evidence_only():
    product = row(
        "phone-a",
        "Alpha Camera Phone",
        brand="Alpha",
        ram_gb="12",
        storage_gb="256",
        processor="Snapdragon Test",
        battery_mah="5000",
        charging="80W charging",
        display_inches="6.7",
        display_type="AMOLED",
        rear_camera="50 MP OIS",
        front_camera="32 MP",
        price_inr="99999",
        user_rating_5="4.9",
    )

    text = build_search_text(product)

    assert "Alpha Camera Phone" in text
    assert "12 GB RAM, 256 GB storage" in text
    assert "Snapdragon Test" in text
    assert "5000" in text and "AMOLED" in text and "50 MP OIS" in text
    assert "99999" not in text and "4.9" not in text
    assert product["source_url"] not in text


def test_semantic_index_round_trip_and_meaning_match(tmp_path):
    path = catalogue(
        tmp_path / "catalogue.csv",
        [
            row("battery-phone", "Alpha Device", battery_mah="7000"),
            row("camera-phone", "Beta Device", rear_camera="Pro camera", battery_mah=""),
        ],
    )
    encoder = FakeEncoder()
    index = SemanticIndex.from_catalogue(path, encoder)
    output = tmp_path / "semantic.npz"

    index.save(output)
    loaded = SemanticIndex.load(output)
    scores = loaded.cosine_scores("long lasting endurance", encoder)

    assert loaded.product_ids == ("battery-phone", "camera-phone")
    assert loaded.dimension == 4
    assert scores[0] > scores[1]
    with pytest.raises(FileExistsError):
        index.save(output)
    with pytest.raises(ValueError, match="encoder"):
        loaded.cosine_scores("battery", OtherEncoder())


def test_semantic_index_validates_schema_output_and_extension(tmp_path):
    wrong = tmp_path / "wrong.csv"
    wrong.write_text("product_id,product_name\na,Alpha\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        SemanticIndex.from_catalogue(wrong, FakeEncoder())
    with pytest.raises(ValueError, match="zero vector"):
        SemanticIndex(("a",), np.zeros((1, 2)), "hash", "encoder")
    valid = SemanticIndex(("a",), np.ones((1, 2)), "hash", "encoder")
    with pytest.raises(ValueError, match=".npz"):
        valid.save(tmp_path / "semantic.json")


def test_product_loader_rejects_invalid_filter_values(tmp_path):
    path = catalogue(tmp_path / "catalogue.csv", [row("a", "Alpha", user_rating_5="6")])
    with pytest.raises(ValueError, match="user_rating"):
        load_products(path)


def test_all_strict_constraints_are_enforced_together(tmp_path):
    retriever = retriever_for(
        tmp_path,
        [
            row(
                "target",
                "OnePlus Camera Phone",
                brand="OnePlus",
                price_inr="29999",
                ram_gb="12",
                storage_gb="256",
                user_rating_5="4.5",
                rear_camera="Pro camera",
            ),
            row("expensive", "OnePlus Camera Pro", brand="OnePlus", price_inr="39999"),
            row("excluded", "Samsung Camera Phone", brand="Samsung", user_rating_5="4.8"),
            row("unrated", "OnePlus Camera Lite", brand="OnePlus", user_rating_5=""),
        ],
    )
    constraints = SearchConstraints(
        max_price_inr=30000,
        min_ram_gb=8,
        included_brands=("oneplus",),
        excluded_brands=("SAMSUNG",),
        min_rating_5=4.4,
        min_storage_gb=256,
    )

    for mode in ("bm25", "semantic", "hybrid"):
        results = retriever.search("camera phone", mode=mode, constraints=constraints)
        assert [result.product_id for result in results] == ["target"]


@pytest.mark.parametrize(
    "constraints",
    [
        {"max_price_inr": 0},
        {"min_ram_gb": -1},
        {"min_storage_gb": float("nan")},
        {"min_rating_5": 5.1},
        {"included_brands": ("",)},
        {"included_brands": ("Apple",), "excluded_brands": ("apple",)},
    ],
)
def test_constraints_reject_invalid_or_conflicting_values(constraints):
    with pytest.raises(ValueError):
        SearchConstraints(**constraints)


def test_score_normalization_is_explicit_and_bounded():
    assert normalize_bm25_scores({"a": 4.0, "b": 2.0, "c": 0.0}) == {
        "a": 1.0,
        "b": 0.5,
        "c": 0.0,
    }
    assert normalize_cosine_score(-1) == 0
    assert normalize_cosine_score(0) == 0.5
    assert normalize_cosine_score(1) == 1
    with pytest.raises(ValueError):
        normalize_bm25_scores({"a": -1})


def test_alpha_changes_hybrid_order_in_a_controlled_example(tmp_path):
    retriever = retriever_for(
        tmp_path,
        [
            row("lexical", "Keyword Hero", rear_camera="", battery_mah=""),
            row("semantic", "Other Device", rear_camera="Pro camera", battery_mah=""),
        ],
    )

    lexical_first = retriever.search("keyword photography", alpha=0.75)
    semantic_first = retriever.search("keyword photography", alpha=0.25)

    assert lexical_first[0].product_id == "lexical"
    assert semantic_first[0].product_id == "semantic"
    assert lexical_first[0].score == pytest.approx(
        0.75 * lexical_first[0].bm25_normalized_score
        + 0.25 * lexical_first[0].semantic_normalized_score
    )


def test_search_handles_empty_results_and_validates_options(tmp_path):
    retriever = retriever_for(tmp_path, [row("a", "Alpha Phone")])
    assert retriever.search("", mode="semantic") == ()
    assert retriever.search("unknown", mode="bm25") == ()
    assert (
        retriever.search("alpha", constraints=SearchConstraints(included_brands=("Samsung",))) == ()
    )
    with pytest.raises(ValueError, match="mode"):
        retriever.search("alpha", mode="other")
    with pytest.raises(ValueError, match="alpha"):
        retriever.search("alpha", alpha=2)
    with pytest.raises(ValueError, match="limit"):
        retriever.search("alpha", limit=0)


def test_bm25_mode_does_not_call_encoder_or_report_a_semantic_score(tmp_path):
    path = catalogue(tmp_path / "catalogue.csv", [row("a", "Alpha Phone")])
    encoder = FakeEncoder()
    semantic = SemanticIndex.from_catalogue(path, encoder)
    retriever = HybridRetriever(
        load_products(path),
        BM25Index.from_catalogue(path),
        semantic,
        QueryFailingEncoder(),
        catalogue_sha256=semantic.catalogue_sha256,
    )

    result = retriever.search("alpha", mode="bm25")[0]

    assert result.semantic_cosine_score == 0
    assert result.semantic_normalized_score == 0


def test_retriever_rejects_misaligned_artifacts(tmp_path):
    path = catalogue(tmp_path / "catalogue.csv", [row("a", "Alpha Phone")])
    encoder = FakeEncoder()
    products = load_products(path)
    bm25 = BM25Index.from_catalogue(path)
    semantic = SemanticIndex(("other",), np.ones((1, 2)), bm25.catalogue_sha256, encoder.identifier)
    with pytest.raises(ValueError, match="product order"):
        HybridRetriever(
            products,
            bm25,
            semantic,
            encoder,
            catalogue_sha256=bm25.catalogue_sha256,
        )


def test_evaluation_and_alpha_comparison_use_real_judgments(tmp_path):
    retriever = retriever_for(
        tmp_path,
        [
            row("battery", "Power Device", battery_mah="7000"),
            row("camera", "Photo Device", rear_camera="Pro camera", battery_mah=""),
        ],
    )
    cases = [
        {
            "case_id": "endurance",
            "query": "long lasting endurance",
            "relevant_product_ids": ["battery"],
        },
        {
            "case_id": "photos",
            "query": "photography",
            "relevant_product_ids": ["camera"],
            "constraints": {"max_price_inr": 30000},
        },
    ]

    semantic = evaluate_retriever(retriever, cases, mode="semantic", limit=1)
    comparison = compare_configurations(retriever, cases, alphas=(0.25, 0.75), limit=1)

    assert semantic["metrics"] == {
        "recall_at_k": 1.0,
        "mrr_at_k": 1.0,
        "ndcg_at_k": 1.0,
        "constraint_satisfaction_rate": 1.0,
    }
    assert [report["mode"] for report in comparison["reports"]] == [
        "bm25",
        "semantic",
        "hybrid",
        "hybrid",
    ]
    assert comparison["selection"]["alpha"] == 0.25
    assert semantic["metrics_by_category"]["uncategorized"] == semantic["metrics"]


def test_evaluation_file_is_catalogue_hash_pinned(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            {
                "catalogue_sha256": "old",
                "cases": [{"case_id": "a", "query": "alpha", "relevant_product_ids": ["a"]}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="different catalogue"):
        load_evaluation_cases(path, expected_catalogue_sha256="new")


def test_constraints_from_dict_rejects_unknown_fields_and_string_brand_lists():
    with pytest.raises(ValueError, match="unknown"):
        SearchConstraints.from_dict({"maximum_weight": 200})
    with pytest.raises(ValueError, match="list"):
        SearchConstraints.from_dict({"included_brands": "Apple"})
    with pytest.raises(ValueError, match="brand names"):
        SearchConstraints.from_dict({"included_brands": ["Apple", 1]})


def test_catalogue_product_constraint_boundary_values():
    product = CatalogueProduct("a", "A", "Apple", 30000, 8, 128, 4.0, "https://example.test")
    constraints = SearchConstraints(
        max_price_inr=30000,
        min_ram_gb=8,
        min_storage_gb=128,
        min_rating_5=4,
        included_brands=("APPLE",),
    )
    assert constraints.matches(product)
