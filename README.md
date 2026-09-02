# SearchRank-AI

SearchRank-AI is a portfolio project for evidence-grounded laptop search and comparison. Its
target architecture uses agentic retrieval-augmented generation (RAG), but the project is being
built and evaluated incrementally so every result remains explainable and reproducible.

## Current status

**Phase 0 — repository and project foundation (complete).** The repository currently contains packaging,
configuration, logging, documentation, and smoke-test foundations only. It does not yet contain a
dataset, retrieval system, database, agent workflow, API, user interface, or measured search
results.

## Target capabilities

When complete, the focused application will:

1. Understand natural-language laptop-shopping requests.
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

Run the Phase 0 checks:

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
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
artifacts/           Generated indexes and embeddings (ignored)
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
