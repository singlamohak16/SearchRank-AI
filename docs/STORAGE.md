# PostgreSQL and pgvector storage

Date: 2026-09-06. Phase 4 implementation and local validation record.

## Purpose

Phase 3 proved retrieval against local BM25 JSON and semantic NPZ artifacts. Phase 4 adds a durable
storage boundary for complete product evidence and embeddings without changing those measured
retrieval baselines. Later tools can ask for ranked IDs or retrieve full evidence without reading
the catalogue CSV directly.

## Schema

The `searchrank_ai.products` table stores the approved 18 catalogue fields plus one embedding:

- `product_id` is the primary key and remains the stable 91mobiles-derived ID.
- Required identity, strict-filter, and provenance values use non-null typed columns.
- Missing optional evidence remains SQL `NULL`; ingestion never fills it from model knowledge.
- `embedding vector(384)` stores the pinned Phase 3 MiniLM representation.

`searchrank_ai.catalogue_metadata` has one row containing schema version, catalogue SHA-256,
encoder identifier, embedding dimension, and product count. It prevents downstream code from
treating an unexplained vector set as current catalogue evidence.

## Ingestion guarantees

Before writing, the loader validates the exact Phase 1 schema, numeric/date values, unique product
IDs, catalogue checksum, semantic-index product order, finite vectors, encoder identity, and vector
dimension. It then acquires an application-schema advisory lock and performs all upserts, stale-ID
deletion, and metadata replacement in one transaction.

The connection runs in autocommit mode so standalone reads and pgvector type registration do not
leave an implicit transaction open. Schema creation and ingestion remain enclosed in explicit
transaction blocks and therefore retain their all-or-nothing behavior.

This is idempotent in the practical database sense: identical inputs produce the same product,
embedding, and metadata state. The command does not preserve arbitrary manual database edits,
because the generated catalogue is the source of truth.

## Queries

`get_product_details` deduplicates requested IDs while preserving their first-requested order. It
returns full stored records and reports unknown IDs separately rather than inventing placeholder
products. `vector_search` validates the query dimension, uses pgvector cosine distance, returns full
product evidence, and resolves equal distances by stable product ID.

At 3,062 records, exact pgvector ordering keeps setup and explanation simple. An approximate vector
index should be added only after Phase 7 latency measurements show a need.

## Setup and commands

Use PostgreSQL with the pgvector extension available. Give the configured application user
permission to create the extension and `searchrank_ai` schema, then set the connection URL only in
your local environment:

```powershell
$env:SEARCHRANK_DATABASE_URL = "postgresql://username:password@localhost:5432/searchrank"

.venv\Scripts\python.exe -X utf8 -m searchrank_ai.storage ingest `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue.csv `
  --semantic-index artifacts\semantic\phase3-index.npz

.venv\Scripts\python.exe -X utf8 -m searchrank_ai.storage details `
  91mobiles:xiaomi-redmi-turbo-5
```

Do not put the real URL in `.env.example`, logs, tests, or Git.

## Tests and evidence

Deterministic unit tests cover complete field conversion, hash/order/ID validation, schema SQL,
the autocommit connection model, parameterized ingestion, missing-ID handling, vector dimensions,
cosine result mapping, and unsafe schema rejection. The real ignored local files were loaded
through the new boundary: 3,062 product rows aligned to a 3,062 by 384 semantic matrix and the
recorded Phase 3 checksum/model identity.

The optional integration test performs two identical ingestions, product lookup, missing-ID
handling, and real pgvector cosine search in a unique schema, then removes that schema. Run it only
against a disposable database:

```powershell
$env:SEARCHRANK_TEST_DATABASE_URL = "postgresql://username:password@localhost:5432/searchrank_test"
.venv\Scripts\python.exe -m pytest -m integration tests\test_storage_integration.py -q
```

This machine had no PostgreSQL service during Phase 4, so that live test was skipped and no live
database result is claimed. Docker setup remains Phase 7 work.

## Limitations

- The storage search accepts an embedding; encoding natural-language queries remains in the
  existing semantic/provider boundary.
- Database-backed BM25 or complete hybrid scoring is not introduced; Phase 3 remains the measured
  retrieval implementation.
- No connection pooling, migrations framework, API, agent, or approximate vector index exists yet.
- Creating the pgvector extension may require a database administrator on managed PostgreSQL.
