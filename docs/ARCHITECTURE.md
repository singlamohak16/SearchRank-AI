# Architecture

## Current architecture

The approved application domain is smartphones (changed from laptops on 2026-09-03). The Phase 0
foundation contains a Python package boundary, validated environment configuration, shared logging,
and smoke tests. Phase 1 has added local suitability-audit paths:

```text
Unchanged local ZIP -> streamed CSV inventory -> exact laptop-category records
                    -> deterministic title/numeric/ID probes -> local review artifacts
```

`data_audit.py` handles streaming, validation, counts, provenance, and artifact output.
`audit_titles.py` estimates title-field coverage and flags uncertainty; it is not a production
cleaner or product schema. Original records remain separate from derived findings. No audit step
executes catalogue text, calls an LLM, downloads images, or checks live product pages.

The retained flow above belongs to the rejected laptop source. The rejected Amazon smartphone
candidate follows this audit-only path:

```text
Unchanged phone ZIP -> all six-column CSV records -> phone_titles evidence probes
                    -> numeric / direct-or-sponsored URL checks / duplicate groups
                    -> report.json + records.jsonl + deterministic samples.json
```

`phone_audit.py` preserves all records and reports duplicate-field conflicts without selecting or
deleting rows. `phone_titles.py` separates explicit capacities from unlabelled pair hypotheses,
flags expansion/virtual-RAM uncertainty, and assigns review categories. Unknown remains unknown.
These modules are audit tools, not the final product schema or production cleaning pipeline.

The adopted 91mobiles path is:

```text
Unchanged 17-column ZIP -> schema and source-hash validation -> explicit field parsers
                        -> evidence-based eligibility reasons -> 18-field core catalogue CSV
                        -> report.json + records.jsonl + deterministic samples.json
```

`mobile_catalogue.py` validates all rows before writing, derives stable IDs from unique source URL
slugs, normalizes only explicit units/scales, rejects capacity-evidenced feature phones and
announced products, and refuses output overwrites or duplicate product IDs. The audit JSONL retains
every raw value. The generated catalogue excludes `spec_score`, `antutu_score`, `awards`,
`expert_rating`, and `store` as instructed. See [the catalogue audit](MOBILE_CATALOGUE_AUDIT.md).

The Phase 2 keyword path is now:

```text
Generated 18-field catalogue CSV -> exact schema and ID validation
                                 -> weighted Unicode term frequencies
                                 -> versioned local BM25 JSON index
                                 -> query tokenization and BM25 scoring
                                 -> ranked product IDs, names, source URLs, and scores
```

`bm25.py` provides index building, loading, search, and binary-relevance evaluation without a
runtime dependency. Product names receive the strongest fixed lexical weight, brands a smaller
boost, and stored processor/display/camera/charging/battery evidence remains searchable. Stable
product IDs break score ties. The index carries the input catalogue hash and generated index files
remain ignored. Reviewed judgments can pin that hash to reject stale evaluations.

This is a retrieval component, not a user-facing search workflow. It does not parse or enforce hard
constraints, call an LLM, retrieve semantically, combine rankers, fetch URLs, or load a database.
Those boundaries keep the BM25 baseline independently measurable before Phase 3.

The Phase 3 retrieval path is:

```text
18-field catalogue -> labelled search text -> pinned MiniLM document embeddings -> local NPZ index
                  \-> Phase 2 BM25 index

query -> optional strict constraints -> eligible product IDs
      -> BM25 scores / semantic cosine scores
      -> per-query score normalization
      -> measured hybrid combination (alpha = 0.25)
      -> stable ranked product IDs with filter evidence and source URLs
```

`semantic.py` owns search-text construction, the Sentence Transformers adapter, embedding
normalization, and the versioned local vector artifact. `retrieval.py` aligns the catalogue, BM25
index, and semantic index by product order and catalogue hash. It supports independently measurable
`bm25`, `semantic`, and `hybrid` modes.

Price, RAM, storage, rating, and included/excluded brands are checked against structured values
before scores are normalized or ranked. A missing rating fails a minimum-rating constraint, and
contradictory brand constraints are rejected. The hybrid score is 25% max-normalized BM25 and 75%
shifted cosine similarity, selected from the measured 0.25/0.50/0.75 comparison. This phase uses an
in-memory NumPy matrix.

The Phase 4 persistence path is:

```text
validated 18-field catalogue + aligned semantic NPZ
    -> catalogue hash / product order / encoder / dimension checks
    -> one transactional PostgreSQL synchronization
    -> complete product rows + pgvector embeddings + catalogue metadata

product IDs -> ordered complete evidence + explicit missing IDs
query embedding -> pgvector cosine distance -> ranked complete product records
```

`storage.py` owns the database boundary. The `searchrank_ai.products` table stores the complete
core catalogue and one fixed-dimension `vector` per product. A singleton metadata row records the
schema version, catalogue hash, encoder identifier, dimension, and product count. An advisory
transaction lock prevents two ingestion runs for the same application schema from interleaving.
Upserts and stale-row deletion occur in one transaction, so a failure cannot expose a partially
synchronized catalogue.

The Psycopg connection uses autocommit for standalone reads and type-registration queries. Schema
creation and ingestion use explicit transaction blocks, ensuring they commit atomically without an
implicit outer transaction that could be discarded when the connection closes.

Database values use parameters, while the only interpolated identifiers are fixed table names
inside a strictly validated lowercase schema. Product text remains untrusted data. Exact pgvector
cosine search is appropriate for 3,062 records; an approximate index is deferred until measured
scale or latency justifies one. The existing in-memory hybrid retriever remains independently
measurable rather than being silently replaced.

## Current agent workflow and application boundary

```text
User
  -> Streamlit demonstration
  -> FastAPI backend
  -> one bounded LangGraph workflow
       -> request analysis and structured constraints
       -> explicit search, comparison, clarification, conflict, or unsupported route
       -> catalogue search tool (BM25, semantic, or hybrid + strict filters)
       -> product details tool
       -> evidence verification tool
       -> at most one query reformulation and four total tool calls
  -> deterministic rendering of verified facts, conclusions, and unavailable information
  -> validated JSON response and source links

Storage: PostgreSQL + pgvector
```

`workflow.py` now owns the single compiled LangGraph graph and its conditional routes. The LLM is
limited to request understanding, essential clarification, one bounded query reformulation, and a
structured answer draft. Price, RAM, storage, rating, brand filters, exact evidence checks, citation
validation, and final rendering remain deterministic Python logic. Conflicting constraints stop
before retrieval, a failed search receives no more than one reformulation, and the workflow refuses
to exceed four recorded tool calls.

The configurable provider boundary has an offline scripted mock for normal tests and an optional
OpenAI Responses API adapter. The adapter requests strict JSON output, disables response storage,
and labels catalogue fields as untrusted data. Catalogue text can be quoted as evidence but cannot
change workflow instructions, relax constraints, or authorize another action. The evidence verifier
rejects unknown product IDs, values that do not exactly match stored records, unsupported comparison
criteria, and invalid numeric winners before any answer is shown.

Following the 2026-09-09 review, stored details are checked against the original strict constraints
before draft generation and again in the verifier. Violations take a direct verification-failure
route. Missing-information output contains only verified product/field pairs rendered with fixed
labels and stored citations. `evidence_policy.py` owns the comparison field/direction mapping;
the draft cannot independently change what `lowest price` or another directional criterion means.

## Component boundaries

- **Data:** schema, cleaning, provenance, and reproducible ingestion.
- **Retrieval:** independently measurable BM25, semantic, and hybrid implementations.
- **Storage:** product records and embeddings with traceable identifiers.
- **Workflow:** state and conditional routes with explicit retry/tool-call limits.
- **Providers:** configurable LLM interface plus a deterministic test double.
- **API:** Pydantic validation, component readiness, HTTP error mapping, and service delegation.
- **UI:** a single Streamlit page that communicates only through the JSON API.
- **Evaluation:** reviewed scenarios, reproducible metrics, and documented failure cases.

Data, retrieval, storage, workflow, provider, API, and UI boundaries are implemented through Phase
6. Containerization and broad evaluation remain later-phase work.

## API and interface boundary

`api_models.py` owns the public Pydantic contracts. `api.py` validates and maps HTTP concerns, then
delegates blocking calls to injected application services through a thread pool. It does not
implement ranking, filters, workflow routes, database queries, or evidence rules.

`services.py` assembles the production dependencies once during application startup. Its readiness
is component-aware: local retrieval may be available while PostgreSQL or the real LLM provider is
not. `/health` reports that distinction, and affected routes return `503` with safe setup messages.
The embedding adapter defaults to local cached files in the API to prevent unexpected startup
network calls.

`streamlit_app.py` sends JSON through the transport-only `api_client.py`. It renders API results and
workflow audit fields but has no direct access to retrieval or agent objects. This keeps the UI
replaceable and prevents presentation code from silently relaxing strict constraints.
