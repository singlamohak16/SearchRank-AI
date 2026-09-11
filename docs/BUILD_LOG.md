# Build Log

This log records work when it actually occurs. Planned work belongs in the roadmap, not here.

## 2026-09-02 — Phase 0: repository and project foundation

Status: complete

- Confirmed that the starting workspace was empty and not a Git repository.
- Confirmed Python 3.12.13 and Git 2.53.0 were available.
- Initialized local Git with `main` and created `phase/00-foundation`.
- Added the Python package, configuration, logging, documentation, and test foundations.
- Added ignore rules for secrets, generated data, embeddings, indexes, caches, and local databases.
- Created an isolated `.venv` and installed the declared editable development dependencies.

Validation environment: Windows, Python 3.12.13, pytest 8.4.2, Ruff 0.16.5.

- `python -m pytest`: 3 passed in 0.03 seconds.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: 10 files already formatted.
- `python -m pip check`: no broken requirements.
- Installed-package import smoke check: passed.
- Ignore-rule check: `.env` and generated artifact paths are ignored; `.env.example` is trackable.
- Common secret-pattern scan: no matches.

## 2026-09-03 — Phase 1: approved Amazon India suitability audit

Status: audit complete; Phase 1 still in progress.

- Started from the clean Phase 0 `main` checkout and created `phase/01-data-pipeline`.
- Downloaded the user-approved Amazon India archive from Kaggle: 114,888,404 bytes. Kept it
  unchanged under ignored raw data; no retailer scraping or image downloads.
- Added streaming inventory, conservative Hindi/English title coverage probes, review flags,
  source-ID/URL validation, explicit zero-sentinel handling, and deterministic review samples.
- Inspected title samples and low-price/storage cases. Found category contamination, source
  errors, mixed-language text, missing ratings, bundles, and renewed products.
- Added synthetic regression tests and a detailed source/licence/suitability report.
- Final audit rules found 7,023 category rows, 4,702 tentative candidates without current anomaly
  flags, and 2,458 rated candidates. These are not production-cleaning or extraction-accuracy results.
- Kept adoption and remaining Phase 1 implementation pending the mixed-language dataset choice.

Validation environment: Windows 11 build 26200, Python 3.12.13, pytest 8.4.2, Ruff 0.16.5.

- `python -m pytest -q`: 56 passed in 0.22 seconds on the final check.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed.
- `python -m pip check`: no broken requirements.
- Two full-source runs matched on all non-run-metadata report fields and produced byte-identical
  review, category, and sample files. Count reconciliations passed.
- Archive hash matched before/after; raw and generated report paths are ignored.

No commit, push, pull request, schema adoption, production catalogue, or later-phase work was done.

### Later on 2026-09-03 — Amazon rejected; replacement screening

- Recorded the user's rejection of Amazon India without deleting the raw archive or audit work.
- Checked publisher pages and public previews for replacements, including Flipkart, Vibish's
  India source, Abhinav's specifications, eBay, and smaller gaming/review collections.
- Verified the Flipkart preview's separate RAM/storage fields and numeric rating profile.
- Found a concrete title/engineered-field contradiction in the larger India alternative and
  verified that its cleaned schema lacks customer ratings.
- Added a cited screening note and updated selection status. No new dataset was downloaded.
- Kept the original size/scope requirements unchanged; a smaller historical candidate needs approval.

Documentation-only update: no production code or tests changed, and no new test run is claimed.

### Later on 2026-09-03 — Smartphone alternative screening

- Researched smartphones as a possible catalogue domain without changing the approved scope.
- Compared recent and established public dataset cards, schemas, profiles, and sample records.
- Identified a 3,529-row Amazon India source with 2,805 unique ASINs, evidence-rich English titles,
  INR prices, ratings/review counts, and source URLs as the strongest candidate for a full audit.
- Recorded its unresolved duplicate, title-extraction, missing-rating, low-price, and category-purity
  risks rather than treating publisher cleaning claims as verified.
- Rejected a 33,000-row alternative for public-sample consistency failures, including impossible RAM
  values for keypad phones and review counts that exceed rating counts.

Documentation-only update: no dataset was downloaded, no scope was changed, no production code or
tests changed, and no new test run is claimed.

### Later on 2026-09-03 — Approved smartphone scope and full-source audit

- Applied the user's explicit smartphone scope approval to AGENTS.md, README, package metadata,
  architecture, and decision records. Kept the earlier laptop work intact as history.
- Downloaded the specifically approved Amazon phone ZIP (331,607 bytes) and recorded its SHA-256.
- Added offline `phone_audit.py` and `phone_titles.py` with synthetic regression tests. Preserved
  every source field and row; separated explicit capacity evidence from unlabelled-pair hypotheses.
- Audited all 3,529 records. Found 2,805 distinct mixed-product ASINs, 705 repeated-ID groups,
  724 excess rows, 77 missing ratings, and 19 missing prices. Repeated groups differ only in URLs.
- Safely decoded 54 stored sponsored destinations without network requests; all source IDs match.
- Found 2,711 accessory/bundle review rows and 450 distinct heuristic smartphone candidates.
  Only 260 distinct explicit-core candidates remain (251 rated), or 360 including inferred pairs
  (350 rated). No record was adopted, repaired, or deleted.
- Inspected fixed-seed category/core samples and low-price, URL, and capacity-conflict examples.
- Documented the failed suitability verdict and corrected the earlier preview-based recommendation.

Validation: Windows 11 build 26200, Python 3.12.13. `pytest -q`: 110 passed in 0.41 seconds. Ruff
lint and format checks passed (18 files); dependency consistency passed. Two final-rule full-source
runs matched outside run metadata and produced byte-identical records/samples/duplicate artifacts.
Count reconciliations and unchanged archive hash passed; raw/output paths remain Git-ignored.

Phase 1 is still incomplete. No production catalogue/schema, commit, push, or later phase was done.

## 2026-09-04 — Phase 1: adopted 91mobiles catalogue and cleaning pipeline

Status: complete locally; commit and push not authorized.

- Screened and then downloaded the user-approved Suresh Khadka dataset from Kaggle. Preserved the
  210,165-byte ZIP unchanged under ignored raw data with SHA-256
  `98604a14020c9e7e45bcf0b578540d7a20f8dad4be8ad31686a05720b438c297`.
- Audited all 4,000 rows and 17 source columns. Found 4,000 unique names, URLs, and derived URL-slug
  product IDs, with no exact duplicate rows or duplicate product IDs.
- Added deterministic source URL, INR price, rating-scale, RAM/storage, battery, display, release,
  and brand handling. Every original field and row remains in ignored JSONL audit evidence.
- Applied the documented eligibility rule without guessing or price-only deletion. Retained 3,062
  smartphones; excluded rows have explicit, possibly overlapping reasons for missing price,
  missing capacity, feature-phone capacity, or announced status.
- Generated an 18-field core catalogue. Per user direction, excluded specification score, AnTuTu
  score, awards, expert rating, and store from the final CSV.
- Inspected fixed-seed accepted/rejected samples plus price, capacity, display, brand, camera, and
  release extremes. Recorded source, licence tension, exact missingness, schema, and limitations.

Validation environment: Windows 11 build 26200, Python 3.12.13.

- `python -m pytest -q`: 142 passed in 0.50 seconds on the final check.
- Ruff lint and format checks passed for 22 files; dependency consistency passed.
- Two full-source runs matched on every report field outside run metadata and produced
  byte-identical catalogues, JSONL records, and fixed-seed samples.
- The final catalogue has SHA-256
  `c3428dd04e5d02c6a66ce00f5961f6b1f6ba9dcc30d86a37ffde84523619c7ea`.
- Raw, processed, and generated artifact paths are ignored; no real dataset row was added to Git.

Phase 1 implementation and documentation are complete. No commit, push, retrieval code, or later
phase work was performed.

## 2026-09-04 — Phase 2: BM25 keyword retrieval baseline

Status: complete locally; commit and push not authorized.

- Created the required `phase/02-bm25-retrieval` branch from the clean Phase 2 starting point.
- Added exact Phase 1 catalogue-schema validation and deterministic Unicode tokenization.
- Added inspectable BM25 scoring with fixed field weights, stable product-ID tie-breaking, and
  traceable product names/source URLs in every result.
- Added a versioned JSON index carrying the input catalogue hash, parameters, weights, lengths, and
  term frequencies. Build/evaluation output refuses overwrite and remains ignored.
- Added a command-line build, search, and binary-relevance evaluation workflow.
- Added a catalogue-hash-pinned, manually reviewed 12-query exact-model benchmark across 12 brands.
- Documented that this phase does not implement semantic meaning, query correction, hybrid ranking,
  strict filters, storage, an LLM, or a user-facing request path.

Measured local checkpoint: 3,062 documents; index size 1,145,647 bytes; Recall@10, MRR@10, and
NDCG@10 each 1.000 on the narrow 12-query navigational set. One index build/save took 0.4963
seconds. A warm in-memory loop of 1,200 searches averaged 0.332732 ms/search. Environment: Windows
build 26200, Python 3.12.14, Intel64 Family 6 Model 186, 16 logical processors. No embedding model,
LLM, network call, or result cache was used.

Validation environment: Windows build 26200, Python 3.12.14.

- `python -m pytest -q`: 157 passed on the final check.
- Ruff lint and format checks passed for 25 files.
- Dependency consistency and diff whitespace checks passed.
- Two independent full index builds were byte-identical.
- Two benchmark reports from independently loaded indexes were byte-identical.

Phase 2 implementation and documentation are complete. No commit, push, or Phase 3 work was
performed.

## 2026-09-04 — Phase 2 collaborative branch review

Status: complete locally; review changes are not committed or pushed.

- Fetched the shared `SearchRank-AI-Team/SearchRank-AI` repository and reviewed the three Phase 2
  commits already present on `phase/02-bm25-retrieval` against the latest `origin/main`.
- Preserved the collaborator's BM25 design and documentation; no semantic, hybrid, constraint, or
  Phase 3 behavior was added.
- Re-ran the real 3,062-document benchmark and reproduced Recall@10, MRR@10, and NDCG@10 of 1.000
  on its deliberately narrow 12-query exact-model judgment set.
- Added direct synthetic coverage for exact brand, processor, display, charging, and camera keyword
  queries, including traceable source URLs and positive scores.

Validation on the reviewed branch:

- `python -m pytest -q`: 162 passed.
- Ruff lint and format checks passed for 25 files.
- Dependency consistency and diff whitespace checks passed.

Phase 2 is complete locally. The existing remote Phase 2 branch was not changed by this review, no
merge was performed, and Phase 3 was not started.

## 2026-09-05 — Phase 3: semantic, hybrid, and constrained retrieval

Status: complete locally; commit and push not authorized.

- Fetched the shared repository, confirmed Phase 2 was merged through PR #3, and created
  `phase/03-hybrid-retrieval` from the latest `origin/main`.
- Added labelled search-text construction and a small Sentence Transformers adapter using a pinned
  `all-MiniLM-L6-v2` revision. Generated 3,062 normalized 384-dimensional embeddings locally.
- Added a versioned, no-pickle NPZ artifact with catalogue hash, encoder identity, product IDs, and
  aligned vectors. Two complete builds were byte-identical.
- Added independently selectable BM25, semantic, and hybrid search with inspectable raw and
  normalized score components and stable product-ID tie-breaking.
- Added deterministic filters for maximum price, minimum RAM/storage/rating, and included/excluded
  brands. Missing ratings fail rating requirements; conflicting brand rules are rejected.
- Expanded the reviewed evaluation to 20 cases and compared hybrid alpha values 0.25, 0.50, and
  0.75. Selected 0.25 by the documented metric rule.
- Added synthetic tests with an injected fake encoder, keeping normal tests offline and independent
  of the production model.

Measured environment: Windows 11 build 26200, Python 3.12.14, Intel64 Family 6 Model 186,
Sentence Transformers 5.7.0, PyTorch 2.14.0, and NumPy 2.5.2. One recorded CPU run took 11.2110
seconds to load the cached model, 63.4999 seconds to encode the catalogue, and 0.2954 seconds to
save the 4,391,982-byte index. Total: 75.0062 seconds. No LLM or API key was used.

Measured retrieval results are recorded in `docs/EVALUATION.md` and `docs/HYBRID_RETRIEVAL.md`.
The selected alpha 0.25 produced Recall@10 0.925000, MRR@10 0.950000, NDCG@10 0.928558, and
constraint satisfaction 1.000000 on the 20-case set.

Phase 3 is complete locally. No commit, push, pull request, merge, database, agent, API, UI, or
Phase 4 work was performed.

## 2026-09-06 — Phase 4: PostgreSQL and pgvector persistence

Status: implementation complete locally; commit and push not authorized.

- Fast-forwarded local `main` to the merged Phase 3 pull request and created `phase/04-storage`.
- Added a complete typed storage record matching the 18-field approved catalogue schema.
- Added validation that rejects a mismatched catalogue checksum, product order, duplicate IDs,
  invalid values, non-finite embeddings, and incomplete model metadata before database writes.
- Added an isolated PostgreSQL schema with typed constraints, fixed-dimension pgvector embeddings,
  and catalogue metadata for provenance and reproducibility.
- Added transactional, advisory-locked full synchronization with parameterized upserts and stale-ID
  deletion. Product IDs and missing values are preserved.
- Added ordered complete product-detail lookup with explicit missing IDs and pgvector cosine search
  with deterministic product-ID tie-breaking.
- Added a command-line ingestion/details path using environment-only credentials.
- Added deterministic storage tests and an optional live PostgreSQL integration test using a unique
  disposable schema. No PostgreSQL, Docker, LLM, API, UI, or agent workflow was introduced.

Real local artifact validation loaded 3,062 products and aligned all 384 dimensions against
catalogue SHA-256 `c3428dd04e5d02c6a66ce00f5961f6b1f6ba9dcc30d86a37ffde84523619c7ea`
and the pinned MiniLM encoder identity. The live integration test was skipped because this machine
has no PostgreSQL service and `SEARCHRANK_TEST_DATABASE_URL` was not set; no database result is
claimed.

Validation:

- `python -m pytest -q`: 191 passed, one live-database integration test skipped.
- Ruff lint and format checks passed for 33 files.
- Dependency consistency and diff whitespace checks passed.

## 2026-09-07 — Phase 4 pull-request review fix

Status: fixed and committed locally; push not authorized.

- Reviewed PR #5 and found that pgvector type registration could open an implicit Psycopg
  transaction before ingestion. The explicit ingestion transaction would then be only a savepoint,
  allowing connection close to discard successful-looking writes.
- Opened Psycopg connections in autocommit mode while retaining explicit atomic transaction blocks
  for schema creation and catalogue ingestion.
- Added a regression test that verifies the production connection is created with autocommit
  enabled and updated the architecture/storage documentation.

Validation:

- `python -m pytest -q`: 191 passed, one live-database integration test skipped.
- Ruff lint and format checks passed for 33 files.
- Dependency consistency and diff whitespace checks passed.

## 2026-09-08 — Phase 5: bounded agentic RAG workflow

Status: implementation complete locally; commit and push not authorized.

- Fast-forwarded local `main` after Phase 4 pull request #5 was merged and created
  `phase/05-agentic-rag`.
- Added one explicit LangGraph workflow with search, comparison, clarification, conflict,
  unsupported, one-reformulation, no-result, and verification routes.
- Added catalogue-search, product-details, and evidence-verification tools around the existing
  retrieval and storage boundaries.
- Added a configurable LLM provider interface, a scripted offline mock, and an optional OpenAI
  Responses API adapter with strict structured output and response storage disabled.
- Kept strict constraints, tool-call limits, evidence matching, citation checks, comparison winner
  validation, and final answer rendering deterministic.
- Added adversarial coverage proving that instructions embedded in catalogue text remain inert
  evidence and cannot alter the workflow.
- Documented the state, routes, contracts, trust boundary, limitations, and optional integration
  setup in `docs/AGENTIC_RAG.md`.

Validation:

- `python -m pytest -q`: 211 passed; the optional live-LLM and live-database tests were skipped.
- Focused Phase 5 suite: 20 passed; the optional live-LLM test was skipped.
- Ruff lint and format checks passed for 42 files.
- Dependency consistency and diff whitespace checks passed.

Phase 5 implementation and documentation are complete locally. No commit, push, pull request,
merge, API, UI, container, or Phase 6 work was performed.

## 2026-09-09 — Phase 5 PR #6 verification fixes

Status: fixed and validated locally on `phase/05-agentic-rag`; fixes not committed or pushed.

- Reproduced the review's three false verification successes with the scripted mock provider.
- Replaced missing-information prose with verified product/field objects, fixed labels, and stored
  citations; updated the provider schema and parser.
- Added stored-record constraint checks before draft generation and inside the evidence tool.
  Constraint failures use the existing bounded verification route.
- Added an application-owned criterion/field/direction policy and passed it to the provider.
- Added 50 regression cases, including positive coverage, and updated the Phase 5 documentation.

Validation: full suite 261 passed and two optional live integrations skipped; focused suite
70 passed. Ruff lint and formatting passed for 43 files; dependency and whitespace checks passed.
No commit, push, PR modification, merge, or Phase 6 work was performed for these fixes.

## 2026-09-10 — Phase 6: FastAPI backend and Streamlit demonstration

Status: implementation complete locally; commit and push not authorized.

- Fast-forwarded local `main` to merged Phase 5 pull request #6 and created `phase/06-api-ui`.
- Added separate Pydantic contracts and four FastAPI routes: health, direct retrieval, bounded agent
  query, and complete product lookup.
- Added a stable JSON error envelope for request validation, unknown products, invalid service
  inputs, and unavailable configured components.
- Added component-aware startup so `/health` and ready endpoints remain usable when PostgreSQL or a
  real LLM provider is not configured.
- Made API embedding startup offline-first after discovering that a cached model still attempted
  slow metadata requests. The first download now requires explicit opt-in.
- Added one Streamlit search/comparison page and a transport-only standard-library API client. The
  UI imports no retrieval, storage, workflow, or evidence business logic.
- Added offline API, client, service-assembly, validation, readiness, and error-path tests.
- Added `docs/API_AND_UI.md` and updated the README, architecture, decisions, evaluation record,
  environment template, and dependencies for the implemented boundary.

Real local smoke validation loaded the 3,062-product catalogue, aligned BM25/semantic indexes, and
cached pinned embedding model without network access. Hybrid search for `Samsung AMOLED` under
₹30,000 returned three stored product IDs. PostgreSQL and the real LLM were not configured, and
health correctly marked only product lookup and agent query unavailable; no live database or paid
provider result is claimed.

Validation:

- `python -m pytest -q`: 278 passed; the optional live-LLM and live-database tests were skipped.
- Focused API, client, service-assembly, and Streamlit suite: 16 passed.
- Real local FastAPI `/health` and constrained `/search` smoke requests returned HTTP 200.
- The headless Streamlit server returned HTTP 200; its app harness rendered both tabs without an
  application exception.
- Ruff lint and format checks passed for 53 files.
- Dependency consistency and diff whitespace checks passed.

Phase 6 implementation, tests, and documentation are complete locally. No commit, push, pull
request, merge, Docker, broad evaluation, or Phase 7 work was performed.

## 2026-09-11 — Phase 6 pull request #7 review fixes

Status: fixed and validated locally on `phase/06-api-ui`; review fixes are not committed or pushed.

- Escaped untrusted catalogue product names before Streamlit Markdown rendering so names cannot
  create links, images, or multiline content in result headings.
- Made every numeric search request field strict so JSON booleans are rejected instead of being
  coerced to zero or one.
- Converted transport timeouts into the same safe API-client error used for connection failures.
- Updated the README's current phase and pull-request status.
- Added regression coverage for Markdown-like catalogue names, Boolean numeric values, and timeout
  failures.

Validation:

- `python -m pytest -q`: 280 passed; the optional live-LLM and live-database tests were skipped.
- Focused API, client, service-assembly, and Streamlit suite: 18 passed.
- Ruff lint and format checks passed for 53 files.
- Dependency consistency and diff whitespace checks passed.

No live database, paid provider, deployment, merge, or Phase 7 work was performed for these fixes.

## 2026-09-11 — Phase 7: evaluation, hardening, and Docker configuration

Status: Phase 7 complete locally on `phase/07-evaluation`, including live Docker verification after
installation and restart. Local commits were authorized on 2026-09-11; push and pull request remain
pending separate approval.

- Fast-forwarded local `main` to merged Phase 6 pull request #7 and created
  `phase/07-evaluation`.
- Added 16 reviewed scripted-agent scenarios, bringing the combined retrieval/agent scenario count
  to 36 without mixing their different evidence boundaries.
- Added deterministic agent metrics with explicit denominators, outcome details, and reproducible
  CLI output.
- Added a warmed in-process API latency harness around the real hybrid retriever.
- Added an offline-only model option to retrieval evaluation and semantic index builds after a
  cached-model run attempted unnecessary network metadata requests.
- Added adversarial, metric, loader, API-to-workflow, and container-configuration tests.
- Added a two-stage non-root image, PostgreSQL/pgvector + API + Streamlit Compose topology, read-only
  data mounts, health checks, named volumes, and an opt-in ingestion service.
- Added the detailed Phase 7 measurement and limitations report.

Measured results:

- Retrieval: the 20-case BM25, semantic, and hybrid report reproduced Phase 3 exactly; hybrid
  `alpha = 0.25` remained selected.
- Agent: 16/16 scenarios matched expected status, route, tool sequence, and retry count with a
  scripted mock; average tool calls were 2.1875.
- API: 50 warmed in-process hybrid searches measured 12.9782 ms median and 16.7325 ms p95.
- Indexing: BM25 took 0.2327 seconds; semantic indexing took 56.1828 seconds on CPU. Both artifact
  hashes matched their earlier versions.
- Initially, Compose YAML parsed and static checks passed while Docker was unavailable. The
  post-installation continuation below records the live results.

Initial validation before installing Docker:

- `python -m pytest -q`: 296 passed; Docker, live-LLM, and live-database integrations were skipped.
- Focused Phase 7 evaluation/container suite: 16 passed; live Docker validation was skipped.
- Ruff lint and formatting passed for 57 files after formatting corrections.
- Dependency consistency, Compose YAML parsing, and Git whitespace checks passed.

Post-restart continuation on 2026-09-11:

- Verified WSL2 and Docker Engine 29.7.2 with Compose 5.5.1; started PostgreSQL 16.15.
- Added CPU-only PyTorch to the image. Fixed a real image-build conflict caused by installing
  multiple versions from the wheel directory; runtime now resolves the package offline from it.
- Bound API/UI ports to loopback and made API container health depend on usable search and product
  storage. Added four regression cases for the readiness gate.
- Built all application images and ingested 3,062 products with 384-dimensional embeddings twice;
  both ingestion reports retained the same catalogue hash and model identifier.
- Started the database, API, and UI; verified search/product readiness, Streamlit health, non-root
  runtime identity, and container package consistency. Default query requests correctly return 503
  until a real provider is configured.
- Added four opt-in live HTTP checks for all three search modes, strict constraints, database-backed
  product evidence, invalid requests, unavailable products, and UI health.
- Final full host suite: **305 passed, two skipped**, including Docker configuration and live HTTP
  cases. A fresh temporary test directory resolved Windows permissions from an earlier attempt
  with 55 setup errors; no assertions were weakened.
- Disposable Linux container suite: **25 passed**, including actual PostgreSQL ingestion, lookup,
  vector search, evaluation, API, and Streamlit rendering. Its temporary test schema was removed.
- The host's direct database test and real-LLM opt-in remained skipped. The Linux run separately
  covers the database; no real LLM was called. All recorded warnings and conditions are in the
  Phase 7 report.
