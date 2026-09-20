# Architecture

Current runtime, documented on 2026-09-18. SearchRank-AI is a local smartphone catalogue search and
comparison demonstration, not a retailer integration or an autonomous purchasing agent.

## Data preparation

```text
Unmodified source ZIP (kept locally)
  -> full-file audit + deterministic smartphone eligibility rules
  -> 3,062-row core catalogue, source URLs, URL-derived IDs, SHA-256
       -> BM25 index
       -> pinned MiniLM encoder -> normalized 384-dimensional NumPy index
       -> transactional PostgreSQL ingestion of products + pgvector embeddings
```

The source snapshot has 4,000 rows. Cleaning requires usable price and explicit RAM/storage,
excludes announced products, and never fills unknown specifications by guessing. Optional source
attributes such as awards and expert scores are excluded. See the
[dataset audit](MOBILE_CATALOGUE_AUDIT.md) for the exact rules and 18 retained fields.

Index loading checks catalogue identity and product ordering. Storage ingestion validates the
catalogue hash, IDs, vector dimensions, and encoder identity. A single transaction synchronizes the
catalogue and its metadata; a failed ingestion must not leave partial data. Synchronization can
remove obsolete rows, so it is an explicit setup operation, never an API startup side effect.

## Runtime responsibilities

| Layer | Responsibility | Main modules |
|---|---|---|
| Presentation | Forms, escaped cards, shortlist, comparisons, evidence panels | `streamlit_app`, `ui_presentation` |
| HTTP client/API | Typed requests, validation, sanitized failures, service readiness | `api_client`, `api`, `api_models` |
| Retrieval | Eligible records, lexical/semantic scores, deterministic ranking | `bm25`, `semantic`, `retrieval` |
| Storage | Product evidence, ingestion, exact vector-search interface | `storage` |
| Agent | Bounded routing and tool orchestration | `workflow`, `agent_models`, `agent_tools` |
| Provider | Structured model tasks; default scripted mock for tests | `llm`, `gemini` |
| Verification | Evidence field policy, citation/value/comparison checks | `evidence_policy`, `agent_tools` |
| Assembly/evaluation | Configuration, services, benchmark execution | `config`, `services`, `evaluation` |

The UI calls FastAPI over HTTP; it does not open PostgreSQL or receive an LLM key. Ordinary search
does not call an LLM. Side-by-side comparison displays stored facts and does not need AI generation.

### Search

`POST /search` applies explicit brand, price, RAM, storage, and rating constraints before ranking.
Missing required filter values do not pass. Numeric and boolean validation happens at the API
boundary; a model cannot override Python's strict filtering.

The retriever scores eligible products using BM25 and/or MiniLM cosine similarity. BM25 scores
are normalized against the eligible maximum; cosine is mapped into a comparable bounded range.
Hybrid score is `alpha * normalized_bm25 + (1 - alpha) * normalized_cosine`.
Stable tie-breaking and component scores make results inspectable. The selected `alpha=0.25`
comes from the [small reviewed evaluation](RESULTS.md), not a universal ranking rule.

API hybrid retrieval runs against the local BM25/NumPy artifacts. PostgreSQL stores full product
details for `GET /products/{product_id}` and for agent evidence. A separate exact pgvector cosine
search implementation is tested, but is not used to produce the API's measured hybrid ranking.
There is no approximate vector index or database-backed BM25 in the current architecture.

### Agent query

```text
Request + optional context
  -> structured request analysis
       -> clarify / reject unsupported request / report conflicting constraints
       -> search or compare
            -> catalogue search (at most one bounded reformulation)
            -> authoritative product details
            -> structured answer draft
            -> deterministic evidence verification
                 -> render accepted facts and comparisons with citations
                 -> withhold failed claims / report unavailable information
```

The graph allows at most one reformulation and four tool calls. Model interpretation remains
fallible: correctly enforcing an incorrectly extracted budget is not the same as understanding the
user. Structured schemas constrain output shape; Python checks product/source identity, values,
supported criteria, numeric comparisons, and missing-information claims against supplied evidence.
The final answer is rendered from validated structured content, not arbitrary model prose.

Gemini additionally restricts directional winner claims to unique supported winners in the supplied
group. Ties are shown as facts rather than silently broken. This does not replace the verifier or
establish that source data is true in the real world. See [agent details](AGENTIC_RAG.md).

## Trust and operational boundaries

- Catalogue text is untrusted data, never an instruction source. UI text is escaped; external image
  and source links use HTTPS host allowlists. Images can still fail or require third-party requests.
- Gemini receives the question, supplied context, and at most five retrieved products. Avoid private
  input. Provider data-use rules apply; credentials stay in private environment variables.
- Provider network errors are sanitized. Gemini has no automatic provider fallback or HTTP retry.
  Free-tier confirmation is an operator attestation, not a billing safeguard.
- `/health` checks component readiness. The product probe checks ingestion metadata, catalogue hash,
  row count, and one readable product. It is not a full row/vector audit or a remote LLM quota check.
- Default mock mode makes query readiness false while search/products can remain usable. A degraded
  overall status therefore does not necessarily mean the website cannot search.
- Compose binds UI/API to localhost, keeps PostgreSQL internal, uses persistent named volumes,
  mounts catalogue/indexes read-only, and runs the app as a non-root user. The sample database
  credentials are local-demo defaults, not production secrets or deployment guidance.
- No authentication, connection-pooling framework, public deployment, or concurrent-load guarantee
  is included. Dependencies use ranges rather than a full lock; initial model downloads need internet.

## Why these choices

BM25 gives transparent lexical matching; MiniLM adds a compact semantic signal. Keeping constraints
and verification deterministic makes failures testable and explainable. LangGraph expresses a few
bounded routes instead of an open-ended autonomous loop. Streamlit keeps the portfolio small while
FastAPI preserves a separate, testable interface.

Earlier laptop and rejected-phone audit modules remain as historical evidence. They are not part of
the serving data path. The [decision log](DECISIONS.md) records alternatives; [setup](SETUP.md)
explains how to recreate the active path without redistributing the data.
