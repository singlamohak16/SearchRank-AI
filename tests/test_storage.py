"""Unit tests for Phase 4 catalogue and PostgreSQL storage boundaries."""

from __future__ import annotations

import csv
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import numpy as np
import pgvector.psycopg as pgvector_psycopg
import psycopg
import pytest

from searchrank_ai.data_audit import sha256
from searchrank_ai.mobile_catalogue import FINAL_FIELDS
from searchrank_ai.semantic import SemanticIndex
from searchrank_ai.storage import (
    CatalogueBatch,
    PostgresStorage,
    StoredProduct,
    load_catalogue_batch,
)


def _row(product_id: str = "91mobiles:test-phone", name: str = "Test Phone") -> dict[str, str]:
    return {
        "product_id": product_id,
        "product_name": name,
        "brand": "Test",
        "price_inr": "19999",
        "ram_gb": "8",
        "storage_gb": "128",
        "user_rating_5": "4.25",
        "processor": "Test Chip",
        "battery_mah": "5000",
        "charging": "45W Fast Charging",
        "display_inches": "6.5",
        "display_type": "AMOLED",
        "rear_camera": "50 MP",
        "front_camera": "16 MP",
        "release_date": "2025-06-01",
        "release_status": "Released",
        "source_url": "https://www.91mobiles.com/test-phone-price-in-india",
        "image_url": "",
    }


def _catalogue(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FINAL_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _batch(tmp_path: Path, rows: list[dict[str, str]] | None = None) -> CatalogueBatch:
    selected = rows or [_row()]
    path = _catalogue(tmp_path / "catalogue.csv", selected)
    embeddings = np.asarray([[0.6, 0.8]] * len(selected), dtype=np.float32)
    index = SemanticIndex(
        tuple(row["product_id"] for row in selected), embeddings, sha256(path), "test-encoder@1"
    )
    return load_catalogue_batch(path, index)


class FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]] | None = None, fetchone: Any = None) -> None:
        self.rows = rows or []
        self.fetchone_value = fetchone
        self.executions: list[tuple[str, Any]] = []
        self.many: list[tuple[str, Any]] = []

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def __iter__(self):
        return iter(self.rows)

    def execute(self, statement: str, parameters: Any = None) -> None:
        self.executions.append((statement, parameters))

    def executemany(self, statement: str, parameters: Any) -> None:
        self.many.append((statement, parameters))

    def fetchone(self) -> Any:
        return self.fetchone_value


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.closed = False

    def transaction(self):
        return nullcontext()

    def cursor(self) -> FakeCursor:
        return self._cursor

    def close(self) -> None:
        self.closed = True


def test_connect_uses_autocommit_for_explicit_transaction_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(FakeCursor())
    captured: dict[str, Any] = {}

    def connect(database_url: str, *, autocommit: bool) -> FakeConnection:
        captured.update(database_url=database_url, autocommit=autocommit)
        return connection

    monkeypatch.setattr(psycopg, "connect", connect)
    monkeypatch.setattr(pgvector_psycopg, "register_vector", lambda _connection: None)

    storage = PostgresStorage.connect("postgresql://example.test/searchrank")

    assert storage.connection is connection
    assert captured == {
        "database_url": "postgresql://example.test/searchrank",
        "autocommit": True,
    }


def test_catalogue_batch_preserves_all_fields_and_alignment(tmp_path: Path) -> None:
    batch = _batch(tmp_path)

    assert batch.catalogue_sha256
    assert batch.encoder_identifier == "test-encoder@1"
    assert batch.dimension == 2
    assert batch.products[0] == StoredProduct(
        product_id="91mobiles:test-phone",
        product_name="Test Phone",
        brand="Test",
        price_inr=19999,
        ram_gb=8.0,
        storage_gb=128.0,
        user_rating_5=4.25,
        processor="Test Chip",
        battery_mah=5000,
        charging="45W Fast Charging",
        display_inches=6.5,
        display_type="AMOLED",
        rear_camera="50 MP",
        front_camera="16 MP",
        release_date=batch.products[0].release_date,
        release_status="Released",
        source_url="https://www.91mobiles.com/test-phone-price-in-india",
        image_url=None,
    )


def test_catalogue_batch_rejects_wrong_hash_order_and_duplicate_ids(tmp_path: Path) -> None:
    path = _catalogue(tmp_path / "catalogue.csv", [_row(), _row("91mobiles:second", "Second")])
    wrong_hash = SemanticIndex(
        ("91mobiles:test-phone", "91mobiles:second"),
        np.eye(2, dtype=np.float32),
        "wrong-hash",
        "test-encoder@1",
    )
    with pytest.raises(ValueError, match="different catalogue"):
        load_catalogue_batch(path, wrong_hash)

    wrong_order = SemanticIndex(
        ("91mobiles:second", "91mobiles:test-phone"),
        np.eye(2, dtype=np.float32),
        sha256(path),
        "test-encoder@1",
    )
    with pytest.raises(ValueError, match="product order"):
        load_catalogue_batch(path, wrong_order)

    duplicate_path = _catalogue(tmp_path / "duplicates.csv", [_row(), _row()])
    duplicate_index = SemanticIndex(
        ("91mobiles:test-phone", "91mobiles:other"),
        np.eye(2, dtype=np.float32),
        sha256(duplicate_path),
        "test-encoder@1",
    )
    with pytest.raises(ValueError, match="unique"):
        load_catalogue_batch(duplicate_path, duplicate_index)


def test_catalogue_batch_validates_direct_construction(tmp_path: Path) -> None:
    product = _batch(tmp_path).products[0]

    with pytest.raises(ValueError, match="counts"):
        CatalogueBatch(
            products=(product,),
            embeddings=np.eye(2, dtype=np.float32),
            catalogue_sha256="hash",
            encoder_identifier="encoder",
        )
    with pytest.raises(ValueError, match="finite"):
        CatalogueBatch(
            products=(product,),
            embeddings=np.asarray([[float("nan"), 1.0]], dtype=np.float32),
            catalogue_sha256="hash",
            encoder_identifier="encoder",
        )


def test_schema_and_ingestion_use_pgvector_and_parameterized_values(tmp_path: Path) -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    registration_calls = []

    def register_vector(registered_connection: FakeConnection) -> None:
        assert registered_connection is connection
        assert any("CREATE EXTENSION" in statement for statement, _ in cursor.executions)
        registration_calls.append(registered_connection)

    storage = PostgresStorage(connection, vector_registrar=register_vector)
    batch = _batch(tmp_path)

    with pytest.raises(RuntimeError, match="initialize"):
        storage.ingest(batch)
    storage.initialize_schema(batch.dimension)
    summary = storage.ingest(batch)

    statements = "\n".join(statement for statement, _ in cursor.executions)
    assert "CREATE EXTENSION IF NOT EXISTS vector" in statements
    assert "embedding vector(2) NOT NULL" in statements
    assert "CREATE TABLE IF NOT EXISTS searchrank_ai.catalogue_metadata" in statements
    assert registration_calls == [connection]
    assert "pg_advisory_xact_lock" in statements
    assert cursor.many and "%s" in cursor.many[0][0]
    assert "Test Phone" not in cursor.many[0][0]
    assert summary.products == 1
    assert summary.dimension == 2


def test_product_lookup_preserves_request_order_and_reports_missing_ids() -> None:
    first = StoredProduct(**_stored_values("91mobiles:first", "First"))
    second = StoredProduct(**_stored_values("91mobiles:second", "Second"))
    cursor = FakeCursor(
        rows=[
            tuple(getattr(first, field) for field in first.__dataclass_fields__),
            tuple(getattr(second, field) for field in second.__dataclass_fields__),
        ]
    )
    storage = PostgresStorage(FakeConnection(cursor))

    lookup = storage.get_product_details(
        ["91mobiles:second", "91mobiles:missing", "91mobiles:first", "91mobiles:second"]
    )

    assert [product.product_id for product in lookup.products] == [
        "91mobiles:second",
        "91mobiles:first",
    ]
    assert lookup.missing_product_ids == ("91mobiles:missing",)


def _stored_values(product_id: str, name: str) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "product_name": name,
        "brand": "Test",
        "price_inr": 10000,
        "ram_gb": 8.0,
        "storage_gb": 128.0,
        "user_rating_5": 4.0,
        "processor": None,
        "battery_mah": None,
        "charging": None,
        "display_inches": None,
        "display_type": None,
        "rear_camera": None,
        "front_camera": None,
        "release_date": None,
        "release_status": None,
        "source_url": f"https://example.test/{product_id}",
        "image_url": None,
    }


def test_vector_search_validates_dimension_and_returns_ranked_products() -> None:
    first = StoredProduct(**_stored_values("91mobiles:first", "First"))
    row = tuple(getattr(first, field) for field in first.__dataclass_fields__) + (0.75,)
    cursor = FakeCursor(rows=[row], fetchone=(2,))
    storage = PostgresStorage(FakeConnection(cursor))

    results = storage.vector_search([0.6, 0.8], limit=5)

    assert results[0].rank == 1
    assert results[0].product.product_id == "91mobiles:first"
    assert results[0].cosine_similarity == 0.75
    assert "embedding <=> %s" in cursor.executions[-1][0]

    with pytest.raises(ValueError, match="dimension"):
        storage.vector_search([1.0, 0.0, 0.0])


@pytest.mark.parametrize(
    ("schema", "message"),
    [("Bad-Schema", "safe lowercase"), ("public; DROP SCHEMA public", "safe lowercase")],
)
def test_storage_rejects_unsafe_schema_names(schema: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        PostgresStorage(FakeConnection(FakeCursor()), schema=schema)
