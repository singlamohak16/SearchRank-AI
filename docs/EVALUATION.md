# Evaluation

Phase 2 added the first narrow BM25 benchmark. Phase 3 compares BM25, semantic, and hybrid
retrieval and records deterministic constraint satisfaction. Phase 5 adds offline engineering tests
for agent routing and grounding; broad real-model agent evaluation has not been run.

On 2026-09-02, the Phase 0 suite ran on Windows with Python 3.12.13 and pytest 8.4.2:
3 smoke tests passed in 0.03 seconds. This is an engineering validation result, not a search-quality
metric.

Later phases will record measured results for BM25, semantic, and hybrid retrieval separately,
including Recall@10, NDCG@10, hybrid-alpha ablation, constraint satisfaction, citation correctness,
unsupported-claim behavior, tool-call counts, and latency. Every report will include the dataset
size, evaluation-set size, hardware, embedding model, caching conditions, and whether the LLM was
mocked or real.

This file must never contain estimated or fabricated metrics presented as results.

## 2026-09-03 — Dataset suitability checks, not retrieval evaluation

The [Amazon India audit](DATASET_AUDIT.md) records actual full-file counts, source hash, title
coverage, fixed-seed spot-check conditions, and limitations. Two runs of the final audit rules
produced identical non-timing results and byte-identical review/sample/category artifacts.

At the laptop-audit checkpoint, the synthetic suite had 56 passing tests. Coverage includes Hindi/English capacity
patterns, GPU-vs-RAM separation, ambiguous and missing evidence, accessories/desktops, numeric
sentinels, URL/ASIN agreement, source preservation, malformed input, and deterministic reruns.

The tentative candidate counts are **not** extraction accuracy, a manually verified usable-product
count, retrieval metrics, or proof of catalogue quality. No embedding model or LLM was used.
No paid API or network call is needed for tests or re-auditing an existing local archive.

## 2026-09-03 — Smartphone audit checkpoint

The [smartphone source audit](PHONE_DATASET_AUDIT.md) covers all 3,529 records with 2,805 unique IDs.
Its final rules identify 450 unique smartphone candidates, 260 explicit-core candidates, and 360
if inferred unlabelled capacity pairs are included. These are heuristic coverage counts, not verified
usable products, extraction accuracy, or retrieval results. The dataset is not recommended for adoption.

The combined synthetic suite produced **110 passed in 0.41 seconds** on Windows 11 build 26200,
Python 3.12.13. Ruff lint/format and dependency checks passed. Full-source repeat runs matched on all
non-run report fields and byte-identical JSONL/sample/duplicate artifacts, and preserved the source hash.
Fixed-seed category and explicit-core samples were inspected without an independent ground-truth set.
No LLM, embedding model, retailer access, or retrieval evaluation was used.

## 2026-09-04 — Adopted catalogue reproducibility checkpoint

The [91mobiles catalogue audit](MOBILE_CATALOGUE_AUDIT.md) measured 4,000 source rows and 3,062
eligible core-catalogue rows. The final set has 2,983 normalized ratings, 70 derived brands, unique
product IDs/source URLs, and no exact source duplicates. These are dataset and cleaning measurements,
not retrieval quality or independent specification-accuracy results.

The combined synthetic suite produced **142 passed in 0.50 seconds** on Windows 11 build 26200,
Python 3.12.13 on the final check. Tests cover field parsing, rating-scale
normalization, feature-phone and announcement exclusion, URL/ID validation, missing-value
preservation, raw-row retention, core-only schema enforcement, malformed sources, overwrite
refusal, duplicate-ID refusal, and deterministic reruns.

Two complete source runs matched on every report field except run metadata. Their cleaned CSV,
records JSONL, and sample JSON files were byte-identical. The source hash remained unchanged. No
LLM, embedding model, retailer request, image download, manually labelled ground truth, or search
evaluation was used.

## 2026-09-04 — BM25 navigational baseline

The [Phase 2 retrieval report](BM25_RETRIEVAL.md) defines the implementation, evaluation scope,
commands, environment, timings, and failure modes. The reviewed set has 12 exact-model queries and
one exact base-model product ID judged relevant per query. On the adopted 3,062-document catalogue,
BM25 returned every judged target at rank 1: Recall@10, MRR@10, and NDCG@10 were each 1.000.

This perfect result must not be generalized. The set measures exact known-model navigation across
12 brands, not broad shopping relevance, semantic concepts, misspellings, filters, family-level
variant recall, or unseen queries. RAM/storage variants are unjudged. The evaluation file pins the
catalogue SHA-256 so a changed catalogue fails validation rather than reusing stale judgments.

No embedding model, LLM, network request, or result cache was used. The only caching condition in
the reported query timing was an already loaded in-memory BM25 index.

## 2026-09-05 — Semantic, hybrid, and strict-constraint baseline

The Phase 3 set expands evaluation to 20 reviewed cases: 12 exact base-model targets, four complete
catalogue families used for semantic phrasing, and four variants selected by explicit strict
constraints. The family judgments use product-family names in this catalogue; they are not claims
about real-world gaming, camera, or durability quality. See
[the full Phase 3 report](HYBRID_RETRIEVAL.md).

All runs used the 3,062-product catalogue, the pinned
`sentence-transformers/all-MiniLM-L6-v2` revision, 384-dimensional normalized embeddings, and
`k = 10`.

| Configuration | Recall@10 | MRR@10 | NDCG@10 | Constraint satisfaction |
|---|---:|---:|---:|---:|
| BM25 | 0.811111 | 0.812500 | 0.808979 | 1.000000 |
| Semantic | 0.937500 | 0.887500 | 0.899768 | 1.000000 |
| Hybrid, alpha 0.25 | 0.925000 | 0.950000 | 0.928558 | 1.000000 |
| Hybrid, alpha 0.50 | 0.859722 | 0.827222 | 0.826990 | 1.000000 |
| Hybrid, alpha 0.75 | 0.815278 | 0.816250 | 0.811935 | 1.000000 |

Alpha 0.25 is the selected hybrid setting because it has the best hybrid NDCG@10 and MRR@10.
Semantic-only retains slightly higher Recall@10. Every returned result satisfied its recorded
constraints; this rate measures deterministic filter behavior on four constraint cases, not
natural-language constraint extraction.

## 2026-09-08 — Agentic RAG engineering checkpoint

The focused Phase 5 suite produced **20 passed and one skipped optional integration test**. The full
repository suite produced **211 passed and two skipped optional integration tests**. Tests use a
scripted LLM provider and synthetic product evidence; they do not make a network request or require
a live database.

Coverage includes separate search and comparison routes, clarification for ambiguous "best"
requests, unsupported requests, conflicting brand constraints, one failed-search reformulation,
no-result handling, the four-tool ceiling, exact field/value evidence checks, missing-value
handling, product-ID citation matching, explicit comparison criteria, deterministic numeric winner
validation, and catalogue prompt-injection text treated as inert data. Provider tests also verify
that the optional OpenAI request uses structured output, disables response storage, and carries the
untrusted-data instruction.

This checkpoint validates implementation behavior, not response quality in the wild. The optional
OpenAI test was skipped because `SEARCHRANK_RUN_LLM_INTEGRATION` was not enabled, and the PostgreSQL
integration test was skipped because `SEARCHRANK_TEST_DATABASE_URL` was not set. No real-model
accuracy, latency, token, cost, safety, or user-satisfaction metric is claimed. A broader reviewed
agent evaluation remains Phase 7 work.

## 2026-09-09 — Phase 5 review regression checkpoint

Review of PR #6 reproduced three false verification successes: arbitrary text in the missing-data
section, stored evidence violating the extracted budget, and a direction inconsistent with
`lowest price`. The 2026-09-08 suite did not cover these cases; its passing result was insufficient
to establish those guarantees.

After the fixes, the full offline suite produced **261 passed and two skipped integrations**;
the focused tool/workflow/provider suite produced **70 passed**. The 50 added cases cover each
reproduced failure and related valid/invalid cases, including all strict filters against changed
database records and all comparison-policy entries. Ruff lint/format (43 files), dependency
consistency, and diff whitespace checks passed. No real LLM, PostgreSQL service, live catalogue
update, or new retrieval-quality evaluation was used.
