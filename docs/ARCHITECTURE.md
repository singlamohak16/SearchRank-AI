# Architecture

## Current architecture

Phase 0 contains only a Python package boundary, validated environment configuration, shared
logging setup, and automated smoke tests. No search or RAG request path exists yet.

## Target request flow

```text
User
  -> Streamlit demonstration
  -> FastAPI backend
  -> one bounded LangGraph workflow
       -> catalogue search tool (BM25, semantic, or hybrid + strict filters)
       -> product details tool
       -> evidence verification tool
  -> grounded answer with product-ID citations

Storage: PostgreSQL + pgvector
```

The workflow will use an LLM only for request understanding, essential clarification, one bounded
query reformulation, and grounded response generation. Price, RAM, storage, rating, brand filters,
and deterministic evidence checks will remain ordinary Python logic.

## Planned component boundaries

- **Data:** schema, cleaning, provenance, and reproducible ingestion.
- **Retrieval:** independently measurable BM25, semantic, and hybrid implementations.
- **Storage:** product records and embeddings with traceable identifiers.
- **Workflow:** state and conditional routes with explicit retry/tool-call limits.
- **Providers:** configurable LLM interface plus a deterministic test double.
- **API:** validation and orchestration without presentation logic.
- **UI:** a single demonstration page that calls the API.
- **Evaluation:** reviewed scenarios, reproducible metrics, and documented failure cases.

These are target boundaries, not claims about completed functionality.

