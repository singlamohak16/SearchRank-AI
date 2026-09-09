# Agentic RAG workflow and evidence tools

Date: 2026-09-08. Phase 5 implementation and local validation record.

Updated: 2026-09-09 after review of PR #6. The three verification fixes are complete locally.

## Purpose

Phase 5 connects request understanding, the measured Phase 3 retriever, and Phase 4 product-detail
storage through one bounded LangGraph workflow. The graph uses an LLM only for request
interpretation, one optional search reformulation, and selection of answer facts. Deterministic
Python still owns strict constraints, product lookup, numerical comparison, citations, and the
decision to release or reject proposed claims.

## Workflow

```text
request
  -> analyze request
       -> clarification -------------------------------> stop
       -> unsupported information ---------------------> stop
       -> conflicting constraints ---------------------> stop
       -> catalogue search
            -> no result -> reformulate once -> search
            -> still no result ------------------------> stop
            -> product details
                 -> strict constraint violation -> verify evidence -> reject
                 -> search answer generation -----\
                 -> comparison generation ---------+-> verify evidence -> answer or reject
```

Search and comparison use distinct generation nodes. A “best” request without an explicit
criterion is routed to clarification. Included and excluded brand conflicts are rejected before a
search. A comparison that resolves to fewer than two stored products is qualified instead of being
invented.

The graph records its visited nodes, tool calls, retry count, retrieved product IDs, missing IDs,
constraints, and verification result. One request may make at most four tool calls. It may
reformulate an unsuccessful search only once, so there is no open-ended model/tool loop.

## Three tools

1. `CatalogueSearchTool` passes the normalized query, selected retrieval mode, measured hybrid
   alpha, result limit, and typed `SearchConstraints` to the existing retriever. Price, RAM,
   storage, rating, and brand rules remain deterministic.
2. `ProductDetailsTool` accepts product IDs through a small repository protocol. `PostgresStorage`
   already satisfies that protocol and returns complete stored rows plus explicit missing IDs.
3. `EvidenceVerificationTool` compares proposed field values and citations with retrieved
   `StoredProduct` records. It verifies numerical higher/lower conclusions only when the criterion
   was explicit and the selected winner follows the stored values.

Catalogue strings are never instructions to these tools. A product name or processor value that
says to ignore rules is handled as an ordinary string. It cannot create a tool call, change a
constraint, or make a false value pass verification.

## Grounded response contract

The provider returns a structured answer-advice object rather than unrestricted prose:

- factual claims contain a product ID, catalogue field, proposed value, and product/source URL;
- numerical comparisons contain all product IDs, an explicit criterion, direction, selected
  product, and citations;
- unavailable items are structured `product_id`/`field` pairs, not prose.

The verifier rejects unknown products, non-catalogue fields, missing or mismatched values,
incorrect URLs, unsupported comparison fields, missing criteria, ties presented as a unique
winner, and incorrect numerical conclusions. The final Markdown response is rendered from verified
stored values rather than copying arbitrary generated sentences. It labels catalogue facts,
derived conclusions, and unavailable information separately.

### Review fixes: missing information, stored constraints, and comparison intent

Every proposed missing-information item must reference a retrieved product and a recognized field.
For collected fields, the stored value must be null. For uncollected attributes, a fixed allowlist
currently supports weight, rating count, live price, stock availability, and warranty. These are
labels for unavailable information, not new catalogue columns or inferred values. The verifier
rejects arbitrary strings, unknown IDs/fields, and values incorrectly described as missing. Only
`VerificationReport.verified_unavailable` is rendered, using fixed wording and stored citations.
The provider's JSON schema and parser both require objects instead of the former string list.

Database records may differ from local retrieval artifacts. The workflow rechecks all stored
records with the original `SearchConstraints` before asking the provider for a draft. Any violation
routes directly to the evidence-verification tool and returns `verification_failed`; it does not
silently relax filters or generate an answer. The verifier also checks these constraints itself.
This preserves the existing four-tool ceiling. A changed value that still satisfies the constraints
may be used and cited from storage; the check does not assert identical catalogue snapshots.

`evidence_policy.py` binds each recognized comparison criterion to a numeric field and, when
directional, a required direction. For example, `lowest price` requires `price_inr`/`lower`,
`highest rating` requires `user_rating_5`/`higher`, and `smallest display` requires
`display_inches`/`lower`. Neutral criteria such as `price` permit either factual direction without
claiming an overall preference. Unknown criteria or incorrect field/direction combinations fail
verification. The provider receives this policy and is instructed to preserve directional intent
when normalizing criteria; natural-language interpretation still depends on the provider.

## Providers and secrets

`LLMProvider` is an application-owned interface. `MockLLMProvider` is scripted and network-free,
which makes route and safety tests deterministic. `OpenAIResponsesProvider` is an optional real
adapter using the Responses API with strict JSON-schema output, `store=False`, and catalogue data
delimited inside a JSON input. The developer instructions explicitly state that catalogue strings
are untrusted.

The mock is the default. To opt into a real provider, keep credentials outside Git and set values
locally:

```powershell
$env:SEARCHRANK_LLM_PROVIDER = "openai"
$env:SEARCHRANK_LLM_MODEL = "a structured-output-capable model available to your account"
$env:SEARCHRANK_LLM_API_KEY = "your-local-secret"
```

No key or model is hard-coded. The provider factory refuses an unknown provider or an OpenAI
configuration missing either value.

## Tests

The Phase 5 tests cover:

- search, comparison, clarification, unsupported, conflict, and no-result routes;
- distinct search and comparison paths;
- one successful and one unsuccessful bounded reformulation;
- the four-call maximum on the longest successful path;
- strict constraint forwarding;
- complete details and explicit missing IDs;
- exact values, dates, citations, missing evidence, criteria, and numerical winners;
- malicious instructions embedded in catalogue fields;
- structured, non-stored OpenAI request construction;
- configuration errors and network-free mock behavior.

The 2026-09-09 review-fix run produced 70 passing focused tests and 261 passing repository tests;
the two optional live integrations were skipped. New cases cover raw-text bypasses, malformed
missing-information objects, unknown IDs/fields, falsely missing values, valid missing values and
citations, every strict filter against changed database records, valid changed records, every
comparison-policy entry, reversed direction, wrong fields, and unsupported criteria.

Run the normal offline suite with:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

The optional live-provider smoke test requires a real key, model, and an explicit cost-bearing opt
in:

```powershell
$env:SEARCHRANK_RUN_LLM_INTEGRATION = "1"
.venv\Scripts\python.exe -m pytest -m integration tests\test_llm_integration.py -q
```

The live LLM test was not run during Phase 5. No provider-quality or latency result is claimed.

## Limitations

- Phase 5 exposes a Python service boundary, not a CLI, API, or interface; Phase 6 will wire it into
  FastAPI and Streamlit.
- Only stored numerical fields support deterministic higher/lower conclusions. Processor and
  camera text can be cited as facts but are not automatically ranked as “better.”
- The mock tests establish control-flow and evidence guarantees, not real-model classification or
  writing quality.
- The Phase 3 retrieval benchmark remains only 20 cases. Broader agent scenarios and metrics belong
  to Phase 7.
- A running PostgreSQL/pgvector database and local retrieval artifacts are still required for a
  complete production assembly.
