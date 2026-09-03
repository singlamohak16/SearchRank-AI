# SearchRank-AI

SearchRank-AI is a portfolio project for evidence-grounded smartphone search and comparison. Its
target architecture uses agentic retrieval-augmented generation (RAG), but the project is being
built and evaluated incrementally so every result remains explainable and reproducible.

## Current status

**Phases 0 and 1 are complete.** The approved 91mobiles source audit retains 3,062 of 4,000 rows
as price- and capacity-filter-ready smartphones. The reproducible catalogue has stable IDs, INR
prices, explicit RAM/storage, normalized user-rating scales, comparison specifications, dates, and
source URLs. Missing values remain empty and five optional source attributes are excluded.

See [the adopted catalogue audit](docs/MOBILE_CATALOGUE_AUDIT.md) for the measured findings,
core-only schema, reproduction command, and limitations. The rejected
[Amazon phone audit](docs/PHONE_DATASET_AUDIT.md), earlier [laptop audit](docs/DATASET_AUDIT.md),
and [screening notes](docs/DATASET_CANDIDATES.md) remain as decision history. Raw data, processed
catalogues, and generated audit files stay local and ignored by Git.

No retrieval system, database, agent workflow, API, user interface, or search-quality result exists
yet. Phase 2 will begin only after explicit approval.

## Target capabilities

When complete, the focused application will:

1. Understand natural-language smartphone-shopping requests.
2. Extract explicit price, RAM, brand, rating, and storage constraints.
3. Compare BM25 keyword, semantic, and hybrid retrieval.
4. Apply strict constraints in deterministic Python code.
5. Retrieve full records for shortlisted products.
6. Generate comparisons using only stored product evidence.
7. Verify factual claims and product-ID citations.
8. State when the catalogue does not contain enough evidence.

The project will not train models, scrape live stores, purchase products, or implement user
profiling. See [the architecture notes](docs/ARCHITECTURE.md) for the planned system boundary.

## Foundation setup

Python 3.11 or newer is required. From PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the current checks:

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Rebuild the adopted local catalogue after placing the approved archive at the documented ignored
raw-data path:

```powershell
python -X utf8 -m searchrank_ai.mobile_catalogue `
  --archive data\raw\suresh_91mobiles_2008_2026\source.zip `
  --audit-dir artifacts\suresh_91mobiles_audit\new-run `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue-new.csv
```

Environment variables are documented in `.env.example`. Copy it to `.env` only for local use;
`.env` is ignored by Git. The foundation reads process environment variables directly and does
not require secrets for its tests.

## Planned repository layout

```text
src/searchrank_ai/   Application code
tests/               Automated tests and permitted synthetic fixtures
docs/                Build, design, architecture, and evaluation records
data/                Local raw and processed data (ignored by default)
artifacts/           Generated audits, indexes, and embeddings (ignored)
```

## Development principles

- Keep product IDs traceable from source data to final citations.
- Use deterministic code for constraints, scores, and verifiable claims.
- Never invent missing product specifications or evaluation results.
- Treat catalogue descriptions as untrusted data.
- Keep unit tests independent of paid APIs.
- Record limitations and failed cases alongside measured results.

## Roadmap

The work is divided into nine gated phases: foundation, data, BM25 retrieval, semantic/hybrid
retrieval, PostgreSQL/pgvector storage, the LangGraph workflow, API/UI, evaluation/Docker, and
final documentation/release. A later phase begins only after explicit approval.
