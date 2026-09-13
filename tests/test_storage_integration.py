"""Optional PostgreSQL/pgvector integration coverage for Phase 4."""

from __future__ import annotations

import os
import uuid

import numpy as np
import pytest

from searchrank_ai.storage import CatalogueBatch, PostgresStorage, StoredProduct

psycopg = pytest.importorskip("psycopg")
pytest.importorskip("pgvector.psycopg")

TEST_DATABASE_URL = os.getenv("SEARCHRANK_TEST_DATABASE_URL", "").strip()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="SEARCHRANK_TEST_DATABASE_URL is not set"),
]


def test_postgres_ingestion_lookup_and_vector_search() -> None:
    schema = f"searchrank_test_{uuid.uuid4().hex[:12]}"
    storage = PostgresStorage.connect(TEST_DATABASE_URL, schema=schema)
    connection = storage.connection
    products = (
        _product("91mobiles:first", "First Phone"),
        _product("91mobiles:second", "Second Phone"),
    )
    batch = CatalogueBatch(
        products=products,
        embeddings=np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        catalogue_sha256="synthetic-catalogue-sha256",
        encoder_identifier="synthetic-encoder@1",
    )
    try:
        with pytest.raises(psycopg.Error):
            storage.check_readiness(batch.catalogue_sha256)
        storage.initialize_schema(batch.dimension)
        assert not storage.check_readiness(batch.catalogue_sha256)
        first_summary = storage.ingest(batch)
        assert storage.check_readiness(batch.catalogue_sha256)
        assert not storage.check_readiness("wrong-catalogue")
        second_summary = storage.ingest(batch)
        lookup = storage.get_product_details(
            ["91mobiles:second", "91mobiles:missing", "91mobiles:first"]
        )
        results = storage.vector_search([1.0, 0.0], limit=2)

        assert first_summary == second_summary
        assert [product.product_id for product in lookup.products] == [
            "91mobiles:second",
            "91mobiles:first",
        ]
        assert lookup.missing_product_ids == ("91mobiles:missing",)
        assert [result.product.product_id for result in results] == [
            "91mobiles:first",
            "91mobiles:second",
        ]
        assert results[0].cosine_similarity == pytest.approx(1.0)
        with connection.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM {schema}.products WHERE product_id = %s", (products[0].product_id,)
            )
        assert not storage.check_readiness(batch.catalogue_sha256)
    finally:
        with connection.transaction(), connection.cursor() as cursor:
            cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        storage.close()


def _product(product_id: str, name: str) -> StoredProduct:
    return StoredProduct(
        product_id=product_id,
        product_name=name,
        brand="Test",
        price_inr=10000,
        ram_gb=8.0,
        storage_gb=128.0,
        user_rating_5=4.0,
        processor=None,
        battery_mah=None,
        charging=None,
        display_inches=None,
        display_type=None,
        rear_camera=None,
        front_camera=None,
        release_date=None,
        release_status="Released",
        source_url=f"https://example.test/{product_id}",
        image_url=None,
    )
