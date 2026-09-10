# SearchRank-AI

> An evidence-grounded Agentic RAG project for smartphone search and comparison.

## What I am building

I am building SearchRank-AI to explore a practical question: **how can an LLM help someone search
and compare products without inventing specifications or ignoring strict requirements?**

A user should eventually be able to ask:

> Compare OnePlus and Samsung phones under ₹30,000. Show only models with at least 8 GB RAM,
> 128 GB storage, and a rating of 4 or above.

The system will understand the request, retrieve relevant smartphones, enforce the numeric filters
in deterministic Python code, collect the complete product evidence, and generate a comparison in
which every product claim can be traced to a product ID and source URL.

This is an incremental portfolio project. The data foundation, BM25 and semantic retrieval,
measured hybrid ranking, strict catalogue filters, PostgreSQL/pgvector storage, and bounded agent
workflow are complete. A FastAPI boundary and a thin Streamlit demonstration are now implemented.

## Why this project is technically interesting

Product search combines two different problems:

- **Relevance:** understanding phrases such as “good for gaming” or “strong battery life.”
- **Correctness:** never returning a ₹40,000 phone for an “under ₹30,000” request.

Semantic similarity can help with relevance, but it should not decide whether a product satisfies a
hard constraint. SearchRank-AI therefore separates responsibilities:

- BM25 and semantic retrieval will find relevant candidates.
- Deterministic filters will enforce price, RAM, storage, brand, and rating requirements.
- An LLM will interpret requests and explain comparisons, not override catalogue facts.
- An evidence verifier will check factual claims and product citations before a response is returned.

The project is not a model-training or collaborative-filtering system. It uses pretrained models
inside a focused retrieval and reasoning workflow.

## Current project status

**Phase 0 through Phase 5 are merged into `main`. Phase 6 is implemented and validated locally on
its phase branch; it has not been committed or pushed.**

What works today:

- Python package, configuration, logging, and quality-check foundations.
- A reproducible audit and cleaning pipeline for the approved smartphone dataset.
- Stable product IDs derived from unique source URLs.
- Deterministic parsing for INR prices, RAM, storage, ratings, batteries, displays, and dates.
- Explicit rejection reasons for records that are not filter-ready smartphones.
- Preservation of every original row and value in local audit evidence.
- A cleaned, core-only catalogue containing 3,062 smartphones.
- A deterministic BM25 index and command-line keyword search with traceable product IDs.
- A 12-query reviewed exact-model benchmark and reproducible Recall@10, MRR@10, and NDCG@10.
- A pinned 384-dimensional sentence-transformer and reproducible local semantic index.
- BM25, semantic, and hybrid search with explicit score components.
- Deterministic maximum-price, minimum-RAM, minimum-storage, minimum-rating, and brand filters.
- A 20-case reviewed retrieval benchmark with a measured hybrid weight of `alpha = 0.25`.
- A PostgreSQL schema for all 18 catalogue fields and aligned pgvector embeddings.
- Transactional, reproducible ingestion guarded by catalogue hash, product order, and model identity.
- Ordered product-detail lookup with explicit missing IDs and database-backed cosine vector search.
- One bounded LangGraph with separate search, comparison, clarification, unsupported, conflict,
  and no-result routes.
- Catalogue-search, product-details, and deterministic evidence-verification tools.
- One permitted search reformulation and a four-tool-call ceiling.
- Structured answer generation whose values and product/source citations must pass deterministic
  verification before rendering.
- A configurable LLM interface, network-free mock, and optional OpenAI Responses API adapter.
- Four validated FastAPI endpoints for health, retrieval, agent queries, and product details.
- Component-aware readiness and stable validation, not-found, and unavailable-service errors.
- One Streamlit page that calls the API and exposes results, constraints, grounded answers,
  citations, and workflow evidence.
- Synthetic automated tests that do not require a paid API or network access.

Not implemented yet:

- Agent-quality metrics and broad end-to-end evaluation.
- Docker Compose, authentication, rate limiting, and production deployment controls.

This distinction is intentional: the repository only claims behavior that has actually been built
and tested.

## System design

```mermaid
flowchart TD
    U[User request] --> UI[Streamlit demonstration]
    UI --> API[FastAPI backend]
    API --> G[Bounded LangGraph workflow]
    G --> Q[Understand request and extract constraints]
    Q --> S[Catalogue Search Tool]
    S --> B[BM25 retrieval]
    S --> E[Semantic retrieval]
    B --> H[Hybrid ranking]
    E --> H
    H --> F[Deterministic constraint filters]
    F --> D[Product Details Tool]
    D --> L[Grounded comparison generation]
    L --> V[Evidence Verification Tool]
    V --> R[Answer with product-ID citations]
    IDX[(BM25 + semantic artifacts)] <--> S
    DB <--> D
```

The implemented Phase 5 workflow has one bounded graph and three meaningful tools:

1. **Catalogue Search Tool** — retrieves and ranks product IDs, then applies strict filters.
2. **Product Details Tool** — returns complete stored evidence for selected product IDs.
3. **Evidence Verification Tool** — checks claims, numerical values, and product citations.

## Phase 1: data pipeline

The adopted source is Suresh Khadka's
[Mobile Phones Specs & Prices Dataset (2008–2026)](https://www.kaggle.com/datasets/suresh2837/mobile-phones-specs-and-prices-dataset-20082026),
which states that its records were collected from public 91mobiles listings.

The pipeline processes the data as follows:

```text
unchanged source ZIP
    -> checksum and 17-column schema validation
    -> explicit price, rating, capacity, display, battery, date, and URL parsing
    -> evidence-based eligibility rules with recorded rejection reasons
    -> 18-column core smartphone catalogue
    -> reproducible audit report, retained raw records, and fixed-seed samples
```

### Measured catalogue outcome

| Measurement | Result |
|---|---:|
| Source rows | 4,000 |
| Cleaned smartphone records | 3,062 |
| Unique cleaned product IDs | 3,062 |
| Brands represented | 70 |
| Records with user ratings | 2,983 |
| Exact duplicate source rows | 0 |
| Automated tests | 142 passing |

A record enters the cleaned catalogue only when it has a valid product name and source URL, a
positive INR price, explicit RAM and storage, at least 1 GB RAM and 8 GB storage, and no
“announced” or “to be announced” marker. These rules exclude feature phones and incomplete records
without inventing facts or relying on price alone.

### Core catalogue fields

The final catalogue contains only the fields needed for search, comparison, and evidence:

- Identity: `product_id`, `product_name`, `brand`
- Strict filters: `price_inr`, `ram_gb`, `storage_gb`, `user_rating_5`
- Comparison evidence: processor, battery, charging, display, rear camera, and front camera
- Provenance: release date/status, source URL, and image URL

At the user's direction, the final dataset excludes `spec_score`, `antutu_score`, `awards`,
`expert_rating`, and `store`. Their original values are retained only in ignored audit evidence.

Ratings explicitly stored on a `/10` scale are mathematically normalized to `/5`. Missing values
remain empty; the pipeline never fills them from model knowledge.

## Getting started

### Requirements

- Python 3.11 or newer
- Git

### Install the project

```powershell
git clone https://github.com/singlamohak16/SearchRank-AI.git
cd SearchRank-AI
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The current tests require no API key. Future provider credentials will be read from environment
variables documented in `.env.example`; real credentials must never be committed.

### Reproduce the cleaned catalogue

The real dataset is not committed. Download the approved Kaggle archive and save it as:

```text
data/raw/suresh_91mobiles_2008_2026/source.zip
```

Then run:

```powershell
.venv\Scripts\python.exe -X utf8 -m searchrank_ai.mobile_catalogue `
  --archive data\raw\suresh_91mobiles_2008_2026\source.zip `
  --audit-dir artifacts\suresh_91mobiles_audit\new-run `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue.csv
```

The command refuses to overwrite existing outputs. Two complete runs with the adopted source
produced byte-identical catalogues and audit evidence.

### Run the quality checks

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m pip check
```

The latest full Phase 6 run produced **278 passing tests and two skipped integration tests**. The
skips are expected when the disposable PostgreSQL URL and explicit live-LLM opt-in are unset. This
is an engineering result, not a search-, agent-quality-, or latency score.

### Build and search the BM25 baseline

After generating the local catalogue, build the ignored retrieval index:

```powershell
.venv\Scripts\python.exe -X utf8 -m searchrank_ai.bm25 build `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue.csv `
  --output artifacts\bm25\phase2-index.json

.venv\Scripts\python.exe -X utf8 -m searchrank_ai.bm25 search `
  --index artifacts\bm25\phase2-index.json `
  --query "snapdragon 8 gen 3 amoled" `
  --limit 10
```

The direct BM25 command searches names and stored specification text without numeric or categorical
shopping constraints. The hybrid retriever and API apply those filters separately. See the
[Phase 2 retrieval report](docs/BM25_RETRIEVAL.md) for design, evaluation conditions, and limits.

### Build and search the semantic and hybrid indexes

The first semantic build downloads the pinned public model revision. Later runs can use the cached
model without a network connection.

```powershell
.venv\Scripts\python.exe -X utf8 -m searchrank_ai.retrieval build-semantic `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue.csv `
  --output artifacts\semantic\phase3-index.npz `
  --device cpu

.venv\Scripts\python.exe -X utf8 -m searchrank_ai.retrieval search `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue.csv `
  --bm25-index artifacts\bm25\phase2-index.json `
  --semantic-index artifacts\semantic\phase3-index.npz `
  --mode hybrid --alpha 0.25 `
  --query "oneplus nord 6" `
  --max-price 40000 --min-ram 8 --min-storage 256 --min-rating 4.4 `
  --include-brand OnePlus
```

All strict constraints are checked against structured catalogue fields before ranking. See the
[Phase 3 retrieval report](docs/HYBRID_RETRIEVAL.md) for formulas, measurements, and limitations.

### Load PostgreSQL and pgvector storage

Phase 4 expects an existing PostgreSQL database in which the configured user may create the
`vector` extension and the isolated `searchrank_ai` schema. Put the real connection string only in
your local `.env` or shell environment:

```powershell
$env:SEARCHRANK_DATABASE_URL = "postgresql://username:password@localhost:5432/searchrank"

.venv\Scripts\python.exe -X utf8 -m searchrank_ai.storage ingest `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue.csv `
  --semantic-index artifacts\semantic\phase3-index.npz
```

The ingestion command creates the schema, loads or updates every product and embedding in one
transaction, removes rows not present in the incoming catalogue, and records the catalogue hash,
encoder identity, vector dimension, and product count. Re-running it with identical inputs leaves
the same logical database state. Retrieve complete evidence by product ID with:

```powershell
.venv\Scripts\python.exe -X utf8 -m searchrank_ai.storage details `
  91mobiles:xiaomi-redmi-turbo-5 91mobiles:unknown-phone
```

See the [Phase 4 storage report](docs/STORAGE.md) for schema, validation, integration-test setup,
and current limitations.

### Run the bounded agent workflow

Phase 5 provides an application service rather than a public command. Construct `AgentWorkflow`
with the existing hybrid retriever, a product-details repository such as `PostgresStorage`, the
evidence verifier, and either the mock or configured real LLM provider. The graph classifies the
request, validates constraints, searches, retrieves full evidence, generates a structured draft,
and releases only claims that pass deterministic verification.

Stored product records are checked against the strict constraints again before answer generation.
Missing-information claims use verified product/field pairs and fixed wording; numerical comparison
criteria are tied to an application-owned field and direction policy.

The normal suite uses `MockLLMProvider` and never makes an API call. A live OpenAI smoke test is
available only with a local key, explicit model, and `SEARCHRANK_RUN_LLM_INTEGRATION=1`. See the
[Phase 5 agentic RAG report](docs/AGENTIC_RAG.md) for the routes, tool contracts, safeguards, and
setup boundary.

### Run the API and Streamlit demonstration

The API loads the local catalogue and retrieval indexes, uses PostgreSQL for complete product
records, and enables agent queries only when a real LLM provider is configured. It remains
inspectable through `/health` when one of those components is unavailable. After completing the
earlier setup steps, start the backend and UI in separate terminals:

```powershell
.venv\Scripts\python.exe -m uvicorn searchrank_ai.api:app --reload
```

```powershell
$env:SEARCHRANK_API_URL = "http://127.0.0.1:8000"
.venv\Scripts\python.exe -m streamlit run src\searchrank_ai\streamlit_app.py
```

Open `http://127.0.0.1:8000/docs` for the four-endpoint OpenAPI interface. The Streamlit URL is
printed by Streamlit when it starts. API startup defaults to cached model files only; set
`SEARCHRANK_EMBEDDING_LOCAL_ONLY=0` only for an intentional first-time model download. See the
[Phase 6 API and UI guide](docs/API_AND_UI.md) for request contracts, readiness behavior, and
limitations.

## Repository structure

```text
SearchRank-AI/
├── src/searchrank_ai/
│   ├── config.py              # validated environment configuration
│   ├── logging_config.py      # shared logging setup
│   ├── mobile_catalogue.py    # adopted audit and cleaning pipeline
│   ├── bm25.py                # deterministic keyword index, search, and evaluation
│   ├── semantic.py            # search text, encoder adapter, and local vector index
│   ├── retrieval.py           # semantic/hybrid ranking, filters, and comparison evaluation
│   ├── storage.py             # PostgreSQL schema, ingestion, details, and pgvector search
│   ├── agent_models.py        # typed workflow, claim, citation, and outcome contracts
│   ├── agent_tools.py         # search, details, and deterministic verification tools
│   ├── evidence_policy.py     # fixed field labels and comparison field/direction rules
│   ├── llm.py                 # configurable mock and optional OpenAI providers
│   ├── workflow.py            # bounded LangGraph routes and response rendering
│   ├── api_models.py          # validated public request and response contracts
│   ├── services.py            # component-aware runtime assembly
│   ├── api.py                 # four FastAPI endpoints and error mapping
│   ├── api_client.py          # transport-only JSON client for the UI
│   ├── streamlit_app.py       # one-page search and comparison demonstration
│   ├── data_audit.py          # retained historical laptop audit
│   └── phone_audit.py         # retained rejected Amazon-phone audit
├── tests/                     # synthetic unit and reproducibility tests
├── evaluation/                # reviewed retrieval queries and relevance judgments
├── docs/                      # architecture, decisions, audits, and evaluation notes
├── data/                      # local raw/processed data; ignored by Git
├── artifacts/                 # local audit/index outputs; ignored by Git
├── .env.example
├── AGENTS.md
└── pyproject.toml
```

The rejected audit modules and reports remain in the repository because they document how the
dataset decision changed when full-file evidence contradicted the initial preview. That history is
part of the engineering work, not active laptop scope.

## Roadmap

| Phase | Deliverable | Status |
|---:|---|---|
| 0 | Repository and project foundation | Complete |
| 1 | Dataset selection, audit, schema, and cleaning | Complete |
| 2 | BM25 keyword retrieval baseline | Complete |
| 3 | Semantic retrieval, hybrid ranking, and strict constraints | Complete |
| 4 | PostgreSQL and pgvector persistence | Complete and merged |
| 5 | Agentic RAG workflow and evidence tools | Complete and merged |
| 6 | FastAPI backend and Streamlit demonstration | Complete locally |
| 7 | Evaluation, hardening, and Docker Compose | Not started |
| 8 | Final documentation and portfolio release | Not started |

Each phase is developed, tested, documented, reviewed, and merged separately. This keeps the Git
history believable and prevents later components from hiding weaknesses in the foundations.

## Engineering principles

- Treat catalogue text as untrusted input.
- Keep product IDs traceable from source data to final citations.
- Enforce strict numerical constraints with deterministic code.
- Never invent missing specifications, URLs, or evaluation results.
- Evaluate BM25, semantic, and hybrid retrieval separately before selecting a configuration.
- Keep automated tests independent of paid APIs.
- Document rejected approaches and failure cases alongside successful results.

## Current limitations

- The catalogue is a historical snapshot, not live price or inventory data.
- The source has no rating-count field, so rating confidence cannot be weighted by review volume.
- Some processor, rating, display, release-date, charging, and image values remain unavailable.
- Product variants remain separate when the source provides distinct names and URLs.
- Some release and specification claims have not been verified against manufacturers.
- PostgreSQL is not bundled and Docker is intentionally deferred to Phase 7. The live pgvector
  integration test therefore requires an explicitly configured disposable test database.
- Kaggle lists the dataset as CC0, while the publisher also states learning/non-commercial use.
  For caution, raw data, processed data, and generated audit artifacts are not committed.
- The 20-case retrieval benchmark is still too small for broad search-quality claims. Phase 5
  validates workflow behavior with mocks; broad real-model agent evaluation remains Phase 7 work.
- The API and Streamlit page are a local demonstration without authentication, rate limiting,
  connection pooling, deployment TLS, or measured concurrency and latency.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Adopted catalogue audit](docs/MOBILE_CATALOGUE_AUDIT.md)
- [BM25 retrieval baseline](docs/BM25_RETRIEVAL.md)
- [Semantic and hybrid retrieval](docs/HYBRID_RETRIEVAL.md)
- [PostgreSQL and pgvector storage](docs/STORAGE.md)
- [Agentic RAG workflow and evidence tools](docs/AGENTIC_RAG.md)
- [FastAPI backend and Streamlit demonstration](docs/API_AND_UI.md)
- [Decision log](docs/DECISIONS.md)
- [Build log](docs/BUILD_LOG.md)
- [Evaluation record](docs/EVALUATION.md)
- [Dataset screening history](docs/DATASET_CANDIDATES.md)

SearchRank-AI is intentionally being built as a system I can explain end to end: where the data
came from, why records were retained or rejected, how retrieval will be evaluated, which decisions
belong to deterministic code, and what evidence supports every generated answer.
