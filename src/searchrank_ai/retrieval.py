"""Semantic, BM25, and hybrid retrieval with deterministic constraints."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from searchrank_ai.bm25 import BM25Index
from searchrank_ai.data_audit import sha256
from searchrank_ai.mobile_catalogue import FINAL_FIELDS
from searchrank_ai.semantic import (
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
    SemanticIndex,
    SentenceTransformerEncoder,
    TextEncoder,
)

RetrievalMode = Literal["bm25", "semantic", "hybrid"]
SUPPORTED_MODES = ("bm25", "semantic", "hybrid")
DEFAULT_ALPHA = 0.5
ALPHA_CANDIDATES = (0.25, 0.5, 0.75)


def _required_number(raw: str, field: str, *, integral: bool = False) -> float | int:
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"catalogue {field} must be numeric") from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"catalogue {field} must be positive and finite")
    if integral:
        if not value.is_integer():
            raise ValueError(f"catalogue {field} must be an integer")
        return int(value)
    return value


def _optional_number(raw: str, field: str) -> float | None:
    if not raw:
        return None
    value = float(_required_number(raw, field))
    return value


@dataclass(frozen=True)
class CatalogueProduct:
    product_id: str
    product_name: str
    brand: str
    price_inr: int
    ram_gb: float
    storage_gb: float
    user_rating_5: float | None
    source_url: str


def load_products(path: Path) -> tuple[CatalogueProduct, ...]:
    """Load only identity, filter evidence, and provenance from the approved catalogue."""
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FINAL_FIELDS:
            raise ValueError("catalogue schema does not match the approved Phase 1 schema")
        products = tuple(
            CatalogueProduct(
                product_id=row["product_id"],
                product_name=row["product_name"],
                brand=row["brand"],
                price_inr=int(_required_number(row["price_inr"], "price_inr", integral=True)),
                ram_gb=float(_required_number(row["ram_gb"], "ram_gb")),
                storage_gb=float(_required_number(row["storage_gb"], "storage_gb")),
                user_rating_5=_optional_number(row["user_rating_5"], "user_rating_5"),
                source_url=row["source_url"],
            )
            for row in reader
        )
    if not products:
        raise ValueError("catalogue contains no records")
    ids = [product.product_id for product in products]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("catalogue product IDs must be non-empty and unique")
    if any(
        not product.product_name or not product.brand or not product.source_url
        for product in products
    ):
        raise ValueError("catalogue identity and provenance fields must be non-empty")
    if any(
        product.user_rating_5 is not None and not 0 < product.user_rating_5 <= 5
        for product in products
    ):
        raise ValueError("catalogue user_rating_5 must be empty or in the range (0, 5]")
    return products


def _constraint_number(
    value: float | int | None, field: str, *, maximum: float | None = None, positive: bool = False
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    converted = float(value)
    lower_valid = converted > 0 if positive else converted >= 0
    if (
        not math.isfinite(converted)
        or not lower_valid
        or (maximum is not None and converted > maximum)
    ):
        raise ValueError(f"invalid {field}")
    return converted


def _brands(values: Sequence[str], field: str) -> tuple[str, ...]:
    if isinstance(values, str) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"{field} must contain only brand names")
    normalized = tuple(dict.fromkeys(value.strip().casefold() for value in values))
    if any(not value for value in normalized):
        raise ValueError(f"{field} cannot contain an empty brand")
    return normalized


@dataclass(frozen=True)
class SearchConstraints:
    max_price_inr: float | None = None
    min_ram_gb: float | None = None
    included_brands: tuple[str, ...] = ()
    excluded_brands: tuple[str, ...] = ()
    min_rating_5: float | None = None
    min_storage_gb: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_price_inr",
            _constraint_number(self.max_price_inr, "max_price_inr", positive=True),
        )
        object.__setattr__(self, "min_ram_gb", _constraint_number(self.min_ram_gb, "min_ram_gb"))
        object.__setattr__(
            self,
            "min_rating_5",
            _constraint_number(self.min_rating_5, "min_rating_5", maximum=5),
        )
        object.__setattr__(
            self, "min_storage_gb", _constraint_number(self.min_storage_gb, "min_storage_gb")
        )
        included = _brands(self.included_brands, "included_brands")
        excluded = _brands(self.excluded_brands, "excluded_brands")
        if set(included) & set(excluded):
            raise ValueError("the same brand cannot be both included and excluded")
        object.__setattr__(self, "included_brands", included)
        object.__setattr__(self, "excluded_brands", excluded)

    @classmethod
    def from_dict(cls, values: Mapping[str, object] | None) -> SearchConstraints:
        if values is None:
            return cls()
        allowed = {
            "max_price_inr",
            "min_ram_gb",
            "included_brands",
            "excluded_brands",
            "min_rating_5",
            "min_storage_gb",
        }
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"unknown constraint fields: {sorted(unknown)}")
        payload = dict(values)
        for field in ("included_brands", "excluded_brands"):
            brands = payload.get(field, ())
            if isinstance(brands, str) or not isinstance(brands, Sequence):
                raise ValueError(f"{field} must be a list of brand names")
            payload[field] = tuple(brands)
        return cls(**payload)

    def matches(self, product: CatalogueProduct) -> bool:
        brand = product.brand.casefold()
        return not (
            (self.max_price_inr is not None and product.price_inr > self.max_price_inr)
            or (self.min_ram_gb is not None and product.ram_gb < self.min_ram_gb)
            or (self.included_brands and brand not in self.included_brands)
            or brand in self.excluded_brands
            or (
                self.min_rating_5 is not None
                and (product.user_rating_5 is None or product.user_rating_5 < self.min_rating_5)
            )
            or (self.min_storage_gb is not None and product.storage_gb < self.min_storage_gb)
        )


def normalize_bm25_scores(scores: Mapping[str, float]) -> dict[str, float]:
    if any(not math.isfinite(value) or value < 0 for value in scores.values()):
        raise ValueError("BM25 scores must be finite and non-negative")
    maximum = max(scores.values(), default=0.0)
    if maximum == 0:
        return {product_id: 0.0 for product_id in scores}
    return {product_id: value / maximum for product_id, value in scores.items()}


def normalize_cosine_score(score: float) -> float:
    if not math.isfinite(score):
        raise ValueError("cosine score must be finite")
    return min(1.0, max(0.0, (score + 1.0) / 2.0))


@dataclass(frozen=True)
class RetrievalResult:
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

    def as_dict(self) -> dict[str, int | float | str | None]:
        return {
            key: round(value, 8) if isinstance(value, float) else value
            for key, value in self.__dict__.items()
        }


class HybridRetriever:
    """Search one aligned catalogue using lexical, semantic, or hybrid scores."""

    def __init__(
        self,
        products: Sequence[CatalogueProduct],
        bm25_index: BM25Index,
        semantic_index: SemanticIndex,
        encoder: TextEncoder,
        *,
        catalogue_sha256: str,
    ) -> None:
        self.products = tuple(products)
        product_ids = tuple(product.product_id for product in self.products)
        if not product_ids or len(product_ids) != len(set(product_ids)):
            raise ValueError("retriever requires unique products")
        if product_ids != tuple(document.product_id for document in bm25_index.documents):
            raise ValueError("BM25 index product order does not match the catalogue")
        if product_ids != semantic_index.product_ids:
            raise ValueError("semantic index product order does not match the catalogue")
        if not (catalogue_sha256 == bm25_index.catalogue_sha256 == semantic_index.catalogue_sha256):
            raise ValueError("retrieval artifacts refer to different catalogues")
        if encoder.identifier != semantic_index.encoder_identifier:
            raise ValueError("encoder does not match the semantic index")
        self.bm25_index = bm25_index
        self.semantic_index = semantic_index
        self.encoder = encoder
        self.catalogue_sha256 = catalogue_sha256
        self._product_by_id = {product.product_id: product for product in self.products}

    @classmethod
    def from_paths(
        cls,
        catalogue_path: Path,
        bm25_index_path: Path,
        semantic_index_path: Path,
        encoder: TextEncoder,
    ) -> HybridRetriever:
        return cls(
            load_products(catalogue_path),
            BM25Index.load(bm25_index_path),
            SemanticIndex.load(semantic_index_path),
            encoder,
            catalogue_sha256=sha256(catalogue_path),
        )

    def search(
        self,
        query: str,
        *,
        mode: RetrievalMode = "hybrid",
        constraints: SearchConstraints | None = None,
        alpha: float = DEFAULT_ALPHA,
        limit: int = 10,
    ) -> tuple[RetrievalResult, ...]:
        if mode not in SUPPORTED_MODES:
            raise ValueError(f"unsupported retrieval mode: {mode}")
        if limit <= 0:
            raise ValueError("limit must be positive")
        if not math.isfinite(alpha) or not 0 <= alpha <= 1:
            raise ValueError("alpha must be finite and between 0 and 1")
        if not query.strip():
            return ()
        active_constraints = constraints or SearchConstraints()
        eligible = tuple(
            product for product in self.products if active_constraints.matches(product)
        )
        if not eligible:
            return ()
        eligible_ids = {product.product_id for product in eligible}

        bm25_raw = {product_id: 0.0 for product_id in eligible_ids}
        if mode in {"bm25", "hybrid"}:
            bm25_raw.update(
                {
                    result.product_id: result.score
                    for result in self.bm25_index.search(query, limit=len(self.products))
                    if result.product_id in eligible_ids
                }
            )
        bm25_normalized = normalize_bm25_scores(bm25_raw)

        semantic_cosine = {product_id: 0.0 for product_id in eligible_ids}
        if mode in {"semantic", "hybrid"}:
            semantic_cosine.update(
                {
                    product_id: score
                    for product_id, score in zip(
                        self.semantic_index.product_ids,
                        self.semantic_index.cosine_scores(query, self.encoder),
                        strict=True,
                    )
                    if product_id in eligible_ids
                }
            )
        semantic_normalized = (
            {
                product_id: normalize_cosine_score(score)
                for product_id, score in semantic_cosine.items()
            }
            if mode in {"semantic", "hybrid"}
            else {product_id: 0.0 for product_id in eligible_ids}
        )

        if mode == "bm25":
            scores = bm25_normalized
            candidates = [product for product in eligible if bm25_raw[product.product_id] > 0]
        elif mode == "semantic":
            scores = semantic_normalized
            candidates = list(eligible)
        else:
            scores = {
                product.product_id: alpha * bm25_normalized[product.product_id]
                + (1 - alpha) * semantic_normalized[product.product_id]
                for product in eligible
            }
            candidates = list(eligible)

        ordered = sorted(
            candidates, key=lambda product: (-scores[product.product_id], product.product_id)
        )[:limit]
        return tuple(
            RetrievalResult(
                rank=rank,
                product_id=product.product_id,
                product_name=product.product_name,
                brand=product.brand,
                price_inr=product.price_inr,
                ram_gb=product.ram_gb,
                storage_gb=product.storage_gb,
                user_rating_5=product.user_rating_5,
                source_url=product.source_url,
                score=scores[product.product_id],
                bm25_raw_score=bm25_raw[product.product_id],
                bm25_normalized_score=bm25_normalized[product.product_id],
                semantic_cosine_score=semantic_cosine[product.product_id],
                semantic_normalized_score=semantic_normalized[product.product_id],
            )
            for rank, product in enumerate(ordered, start=1)
        )


def _dcg(relevances: Sequence[int]) -> float:
    return sum(value / math.log2(rank + 1) for rank, value in enumerate(relevances, start=1))


def _aggregate_metrics(results: Sequence[Mapping[str, object]]) -> dict[str, float]:
    return {
        "recall_at_k": sum(float(value["recall_at_k"]) for value in results) / len(results),
        "mrr_at_k": sum(float(value["reciprocal_rank_at_k"]) for value in results) / len(results),
        "ndcg_at_k": sum(float(value["ndcg_at_k"]) for value in results) / len(results),
        "constraint_satisfaction_rate": sum(
            bool(value["constraint_satisfied"]) for value in results
        )
        / len(results),
    }


def evaluate_retriever(
    retriever: HybridRetriever,
    cases: Sequence[Mapping[str, object]],
    *,
    mode: RetrievalMode,
    alpha: float = DEFAULT_ALPHA,
    limit: int = 10,
) -> dict:
    if not cases:
        raise ValueError("evaluation requires at least one case")
    known = retriever._product_by_id
    results = []
    for case in cases:
        case_id = str(case.get("case_id", ""))
        query = str(case.get("query", ""))
        judgments = case.get("relevant_product_ids")
        if not case_id or not query.strip():
            raise ValueError("each evaluation case requires a non-empty ID and query")
        if (
            not isinstance(judgments, list)
            or not judgments
            or not all(isinstance(value, str) and value for value in judgments)
        ):
            raise ValueError(f"evaluation case {case_id!r} has invalid relevance judgments")
        relevant = set(judgments)
        unknown = relevant - known.keys()
        if unknown:
            raise ValueError(f"evaluation case {case_id!r} has unknown IDs: {sorted(unknown)}")
        constraints_value = case.get("constraints")
        if constraints_value is not None and not isinstance(constraints_value, Mapping):
            raise ValueError(f"evaluation case {case_id!r} has invalid constraints")
        constraints = SearchConstraints.from_dict(constraints_value)
        excluded_judgments = [value for value in relevant if not constraints.matches(known[value])]
        if excluded_judgments:
            raise ValueError(
                f"evaluation case {case_id!r} constraints exclude judged IDs: {excluded_judgments}"
            )
        ranked = retriever.search(
            query, mode=mode, constraints=constraints, alpha=alpha, limit=limit
        )
        retrieved = [result.product_id for result in ranked]
        binary = [int(value in relevant) for value in retrieved]
        hits = sum(binary)
        first_hit = next((rank for rank, value in enumerate(binary, start=1) if value), None)
        ideal = [1] * min(len(relevant), limit)
        results.append(
            {
                "case_id": case_id,
                "category": str(case.get("category", "uncategorized")),
                "query": query,
                "retrieved_product_ids": retrieved,
                "recall_at_k": hits / len(relevant),
                "reciprocal_rank_at_k": 0.0 if first_hit is None else 1 / first_hit,
                "ndcg_at_k": _dcg(binary) / _dcg(ideal),
                "constraint_satisfied": all(
                    constraints.matches(known[value]) for value in retrieved
                ),
            }
        )
    categories = sorted({str(value["category"]) for value in results})
    return {
        "mode": mode,
        "alpha": alpha if mode == "hybrid" else None,
        "k": limit,
        "cases": len(results),
        "catalogue_documents": len(retriever.products),
        "catalogue_sha256": retriever.catalogue_sha256,
        "encoder_identifier": retriever.semantic_index.encoder_identifier,
        "metrics": _aggregate_metrics(results),
        "metrics_by_category": {
            category: _aggregate_metrics(
                [value for value in results if value["category"] == category]
            )
            for category in categories
        },
        "results": results,
    }


def compare_configurations(
    retriever: HybridRetriever,
    cases: Sequence[Mapping[str, object]],
    *,
    alphas: Sequence[float] = ALPHA_CANDIDATES,
    limit: int = 10,
) -> dict:
    if not alphas:
        raise ValueError("at least one hybrid alpha is required")
    reports = [
        evaluate_retriever(retriever, cases, mode="bm25", limit=limit),
        evaluate_retriever(retriever, cases, mode="semantic", limit=limit),
    ]
    hybrid_reports = [
        evaluate_retriever(retriever, cases, mode="hybrid", alpha=alpha, limit=limit)
        for alpha in alphas
    ]
    reports.extend(hybrid_reports)
    best = max(
        hybrid_reports,
        key=lambda report: (
            report["metrics"]["ndcg_at_k"],
            report["metrics"]["mrr_at_k"],
            report["metrics"]["recall_at_k"],
            -abs(report["alpha"] - 0.5),
            -report["alpha"],
        ),
    )
    return {
        "selection": {
            "alpha": best["alpha"],
            "rule": "highest NDCG@k, then MRR@k, Recall@k, proximity to 0.5, lower alpha",
        },
        "reports": reports,
    }


def load_evaluation_cases(path: Path, *, expected_catalogue_sha256: str) -> tuple[dict, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("catalogue_sha256") != expected_catalogue_sha256:
        raise ValueError("evaluation judgments were created for a different catalogue")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
        raise ValueError("evaluation file must contain a cases list")
    ids = [str(case.get("case_id", "")) for case in cases]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("evaluation case IDs must be non-empty and unique")
    return tuple(cases)


def _write_json(path: Path, payload: object) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _add_artifact_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--catalogue", required=True, type=Path)
    parser.add_argument("--bm25-index", required=True, type=Path)
    parser.add_argument("--semantic-index", required=True, type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device")
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="load the embedding model from the local cache without network metadata checks",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-semantic", help="embed the Phase 1 catalogue")
    build.add_argument("--catalogue", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--model", default=DEFAULT_MODEL_NAME)
    build.add_argument("--revision", default=DEFAULT_MODEL_REVISION)
    build.add_argument("--device")
    build.add_argument(
        "--local-files-only",
        action="store_true",
        help="load the embedding model from the local cache without network metadata checks",
    )
    search = commands.add_parser("search", help="search using BM25, semantic, or hybrid ranking")
    _add_artifact_arguments(search)
    search.add_argument("--query", required=True)
    search.add_argument("--mode", choices=SUPPORTED_MODES, default="hybrid")
    search.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--max-price", type=float)
    search.add_argument("--min-ram", type=float)
    search.add_argument("--include-brand", action="append", default=[])
    search.add_argument("--exclude-brand", action="append", default=[])
    search.add_argument("--min-rating", type=float)
    search.add_argument("--min-storage", type=float)
    evaluation = commands.add_parser("evaluate", help="compare retrieval configurations")
    _add_artifact_arguments(evaluation)
    evaluation.add_argument("--cases", required=True, type=Path)
    evaluation.add_argument("--alphas", nargs="+", type=float, default=list(ALPHA_CANDIDATES))
    evaluation.add_argument("--limit", type=int, default=10)
    evaluation.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    encoder = SentenceTransformerEncoder(
        args.model,
        revision=args.revision,
        device=args.device,
        local_files_only=getattr(args, "local_files_only", False),
    )
    if args.command == "build-semantic":
        index = SemanticIndex.from_catalogue(args.catalogue, encoder)
        index.save(args.output)
        print(json.dumps({"documents": len(index.product_ids), "dimension": index.dimension}))
        return 0
    retriever = HybridRetriever.from_paths(
        args.catalogue, args.bm25_index, args.semantic_index, encoder
    )
    if args.command == "search":
        constraints = SearchConstraints(
            max_price_inr=args.max_price,
            min_ram_gb=args.min_ram,
            included_brands=tuple(args.include_brand),
            excluded_brands=tuple(args.exclude_brand),
            min_rating_5=args.min_rating,
            min_storage_gb=args.min_storage,
        )
        results = retriever.search(
            args.query,
            mode=args.mode,
            constraints=constraints,
            alpha=args.alpha,
            limit=args.limit,
        )
        print(json.dumps([result.as_dict() for result in results], ensure_ascii=False))
        return 0
    cases = load_evaluation_cases(args.cases, expected_catalogue_sha256=retriever.catalogue_sha256)
    report = compare_configurations(retriever, cases, alphas=args.alphas, limit=args.limit)
    _write_json(args.output, report)
    print(json.dumps([item["metrics"] for item in report["reports"]]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
