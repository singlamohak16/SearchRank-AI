# BM25 keyword retrieval baseline

Date: 2026-09-04. Phase 2 implementation and measured local results.

## Scope and boundary

Phase 2 adds deterministic keyword retrieval over the approved smartphone catalogue. It does not
add semantic retrieval, hybrid ranking, query interpretation, an LLM, a database, or deterministic
price/RAM/storage/rating filters. A query such as `Samsung AMOLED` is a keyword query; a phrase such
as `Samsung under 30000` is **not** a correctly enforced price constraint in this phase.

The implementation uses only the Python standard library. Catalogue strings are treated as
untrusted text: the code case-folds and tokenizes them but never executes them, follows their URLs,
or sends them to another service.

## Index design

`searchrank_ai.bm25` validates the exact 18-column Phase 1 schema and rejects empty catalogues,
empty product IDs, duplicate product IDs, and records without searchable text. Each document keeps
its original `product_id`, `product_name`, and `source_url` so ranked output remains traceable.

The baseline tokenizes Unicode alphanumeric runs and uses the Robertson BM25 formula with
`k1 = 1.5` and `b = 0.75`. The following simple, fixed field weights are encoded as term-frequency
weights:

| Catalogue evidence | Weight |
|---|---:|
| Product name | 3 |
| Brand | 2 |
| Processor, charging, display type, rear camera, front camera | 1 |
| Battery capacity plus `mah`/`battery` labels | 1 |

Price, RAM, storage, rating, release date, URLs, and image URLs are not indexed. The first four are
strict filter attributes reserved for deterministic handling in Phase 3; indexing source/image
URLs would add irrelevant tokens. Repeated query terms use their query-term frequency. Products
with a zero BM25 score are omitted, and equal scores are ordered by product ID for reproducibility.

The generated JSON index records its format version, BM25 parameters, field weights, catalogue
SHA-256, document lengths, and term frequencies. Loading rejects an incompatible format or field
configuration. Generated indexes and reports remain under ignored `artifacts/`; the source-derived
index is not committed.

## Commands

Build the index from the locally generated Phase 1 catalogue:

```powershell
.venv\Scripts\python.exe -X utf8 -m searchrank_ai.bm25 build `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue.csv `
  --output artifacts\bm25\phase2-index.json
```

Search it and receive ranked product IDs, names, source URLs, and scores as JSON:

```powershell
.venv\Scripts\python.exe -X utf8 -m searchrank_ai.bm25 search `
  --index artifacts\bm25\phase2-index.json `
  --query "snapdragon 8 gen 3 amoled" `
  --limit 10
```

Run the reviewed navigational benchmark:

```powershell
.venv\Scripts\python.exe -X utf8 -m searchrank_ai.bm25 evaluate `
  --index artifacts\bm25\phase2-index.json `
  --cases evaluation\bm25_navigational.json `
  --limit 10 `
  --output artifacts\bm25\phase2-evaluation.json
```

All output-writing commands refuse to replace an existing file. Use a new path for a repeat run.

## Measured checkpoint

The committed benchmark contains 12 manually reviewed exact-model queries spanning Apple, Google,
OnePlus, Samsung, Xiaomi, Motorola, POCO, realme, vivo, Nothing, OPPO, and Infinix. Each query has
one exact base-model product ID judged relevant. RAM/storage variants are deliberately unjudged.
The benchmark pins the adopted catalogue hash so stale judgments fail instead of silently running
against different data.

On the 3,062-document catalogue with SHA-256
`c3428dd04e5d02c6a66ce00f5961f6b1f6ba9dcc30d86a37ffde84523619c7ea`, the recorded run produced:

| Metric | Result |
|---|---:|
| Recall@10 | 1.000 |
| MRR@10 | 1.000 |
| NDCG@10 | 1.000 |
| Exact targets ranked first | 12 / 12 |

Environment: Windows build 26200, Python 3.12.14, Intel64 Family 6 Model 186, 16 logical
processors. Building and saving the 1,145,647-byte index took 0.4963 seconds in one recorded run.
A warm in-memory loop of the 12 queries repeated 100 times took 0.399278 seconds, averaging
0.332732 ms per search. These timings describe this machine and run; they are not service latency.
There was no embedding model, network call, LLM, or result cache. The index was already loaded for
the search timing. Two complete index builds were byte-identical, as were evaluation reports loaded
from those independent indexes.

This is intentionally a narrow navigational benchmark. Its perfect scores show that exact known
model names work in these 12 judgments; they do not establish performance for broad shopping needs,
misspellings, synonyms, subjective concepts, constraints, unseen queries, or all relevant variants.

## Known failure modes

- Lexical mismatch: `great screen` does not automatically mean `AMOLED` or `LTPO`.
- Misspellings and model aliases are not corrected.
- BM25 is bag-of-words ranking and does not require tokens to form an exact phrase.
- Broad tokens such as `phone`, `pro`, or `battery` have low discriminative value.
- The benchmark does not judge every relevant variant, so it cannot measure family-level recall.
- Numeric hard requirements are not enforced by retrieval and must not be inferred from scores.
- Results reflect a historical catalogue snapshot and inherit its documented source limitations.

Phase 3 can compare semantic and hybrid retrieval against this unchanged lexical baseline and add
deterministic hard-constraint handling as a separate step.
