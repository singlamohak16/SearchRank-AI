# Evaluation

No retrieval or agent evaluation has been run yet. Phase 0 validates only the project foundation.

On 2026-09-02, the Phase 0 suite ran on Windows with Python 3.12.13 and pytest 8.4.2:
3 smoke tests passed in 0.03 seconds. This is an engineering validation result, not a search-quality
metric.

Later phases will record measured results for BM25, semantic, and hybrid retrieval separately,
including Recall@10, NDCG@10, hybrid-alpha ablation, constraint satisfaction, citation correctness,
unsupported-claim behavior, tool-call counts, and latency. Every report will include the dataset
size, evaluation-set size, hardware, embedding model, caching conditions, and whether the LLM was
mocked or real.

This file must never contain estimated or fabricated metrics presented as results.
