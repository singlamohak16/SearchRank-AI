# Amazon India smartphone suitability audit

Date: 2026-09-03. Status: audit complete; **do not adopt this source as the primary catalogue**.
The user approved the change to smartphones and this source's download/audit. The smartphone scope
remains approved. Phase 1 was later completed with the different
[91mobiles source](MOBILE_CATALOGUE_AUDIT.md); this report remains rejection evidence only.

## Verdict

The preview-based recommendation was too optimistic about usable scale. The 2,805 distinct ASINs
are mixed-product identifiers, not 2,805 smartphones. Most records are accessories. Conservative
rules identify 450 unique smartphone candidates, and only 260 with explicit RAM/storage plus valid
price/ID/source evidence. Allowing inferred, unlabelled RAM/storage pairs raises that tentative
core to 360. These are audit-rule outputs, **not manually verified usable-product counts**.

This source solves the previous dataset's mixed-language problem but does not meet the preferred
2,000–5,000 smartphone scale or provide a strong roughly 1,000-product fallback. No missing facts
were fabricated to enlarge the catalogue. Do not resume production cleaning on this source without
a deliberate user-approved compromise.

## Source and preservation

- [Publisher card](https://www.kaggle.com/datasets/prothomeshmistry/amazon-big-billion-sale-22-2025-mobile-phones).
- Download endpoint: `https://www.kaggle.com/api/v1/datasets/download/prothomeshmistry/amazon-big-billion-sale-22-2025-mobile-phones`.
- Publisher-listed licence: MIT. The archive contains one CSV and no separate licence file.
  Source attribution is retained; no source rows are committed or redistributed.
- Downloaded on 2026-09-03; publisher/file labels describe a 2025 sale snapshot. Not current prices.
- Preserved archive: `data/raw/amazon_india_phones_2025/source.zip`, 331,607 bytes.
- CSV member: `Amazon Big Billion Sale 2025 -Oct Mobile Phones.csv`, 2,559,377 bytes.
- SHA-256: `11e590bccf3142298ed58d68050ccdc2e69710ff5fc9a451d5e4e8f231ca3c31`.
- Downloading the latest endpoint is not a version pin. The hash identifies the actual audited file.

Raw bytes were unchanged before/after the audit. Both this archive and the earlier laptop archive
remain local and ignored. No retailer pages, images, reviews, or additional datasets were fetched.

## Full-file inventory

The exact six-column schema is `Product_Name`, `Price`, `Rating`, `Review_Count`, `ASIN`, `Product_URL`.
No separate brand, model, RAM, storage, processor, battery, camera, or description columns exist.

| Check | Actual result |
| --- | ---: |
| CSV records | 3,529 |
| Distinct ASINs | 2,805 |
| Distinct exact titles | 2,792 |
| Distinct original URLs | 3,529 |
| Repeated-ASIN groups | 705 |
| Excess rows beyond one per ASIN | 724 |
| Fully identical six-field duplicate rows | 0 |
| Valid positive numeric prices | 3,510 |
| Missing prices (`N/A`) | 19 (0.54%) |
| Valid numeric ratings, 1–5 | 3,452 |
| Missing ratings (`N/A`) | 77 (2.18%) |
| Valid nonnegative integer review counts | 3,529 |
| ASIN format / source-ID checks passed | 3,529 |
| Sponsored URLs decoded locally | 54 |
| Titles containing Devanagari | 0 |

All repeated-ASIN groups differ **only in the URL**; the other five fields agree within each group.
The differing URLs contain search/referral parameters. This is useful future deduplication evidence,
but the audit does not delete records or choose a representative.

All 54 sponsored URLs contain a single same-origin relative destination with the matching ASIN.
The audit decodes that stored destination without requesting it, then derives a canonical Amazon
India URL while preserving the original. URL syntax/ID agreement is not a live availability check.

The full-file price minimum/median/maximum is INR 39 / 299 / 179,999. There are 2,944 positive
prices below INR 3,000. Sampled INR 299/284 records are covers, cases, and holders, not low-cost
smartphones. The price threshold is only a review flag, never an automatic price correction.

## Category and specification findings

Categories below are mutually exclusive **review buckets**, not ground-truth product classes.
Accessory mentions in a phone bundle may trigger the same bucket as standalone accessories;
other-device keywords may refer to a compatible device rather than the item sold.

| Review bucket | Rows | Unique ASINs |
| --- | ---: | ---: |
| Accessory or bundle keywords | 2,711 | 2,084 |
| Smartphone candidates | 490 | 450 |
| Keypad-phone keywords | 69 | 65 |
| Other-device keywords | 30 | 20 |
| Unresolved | 229 | 186 |
| Total | 3,529 | 2,805 |

76.82% of rows trigger accessory/bundle review. Unresolved examples include feature phones,
chargers, gaming coolers, and some smartphones with unfamiliar names or capacity notation.
The classifier is intentionally not presented as a complete smartphone-labeling system.

| Tentative candidate tier | Rows | Unique ASINs | Rated unique ASINs |
| --- | ---: | ---: | ---: |
| Smartphone-candidate bucket | 490 | 450 | 438 |
| Explicit RAM/storage + price/source evidence | 291 | 260 | 251 |
| Including inferred unlabelled RAM/storage pairs | 391 | 360 | 350 |

The last two tiers have no current price/renewed/ambiguity flags. Absence of a flag does not prove
the listing is correct. Missing ratings remain unavailable; zero review counts are not invented
feedback. No device's physical specifications were checked against an external manufacturer.

Important limitations found in source text:

- Apple examples often state storage without RAM; the audit does not infer RAM from model names.
- Unlabelled pairs such as `8GB+128GB` are hypotheses, not explicit installed-RAM facts.
- Virtual/dynamic/expanded RAM wording and `8+8*GB` expressions need careful treatment; they do not
  become 16 GB physical RAM.
- ASIN `B0B3CZ7P4V` labels both 12 GB and 256 GB as storage. The audit leaves the conflict unresolved
  rather than silently changing the first label to RAM.
- Bundles, shorthand, misspellings, brand aliases, and unsupported capacity formats cause conservative
  exclusions. These gaps cannot plausibly justify calling the full mixed-product file a phone catalogue.
- Camera megapixels, battery capacity, marketing claims, and CPU names are retained only as raw text;
  this audit does not infer camera quality, runtime, or gaming performance.

## Reproduction and verification

From the project directory, with the existing environment:

```powershell
.venv\Scripts\python.exe -X utf8 -m searchrank_ai.phone_audit --archive data/raw/amazon_india_phones_2025/source.zip --output-dir artifacts/phone_audit/new-run
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
```

Use a new output directory on each run. Outputs are `report.json`, `records.jsonl`, `samples.json`,
and `duplicate_groups.json`. Every original field and CSV record number is retained in JSONL;
derived evidence is separate. Invalid schema/malformed rows fail instead of disappearing silently.

Recorded validation: Windows 11 build 26200, Python 3.12.13. On 2026-09-03, the suite produced
**110 passed in 0.41 seconds**; Ruff lint and formatting checks passed; dependency consistency passed.
Tests use synthetic data, including missing/sentinel values, untrusted URLs, sponsor destinations,
ambiguous memory, accessory/bundle cases, prompt-injection text, malformed files, duplicate conflicts,
raw preservation, and deterministic reruns. No LLM or embedding model was used.

Full-source runs `run2` and `run3` matched on every report field except run metadata and produced
byte-identical records, samples, and duplicate-group files. Category totals, rating counts, and
unique-plus-excess ID counts each reconcile to 3,529. The archive hash also matched.

Fixed-seed (20260903) samples were inspected: 20 rows from each of the five review buckets plus
20 explicit-core rows, with possible overlap between samples. The explicit-core sample agreed with
the stored title evidence. This is a spot check, not an independent accuracy benchmark. The keyword
rules intentionally leave unresolved cases and retain phone bundles in review.

## Next decision

Keep the approved smartphone domain, but choose another source or explicitly accept a much smaller
catalogue. Prefer genuine distinct devices/variants and structured evidence over advertised row
counts. Dataset adoption, production schema, cleaning, and Phase 1 completion remain pending.
No commit, push, remote change, or later-phase work was performed.
