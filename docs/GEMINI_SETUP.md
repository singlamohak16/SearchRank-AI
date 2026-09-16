# Optional Gemini integration (approved before Phase 8)

The user approved this extension on 2026-09-14. It does not start Phase 8. Git commits, pushes,
and publication require separate approval. Phases 0–7 remain merged; the integration was developed
on `phase/07-gemini-integration`.

## Why this provider

The user requires no paid API usage. AI Studio showed **Free tier** for the dedicated SearchRank-AI
project before live requests were sent. A masked suffix comparison confirmed the saved user key
belonged to that project; the full key was neither displayed nor written to the repository.

The selected model is `gemini-3.1-flash-lite`, using the Gemini Developer API's `generateContent`
endpoint. Google lists standard text input/output in its free tier and supports structured output.
Free availability and quotas depend on the project, region, and current provider policy.

- [Model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite)
- [Pricing and data-use conditions](https://ai.google.dev/gemini-api/docs/pricing)
- [API reference](https://ai.google.dev/api/generate-content)

Do not enable billing. The application cannot enforce Google's billing state or promise that a
model remains free. `SEARCHRANK_GEMINI_FREE_TIER_CONFIRMED=1` is an explicit operator confirmation,
not a billing check, spending cap, or bypass of Google's quotas. If billing is enabled later, stop
the app and re-evaluate this setup before more requests. There is no automatic model/provider
fallback or HTTP retry, including on quota errors.

## Private configuration on Windows

Create a dedicated key in AI Studio and store it as a **User environment variable** named
`GEMINI_API_KEY`. Never paste the key into chat, source files, screenshots, or commits. Environment
variables are not encrypted storage; local administrators and Docker administrators may inspect
process/container environments. Do not share full Docker inspection or resolved Compose output.

The application reads these process environment settings:

```text
SEARCHRANK_LLM_PROVIDER=gemini
SEARCHRANK_LLM_MODEL=gemini-3.1-flash-lite
SEARCHRANK_GEMINI_FREE_TIER_CONFIRMED=1
GEMINI_API_KEY=<private environment variable, not a repository value>
```

OpenAI continues to use `SEARCHRANK_LLM_API_KEY`; it never falls back to the Gemini credential.
The default remains `mock`, so cloning the repository does not make live calls automatically.
Python does not load `.env` automatically. Compose can load `.env`, but the Windows helper avoids
placing credentials in this OneDrive-backed working folder.

With Docker Desktop running and the existing catalogue/index/database setup available:

```powershell
# First run after changing code: builds the new image and starts the existing local stack.
.\scripts\start_gemini.ps1 -FreeTierConfirmed -Build

# Later starts using the same image:
.\scripts\start_gemini.ps1 -FreeTierConfirmed
```

The helper loads the saved key into the child process environment, restores its previous process
settings afterward, and neither persists nor prints the secret. Only the API service receives the
Gemini key; the UI and ingestion service do not. API/UI remain bound to localhost. Existing
database volumes and catalogue files are retained; this script does not ingest or delete data.
Open http://127.0.0.1:8501/ and choose the agent-query tab.

Health reports local component readiness, not remote credential/quota validity. A real request is
required to check the latter. Agent queries have a separate 90-second UI timeout; ordinary
search/health calls retain 30 seconds. Each Gemini HTTP operation has a 25-second socket timeout;
these are I/O timeouts, not a strict end-to-end deadline.

## Data and correctness boundaries

The provider receives the user's question, supplied conversation context, and up to five retrieved
product records—not the full catalogue. Google's free-tier data-use terms apply; do not enter
confidential or personal material. No hosted search, file uploads, caches, or paid tools are enabled.

The provider reuses application-owned analysis/generation prompts and JSON schemas. Gemini-specific
analysis schemas restrict interpreted criteria to the application's supported keys; unsupported
criteria require clarification or refusal. Answer schemas bind criteria to their allowed field
and direction, bind product/source pairs to retrieved evidence, and disallow comparisons for a
search-only request. These formatting constraints do **not** prove correctness.
For directional criteria, Python also checks the whole retrieved group for a unique numeric winner.
A tied or missing value excludes that sole-winner claim from the schema and asks for factual values
or unavailable-information entries instead. The current answer format does not have a dedicated
tie conclusion; equal values are displayed as cited facts. No tie is silently broken by rank.
Python still enforces catalogue filters, product lookup, citation identity, numeric comparisons,
and missing-information checks. Failed verification withholds claims, rather than weakening rules.

The transport has a fixed HTTPS destination, a header-only credential, no redirects, one candidate,
4,000 output tokens, minimal thinking, and a one-megabyte response-size limit. Blocked, truncated,
malformed, and non-object results fail closed. HTTP/network failures return a sanitized API 503
without logging upstream response bodies or keys. A 429 asks the user to wait/check quotas, not pay.

## Verification and limitations

Offline tests cover configuration, credential isolation, shared prompts, exact criteria, missing
keys, rejected models, timeout/HTTP failures, redirects, malformed outputs, and API error mapping.
Live tests are opt-in and never part of the ordinary offline run:

- `SEARCHRANK_RUN_GEMINI_INTEGRATION=1`: one real constraint-extraction request.
- `SEARCHRANK_RUN_GEMINI_APP_INTEGRATION=1`: three requests through the API boundary using the
  local catalogue and PostgreSQL (search, comparison, unsupported). These can use multiple LLM calls.

Both require explicit Gemini configuration and free-tier confirmation. The separate OpenAI smoke
test remains disabled. Tests print no credential. These are small smoke checks, not a new measured
agent-quality benchmark and not evidence of production reliability.

### Recorded development findings (2026-09-14)

- The first documented candidate, `gemini-2.5-flash-lite`, returned HTTP 404 on generation despite
  appearing in the model list. No automatic fallback was added. An explicitly selected
  `gemini-3.1-flash-lite` minimal request succeeded, followed by a passing constraint-extraction test.
- The first full workflow run had two failures and one pass: a rejected search request and a
  comparison rejected by the verifier for an unapproved criterion; unsupported-question routing
  passed. The comparison schema/instructions were tightened without changing the verifier.
- Subsequent comparison runs failed on criterion mismatches. Focused diagnostics showed invented
  labels (`price_inr_lower`, `user_rating_5_higher`) from request analysis, so the analysis schema
  was constrained to existing policy keys. A following run exposed citation mismatch, addressed by
  adding the exact retrieved product/source pairs to generation schemas. One diagnostic attempt
  received upstream HTTP 503. These failures are retained as evidence of free-provider limitations.
- Early offline test mistakes (mapping access, oversized generated test IDs, and a reserved pytest
  parameter name) were corrected before final validation. No production behavior was weakened.

### Continuation findings (2026-09-16)

- AI Studio still showed Free tier for SearchRank-AI. Docker's recurring stale-socket startup
  failure was recovered by preserving its two temporary directories under timestamped backup
  names. Database volumes were not deleted or re-ingested.
- Initial live search and unsupported-request checks passed; comparison failed on citation
  mismatch. Diagnostics showed five compared IDs but only two citations. Explicit per-product
  citation instructions corrected this without changing the evidence verifier.
- The next failure exposed a genuine rating tie: Galaxy M36 and M35 both had 4.3 in retrieved
  evidence, but Gemini proposed a sole winner. Generation schemas now exclude tied sole-winner
  criteria and restrict unique winners using Python; factual ratings remain required in the test.
- The original smoke assertion incorrectly demanded two sole-winner comparisons despite that tie.
  It now independently checks each requested criterion: a full-group comparison for a unique
  winner, or every retrieved product's verified factual value and no winner claim for a tie.

### Final validation (2026-09-16)

- Offline host suite: **359 passed, 10 skipped**. Skips cover opt-in HTTP, Gemini, OpenAI, and direct
  PostgreSQL checks; the live runs below are separate.
- Real Gemini + catalogue + PostgreSQL workflow: **3 passed** (search, comparison including tied
  ratings, unsupported request). Observed query times were 10.34 s, 25.06 s, and 11.43 s respectively.
- Rebuilt API/UI images and started them using the helper with the saved environment key. Installed
  adapter source hash matched the tested local source; API runtime UID was 999. The database was
  preserved, API/UI remained loopback-only, and all three health components reported ready.
- Host suite with actual API/UI HTTP checks enabled: **363 passed, 6 skipped**. Those six opt-ins
  were not enabled in this host invocation; this does not negate the separate three-case live run.
- Installed-package regression suite in a disposable Linux container, without Gemini credentials:
  **131 passed**, dependency consistency passed. No source-code override was mounted for this run.
- Browser check through Streamlit's Ask / Compare form: the Samsung price/rating query returned
  `answered`, zero retries, ten verified facts, one verified price comparison, and no verification
  issues. Both 4.3 ratings were shown as facts; no sole highest-rating winner was invented.
- Ruff lint/format checks, PowerShell syntax, Compose configuration, and Git whitespace checks
  passed. The saved credential was absent from all 18 changed/new project files.
- One Starlette/AnyIO deprecation warning remains in the test runs. It did not fail tests. Ordinary
  pip script-path/root-build notices are not runtime failures; the serving application is non-root.

Free-tier quota limits and intermittent upstream failures still apply. These successful examples do
not guarantee every natural-language query will produce a verified answer.
