# Phase 8 release preparation

Draft prepared on 2026-09-19 for a proposed **v0.1.0 portfolio release**. This file is not a tag,
published release, or claim that Phase 8 has been committed. The package remains `0.1.0.dev0`.

## Draft release notes

SearchRank-AI demonstrates evidence-grounded smartphone search and comparison over a locally
generated, audited 3,062-product historical catalogue.

- Deterministic data cleaning, URL-derived product identity, and source-linked evidence.
- BM25, pinned MiniLM semantic, and normalized hybrid retrieval with strict Python filters.
- Transactional PostgreSQL/pgvector storage and a bounded, verified LangGraph query workflow.
- FastAPI endpoints and a shopping-style Streamlit interface with a three-phone shortlist.
- Optional Gemini integration; ordinary search/comparison work without paid API access.
- Docker Compose for local services, offline regressions, reviewed evaluation cases, and setup,
  architecture, demonstration, measured-results, and interview documentation.

Retrieval and scripted-agent results were rerun on 2026-09-18. Hybrid alpha 0.25 reached MRR@10
0.950 and NDCG@10 0.928558 on 20 reviewed development queries. All 16 scripted workflow cases
passed. These are not held-out retrieval estimates or real-model accuracy claims. See
[results and conditions](RESULTS.md).

Data, generated indexes, model caches, credentials, and database volumes are not release assets.
Users must separately obtain the source data and recreate the artifacts using [setup](SETUP.md).
Historical prices, incomplete specifications, external images, variable provider quotas, and a
small development benchmark limit the demonstration. The app is not hardened for public production.

## Local verification

Recorded on 2026-09-19:

- Full offline suite: **389 passed, 10 intentionally skipped**, in 32.00 s. The skips cover four
  HTTP service cases, five real-provider cases, and one direct PostgreSQL integration case.
  One existing Starlette/AnyIO deprecation warning remains; no failed assertions.
- Ruff lint, formatting (73 Python files), dependency consistency, and Git whitespace checks passed.
- All inline Markdown local file links passed the release check across **83** tracked/non-ignored
  candidate files. No generated-data/environment-path, oversized-file, or recognized-secret
  findings. Candidate content is under 1 MB; no file exceeded the 2 MB review threshold.
- A separate read-only scan of **191 reachable Git history blobs** found no matches for the same
  recognizable credential/private-key patterns. All 191 decoded as UTF-8. This does not prove
  arbitrary credentials are absent or inspect unreachable objects or remote-only history.
- Git reported 328 loose objects using 738 KiB, no packs and no garbage. Nothing was deleted or
  history-rewritten. Historical audit code/documents are deliberately retained as decision evidence.
- Fresh 2026-09-18 retrieval aggregates and alpha selection matched the Phase 7 report exactly;
  all 16 scripted workflow scenarios passed again. The recorded API example used the real
  catalogue through an in-process test, not a live container.

No new live-provider request, clean-machine install, or production deployment is implied.
The last historical full HTTP-enabled suite passed 384 tests on 2026-09-17; it is not a fresh
Phase 8 service result. The local server port was unavailable when checked on 2026-09-18.

The read-only `scripts/check_release.py` checks tracked plus non-ignored candidate files for
unpublishable generated/environment paths, files above a 2 MB review threshold, several recognizable
credential/private-key formats, and inline Markdown links to publishable local files. It never
prints matched credential values. This is a bounded heuristic check, not a comprehensive secret
scanner or security audit. It does not check remote URL availability, heading anchors, or history.

## Publication checklist — separate approvals required

- [ ] Review the Phase 8 diff and approve its commit(s).
- [ ] Push the approved phase branch and open its pull request.
- [ ] Review and explicitly approve merging the pull request.
- [ ] Approve the package-version change from `0.1.0.dev0` to `0.1.0`, updating both
  `pyproject.toml` and `src/searchrank_ai/__init__.py`, with tests before committing it.
- [ ] Verify clean/up-to-date main, matching version metadata, tests, and final release notes.
- [ ] Explicitly approve creation of the `v0.1.0` tag and GitHub release at the verified commit.

No tag/release is created by phase approval alone. A code license has not been selected; choose one
only through a separate user decision if open-source reuse is intended. A dataset publisher's CC0
label does not license this repository's code, and its conflicting usage note remains unresolved.
Do not attach raw or processed data to a release to work around that issue.

The release checklist is intentionally unfinished until those external/version actions are approved.
Live Amazon/Flipkart/other retailer integration remains deferred and is not part of these notes.
