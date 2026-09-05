# Semantic and hybrid retrieval

Date: 2026-09-05. Phase 3 implementation and measured local results.

## Scope

Phase 3 adds semantic retrieval, measured hybrid ranking, and deterministic filters over the
approved 3,062-product smartphone catalogue. It does not parse constraints from natural language,
store vectors in PostgreSQL, call an LLM, or expose an API.

Catalogue strings remain untrusted input. They are converted to text and vectors but are never
executed, followed as instructions, or sent to an LLM.

## Embedding model

The selected encoder is
[`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
at revision `c21050a7ef692090620a6d037dd736908f9c7cf6`. Its model card describes a
384-dimensional English sentence representation intended for semantic search and lists an
Apache-2.0 licence. The model truncates inputs beyond 256 word pieces; generated product texts in
this project are short structured summaries.

The implementation uses `encode_document` for catalogue text and `encode_query` for searches,
normalizes both, and calculates cosine similarity as their dot product. This follows the
[official semantic-search guidance](https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html)
for a small corpus. A 3,062-row matrix is intentionally kept in memory until Phase 4 introduces
PostgreSQL and pgvector.

## Search text

Each product text contains labelled stored evidence:

- Product name, brand, and the fixed smartphone category
- RAM and storage text
- Processor
- Battery capacity and charging
- Display size and type
- Rear and front cameras

Price and rating are excluded from semantic text because they are hard filters. URLs and image URLs
are excluded because their tokens are not product meaning. Missing values remain absent rather than
being guessed.

## Semantic artifact

The local NPZ stores only:

- Unit-normalized `float32` vectors
- Product IDs in catalogue order
- Catalogue SHA-256
- Pinned encoder identifier
- Format, search-text, and dimension versions

Loading uses `allow_pickle=False`. The retriever refuses catalogue/BM25/semantic artifacts whose
hashes or ordered product IDs disagree. Generated vectors remain ignored by Git.

Two complete builds produced the same 4,391,982-byte file with SHA-256
`bf2aa06bfdd6de65ede547a97cdea24f473fb90628a2eb8f7ab325582541b07b`.

## Strict constraints

The supported constraint object contains:

- Maximum price in INR
- Minimum RAM in GB
- Minimum storage in GB
- Included brands
- Excluded brands
- Minimum user rating on the normalized five-point scale

Filtering happens across the complete catalogue before score normalization and ranking. Boundary
values are inclusive. Brand matching is case-insensitive and exact. A missing rating fails a
minimum-rating rule. Negative/non-finite numbers, ratings above five, empty brands, and the same
brand in both include/exclude lists are rejected.

Weight filtering is omitted because the adopted source has no reliable weight attribute.

## Score normalization and hybrid formula

For the products that pass constraints:

```text
normalized_bm25 = raw_bm25 / maximum_eligible_bm25
normalized_semantic = clamp((cosine_similarity + 1) / 2, 0, 1)

hybrid_score = alpha * normalized_bm25
             + (1 - alpha) * normalized_semantic
```

If every BM25 score is zero, every normalized BM25 component is zero. Results are ordered by score
descending, then product ID for deterministic ties. Returned records expose raw and normalized
components so ranking can be inspected.

## Reviewed evaluation

[`evaluation/retrieval_v1.json`](../evaluation/retrieval_v1.json) contains 20 cases tied to the
catalogue hash:

- 12 exact base-model targets retained from the Phase 2 benchmark
- 4 semantic product-family queries with all matching catalogue family IDs enumerated
- 4 exact queries where structured constraints select the judged variant

The family labels rely on explicit Pixel Fold, vivo X Fold, ASUS ROG Phone, and Motorola Razr model
families. They do not assert independent real-world gaming or folding-quality measurements.

### Overall results at k = 10

| Configuration | Recall@10 | MRR@10 | NDCG@10 | Constraint satisfaction |
|---|---:|---:|---:|---:|
| BM25 | 0.811111 | 0.812500 | 0.808979 | 1.000000 |
| Semantic | 0.937500 | 0.887500 | 0.899768 | 1.000000 |
| Hybrid, alpha 0.25 | 0.925000 | 0.950000 | 0.928558 | 1.000000 |
| Hybrid, alpha 0.50 | 0.859722 | 0.827222 | 0.826990 | 1.000000 |
| Hybrid, alpha 0.75 | 0.815278 | 0.816250 | 0.811935 | 1.000000 |

The deterministic selection rule prioritizes NDCG@10, then MRR@10, Recall@10, proximity to 0.5,
and finally the lower alpha. It selects **alpha 0.25**. Semantic-only has slightly higher recall;
the selected hybrid has the best top-rank quality among the hybrid candidates on this set.

On the four semantic-family cases, Recall@10 rises from 0.055556 for BM25 to 0.687500 for semantic
and 0.625000 for the selected hybrid. Exact-model and strict-constraint categories score 1.000000
for Recall@10, MRR@10, and NDCG@10 under the selected hybrid.

## Measured environment

- Windows 11 build 26200
- Python 3.12.14
- Intel64 Family 6 Model 186, CPU execution
- Sentence Transformers 5.7.0
- PyTorch 2.14.0
- NumPy 2.5.2
- Catalogue: 3,062 documents
- Embeddings: 384-dimensional `float32`
- Model already cached; offline mode enabled for recorded evaluation
- No LLM, API key, query-result cache, database, or GPU

One recorded run took 11.2110 seconds to load the cached model, 63.4999 seconds to encode all
products, and 0.2954 seconds to save the local index, for 75.0062 seconds total. These timings are
machine-specific and are not API latency.

## Commands

Build the semantic index:

```powershell
.venv\Scripts\python.exe -X utf8 -m searchrank_ai.retrieval build-semantic `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue.csv `
  --output artifacts\semantic\phase3-index.npz `
  --device cpu
```

Compare BM25, semantic, and the three alpha values:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
.venv\Scripts\python.exe -X utf8 -m searchrank_ai.retrieval evaluate `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue.csv `
  --bm25-index artifacts\bm25\phase2-index.json `
  --semantic-index artifacts\semantic\phase3-index.npz `
  --cases evaluation\retrieval_v1.json `
  --alphas 0.25 0.50 0.75 --limit 10 `
  --output artifacts\semantic\phase3-evaluation.json
```

Output paths cannot already exist. Offline mode works only after the pinned model revision has been
downloaded once.

## Limitations

- Twenty cases are not enough for broad search-quality or production claims.
- Family judgments use model naming as relevance evidence and do not prove subjective quality.
- The selected alpha may change with a larger and more diverse evaluation set.
- Maximum-score BM25 normalization is query- and eligible-set-dependent.
- The encoder is English-only and the source catalogue is expected to be English.
- Semantic similarity can still rank factually inappropriate products; strict fields are therefore
  never delegated to the encoder.
- There is no weight field, review count, live price, availability, database, API, or agent yet.
