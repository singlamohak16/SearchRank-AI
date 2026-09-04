"""Deterministic BM25 keyword retrieval for the smartphone catalogue.

Catalogue values are treated only as untrusted text. The index keeps stable product
IDs and source URLs for traceability; it does not interpret or enforce constraints.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from searchrank_ai.data_audit import sha256
from searchrank_ai.mobile_catalogue import FINAL_FIELDS

INDEX_FORMAT = "searchrank-ai-bm25"
INDEX_VERSION = 1
DEFAULT_K1 = 1.5
DEFAULT_B = 0.75
FIELD_WEIGHTS = {
    "product_name": 3,
    "brand": 2,
    "processor": 1,
    "charging": 1,
    "display_type": 1,
    "rear_camera": 1,
    "front_camera": 1,
}
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text: str) -> tuple[str, ...]:
    """Case-fold text into deterministic Unicode alphanumeric tokens."""
    return tuple(_TOKEN.findall(text.casefold()))


@dataclass(frozen=True)
class IndexedDocument:
    product_id: str
    product_name: str
    source_url: str
    term_frequencies: dict[str, int]
    length: int


@dataclass(frozen=True)
class SearchResult:
    rank: int
    product_id: str
    product_name: str
    source_url: str
    score: float

    def as_dict(self) -> dict[str, int | str | float]:
        return {
            "rank": self.rank,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "source_url": self.source_url,
            "score": round(self.score, 8),
        }


def _document_from_row(row: dict[str, str]) -> IndexedDocument:
    counts: Counter[str] = Counter()
    for field, weight in FIELD_WEIGHTS.items():
        for token in tokenize(row[field]):
            counts[token] += weight
    if row["battery_mah"]:
        counts.update(tokenize(f"{row['battery_mah']} mah battery"))
    return IndexedDocument(
        product_id=row["product_id"],
        product_name=row["product_name"],
        source_url=row["source_url"],
        term_frequencies=dict(sorted(counts.items())),
        length=sum(counts.values()),
    )


def load_catalogue(path: Path) -> tuple[IndexedDocument, ...]:
    """Validate the Phase 1 CSV and convert each row to searchable terms."""
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FINAL_FIELDS:
            raise ValueError("catalogue schema does not match the approved Phase 1 schema")
        documents = tuple(_document_from_row(row) for row in reader)
    if not documents:
        raise ValueError("catalogue contains no records")
    product_ids = [document.product_id for document in documents]
    if any(not product_id for product_id in product_ids):
        raise ValueError("catalogue contains an empty product ID")
    if len(product_ids) != len(set(product_ids)):
        raise ValueError("catalogue contains duplicate product IDs")
    if any(document.length == 0 for document in documents):
        raise ValueError("catalogue contains a record without searchable text")
    return documents


class BM25Index:
    """Small, immutable in-memory BM25 index with deterministic ranking."""

    def __init__(
        self,
        documents: Sequence[IndexedDocument],
        *,
        catalogue_sha256: str,
        k1: float = DEFAULT_K1,
        b: float = DEFAULT_B,
    ) -> None:
        if not documents:
            raise ValueError("an index requires at least one document")
        if not math.isfinite(k1) or k1 <= 0:
            raise ValueError("k1 must be a positive finite number")
        if not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError("b must be a finite number from 0 to 1")
        ids = [document.product_id for document in documents]
        if len(ids) != len(set(ids)):
            raise ValueError("an index cannot contain duplicate product IDs")
        if any(document.length <= 0 for document in documents):
            raise ValueError("indexed document lengths must be positive")
        if any(
            document.length != sum(document.term_frequencies.values()) for document in documents
        ):
            raise ValueError("indexed document lengths must match their term frequencies")

        self.documents = tuple(documents)
        self.catalogue_sha256 = catalogue_sha256
        self.k1 = float(k1)
        self.b = float(b)
        self.average_document_length = sum(doc.length for doc in documents) / len(documents)
        postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for position, document in enumerate(self.documents):
            for term, frequency in document.term_frequencies.items():
                if frequency <= 0:
                    raise ValueError("term frequencies must be positive")
                postings[term].append((position, frequency))
        self._postings = dict(postings)

    @classmethod
    def from_catalogue(
        cls, path: Path, *, k1: float = DEFAULT_K1, b: float = DEFAULT_B
    ) -> BM25Index:
        return cls(load_catalogue(path), catalogue_sha256=sha256(path), k1=k1, b=b)

    def search(self, query: str, *, limit: int = 10) -> tuple[SearchResult, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        query_terms = Counter(tokenize(query))
        if not query_terms:
            return ()

        scores: dict[int, float] = defaultdict(float)
        document_count = len(self.documents)
        for term, query_frequency in query_terms.items():
            postings = self._postings.get(term, ())
            document_frequency = len(postings)
            if not document_frequency:
                continue
            inverse_document_frequency = math.log(
                1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            for position, term_frequency in postings:
                document = self.documents[position]
                normalization = self.k1 * (
                    1 - self.b + self.b * document.length / self.average_document_length
                )
                scores[position] += (
                    query_frequency
                    * inverse_document_frequency
                    * term_frequency
                    * (self.k1 + 1)
                    / (term_frequency + normalization)
                )

        ordered = sorted(
            scores.items(),
            key=lambda item: (-item[1], self.documents[item[0]].product_id),
        )[:limit]
        return tuple(
            SearchResult(
                rank=rank,
                product_id=self.documents[position].product_id,
                product_name=self.documents[position].product_name,
                source_url=self.documents[position].source_url,
                score=score,
            )
            for rank, (position, score) in enumerate(ordered, start=1)
        )

    def as_dict(self) -> dict:
        return {
            "format": INDEX_FORMAT,
            "version": INDEX_VERSION,
            "catalogue_sha256": self.catalogue_sha256,
            "parameters": {"k1": self.k1, "b": self.b},
            "field_weights": FIELD_WEIGHTS,
            "documents": [
                {
                    "product_id": document.product_id,
                    "product_name": document.product_name,
                    "source_url": document.source_url,
                    "length": document.length,
                    "term_frequencies": document.term_frequencies,
                }
                for document in self.documents
            ],
        }

    def save(self, path: Path) -> None:
        if path.exists():
            raise FileExistsError(f"refusing to overwrite index: {path}")
        payload = json.dumps(
            self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> BM25Index:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("format") != INDEX_FORMAT or payload.get("version") != INDEX_VERSION:
            raise ValueError("unsupported BM25 index format or version")
        if payload.get("field_weights") != FIELD_WEIGHTS:
            raise ValueError("index field weights do not match this implementation")
        try:
            documents = tuple(
                IndexedDocument(
                    product_id=item["product_id"],
                    product_name=item["product_name"],
                    source_url=item["source_url"],
                    term_frequencies={
                        str(term): int(frequency)
                        for term, frequency in item["term_frequencies"].items()
                    },
                    length=int(item["length"]),
                )
                for item in payload["documents"]
            )
            parameters = payload["parameters"]
            catalogue_hash = str(payload["catalogue_sha256"])
            k1 = float(parameters["k1"])
            b = float(parameters["b"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("malformed BM25 index") from error
        return cls(
            documents,
            catalogue_sha256=catalogue_hash,
            k1=k1,
            b=b,
        )


def _dcg(relevances: Iterable[int]) -> float:
    return sum(value / math.log2(rank + 1) for rank, value in enumerate(relevances, start=1))


def evaluate(index: BM25Index, cases: Sequence[dict], *, limit: int = 10) -> dict:
    """Evaluate binary relevance judgments without inventing unlabelled relevance."""
    if not cases:
        raise ValueError("evaluation requires at least one case")
    results = []
    indexed_product_ids = {document.product_id for document in index.documents}
    for case in cases:
        case_id = str(case["case_id"])
        query = str(case["query"])
        judgments = case["relevant_product_ids"]
        if not isinstance(judgments, list) or not all(
            isinstance(product_id, str) and product_id for product_id in judgments
        ):
            raise ValueError(f"evaluation case {case_id!r} has invalid relevance judgments")
        relevant = set(judgments)
        if not relevant:
            raise ValueError(f"evaluation case {case_id!r} has no relevance judgments")
        unknown = relevant - indexed_product_ids
        if unknown:
            raise ValueError(
                f"evaluation case {case_id!r} refers to unknown product IDs: {sorted(unknown)}"
            )
        ranked = index.search(query, limit=limit)
        retrieved = [result.product_id for result in ranked]
        binary = [int(product_id in relevant) for product_id in retrieved]
        hits = sum(binary)
        first_hit = next((rank for rank, value in enumerate(binary, start=1) if value), None)
        ideal = [1] * min(len(relevant), limit)
        results.append(
            {
                "case_id": case_id,
                "query": query,
                "relevant_product_ids": sorted(relevant),
                "retrieved_product_ids": retrieved,
                "recall_at_k": hits / len(relevant),
                "reciprocal_rank_at_k": 0.0 if first_hit is None else 1 / first_hit,
                "ndcg_at_k": _dcg(binary) / _dcg(ideal),
            }
        )
    return {
        "method": "BM25",
        "k": limit,
        "cases": len(results),
        "catalogue_documents": len(index.documents),
        "catalogue_sha256": index.catalogue_sha256,
        "parameters": {"k1": index.k1, "b": index.b},
        "metrics": {
            "recall_at_k": sum(item["recall_at_k"] for item in results) / len(results),
            "mrr_at_k": sum(item["reciprocal_rank_at_k"] for item in results) / len(results),
            "ndcg_at_k": sum(item["ndcg_at_k"] for item in results) / len(results),
        },
        "results": results,
    }


def load_evaluation_cases(
    path: Path, *, expected_catalogue_sha256: str | None = None
) -> tuple[dict, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    judged_catalogue_hash = payload.get("catalogue_sha256")
    if (
        expected_catalogue_sha256 is not None
        and judged_catalogue_hash is not None
        and judged_catalogue_hash != expected_catalogue_sha256
    ):
        raise ValueError("evaluation judgments were created for a different catalogue")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
        raise ValueError("evaluation file must contain a cases list")
    required = {"case_id", "query", "relevant_product_ids"}
    if any(not required <= case.keys() for case in cases):
        raise ValueError("each evaluation case requires an ID, query, and relevance judgments")
    case_ids = [str(case["case_id"]) for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("evaluation case IDs must be unique")
    return tuple(cases)


def _write_json(path: Path, payload: dict) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="build a BM25 index from the Phase 1 catalogue")
    build.add_argument("--catalogue", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--k1", type=float, default=DEFAULT_K1)
    build.add_argument("--b", type=float, default=DEFAULT_B)
    search = commands.add_parser("search", help="search an existing BM25 index")
    search.add_argument("--index", required=True, type=Path)
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=10)
    evaluation = commands.add_parser("evaluate", help="run reviewed binary relevance cases")
    evaluation.add_argument("--index", required=True, type=Path)
    evaluation.add_argument("--cases", required=True, type=Path)
    evaluation.add_argument("--limit", type=int, default=10)
    evaluation.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "build":
        index = BM25Index.from_catalogue(args.catalogue, k1=args.k1, b=args.b)
        index.save(args.output)
        print(json.dumps({"documents": len(index.documents), "output": str(args.output)}))
        return 0
    index = BM25Index.load(args.index)
    if args.command == "search":
        print(json.dumps([item.as_dict() for item in index.search(args.query, limit=args.limit)]))
        return 0
    report = evaluate(
        index,
        load_evaluation_cases(args.cases, expected_catalogue_sha256=index.catalogue_sha256),
        limit=args.limit,
    )
    if args.output:
        _write_json(args.output, report)
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
