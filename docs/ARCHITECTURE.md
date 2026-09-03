# Architecture

## Current architecture

The approved application domain is smartphones (changed from laptops on 2026-09-03). The Phase 0
foundation contains a Python package boundary, validated environment configuration, shared logging,
and smoke tests. Phase 1 has added local suitability-audit paths:

```text
Unchanged local ZIP -> streamed CSV inventory -> exact laptop-category records
                    -> deterministic title/numeric/ID probes -> local review artifacts
```

`data_audit.py` handles streaming, validation, counts, provenance, and artifact output.
`audit_titles.py` estimates title-field coverage and flags uncertainty; it is not a production
cleaner or product schema. Original records remain separate from derived findings. No audit step
executes catalogue text, calls an LLM, downloads images, or checks live product pages.

The retained flow above belongs to the rejected laptop source. The rejected Amazon smartphone
candidate follows this audit-only path:

```text
Unchanged phone ZIP -> all six-column CSV records -> phone_titles evidence probes
                    -> numeric / direct-or-sponsored URL checks / duplicate groups
                    -> report.json + records.jsonl + deterministic samples.json
```

`phone_audit.py` preserves all records and reports duplicate-field conflicts without selecting or
deleting rows. `phone_titles.py` separates explicit capacities from unlabelled pair hypotheses,
flags expansion/virtual-RAM uncertainty, and assigns review categories. Unknown remains unknown.
These modules are audit tools, not the final product schema or production cleaning pipeline.

The adopted 91mobiles path is:

```text
Unchanged 17-column ZIP -> schema and source-hash validation -> explicit field parsers
                        -> evidence-based eligibility reasons -> 18-field core catalogue CSV
                        -> report.json + records.jsonl + deterministic samples.json
```

`mobile_catalogue.py` validates all rows before writing, derives stable IDs from unique source URL
slugs, normalizes only explicit units/scales, rejects capacity-evidenced feature phones and
announced products, and refuses output overwrites or duplicate product IDs. The audit JSONL retains
every raw value. The generated catalogue excludes `spec_score`, `antutu_score`, `awards`,
`expert_rating`, and `store` as instructed. See [the catalogue audit](MOBILE_CATALOGUE_AUDIT.md).

No search or RAG request path exists yet. Phase 2 can consume the generated catalogue only after
its own explicit approval.

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
