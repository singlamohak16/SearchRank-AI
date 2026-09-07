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

## D-006 — Audit Amazon India before committing to dataset adoption

- **Date:** 2026-09-03
- **Status:** Audit completed; adoption rejected by the user on 2026-09-03
- **Decision:** Download and preserve the approved asaniczka Amazon India 2023 archive, audit the
  exact laptop category, and keep raw/derived records out of Git. The user approved the audit,
  not automatic adoption of its output as a cleaned catalogue.
- **Reason:** It supplies ASINs, Amazon India URLs, prices, and ratings at sufficient apparent scale.
  [The measured audit](DATASET_AUDIT.md) found a plausible 4,702-candidate pool, 2,458 rated, but
  mixed-language titles and substantial quality issues make suitability conditional.
- **Alternatives discussed:** The newer Vibish India dataset has structured specifications but
  lacked usable customer ratings in the inspected fields; the Dhanush Flipkart dataset is smaller
  than the original target; other larger alternatives lacked source references or ratings. These
  were screening observations, not comparable full-file audits.
- **Outcome:** Revisit alternatives. Preserve the audit as evidence for rejecting the source.
  Do not silently lower the target size, drop rating support, or translate raw titles into new facts.

## D-007 — Use a streaming, evidence-preserving audit before production cleaning

- **Date:** 2026-09-03
- **Status:** Accepted for the audit only
- **Decision:** Use Python's standard CSV/ZIP libraries and small deterministic title probes.
  Separate original strings from normalized findings, uncertainty, and review flags. Keep
  zero-valued price/rating sentinels explicitly unavailable; preserve all original IDs and rows.
- **Reason:** One sequential read inventories the large archive without an extra extracted copy
  or new runtime dependency. Fixed-seed samples and source hashes make review reproducible.
- **Boundary:** This does not finalize the product schema, deduplication rules, Pandas cleaning
  implementation, condition handling, or retrieval-language strategy. Coverage is not accuracy.
- **Storage convention:** Audit-only capacity comparisons use 1 TB = 1,000 GB; multiple recognized
  drives remain unresolved and original text is retained. Final total-storage semantics need review.

## D-008 — Reopen selection without silently relaxing requirements

- **Date:** 2026-09-03
- **Status:** Accepted search criteria; replacement choice pending
- **Decision:** Prioritize English listings and separate specifications while retaining the
  original laptop scope, size target, rating requirement, and evidence/identifier rules.
- **Finding:** [Replacement screening](DATASET_CANDIDATES.md) has not verified a complete match.
  The smaller Flipkart source is the strongest next audit candidate for core functionality, but
  requires approval of the size trade-off and acceptance of its June 2022 snapshot.
- **Alternatives:** Larger or newer-looking sources have missing ratings, inconsistent engineered
  values, different score semantics, or other provenance/coverage problems. No new source is adopted.

## D-009 — Screen smartphones before deciding whether to change domains

- **Date:** 2026-09-03
- **Status:** Historical research complete; scope and audit subsequently approved (D-010)
- **Decision:** Evaluate public smartphone dataset metadata and samples against the existing search,
  ranking, evidence, and catalogue-quality requirements. Do not change the laptop scope merely
  because the user approved this investigation.
- **Finding:** A 2025 Amazon India mobile listing source is a stronger apparent fit than the screened
  laptop candidates: 3,529 previewed rows, 2,805 unique ASINs, English evidence-rich titles, INR
  prices, customer ratings/review counts, and source URLs. A full audit is still required because
  specifications need title extraction, duplicate ASINs exist, and very low prices suggest possible
  contamination or extraction errors.
- **Alternatives:** Older structured phone datasets lack source identifiers/URLs or sufficient scale.
  A newer 33,000-row source has implausible specifications and internally inconsistent feedback
  counts in public samples. See [replacement screening](DATASET_CANDIDATES.md).
- **Boundary:** No dataset was downloaded or adopted, and the application remains laptop-focused
  unless the user explicitly approves both the smartphone scope and the candidate audit.

## D-010 — Switch to smartphones; do not adopt the failed Amazon phone candidate

- **Date:** 2026-09-03
- **Status:** Smartphone scope approved; audit complete; adoption not recommended
- **Decision:** Apply the user's explicit scope change to smartphones and audit the approved
  Amazon India phone archive without automatically adopting its records. Preserve both raw sources
  and previous audit history. Keep all phase/Git gates unchanged.
- **Finding:** The file contains 3,529 rows and 2,805 distinct ASINs, but the audit flags 2,711 rows
  for accessory/bundle review and finds only 450 unique heuristic smartphone candidates. There are
  260 distinct explicit-core candidates (251 rated); counting inferred unlabelled pairs raises the
  tentative core to 360 (350 rated), not to the originally desired scale.
- **Reason:** A large mixed-product file is not a large smartphone catalogue. English text, valid
  source IDs, and strong overall ratings do not compensate for category contamination and sparse
  structured evidence. All numbers are audit-rule outputs, not verified true-product counts.
- **Boundary:** No catalogue cleaning/schema adoption or later phase is authorized by this verdict.
  A new dataset download requires approval. See [the phone audit](PHONE_DATASET_AUDIT.md).

## D-011 — Adopt the audited 91mobiles core catalogue

- **Date:** 2026-09-04
- **Status:** Accepted; Phase 1 complete
- **Decision:** Adopt Suresh Khadka's 4,000-row 91mobiles dataset after deterministic filtering.
  Retain 3,062 records with a valid source URL, positive INR price, explicit RAM/storage of at least
  1 GB/8 GB, and no announced/to-be-announced marker. Keep the complete raw archive and every raw
  row in ignored local evidence; do not silently repair or merge records.
- **Schema:** Use stable IDs derived from unique 91mobiles URL slugs plus name, brand, price, RAM,
  storage, normalized user rating, processor, battery/charging, display, cameras, release evidence,
  source URL, and image URL. Missing non-eligibility fields remain empty.
- **User-directed exclusion:** Do not put `spec_score`, `antutu_score`, `awards`, `expert_rating`,
  or `store` in the final catalogue. Their original values remain only in raw audit evidence.
- **Reason:** The retained set meets the 2,000–5,000 target with separate filter attributes, unique
  evidence links, high rating coverage, no duplicate IDs, and reproducible output. Capacity rules
  separate sampled feature phones without using product-name knowledge or a price-only cutoff.
- **Rating rule:** Normalize `/5` values directly and `/10` values mathematically to `/5` only when
  the scale is explicit. Never treat `spec_score` or `expert_rating` as customer feedback.
- **Limitations:** There is no review count or live-price timestamp; source facts were not checked
  against manufacturers; some comparison fields remain missing; variants remain separate; and the
  listed CC0 licence conflicts with the publisher's learning/non-commercial usage note. Keep the
  data untracked and document rather than redistribute it. See
  [the measured audit](MOBILE_CATALOGUE_AUDIT.md).

## D-012 — Establish a dependency-free, field-weighted BM25 baseline

- **Date:** 2026-09-04
- **Status:** Accepted; Phase 2 complete locally
- **Decision:** Use a small standard-library BM25 implementation with fixed `k1 = 1.5`, `b = 0.75`,
  product-name weight 3, brand weight 2, and specification-evidence weight 1. Preserve product IDs
  and source URLs in results, serialize a versioned local index, and order equal scores by product ID.
- **Reason:** A direct implementation keeps the lexical baseline inspectable, deterministic, and
  independently testable before semantic or hybrid retrieval is introduced. No external search
  framework is needed for 3,062 documents.
- **Evaluation:** Track a small, catalogue-hash-pinned exact-model benchmark and label its scope
  honestly. The 12-case result establishes navigational behavior only, not broad product-search
  quality or semantic understanding.
- **Boundary:** Do not treat BM25 scores as constraint checks. Price, RAM, storage, brand, and rating
  filters, query parsing, semantic retrieval, and hybrid ranking remain Phase 3. Generated indexes
  and reports stay ignored because they derive from the uncommitted source catalogue.
- **Alternatives:** `rank_bm25` would shorten the scorer but add a runtime dependency and would not
  remove the need for schema, provenance, serialization, deterministic ties, or evaluation code.
  A search server would be disproportionate before the persistence phase.

## D-013 — Use a pinned MiniLM sentence encoder for the first semantic baseline

- **Date:** 2026-09-05
- **Status:** Accepted; measured locally
- **Decision:** Use `sentence-transformers/all-MiniLM-L6-v2` at revision
  `c21050a7ef692090620a6d037dd736908f9c7cf6`. Encode labelled product evidence and queries as
  normalized 384-dimensional vectors, then use their dot product as cosine similarity.
- **Reason:** The catalogue and queries are short English text, the model card explicitly supports
  semantic search, and the 384-dimensional representation is realistic for a 3,062-product
  undergraduate portfolio project. Pinning the revision makes the model input reproducible.
- **Alternatives:** A larger encoder could improve ranking but would increase CPU, memory, download,
  and future database costs before evaluation justifies them. Fine-tuning is outside project scope.
- **Boundary:** Model files and generated vectors remain local and ignored. Unit tests use a tiny
  deterministic encoder and never download the production model.

## D-014 — Separate hard constraints from retrieval scores

- **Date:** 2026-09-05
- **Status:** Accepted
- **Decision:** Filter the complete catalogue by maximum price, minimum RAM, minimum storage,
  minimum user rating, and included/excluded brands before normalizing or ranking candidates.
  Missing ratings fail a minimum-rating requirement. Conflicting included/excluded brands are
  rejected instead of guessed.
- **Reason:** Relevance scores are not proof that a numeric or categorical requirement is satisfied.
  Pre-filtering also avoids losing valid constrained products to an arbitrary retrieval cutoff.
- **Boundary:** Weight is not supported because the adopted catalogue has no reliable weight field.
  Natural-language constraint extraction remains part of the later agent phase.

## D-015 — Select hybrid alpha from the Phase 3 benchmark

- **Date:** 2026-09-05
- **Status:** Accepted; provisional until the broader Phase 7 evaluation
- **Decision:** Normalize positive BM25 scores by the largest eligible BM25 score for that query;
  map cosine similarity from `[-1, 1]` to `[0, 1]`; and calculate
  `alpha * BM25 + (1 - alpha) * semantic`. Select `alpha = 0.25` from candidates 0.25, 0.50, and
  0.75 using highest NDCG@10, then MRR@10, Recall@10, proximity to 0.5, and lower alpha.
- **Evidence:** On the reviewed 20-case set, alpha 0.25 produced NDCG@10 0.928558, MRR@10 0.950000,
  and Recall@10 0.925000. The other hybrid NDCG@10 results were 0.826990 at alpha 0.50 and 0.811935
  at alpha 0.75.
- **Limitation:** Semantic-only Recall@10 was slightly higher at 0.937500. The selected hybrid has
  better top-rank quality on this small set, not universal superiority. Phase 7 must revisit the
  choice with a broader evaluation.

## D-016 — Persist complete products and aligned vectors in PostgreSQL/pgvector

- **Date:** 2026-09-06
- **Status:** Accepted; Phase 4 complete locally
- **Decision:** Store all 18 approved catalogue fields and one fixed-dimension pgvector embedding
  per product in an isolated `searchrank_ai` schema. Record the catalogue SHA-256, pinned encoder
  identity, embedding dimension, product count, and schema version in a singleton metadata row.
- **Ingestion rule:** Require exact catalogue hash and product-order agreement with the semantic
  artifact before opening a write transaction. Upsert the complete incoming set, delete stale IDs,
  and update metadata under one advisory transaction lock. Re-running identical inputs produces
  the same logical state without changing product IDs or inventing values.
- **Retrieval rule:** Product-detail lookup returns complete stored evidence in requested order and
  separately reports unknown IDs. Vector search uses pgvector cosine distance and stable product-ID
  tie-breaking. Phase 3 BM25/hybrid behavior stays independently testable in memory.
- **Alternatives:** An ORM would obscure a small schema and transaction; PostgreSQL arrays would
  not provide pgvector operators; an approximate HNSW/IVFFlat index adds tuning and build cost that
  3,062 records do not yet justify. Docker remains intentionally deferred to Phase 7.
- **Security and limitation:** Credentials remain environment-only and SQL values are parameters.
  This machine has no PostgreSQL service, so the optional live integration test was not run; it is
  gated by `SEARCHRANK_TEST_DATABASE_URL` and uses a unique disposable schema.
