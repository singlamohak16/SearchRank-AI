# Pre-Phase-8 UI/UX redesign

Approved as a separate local extension after Phase 7 and Gemini integration, not as Phase 8.
Implemented on `phase/07-ui-redesign` on 2026-09-16; final validation continued on 2026-09-17.

## What changed

The interface keeps Streamlit and the existing FastAPI contracts. It now presents the catalogue
as a shopping-style search and comparison experience, without pretending to be a live shop.

- **Discover:** example searches, a submitted search form, budget/RAM/storage/rating presets,
  optional custom minimums, include/exclude brands, and advanced retrieval settings. Six product
  cards per page show catalogue images, names, prices, RAM, storage, ratings, and source links.
- **Compare phones:** a session-local shortlist of up to three products, preserved across searches.
  Stored specifications appear side by side; missing values remain "Not available". Selection,
  removal, clearing, and pagination do not repeat a search or call an LLM.
- **Ask AI:** an explicit question form, optional bounded context, provider-privacy notice,
  waiting/error states, and a persistent answer. A verification badge appears only for an
  `answered` response whose evidence verification passed. Sources and workflow details remain
  available in an expandable panel.

The visual treatment uses a light background, blue actions, rounded product cards, labelled native
controls, and stacked mobile layouts. The comparison table scrolls within its own keyboard-focusable
region. A static empty state explains what to do without issuing searches on page load.

## Request and state boundaries

Search requires **Find phones**. Example buttons only prefill text. Presets and optional custom
values are sent to the existing deterministic filters; custom values override presets, including
explicit zero. Changing controls does not silently alter already displayed results: the submitted
query and applied filters remain visible. A new failed or blank submission clears the old result
to avoid presenting it as the new answer. The same rule applies to failed AI submissions.

Visible cards fetch product details through the existing API for image URLs. Successful detail
lookups are cached per session; a new search retains only shortlisted cached records before fetching
its visible results. Details are not fetched for every catalogue product. Missing details do not
prevent basic search cards or shortlist comparisons from displaying.

No retrieval, database schema, catalogue, model adapter, ranking, or verifier was changed. No new
dependency, account, checkout, cart, payment, authentication, or public deployment was introduced.

## Untrusted content and images

All catalogue text in HTML templates is escaped. `st.html` renders controlled templates and CSS;
model text remains ordinary Markdown with unsafe HTML disabled. Source links are restricted to
HTTPS `91mobiles.com` / `www.91mobiles.com`; image URLs to HTTPS `91-img.com` / `www.91-img.com`.
Credentials, nonstandard ports, control characters, and other hosts are rejected.

Images load directly in the browser with lazy loading and no referrer. The UI server does not fetch
arbitrary image URLs. Image hosts can still see normal browser network information, including the
client IP. Missing or rejected URLs receive a neutral placeholder; an allowed URL that later breaks
may show the browser's unavailable-image indicator. Source-host availability and image rights remain
external limitations; no images are fabricated or copied into the repository.

Prices and specifications are historical catalogue snapshots, not current stock, discounts, or live
offers. Ratings have no review counts. The manual comparison table declares no overall winner.

## Run or refresh the local UI

With the existing API running at port 8000:

```powershell
$env:SEARCHRANK_API_URL = "http://127.0.0.1:8000"
.venv\Scripts\python.exe -m streamlit run src\searchrank_ai\streamlit_app.py --server.address=127.0.0.1 --theme.base=light --theme.primaryColor="#205ce4" --browser.gatherUsageStats=false
```

For an already-running Compose stack, refresh **only the UI**:

```powershell
docker compose build ui
docker compose up -d --no-deps ui
```

Then open `http://127.0.0.1:8501/`. This preserves the running API's provider environment and the
database volume. Do not recreate the API from a shell lacking its Gemini configuration; use the
private-key startup procedure in [GEMINI_SETUP.md](GEMINI_SETUP.md) when an API restart is needed.

## Recorded validation

- Automated tests cover explicit submissions, custom and preset filters, shortlist limits,
  cross-search persistence, cached details, pagination/reset, missing data, empty/error states,
  AI quota errors without retries, context bounds, non-answer badges, and hostile HTML/URL input.
- Full offline suite on 2026-09-17: **380 passed, 10 opt-in integration tests skipped**. Ruff lint,
  formatting, and dependency consistency passed. One existing Starlette/AnyIO
  deprecation warning remains. An initial full run exposed test isolation around Streamlit's cached
  API client; the offline smoke now stubs health explicitly and never depends on a running service.
- Full suite with live HTTP checks against the existing API and redesigned local preview:
  **384 passed, six opt-in tests skipped** on 2026-09-17. This includes three retrieval modes,
  strict numeric/brand filters, product evidence, validation errors, and UI health.
- Desktop browser checks used the real 3,062-record catalogue: Samsung search, six loaded product
  images, selecting/removing phones, comparison specifications, and a three-item selection limit.
- At a **390 × 844** viewport, cards stacked into one column and the document stayed 390 pixels
  wide. The wider comparison table scrolled inside its own region. The desktop viewport was restored.
- A live Gemini request through the redesigned form searched Samsung phones below INR 30,000,
  at least 8 GB RAM and 128 GB storage. The evidence panel showed `answered`, zero retries,
  five verified facts, correct constraints, and no verification issues. This is a smoke observation,
  not a new model-quality or latency benchmark.
- Final packaged-UI handoff on 2026-09-17: the completed Docker image's two UI source hashes
  matched the tested workspace. Recreated only `ui`; API and database container IDs stayed unchanged.
  Runtime dependency consistency passed. Browser search and two-phone comparison worked at port
  8501, and the full suite against the normal API/UI addresses again passed **384 tests, six skipped**.

## Remaining limitations

Shortlists and cached results last only for the current Streamlit session; there are no saved
accounts or cross-device lists. The UI is a local demonstration, not a production ecommerce site.
Native Streamlit controls are retained; CSS selectors may require review after dependency upgrades.
Browser checks cover desktop and one mobile viewport, not every device or a full accessibility audit.
Free-tier Gemini quotas and provider behavior still apply. Phase 8 remains separately gated.
