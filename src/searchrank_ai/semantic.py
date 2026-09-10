"""Sentence-transformer embeddings for the Phase 1 smartphone catalogue.

The production adapter is deliberately small. Tests provide an in-memory encoder,
so normal unit tests never download a model or require network access.
"""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from searchrank_ai.data_audit import sha256
from searchrank_ai.mobile_catalogue import FINAL_FIELDS

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_MODEL_REVISION = "c21050a7ef692090620a6d037dd736908f9c7cf6"
INDEX_FORMAT = "searchrank-ai-semantic"
INDEX_VERSION = 1
SEARCH_TEXT_VERSION = 1


class TextEncoder(Protocol):
    """Minimal encoder interface used by the index and deterministic test doubles."""

    @property
    def identifier(self) -> str: ...

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray: ...

    def encode_query(self, text: str) -> np.ndarray: ...


class SentenceTransformerEncoder:
    """Lazy adapter around Sentence Transformers with normalized NumPy output."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        *,
        revision: str = DEFAULT_MODEL_REVISION,
        device: str | None = None,
        local_files_only: bool = False,
    ) -> None:
        if not model_name.strip() or not revision.strip():
            raise ValueError("model name and revision must be non-empty")
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.revision = revision
        self._model = SentenceTransformer(
            model_name,
            revision=revision,
            device=device,
            local_files_only=local_files_only,
        )

    @property
    def identifier(self) -> str:
        return f"{self.model_name}@{self.revision}"

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        values = self._model.encode_document(
            list(texts),
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return np.asarray(values, dtype=np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        value = self._model.encode_query(
            text,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return np.asarray(value, dtype=np.float32)


def build_search_text(row: dict[str, str]) -> str:
    """Build labelled retrieval text from stored evidence without inventing facts."""
    parts = [
        f"product: {row['product_name'].strip()}",
        f"brand: {row['brand'].strip()}",
        "category: smartphone",
        f"memory: {row['ram_gb'].strip()} GB RAM, {row['storage_gb'].strip()} GB storage",
    ]
    labelled_fields = (
        ("processor", "processor"),
        ("battery_mah", "battery mAh"),
        ("charging", "charging"),
        ("display_inches", "display inches"),
        ("display_type", "display type"),
        ("rear_camera", "rear camera"),
        ("front_camera", "front camera"),
    )
    for field, label in labelled_fields:
        value = row[field].strip()
        if value:
            parts.append(f"{label}: {value}")
    return ". ".join(parts)


def _normalized_rows(values: np.ndarray, *, expected_rows: int | None = None) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    if matrix.ndim != 2 or matrix.shape[1] == 0:
        raise ValueError("encoder output must be a non-empty two-dimensional matrix")
    if expected_rows is not None and matrix.shape[0] != expected_rows:
        raise ValueError("encoder output row count does not match the requested texts")
    if not np.isfinite(matrix).all():
        raise ValueError("encoder output contains a non-finite value")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("encoder output contains a zero vector")
    return matrix / norms


@dataclass(frozen=True)
class SemanticIndex:
    """Immutable aligned product IDs and unit embeddings."""

    product_ids: tuple[str, ...]
    embeddings: np.ndarray
    catalogue_sha256: str
    encoder_identifier: str

    def __post_init__(self) -> None:
        if not self.product_ids or any(not value for value in self.product_ids):
            raise ValueError("semantic index requires non-empty product IDs")
        if len(self.product_ids) != len(set(self.product_ids)):
            raise ValueError("semantic index contains duplicate product IDs")
        if not self.catalogue_sha256 or not self.encoder_identifier:
            raise ValueError("semantic index metadata is incomplete")
        matrix = _normalized_rows(self.embeddings, expected_rows=len(self.product_ids)).copy()
        matrix.setflags(write=False)
        object.__setattr__(self, "embeddings", matrix)

    @property
    def dimension(self) -> int:
        return int(self.embeddings.shape[1])

    @classmethod
    def from_catalogue(cls, path: Path, encoder: TextEncoder) -> SemanticIndex:
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != FINAL_FIELDS:
                raise ValueError("catalogue schema does not match the approved Phase 1 schema")
            rows = tuple(reader)
        if not rows:
            raise ValueError("catalogue contains no records")
        product_ids = tuple(row["product_id"] for row in rows)
        if any(not value for value in product_ids) or len(product_ids) != len(set(product_ids)):
            raise ValueError("catalogue product IDs must be non-empty and unique")
        texts = tuple(build_search_text(row) for row in rows)
        embeddings = _normalized_rows(
            encoder.encode_documents(texts), expected_rows=len(product_ids)
        )
        return cls(product_ids, embeddings, sha256(path), encoder.identifier)

    def cosine_scores(self, query: str, encoder: TextEncoder) -> tuple[float, ...]:
        if not query.strip():
            return ()
        if encoder.identifier != self.encoder_identifier:
            raise ValueError("encoder does not match the semantic index")
        query_vector = _normalized_rows(encoder.encode_query(query), expected_rows=1)[0]
        return tuple(float(value) for value in self.embeddings @ query_vector)

    def save(self, path: Path) -> None:
        if path.suffix.casefold() != ".npz":
            raise ValueError("semantic index path must end in .npz")
        metadata = {
            "format": INDEX_FORMAT,
            "version": INDEX_VERSION,
            "search_text_version": SEARCH_TEXT_VERSION,
            "catalogue_sha256": self.catalogue_sha256,
            "encoder_identifier": self.encoder_identifier,
            "dimension": self.dimension,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            np.savez_compressed(
                stream,
                embeddings=self.embeddings,
                product_ids=np.asarray(self.product_ids, dtype=np.str_),
                metadata=np.asarray(json.dumps(metadata, sort_keys=True)),
            )

    @classmethod
    def load(cls, path: Path) -> SemanticIndex:
        try:
            with np.load(path, allow_pickle=False) as archive:
                if set(archive.files) != {"embeddings", "product_ids", "metadata"}:
                    raise ValueError("semantic index has unexpected members")
                embeddings = np.asarray(archive["embeddings"], dtype=np.float32)
                product_ids = tuple(str(value) for value in archive["product_ids"].tolist())
                metadata = json.loads(str(archive["metadata"].item()))
        except (KeyError, json.JSONDecodeError, OSError, TypeError) as error:
            raise ValueError("malformed semantic index") from error
        if not isinstance(metadata, dict) or (
            metadata.get("format") != INDEX_FORMAT
            or metadata.get("version") != INDEX_VERSION
            or metadata.get("search_text_version") != SEARCH_TEXT_VERSION
        ):
            raise ValueError("unsupported semantic index format or version")
        index = cls(
            product_ids,
            embeddings,
            str(metadata.get("catalogue_sha256", "")),
            str(metadata.get("encoder_identifier", "")),
        )
        dimension = metadata.get("dimension")
        if (
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension != index.dimension
            or not math.isfinite(dimension)
        ):
            raise ValueError("semantic index dimension metadata does not match its embeddings")
        return index
