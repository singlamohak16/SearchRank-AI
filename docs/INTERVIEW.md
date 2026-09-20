# Résumé and interview notes

## Résumé bullets

Use only claims you can explain and reproduce. These describe implemented work, not production use:

- Built a smartphone search and comparison application over 3,062 audited catalogue records using
  Python, FastAPI, Streamlit, and PostgreSQL/pgvector, preserving source-linked product evidence.
- Implemented BM25, MiniLM semantic, and hybrid retrieval; achieved MRR@10 of 0.950 and NDCG@10 of
  0.929 for the selected hybrid weight on a 20-query reviewed development benchmark.
- Developed a bounded LangGraph workflow with deterministic filters and citation/value verification;
  passed 16 scripted workflow scenarios covering clarification, refusal, comparison, and invalid claims.

If space permits, explicitly call the retrieval set a **development benchmark**, not a held-out test.
Do not claim 100% real-model accuracy, zero hallucinations, live prices, production deployment,
large-scale vector search, or sub-17-ms AI responses. [Results](RESULTS.md) gives the denominators.

## Five questions to prepare

### 1. Why combine BM25 and embeddings?

BM25 matches names and exact terms transparently. Embeddings help related wording and product
families. I measured each separately before combining normalized scores. Alpha 0.25 improved the
top-rank metrics in my small reviewed set, although semantic-only retrieval recovered more relevant
IDs overall. I would validate that weight on a larger held-out set before treating it as general.

### 2. Why keep filters outside the LLM?

A budget or minimum RAM is a strict requirement, not a preference to be traded for a semantic score.
Python filters eligible records before ranking, and missing values cannot pass required filters.
The model can still misunderstand a user's request, so extraction accuracy remains a separate
evaluation problem from enforcing the extracted constraints.

### 3. How do you prevent unsupported answers?

The model produces a structured draft over retrieved records. Python checks cited product/source
pairs, field values, supported comparisons, and missing information, then renders accepted content.
Invalid drafts are withheld. This reduces specific failure modes; it does not prove the catalogue
is true or that every possible model error is detected. The scripted adversarial tests demonstrate
particular checks, not a universal hallucination guarantee.

### 4. Is pgvector serving your hybrid search?

No. The current API's measured hybrid path uses local BM25 and NumPy embedding artifacts. PostgreSQL
stores product evidence, ingestion metadata, and vectors, with a separately tested exact cosine-search
interface. Keeping that distinction explicit avoids claiming database-backed ranking that is not
wired into the serving path. At a larger scale I would evaluate a database/approximate-index design.

### 5. What would you improve next?

First expand independent evaluation and lock the runtime environment. A real retailer feed is a
separately scoped extension requiring permitted access, stable IDs, freshness tracking, provenance,
and a re-index/update strategy. I would not replace the measured snapshot without retaining a
reproducible evaluation version. Authentication, load tests, and deployment hardening are also
necessary before public production use.
