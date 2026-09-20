# Measured results and reproduction

Consolidated on 2026-09-18. Retrieval and scripted-agent results below were rerun that day; the
timing and live-provider observations are explicitly historical. Full generated reports remain
local/ignored. Reviewed cases and this numeric summary are version-controlled.

## Retrieval

Conditions: 3,062 products; catalogue SHA-256
`c3428dd04e5d02c6a66ce00f5961f6b1f6ba9dcc30d86a37ffde84523619c7ea`; CPU;
cached `sentence-transformers/all-MiniLM-L6-v2` at revision
`c21050a7ef692090620a6d037dd736908f9c7cf6`; 384 dimensions; no network model lookup or LLM.
[The 20 judgments](../evaluation/retrieval_v1.json) contain 12 exact-model, four semantic-family,
and four strict-constraint cases. Results reproduced the earlier Phase 7 metrics.

| Mode | Recall@10 | MRR@10 | NDCG@10 | Constraint satisfaction |
|---|---:|---:|---:|---:|
| BM25 | 0.811111 | 0.812500 | 0.808979 | 1.000000 |
| Semantic | 0.937500 | 0.887500 | 0.899768 | 1.000000 |
| Hybrid, alpha 0.25 | 0.925000 | 0.950000 | 0.928558 | 1.000000 |
| Hybrid, alpha 0.50 | 0.859722 | 0.827222 | 0.826990 | 1.000000 |
| Hybrid, alpha 0.75 | 0.815278 | 0.816250 | 0.811935 | 1.000000 |

Recall measures recovery of judged relevant IDs; MRR emphasizes the first relevant result; NDCG
measures ranking quality using the recorded relevance judgments. The constraint aggregate includes
unconstrained cases (which pass vacuously); only **four** cases meaningfully exercise strict filters.
It is not evidence of natural-language constraint-extraction accuracy.

The rule chooses the hybrid alpha with highest NDCG, then MRR, recall, proximity to 0.5, and lower
alpha. Alpha 0.25 won among these three weights. Semantic-only recall is higher. The same small set
was used for selection and reporting; there is **no held-out generalization estimate** or statistical
significance claim. Family relevance is not a measure of real-world phone quality.

## Scripted workflow evaluation

[Sixteen reviewed scenarios](../evaluation/agent_scenarios_v1.json) use four synthetic products
and `scripted_mock` model outputs. The real graph, tools, verifier, and renderer execute.

| Metric | Result | Denominator |
|---|---:|---:|
| Scenario / status / tool-selection / route accuracy | 1.000000 each | 16 scenarios each |
| Constraint satisfaction | 1.000000 | 4 constrained cases with results |
| Clarification accuracy | 1.000000 | 2 cases |
| Refusal accuracy | 1.000000 | 2 cases |
| Conflict detection | 1.000000 | 1 case |
| Citation correctness | 1.000000 | 8 expected answered cases |
| Unsupported-claim rate | 0.000000 | 16 scenarios |
| Average tool calls | 2.187500 | 16 scenarios |

This includes fabricated-value and wrong-citation drafts that must fail verification. The
unsupported-claim metric detects answered outcomes with failed verification in this scenario set;
it is not a human audit of arbitrary claims. Empty metric categories report null, not perfection.
These results cannot justify “100% accurate AI” or “zero hallucinations.”

## Reproduce both runs

Complete [setup](SETUP.md) first. These recorded output paths were used on 2026-09-18; use a new
filename on subsequent runs because report writers refuse overwrites.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m searchrank_ai.retrieval evaluate `
  --catalogue data/processed/suresh_91mobiles_2008_2026/catalogue.csv `
  --bm25-index artifacts/bm25/phase2-index.json `
  --semantic-index artifacts/semantic/phase3-index.npz `
  --cases evaluation/retrieval_v1.json --alphas 0.25 0.50 0.75 `
  --limit 10 --device cpu --local-files-only `
  --output artifacts/evaluation/phase8-retrieval-20260918.json

.\.venv\Scripts\python.exe -X utf8 -m searchrank_ai.evaluation agent `
  --cases evaluation/agent_scenarios_v1.json `
  --output artifacts/evaluation/phase8-agent-20260918.json
```

The agent command alone does not require the catalogue, a key, or PostgreSQL.

## Historical engineering measurements—not rerun in Phase 8

On 2026-09-11, an i7-13620H Windows 11 laptop with 16,890,519,552 bytes RAM and Python 3.12.14
produced a BM25 index in 0.2327 s (1,145,647 bytes) and a cached CPU semantic index in 56.1828 s
(4,391,982 bytes). Hashes matched the earlier artifacts.

A warmed FastAPI **in-process TestClient** search benchmark used 20 rotating queries, five warmups,
50 sequential samples, hybrid alpha 0.25, and limit 10. Median was **12.9782 ms**, nearest-rank p95
**16.7325 ms** (min 10.7063, max 24.2514). It excludes sockets, PostgreSQL, LLM calls, concurrency,
and cold model loading. Do not describe this as deployed or end-to-end AI latency. Hardware details,
full conditions, and the reproduction command are in [the Phase 7 report](PHASE_7_EVALUATION.md).

On 2026-09-16, three real Gemini workflow smoke tests passed (search, comparison, unsupported
request); observed individual times were 10.34 s, 25.06 s, and 11.43 s. On 2026-09-17, the redesigned
UI returned an answered Samsung search with five verified facts and no retries or verification
issues. These examples establish limited connectivity/integration evidence, not model accuracy or
a latency distribution. Failures and fixes are retained in [Gemini notes](GEMINI_SETUP.md).

## Phase 8 verification boundary

The live API port refused connections during this phase. No Docker restart, database re-ingestion,
new provider request, or fresh browser test was performed. The [documented search example](DEMO.md)
was captured through the real FastAPI route and cached catalogue retriever using an in-process
TestClient. It is labeled accordingly. Offline regression totals and release checks are recorded in
[the release checklist](RELEASE.md); older phase test totals are historical, not additive.

## Remaining evaluation gaps

- Larger independently labeled and held-out retrieval sets, including realistic ambiguous queries.
- Real-provider interpretation and end-to-end answer evaluation across multiple runs and failures.
- Independent verification of source facts; current citations establish catalogue provenance only.
- Cold-start, concurrency, networked/deployed performance, and accessibility testing.
- Fully locked dependency/image environments and a fresh-machine setup reproduction.

Live retailer APIs remain a separate post-Phase-8 proposal, not a silently changed benchmark source.
