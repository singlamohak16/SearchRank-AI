# Phase 6 — FastAPI backend and Streamlit demonstration

## Scope

Phase 6 exposes the existing search, storage, and bounded agent workflow through four HTTP
endpoints and one local Streamlit page. It does not change ranking, strict constraints, workflow
routing, evidence verification, or stored product data.

## HTTP contract

| Method and path | Purpose | Required backing component |
|---|---|---|
| `GET /health` | Report readiness for search, query, and product lookup | None |
| `POST /search` | Run BM25, semantic, or hybrid retrieval with strict filters | Local catalogue and indexes |
| `POST /query` | Run the bounded Phase 5 workflow | Search, PostgreSQL, and a real LLM provider |
| `GET /products/{product_id}` | Return one complete stored product record | PostgreSQL |

FastAPI also exposes generated OpenAPI documentation at `/docs` and `/openapi.json`.

`POST /search` accepts a query, retrieval mode, result limit, hybrid alpha, and the five supported
strict constraint groups: maximum price, minimum RAM, minimum storage, minimum rating, and
included/excluded brands. The default hybrid alpha is the measured Phase 3 value, `0.25`. The API
passes validated constraints to the existing retriever instead of reproducing filter logic.

`POST /query` returns the verified response plus the extracted constraints, retrieved and missing
product IDs, tool history, retry count, workflow path, and a verification summary. This keeps the
demonstration inspectable without returning the complete internal graph state.

All request models reject unknown fields. Blank text, invalid ranges, conflicting brand filters,
unknown product IDs, and unavailable components use a stable JSON error envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": []
  }
}
```

Expected validation failures return `422`, unknown product IDs return `404`, and endpoints whose
local dependencies are not ready return `503`.

## Component-aware startup

The API loads components once during its lifespan. Search requires the Phase 1 catalogue, Phase 2
BM25 index, Phase 3 semantic index, and the pinned embedding model. Product details require the
Phase 4 PostgreSQL database. Agent queries require both plus a configured real provider.

`GET /health` remains available when one or more components cannot start. Its status is `ok` only
when all three endpoint components are ready; otherwise it reports `degraded`, boolean component
states, and safe setup messages. A failure in PostgreSQL therefore does not hide a working local
search endpoint.

Phase 7 review hardening adds a fresh, read-only PostgreSQL probe to each health request, executed
off the async event loop. It checks the schema version, ingestion metadata, nonzero row count,
catalogue hash alignment with loaded retrieval, and a decoded product record. Missing tables,
incomplete ingestion, mismatches, and driver failures report products (and dependent queries) as
unready. Probe errors are sanitized and snapshots do not retain stale failures after recovery.
This does not reconnect a broken connection or ingest data; a dead connection may require an API
restart. Injected test services may provide their own readiness callback.

API startup is offline-first. `SEARCHRANK_EMBEDDING_LOCAL_ONLY=1` prevents surprise network access
and uses the model cached while building the Phase 3 semantic index. Set it to `0` only when an
explicit first-time download is intended.

The default `mock` provider is deliberately not exposed as an interactive query service because it
contains no scripted responses outside tests. Configure the optional real provider to enable
`POST /query`; normal automated tests continue to use injected fakes and make no paid calls.

## Run locally

Generate the catalogue and indexes and load PostgreSQL as documented in the README. Copy the
placeholder variables from `.env.example` into the current shell or a local ignored `.env` loader.
Then start the processes in separate terminals from the repository root:

```powershell
.venv\Scripts\python.exe -m uvicorn searchrank_ai.api:app --reload
```

```powershell
$env:SEARCHRANK_API_URL = "http://127.0.0.1:8000"
.venv\Scripts\python.exe -m streamlit run src\searchrank_ai\streamlit_app.py
```

The Streamlit page checks API health, provides a direct catalogue-search form with the supported
filters, and provides a natural-language search/comparison form. It displays the API's extracted
constraints, ranked results, grounded Markdown response, source links, retrieved IDs, workflow
path, tool calls, and verification summary.

## Boundary and limitations

- Streamlit calls FastAPI over HTTP through `api_client.py`; it does not import the retriever,
  database adapter, LangGraph workflow, or evidence rules.
- Blocking model/database/workflow calls run in FastAPI's thread pool so they do not block the
  event loop. This is a local demonstration, not a throughput claim.
- One shared PostgreSQL connection is sufficient for this demonstration. Connection pooling,
  authentication, rate limiting, CORS policy, deployment TLS, and production monitoring are not
  implemented.
- Product and model text remains untrusted. Untrusted product names are escaped before controlled
  Markdown rendering, Streamlit does not enable unsafe HTML, and the API still releases workflow
  answers only after Phase 5 deterministic verification.
- No API latency or user-experience metric is claimed in Phase 6; those measurements belong to the
  controlled Phase 7 evaluation.
