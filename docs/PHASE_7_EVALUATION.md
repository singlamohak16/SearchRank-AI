# Phase 7 evaluation, hardening, and containers

Phase 7 broadens the evidence for SearchRank-AI without turning small, controlled benchmarks into
production claims. It combines 20 catalogue-grounded retrieval judgments with 16 reviewed
scripted-agent scenarios: 36 scenarios in total.

## Evaluation boundaries

The two sets answer different questions:

- `evaluation/retrieval_v1.json` uses the adopted 3,062-product catalogue and asks whether BM25,
  semantic, and hybrid retrieval rank the recorded relevant product IDs.
- `evaluation/agent_scenarios_v1.json` uses four synthetic product records and scripted mock-LLM
  decisions. It asks whether the real LangGraph, tools, constraints, verifier, and renderer follow
  the expected safe route. It does **not** measure a real model's language understanding.

The agent set covers search, strict constraints, comparison, essential clarification, one bounded
reformulation, unavailable products and attributes, unsupported questions, conflicting brands,
catalogue prompt injection, a fabricated value, and a wrong citation. The expected route, final
status, tool sequence, and retry count are reviewed explicitly in the JSON fixture.

## Reproduce the runs

The generated reports remain ignored under `artifacts/evaluation/` because they depend on local
catalogue and embedding artifacts.

```powershell
.venv\Scripts\python.exe -X utf8 -m searchrank_ai.retrieval evaluate `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue.csv `
  --bm25-index artifacts\bm25\phase2-index.json `
  --semantic-index artifacts\semantic\phase3-index.npz `
  --cases evaluation\retrieval_v1.json `
  --alphas 0.25 0.50 0.75 --limit 10 --device cpu --local-files-only `
  --output artifacts\evaluation\phase7-retrieval.json

.venv\Scripts\python.exe -X utf8 -m searchrank_ai.evaluation agent `
  --cases evaluation\agent_scenarios_v1.json `
  --output artifacts\evaluation\phase7-agent.json

.venv\Scripts\python.exe -X utf8 -m searchrank_ai.evaluation api-latency `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue.csv `
  --bm25-index artifacts\bm25\phase2-index.json `
  --semantic-index artifacts\semantic\phase3-index.npz `
  --cases evaluation\retrieval_v1.json --samples 50 --warmups 5 --device cpu `
  --hardware "describe the measured machine" `
  --output artifacts\evaluation\phase7-api-latency.json
```

The `--local-files-only` flag is deliberate: a cached model must not trigger network metadata
requests during a reproducibility run.
Report writers refuse to overwrite existing files; use a fresh output filename when rerunning.
The final agent measurement is saved locally as `artifacts/evaluation/phase7-agent-v2.json`.

## Retrieval results

The 2026-09-11 rerun reproduced the Phase 3 report exactly at `k = 10`.

| Configuration | Recall@10 | MRR@10 | NDCG@10 | Constraint satisfaction |
|---|---:|---:|---:|---:|
| BM25 | 0.811111 | 0.812500 | 0.808979 | 1.000000 |
| Semantic | 0.937500 | 0.887500 | 0.899768 | 1.000000 |
| Hybrid, alpha 0.25 | 0.925000 | 0.950000 | 0.928558 | 1.000000 |
| Hybrid, alpha 0.50 | 0.859722 | 0.827222 | 0.826990 | 1.000000 |
| Hybrid, alpha 0.75 | 0.815278 | 0.816250 | 0.811935 | 1.000000 |

`alpha = 0.25` remains selected by the documented rule: highest hybrid NDCG@10, then MRR@10,
Recall@10, proximity to 0.5, and lower alpha. Semantic-only still has slightly higher Recall@10,
so this is evidence for the chosen top-rank trade-off, not proof that hybrid retrieval always wins.

## Agent results

The 16-case scripted run on 2026-09-11 produced:

| Metric | Result | Denominator |
|---|---:|---:|
| Scenario accuracy | 1.000000 | 16 scenarios |
| Status accuracy | 1.000000 | 16 scenarios |
| Tool-selection accuracy | 1.000000 | 16 scenarios |
| Route accuracy | 1.000000 | 16 scenarios |
| Constraint-satisfaction rate | 1.000000 | 4 explicitly constrained cases returning products |
| Clarification accuracy | 1.000000 | 2 clarification cases |
| Refusal accuracy | 1.000000 | 2 unsupported cases |
| Conflict-detection accuracy | 1.000000 | 1 conflict case |
| Citation correctness | 1.000000 | 8 expected answered cases |
| Unsupported-claim rate | 0.000000 | 16 scenarios |
| Average tool calls | 2.187500 | 16 scenarios |

These values show deterministic behavior around supplied model decisions. The benchmark scripts the
request analysis and answer draft, so it cannot support a claim about live-LLM accuracy, prompt
robustness across arbitrary attacks, or answer quality in the wild.

## Engineering measurements

Environment recorded on 2026-09-11:

- Lenovo 82XV running Windows 11 Home Single Language, build 26200.
- 13th Gen Intel Core i7-13620H, 10 cores and 16 logical processors.
- 16,890,519,552 bytes of physical memory.
- Python 3.12.14, CPU embedding execution.
- 3,062 catalogue products and the pinned 384-dimensional MiniLM model revision.
- Model files were cached locally; network access was disabled; no LLM was used.

Fresh index runs produced:

| Artifact | Time | Size | Reproducibility check |
|---|---:|---:|---|
| BM25 index | 0.2327 s | 1,145,647 bytes | SHA-256 matched the Phase 2 artifact |
| Semantic index | 56.1828 s | 4,391,982 bytes | SHA-256 matched the Phase 3 artifact |

A warmed `POST /search` run used FastAPI's in-process TestClient, the real hybrid retriever,
`alpha = 0.25`, 20 rotating reviewed queries, five warmups, and 50 measured requests:

| Statistic | Time |
|---|---:|
| Median | 12.9782 ms |
| p95 (nearest rank) | 16.7325 ms |
| Minimum | 10.7063 ms |
| Maximum | 24.2514 ms |

This excludes network sockets, JSON transfer over a real network, PostgreSQL, an LLM call,
concurrency, and cold model loading. It is a local search-endpoint measurement, not deployed API
latency.

## Docker Compose

`compose.yaml` defines:

- PostgreSQL 16 with pgvector and a persistent named volume;
- the FastAPI service with read-only catalogue/artifact mounts and a model-cache volume;
- the Streamlit UI connected to the API by service name; and
- an opt-in `setup` profile for transactional catalogue ingestion.

The image installs the Python package in a two-stage build and runs as an unprivileged `searchrank`
user. Secrets are read from environment variables and are not baked into the image. Local data and
artifacts are excluded from the build context and mounted read-only at runtime.

Run the stack after the Phase 1–3 local artifacts exist:

```powershell
docker compose up -d database
docker compose --profile setup run --rm --build ingest
docker compose up --build -d api ui
docker compose ps
```

Live verification completed on 2026-09-11 after installing Docker Desktop and WSL2 and restarting
Windows. The recorded runtime used Docker Desktop 4.90.0, Docker Engine 29.7.2, Compose 5.5.1,
Python 3.12.14, PostgreSQL 16.15, and CPU-only PyTorch 2.14.0+cpu.

- API, UI, and ingestion images built successfully. The first build exposed conflicting versions
  when installing every downloaded wheel. Resolving `searchrank-ai` with `--no-index --find-links`
  fixed the build while reusing the downloaded packages.
- Database and API containers became healthy; Streamlit started and its health endpoint returned
  `ok`. Published ports bind to `127.0.0.1` only.
- Two ingestion runs each reported 3,062 products, 384 dimensions, catalogue SHA-256
  `c3428dd04e5d02c6a66ce00f5961f6b1f6ba9dcc30d86a37ffde84523619c7ea`, and the same pinned
  MiniLM encoder identifier.
- Live BM25, semantic, and hybrid searches returned Samsung phones within INR 30,000, with at least
  8 GB RAM and 128 GB storage. Each returned product's ID, name, price, and source URL matched the
  database-backed product endpoint.
- Blank searches returned 422 and a missing product returned 404. Default `/query` returned 503
  with the documented message that a real provider must be configured.
- `/health` reported `search=true`, `products=true`, `query=false`, and `status=degraded`, as
  expected for the test-only mock provider. Container readiness checks search and products, so it
  does not confuse a merely reachable HTTP endpoint with usable retrieval/storage.
- Runtime execution used UID/GID 999 (`searchrank`); container dependency consistency passed.

The complete host suite produced **305 passing tests and two expected integration skips** with
Docker configuration and the four live HTTP cases enabled. The host skipped the direct database
integration because PostgreSQL is not published to the host, and the live-LLM opt-in was absent.
A separate disposable Linux container ran **25 passing tests**, including the actual database
integration, evaluation, API, and Streamlit rendering tests. The database test used a unique
temporary schema and removed it afterward.

To reproduce live HTTP checks, set `SEARCHRANK_TEST_API_URL=http://127.0.0.1:8000` and
`SEARCHRANK_TEST_UI_URL=http://127.0.0.1:8501` before running `python -m pytest -q`.
Without those variables, the four HTTP cases are skipped. Docker must be available on `PATH` for
the Compose configuration test.

The Linux regression command used a disposable ingestion container:

```powershell
docker compose --profile setup run --rm `
  -v './tests:/app/tests:ro' `
  -v './evaluation:/app/evaluation:ro' `
  -v './src/searchrank_ai/streamlit_app.py:/app/src/searchrank_ai/streamlit_app.py:ro' `
  -e SEARCHRANK_TEST_DATABASE_URL=postgresql://searchrank:searchrank@database:5432/searchrank `
  ingest sh -c 'python -m pip install --user "pytest>=8,<9" && python -m pytest -q -p no:cacheprovider tests/test_storage_integration.py tests/test_evaluation.py tests/test_streamlit_app.py tests/test_api.py'
```

The Linux run emitted an unregistered integration-marker warning because the repository test
configuration was not mounted, plus a Starlette deprecation warning. The final host run emitted
only the Starlette warning. An earlier host attempt hit permissions on an old pytest temporary
directory (250 passed, two skipped, 55 setup errors); rerunning with a fresh, uniquely named
temporary base directory resolved those setup errors. No application behavior was changed to
bypass a failed assertion.

Ruff lint/format, host/container dependency consistency, Compose configuration, and Git whitespace
checks passed. The named database and model-cache volumes persist across `docker compose down`;
first-time model downloads still require internet access.

## Known limitations and failure cases

- The retrieval judgments remain small and catalogue-specific; family relevance is not independent
  real-world product-quality labeling.
- Agent metrics use scripted model outputs and synthetic products. A real provider may classify or
  extract constraints incorrectly even though downstream enforcement is deterministic.
- Citation correctness means the deterministic verifier accepted all expected valid citations and
  rejected the adversarial mismatch; it is not independent fact checking of the source site.
- The API timing measures warmed, sequential, in-process search only.
- Docker was verified locally with a downloaded model and the default mock provider. Image tags
  and dependency ranges are not a complete version lock; future builds may select newer packages.
- Live LLM interpretation, comparison quality, production deployment, and concurrent load remain
  outside these recorded results.
