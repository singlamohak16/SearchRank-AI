# Decision Log

Important decisions are recorded when they are made. Dataset, retrieval, storage, LLM, and
evaluation choices remain deliberately open until their relevant phases.

## D-001 — Use a `src`-based package layout

- **Date:** 2026-09-02
- **Status:** Accepted
- **Decision:** Application code lives under `src/searchrank_ai`; tests live separately.
- **Reason:** This prevents accidental imports from the repository root and makes packaging and
  test behavior closer to an installed application.
- **Alternative:** A flat script layout is initially simpler, but becomes fragile as the API,
  retrieval, storage, and workflow modules grow.

## D-002 — Support Python 3.11 and newer

- **Date:** 2026-09-02
- **Status:** Accepted
- **Decision:** Declare Python 3.11 as the minimum while developing locally on Python 3.12.
- **Reason:** Python 3.11 provides modern typing and data-class features while retaining broader
  dependency compatibility than requiring only the local interpreter version.

## D-003 — Start configuration and logging with the standard library

- **Date:** 2026-09-02
- **Status:** Accepted
- **Decision:** Read namespaced environment variables into a validated immutable data class and
  use Python logging with a shared format.
- **Reason:** Phase 0 settings are small, and this avoids a framework before it provides value.
  The API phase can revisit this choice if settings become substantially more complex.
- **Security note:** The API-key field is excluded from the configuration representation, and
  configuration values are not logged.

## D-004 — Keep generated and sensitive artifacts out of Git

- **Date:** 2026-09-02
- **Status:** Accepted
- **Decision:** Ignore environment files, raw/processed data, embeddings, indexes, local database
  files, service volumes, caches, logs, and build output.
- **Reason:** This reduces secret leakage, accidental data redistribution, and repository bloat.
  A small permitted test fixture may be added explicitly during the data phase.

## D-005 — Use pytest and Ruff as development tools

- **Date:** 2026-09-02
- **Status:** Accepted
- **Decision:** Declare pytest for tests and Ruff for linting/import sorting/format checking.
- **Reason:** Both are common, lightweight tools with small configurations. Runtime dependencies
  remain empty in Phase 0.

