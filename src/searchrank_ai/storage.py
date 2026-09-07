"""PostgreSQL and pgvector persistence for catalogue records and embeddings.

The storage boundary accepts only a validated Phase 1 catalogue paired with its
aligned Phase 3 semantic index. Database writes are transactional, and product
text is always passed as data rather than interpolated into SQL.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from searchrank_ai.data_audit import sha256
from searchrank_ai.mobile_catalogue import FINAL_FIELDS
from searchrank_ai.semantic import SemanticIndex

SCHEMA_VERSION = 1
DEFAULT_SCHEMA = "searchrank_ai"
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

PRODUCT_COLUMNS = (
    "product_id",
    "product_name",
    "brand",
    "price_inr",
    "ram_gb",
    "storage_gb",
    "user_rating_5",
    "processor",
    "battery_mah",
    "charging",
    "display_inches",
    "display_type",
    "rear_camera",
    "front_camera",
    "release_date",
    "release_status",
    "source_url",
    "image_url",
)


def _optional_text(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


def _required_text(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"catalogue {field} must not be empty")
    return stripped


def _number(
    value: str, field: str, *, required: bool, integral: bool = False
) -> int | float | None:
    stripped = value.strip()
    if not stripped and not required:
        return None
    try:
        parsed = float(stripped)
    except ValueError as error:
        raise ValueError(f"catalogue {field} must be numeric") from error
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"catalogue {field} must be positive and finite")
    if integral:
        if not parsed.is_integer():
            raise ValueError(f"catalogue {field} must be an integer")
        return int(parsed)
    return parsed


def _optional_date(value: str) -> date | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return date.fromisoformat(stripped)
    except ValueError as error:
        raise ValueError("catalogue release_date must use ISO YYYY-MM-DD format") from error


@dataclass(frozen=True, slots=True)
class StoredProduct:
    """A complete stored catalogue record with original identity and provenance."""

    product_id: str
    product_name: str
    brand: str
    price_inr: int
    ram_gb: float
    storage_gb: float
    user_rating_5: float | None
    processor: str | None
    battery_mah: int | None
    charging: str | None
    display_inches: float | None
    display_type: str | None
    rear_camera: str | None
    front_camera: str | None
    release_date: date | None
    release_status: str | None
    source_url: str
    image_url: str | None


@dataclass(frozen=True, slots=True)
class CatalogueBatch:
    """Validated, aligned product records and unit embeddings."""

    products: tuple[StoredProduct, ...]
    embeddings: np.ndarray
    catalogue_sha256: str
    encoder_identifier: str

    def __post_init__(self) -> None:
        matrix = np.asarray(self.embeddings, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[1] == 0:
            raise ValueError("embeddings must be a non-empty two-dimensional matrix")
        if matrix.shape[0] != len(self.products):
            raise ValueError("product and embedding counts do not match")
        if not self.products or not np.isfinite(matrix).all():
            raise ValueError("catalogue batch must contain products and finite embeddings")
        product_ids = tuple(product.product_id for product in self.products)
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("catalogue batch product IDs must be unique")
        if not self.catalogue_sha256 or not self.encoder_identifier:
            raise ValueError("catalogue batch metadata must not be empty")
        object.__setattr__(self, "embeddings", matrix)

    @property
    def dimension(self) -> int:
        return int(self.embeddings.shape[1])


@dataclass(frozen=True, slots=True)
class IngestionSummary:
    products: int
    dimension: int
    catalogue_sha256: str
    encoder_identifier: str


@dataclass(frozen=True, slots=True)
class ProductLookup:
    products: tuple[StoredProduct, ...]
    missing_product_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    rank: int
    product: StoredProduct
    cosine_similarity: float


def _product_from_csv(row: dict[str, str]) -> StoredProduct:
    rating = _number(row["user_rating_5"], "user_rating_5", required=False)
    if rating is not None and rating > 5:
        raise ValueError("catalogue user_rating_5 must not exceed 5")
    return StoredProduct(
        product_id=_required_text(row["product_id"], "product_id"),
        product_name=_required_text(row["product_name"], "product_name"),
        brand=_required_text(row["brand"], "brand"),
        price_inr=int(_number(row["price_inr"], "price_inr", required=True, integral=True)),
        ram_gb=float(_number(row["ram_gb"], "ram_gb", required=True)),
        storage_gb=float(_number(row["storage_gb"], "storage_gb", required=True)),
        user_rating_5=None if rating is None else float(rating),
        processor=_optional_text(row["processor"]),
        battery_mah=_number(row["battery_mah"], "battery_mah", required=False, integral=True),
        charging=_optional_text(row["charging"]),
        display_inches=_number(row["display_inches"], "display_inches", required=False),
        display_type=_optional_text(row["display_type"]),
        rear_camera=_optional_text(row["rear_camera"]),
        front_camera=_optional_text(row["front_camera"]),
        release_date=_optional_date(row["release_date"]),
        release_status=_optional_text(row["release_status"]),
        source_url=_required_text(row["source_url"], "source_url"),
        image_url=_optional_text(row["image_url"]),
    )


def load_catalogue_batch(catalogue_path: Path, semantic_index: SemanticIndex) -> CatalogueBatch:
    """Validate a catalogue and require exact alignment with its semantic index."""
    with catalogue_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FINAL_FIELDS:
            raise ValueError("catalogue schema does not match the approved Phase 1 schema")
        products = tuple(_product_from_csv(row) for row in reader)
    if not products:
        raise ValueError("catalogue contains no records")
    product_ids = tuple(product.product_id for product in products)
    if len(product_ids) != len(set(product_ids)):
        raise ValueError("catalogue product IDs must be unique")
    catalogue_hash = sha256(catalogue_path)
    if catalogue_hash != semantic_index.catalogue_sha256:
        raise ValueError("semantic index was built from a different catalogue")
    if product_ids != semantic_index.product_ids:
        raise ValueError("semantic index product order does not match the catalogue")
    return CatalogueBatch(
        products=products,
        embeddings=semantic_index.embeddings,
        catalogue_sha256=catalogue_hash,
        encoder_identifier=semantic_index.encoder_identifier,
    )


def _product_values(product: StoredProduct) -> tuple[Any, ...]:
    return tuple(getattr(product, column) for column in PRODUCT_COLUMNS)


def _product_from_row(row: Sequence[Any]) -> StoredProduct:
    return StoredProduct(**dict(zip(PRODUCT_COLUMNS, row, strict=True)))


class PostgresStorage:
    """Small PostgreSQL adapter for ingestion, details, and cosine vector search."""

    def __init__(
        self,
        connection: Any,
        *,
        schema: str = DEFAULT_SCHEMA,
        vector_registrar: Any = None,
    ) -> None:
        if not _IDENTIFIER.fullmatch(schema):
            raise ValueError("database schema name must be a safe lowercase SQL identifier")
        self.connection = connection
        self.schema = schema
        self._vector_registrar = vector_registrar
        self._vector_registered = vector_registrar is None

    @classmethod
    def connect(cls, database_url: str, *, schema: str = DEFAULT_SCHEMA) -> PostgresStorage:
        if not database_url.strip():
            raise ValueError("database URL must not be empty")
        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError as error:
            raise RuntimeError(
                "install the project storage dependencies before connecting"
            ) from error
        # Reads should not leave a service connection idle in a transaction. Explicit
        # transaction blocks below still make schema creation and ingestion atomic.
        connection = psycopg.connect(database_url, autocommit=True)
        return cls(connection, schema=schema, vector_registrar=register_vector)

    def close(self) -> None:
        self.connection.close()

    def _name(self, table: str) -> str:
        return f"{self.schema}.{table}"

    def initialize_schema(self, dimension: int) -> None:
        """Create the isolated application schema and fixed-dimension vector column."""
        if isinstance(dimension, bool) or dimension <= 0:
            raise ValueError("embedding dimension must be positive")
        products = self._name("products")
        metadata = self._name("catalogue_metadata")
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema}")
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {products} (
                    product_id text PRIMARY KEY,
                    product_name text NOT NULL,
                    brand text NOT NULL,
                    price_inr integer NOT NULL CHECK (price_inr > 0),
                    ram_gb double precision NOT NULL CHECK (ram_gb > 0),
                    storage_gb double precision NOT NULL CHECK (storage_gb > 0),
                    user_rating_5 double precision CHECK (
                        user_rating_5 > 0 AND user_rating_5 <= 5
                    ),
                    processor text,
                    battery_mah integer CHECK (battery_mah > 0),
                    charging text,
                    display_inches double precision CHECK (display_inches > 0),
                    display_type text,
                    rear_camera text,
                    front_camera text,
                    release_date date,
                    release_status text,
                    source_url text NOT NULL,
                    image_url text,
                    embedding vector({dimension}) NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {metadata} (
                    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
                    schema_version integer NOT NULL,
                    catalogue_sha256 text NOT NULL,
                    encoder_identifier text NOT NULL,
                    embedding_dimension integer NOT NULL CHECK (embedding_dimension > 0),
                    product_count integer NOT NULL CHECK (product_count >= 0)
                )
                """
            )
        if self._vector_registrar is not None and not self._vector_registered:
            self._vector_registrar(self.connection)
            self._vector_registered = True

    def ingest(self, batch: CatalogueBatch) -> IngestionSummary:
        """Synchronize a complete catalogue and its embeddings in one transaction."""
        if not self._vector_registered:
            raise RuntimeError("initialize the database schema before ingestion")
        products_table = self._name("products")
        metadata_table = self._name("catalogue_metadata")
        columns = ", ".join(PRODUCT_COLUMNS)
        placeholders = ", ".join(["%s"] * (len(PRODUCT_COLUMNS) + 1))
        updates = ", ".join(f"{column} = EXCLUDED.{column}" for column in PRODUCT_COLUMNS[1:])
        statement = (
            f"INSERT INTO {products_table} ({columns}, embedding) VALUES ({placeholders}) "
            f"ON CONFLICT (product_id) DO UPDATE SET {updates}, embedding = EXCLUDED.embedding"
        )
        rows = [
            (*_product_values(product), embedding)
            for product, embedding in zip(batch.products, batch.embeddings, strict=True)
        ]
        product_ids = [product.product_id for product in batch.products]
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (self.schema,))
            cursor.executemany(statement, rows)
            cursor.execute(
                f"DELETE FROM {products_table} WHERE NOT (product_id = ANY(%s))",
                (product_ids,),
            )
            cursor.execute(
                f"""
                INSERT INTO {metadata_table} (
                    singleton, schema_version, catalogue_sha256, encoder_identifier,
                    embedding_dimension, product_count
                ) VALUES (true, %s, %s, %s, %s, %s)
                ON CONFLICT (singleton) DO UPDATE SET
                    schema_version = EXCLUDED.schema_version,
                    catalogue_sha256 = EXCLUDED.catalogue_sha256,
                    encoder_identifier = EXCLUDED.encoder_identifier,
                    embedding_dimension = EXCLUDED.embedding_dimension,
                    product_count = EXCLUDED.product_count
                """,
                (
                    SCHEMA_VERSION,
                    batch.catalogue_sha256,
                    batch.encoder_identifier,
                    batch.dimension,
                    len(batch.products),
                ),
            )
        return IngestionSummary(
            products=len(batch.products),
            dimension=batch.dimension,
            catalogue_sha256=batch.catalogue_sha256,
            encoder_identifier=batch.encoder_identifier,
        )

    def get_product_details(self, product_ids: Sequence[str]) -> ProductLookup:
        """Return complete records in requested order and report every unknown ID."""
        if isinstance(product_ids, str):
            raise ValueError("product IDs must be a sequence, not one string")
        requested = tuple(dict.fromkeys(product_id.strip() for product_id in product_ids))
        if any(not product_id for product_id in requested):
            raise ValueError("product IDs must not be empty")
        if not requested:
            return ProductLookup((), ())
        columns = ", ".join(PRODUCT_COLUMNS)
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {columns} FROM {self._name('products')} WHERE product_id = ANY(%s)",
                (list(requested),),
            )
            products = tuple(_product_from_row(row) for row in cursor)
            found = {product.product_id: product for product in products}
        return ProductLookup(
            products=tuple(found[product_id] for product_id in requested if product_id in found),
            missing_product_ids=tuple(
                product_id for product_id in requested if product_id not in found
            ),
        )

    def vector_search(
        self, query_embedding: Sequence[float] | np.ndarray, *, limit: int = 10
    ) -> tuple[VectorSearchResult, ...]:
        """Search stored embeddings with pgvector cosine distance."""
        if not self._vector_registered:
            raise RuntimeError("initialize the database schema before vector search")
        if isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        vector = np.asarray(query_embedding, dtype=np.float32)
        if vector.ndim != 1 or vector.size == 0 or not np.isfinite(vector).all():
            raise ValueError("query embedding must be one non-empty finite vector")
        if float(np.linalg.norm(vector)) == 0:
            raise ValueError("query embedding must not be a zero vector")
        columns = ", ".join(PRODUCT_COLUMNS)
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT embedding_dimension FROM {self._name('catalogue_metadata')} "
                "WHERE singleton = true"
            )
            metadata = cursor.fetchone()
            if metadata is None:
                raise RuntimeError("catalogue metadata is missing; ingest the catalogue first")
            if vector.size != metadata[0]:
                raise ValueError("query embedding dimension does not match stored embeddings")
            cursor.execute(
                f"SELECT {columns}, 1 - (embedding <=> %s) AS cosine_similarity "
                f"FROM {self._name('products')} ORDER BY embedding <=> %s, product_id LIMIT %s",
                (vector, vector, limit),
            )
            rows = tuple(cursor)
        return tuple(
            VectorSearchResult(
                rank=rank,
                product=_product_from_row(row[:-1]),
                cosine_similarity=float(row[-1]),
            )
            for rank, row in enumerate(rows, start=1)
        )


def _database_url() -> str:
    value = os.getenv("SEARCHRANK_DATABASE_URL", "").strip()
    if not value:
        raise ValueError("SEARCHRANK_DATABASE_URL is required")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init", help="create the PostgreSQL/pgvector schema")
    initialize.add_argument("--dimension", type=int, default=384)
    ingest = commands.add_parser("ingest", help="load an aligned catalogue and semantic index")
    ingest.add_argument("--catalogue", required=True, type=Path)
    ingest.add_argument("--semantic-index", required=True, type=Path)
    details = commands.add_parser("details", help="retrieve complete records by product ID")
    details.add_argument("product_ids", nargs="+")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    storage = PostgresStorage.connect(_database_url())
    try:
        if args.command == "init":
            storage.initialize_schema(args.dimension)
            print(json.dumps({"schema": storage.schema, "dimension": args.dimension}))
        elif args.command == "ingest":
            index = SemanticIndex.load(args.semantic_index)
            batch = load_catalogue_batch(args.catalogue, index)
            storage.initialize_schema(batch.dimension)
            print(json.dumps(asdict(storage.ingest(batch))))
        else:
            lookup = storage.get_product_details(args.product_ids)
            print(
                json.dumps(
                    {
                        "products": [asdict(product) for product in lookup.products],
                        "missing_product_ids": lookup.missing_product_ids,
                    },
                    default=str,
                )
            )
    finally:
        storage.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
