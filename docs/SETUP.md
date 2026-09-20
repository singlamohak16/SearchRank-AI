# Local setup and troubleshooting

These commands target **PowerShell on Windows**, from the repository root. Python 3.11+ is declared;
the recorded development runs used Python 3.12. Docker Desktop must be running Linux containers.
Allow disk space and time for Python/PyTorch, model, and Docker image downloads. No paid API is
required for search or stored-specification comparisons.

## 1. Clone and install

```powershell
git clone https://github.com/singlamohak16/SearchRank-AI.git
Set-Location SearchRank-AI
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
```

Using the explicit virtual-environment executable avoids PowerShell activation-policy changes.
Choose another installed compatible Python minor version if 3.12 is unavailable. A GPU is not needed.
Dependency ranges and Docker image tags are not a complete version lock; a later installation may
resolve different compatible versions.

## 2. Obtain the dataset separately

Download the ZIP from the [publisher's Kaggle page](https://www.kaggle.com/datasets/suresh2837/mobile-phones-specs-and-prices-dataset-20082026)
after reviewing its usage conditions. Kaggle may require sign-in. Keep the original archive unchanged
at `data/raw/suresh_91mobiles_2008_2026/source.zip`; create those local folders if needed.

The benchmark snapshot downloaded on 2026-09-04 has archive SHA-256:

```text
98604a14020c9e7e45bcf0b578540d7a20f8dad4be8ad31686a05720b438c297
```

```powershell
Get-FileHash data/raw/suresh_91mobiles_2008_2026/source.zip -Algorithm SHA256
```

If the publisher has replaced the snapshot, do not claim the recorded results apply. Obtain the
matching version if available, or perform a newly approved audit and rebuild/relabel the evaluation
for the new catalogue. Reproduction requires separately obtained source data. The
[audit](MOBILE_CATALOGUE_AUDIT.md) explains the conflicting publisher usage notes.

## 3. Audit and build artifacts

Run once for a fresh workspace:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m searchrank_ai.mobile_catalogue `
  --archive data/raw/suresh_91mobiles_2008_2026/source.zip `
  --audit-dir artifacts/audit/initial `
  --catalogue data/processed/suresh_91mobiles_2008_2026/catalogue.csv

.\.venv\Scripts\python.exe -X utf8 -m searchrank_ai.bm25 build `
  --catalogue data/processed/suresh_91mobiles_2008_2026/catalogue.csv `
  --output artifacts/bm25/phase2-index.json

.\.venv\Scripts\python.exe -X utf8 -m searchrank_ai.retrieval build-semantic `
  --catalogue data/processed/suresh_91mobiles_2008_2026/catalogue.csv `
  --output artifacts/semantic/phase3-index.npz --device cpu
```

The original snapshot should retain 3,062 products with catalogue SHA-256
`c3428dd04e5d02c6a66ce00f5961f6b1f6ba9dcc30d86a37ffde84523619c7ea`.
The encoder is `sentence-transformers/all-MiniLM-L6-v2`, pinned to revision
`c21050a7ef692090620a6d037dd736908f9c7cf6`, with 384 dimensions. The first build downloads
the model. Later cached builds/evaluations can use `--local-files-only`.

Writers refuse to overwrite artifacts. For an intentional rebuild, preserve existing files and
choose fresh output paths, then update application paths consistently. Never mix indexes from
different catalogue versions. Raw data, generated indexes, and reports remain ignored by Git.

## 4. Start the local demonstration

For a **new default/mock setup**, ensure no inherited real-provider settings or credential-bearing
`.env` file are being used. In a fresh PowerShell session:

```powershell
$env:SEARCHRANK_LLM_PROVIDER = 'mock'
$env:SEARCHRANK_LLM_MODEL = ''
$env:SEARCHRANK_LLM_API_KEY = ''
$env:GEMINI_API_KEY = ''
$env:SEARCHRANK_GEMINI_FREE_TIER_CONFIRMED = '0'
docker compose config --quiet
docker compose up -d database
docker compose --profile setup run --rm --build ingest
docker compose up --build -d api ui
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
```

Ingestion synchronizes the complete catalogue, including removing obsolete records, inside a
transaction. Use it for initial setup or an intentional refresh—not as a routine restart step.
It must report the expected count/hash. PostgreSQL uses the internal hostname `database`; it is
deliberately not published on the host's port 5432.

Open [Streamlit](http://127.0.0.1:8501/) and [FastAPI docs](http://127.0.0.1:8000/docs).
Without a real provider, expect `search=true`, `products=true`, `query=false`, and overall
`status=degraded`. Search and stored-fact comparison work; Ask AI is unavailable by design.
Compose readiness requires search and products, not query. A cold container has its own model cache
and may need another model download even if the host cache is populated.

For an unchanged existing stack, `docker compose start database api ui` starts existing containers
without replacing their configured environment. Check readiness afterward. Avoid the mock setup
commands above if you intend to preserve a working Gemini configuration. `docker compose stop`
stops services without deleting data. Do not add `-v` to a teardown command unless you intentionally
want to delete named database/model-cache volumes.

## 5. Optional AI queries

Use the [Gemini guide](GEMINI_SETUP.md) only after confirming your own project has no paid billing
enabled and reviewing current provider terms. Store the key privately, never in this repo.

```powershell
.\scripts\start_gemini.ps1 -FreeTierConfirmed -Build
```

Do not run that helper as a default setup step or as proof that the provider is free. The flag is
your attestation, not a billing check. Do not submit private information. Rate limits and model
availability can change; the app does not silently switch providers. `GET /health` does not send an
LLM request or validate remote quotas. Python does not automatically load `.env`; Compose can.

## 6. Test and evaluate

In a fresh test shell, leave live-provider opt-ins and service URLs unset. Explicitly disable
provider integration if that shell inherited opt-ins:

```powershell
$env:SEARCHRANK_RUN_GEMINI_INTEGRATION = '0'
$env:SEARCHRANK_RUN_GEMINI_APP_INTEGRATION = '0'
$env:SEARCHRANK_RUN_LLM_INTEGRATION = '0'
$env:SEARCHRANK_TEST_DATABASE_URL = ''
$env:SEARCHRANK_TEST_API_URL = ''
$env:SEARCHRANK_TEST_UI_URL = ''
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/check_release.py
```

The ordinary suite uses synthetic fixtures and mocks; it does not need the downloaded catalogue,
PostgreSQL, or an LLM key. Optional service tests report skips. Compose configuration validation may
run if Docker is on PATH; this does not start containers. See [results](RESULTS.md) for real-catalogue
evaluation commands. To check existing API/UI HTTP services without an AI request:

```powershell
$env:SEARCHRANK_TEST_API_URL = 'http://127.0.0.1:8000'
$env:SEARCHRANK_TEST_UI_URL = 'http://127.0.0.1:8501'
.\.venv\Scripts\python.exe -m pytest tests/test_container_integration.py -q
```

Database integration uses a disposable database and temporary schema; see [storage](STORAGE.md).
Never point tests at unrelated production data. Live LLM tests require a separate explicit opt-in.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Website refuses connection | Start Docker Desktop, then existing containers; inspect `docker compose ps`. Wait for API readiness before UI. |
| Docker engine/WSL error | Confirm Linux-container mode and normal startup. Do not delete volumes or Docker state as a first step. |
| `search=false` | Check all three configured files exist and share catalogue/model identity. Verify the model cache/download. |
| `products=false` | Check database health and ingestion of the same catalogue. A broken connection may require an API restart. |
| Only `query=false` | Expected with mock; otherwise verify provider configuration privately. Ordinary search remains available. |
| Provider 429/503 | Wait/check quota or configuration; use ordinary search. Do not enable billing or bypass quotas as a workaround. |
| Existing-output error | Preserve the prior artifact; use a fresh output name and deliberate path update. |
| No results | Loosen explicit constraints; missing values cannot satisfy strict filters. |
| Images missing | External hosts/images may be unavailable; stored textual facts remain usable. |
| Port occupied | Identify its owner before stopping anything; keep changed API/UI ports consistent. |
| Pytest temp-directory permission error | Use `--basetemp` with a new, dedicated temporary folder, never one containing user files. |

Redact secrets before sharing logs. Never post full Docker inspection, resolved Compose
configuration, environment dumps, or real database URLs. This guide consolidates the existing
Windows/container setup; Phase 8 does not claim a new clean-machine installation test.
