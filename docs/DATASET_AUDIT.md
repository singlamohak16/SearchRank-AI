# Amazon India dataset suitability audit

Date: 2026-09-03. Status: audit complete; **source rejected by the user for adoption**.

Decision update: the user judged this dataset unsuitable for the intended project. The findings
below are retained as the audit record, not an active adoption recommendation. See
[replacement screening](DATASET_CANDIDATES.md). Raw data and audit code have not been deleted.

## Initial audit verdict, superseded by the rejection above

**Conditionally suitable for a historical laptop-search demonstration, not ready for ingestion.**
The audit identifies 4,702 tentative candidates after basic field checks and two anomaly
flags, including 2,458 with usable numeric ratings. These are coverage estimates, not a certified
count of clean laptops. They suggest the requested 2,000–5,000-product target is feasible without
inventing specifications. Classification, ambiguous capacities, bundles, and source errors still
need attention in the cleaning pipeline.

The major new trade-off is language: 6,923 of 7,023 laptop-category titles contain Devanagari
characters (98.58%). Spot-checks found Hindi and mixed Hindi-English titles. This is a character
presence measurement, not a language-model classification. English-only title filtering would
retain at most 100 category rows and would not meet the target. English user queries against the
original text will need an explicit cross-language retrieval strategy in later approved phases.
No embedding model or translation service has been selected or run.

Recommendation: adopt only if this historical, mixed-language catalogue is acceptable. Preserve
original titles and IDs, use evidenced technical fields, and evaluate cross-language search later.
Do not replace missing values with defaults or translate descriptions into invented product facts.

## Source, attribution, and permitted handling

Contains information from **Amazon India Products 2023 (1.5M Products)**, published by **asaniczka**
on [Kaggle](https://www.kaggle.com/datasets/asaniczka/amazon-india-products-2023-1-5m-products),
listed under the [Open Data Commons Attribution License 1.0](https://opendatacommons.org/licenses/by/1-0/index.html).

The database licence requires attribution and applicable notices. It does not by itself clear
separate rights in individual images, text, or trademarks. Raw data, extracted review records,
and generated artifacts stay local and ignored by Git. Only synthetic fixtures are in the tests;
no product images were downloaded. Review attribution again before public data redistribution
or a hosted demonstration.

This is the downloaded source **as distributed**, not the author's original pre-processed scrape:
the CSV filename itself ends in `processed.csv`. Preserving it unchanged does not certify the
publisher's transformations. The source describes a 2023 catalogue; downloading it in 2026 does
not make its prices, ratings, specifications, or product availability current.

Download used the public Kaggle dataset endpoint, not live retail scraping. The download URL is
not version-pinned; the following hash identifies the exact audited bytes. A future download
must have the same hash to reproduce these findings, otherwise it needs a new audit.

| Source property | Observed value |
| --- | --- |
| Archive | `data/raw/amazon_india_2023/source.zip` |
| Archive size | 114,888,404 bytes |
| CSV member | `amz_in_total_products_data_processed.csv` |
| Uncompressed CSV size | 669,879,462 bytes |
| CSV CRC32, decimal | 3,121,861,463 |
| Total records | 1,589,160 |
| Unique ASINs across the source | 1,589,160 |
| Categories | 214 |

SHA-256:

```text
239fc37b4ad7ca84178b190ee3739e7716a22b4eefea73ef0081ae0d98acaf60
```

The hash matched before and after every full audit. CSV content was streamed directly from the
archive; no second full-size extracted copy was required.

## What the file actually provides

Eleven columns: `asin`, `title`, `imgUrl`, `productURL`, `stars`, `reviews`, `price`, `listPrice`,
`categoryName`, `isBestSeller`, and `boughtInLastMonth`.

There are **no separate brand, RAM, storage, processor, weight, or description columns**. Technical
coverage therefore depends on what is stated in each title. An image URL is not specification
evidence. The audit does not parse images or enrich records from outside sources.

Prices are treated provisionally as INR from the Amazon India source context. The CSV has no
currency column, so this must remain a documented dataset-level assumption in any future schema.
No exchange-rate conversion or price correction was performed. Only `price`, not `listPrice`,
was used for the candidate checks.

## Laptop-category inventory

The scope is the exact category `लैपटॉप` (laptops). Products placed in other categories were not
added to the laptop pool. All-category counts were calculated only to inventory and reconcile
the downloaded file.

| Check | Count out of 7,023 category records |
| --- | ---: |
| Unique ASINs, all syntactically valid | 7,023 |
| HTTPS Amazon India source URLs matching their ASIN | 7,023 |
| Repeated ASIN rows | 0 |
| Repeated exact-title rows beyond the first occurrence | 230 |
| Positive, finite price | 6,837 |
| Zero price, treated as missing | 186 |
| Numeric rating in the range 1–5 | 3,394 |
| Zero rating, treated as missing | 3,629 |
| Title contains Devanagari characters | 6,923 |
| Renewed/refurbished wording recognized | 1,571 |

No blank or invalid price/rating values were encountered in this category beyond the zero
sentinels. Missing ratings affect 51.67% of category rows; missing prices affect 2.65%.
All-source checks found 92,015 zero prices and 779,603 zero ratings.

URL checks validate format and ASIN agreement, **not reachability or current availability**.
Different ASINs with the same title are preserved: they might be variants, bundles, or seller
listings. Matching titles alone do not establish that a record can safely be deleted.

## Title-only coverage and review rules

The small audit parser recognizes explicit Latin/Hindi brand aliases and a limited technical
vocabulary. Normalized matches are kept beside the unchanged raw record in a local review file.
It does not infer a capacity from a processor, model number, brand reputation, or price.

| Field | One recognized value | Missing / unrecognized | Ambiguous |
| --- | ---: | ---: | ---: |
| Brand | 6,277 | 306 | 440 |
| RAM | 5,538 | 1,443 | 42 |
| Storage | 5,326 | 1,411 | 286 |

These columns describe the entire category, including contaminated rows; individual field
coverage is not the final usable-product count.

- Explicit RAM examples include `16GB RAM`, DDR/LPDDR/SDRAM wording, and Hindi equivalents.
  The shorthand `16GB/512GB SSD` is a separate structural interpretation, not an explicit RAM label.
  The report records 4,279 explicit-rule rows, 1,262 slash-pair-rule rows, and 39 upgrade-context
  rows; rule counts are not the same as successful-value counts because conflicts stay unresolved.
- GPU memory such as `4GB RTX3050` or `GDDR6 4GB` is not taken as system RAM.
- Storage needs a capacity and recognized drive type. Multiple drive mentions are unresolved;
  the audit does not invent a total. A recognized internal drive does not include a separately
  bundled microSD card. Unlabelled extra capacities and damaged titles can still require review.
- Storage uses decimal GB-equivalents: 1 TB = 1,000 GB. Original capacity text is retained.
  This is not available formatted disk space. Production storage semantics remain to be finalized.
- Recognized upgrade language is flagged as ambiguous. Unknown language patterns can escape this
  rule; absence of ambiguity is not proof of correct extraction.
- No renewed wording means **condition not established**, not "new". The condition dictionary
  is incomplete and will need review during cleaning.

Review categories are mutually exclusive, tested in desktop, tablet, accessory, candidate, then
unresolved order:

| Heuristic category | Records |
| --- | ---: |
| Candidate with recognized brand, RAM, and storage | 4,831 |
| Accessory keyword, without a complete hardware pair | 406 |
| Accessory or bundle wording with a hardware pair | 39 |
| Desktop keyword or desktop-family wording | 20 |
| Tablet keyword | 2 |
| Other unresolved title | 1,725 |
| Total | 7,023 |

These are **review buckets**, not validated class labels. For example, a laptop bundled with a
bag can enter the accessory/bundle bucket, and a mouse bundle can remain in the candidate bucket.
No raw record was removed or rewritten.

## Candidate funnel

| Successive check | Records |
| --- | ---: |
| Candidate title bucket | 4,831 |
| Plus valid ID/source URL/title and positive price | 4,704 |
| Plus no current anomaly flags | 4,702 |
| Plus a usable numeric rating | 2,458 |

Anomaly flags are deliberately visible review triggers: positive price below 5,000 or extracted
storage below 16 GB. These thresholds do not prove a value is wrong and never replace it. Two
candidate titles state 4 GB SSD capacity; both remain unchanged and flagged, not "corrected" to TB.

The 4,704 core-field candidates have 4,690 different exact titles. Their observed price minimum,
median, and maximum are 9,999, 75,919, and 569,990, respectively. These describe historical source
values, not current market prices or guarantees that the values are accurate.

Of those 4,704 candidates, 1,098 explicitly mention renewed/refurbished condition. Of the 2,458
rated candidates, 349 do so. Excluding these would reduce the rated pool to 2,109 before further
cleaning; it would **not** establish that the remaining records are new. The final catalogue size
must be measured again after condition, bundle, duplicate, and anomaly decisions.

## Spot-check findings, not an accuracy benchmark

The assistant inspected a fixed-seed sample of 40 category rows and a fixed-seed sample of 30
final core-field candidates, plus targeted low-price and low-storage records. The samples may
overlap. Original text and automated findings are retained locally for human review.

Important findings included:

- `B08VJ74CBG`: a laptop skin in the laptop category.
- `B0929H41P3`: a desktop in the laptop category.
- `B01N19HY16`: a 263-price touchpad protector whose title copies laptop RAM/storage. A complete
  spec pair alone did not make it a laptop; it now goes to the accessory/bundle review bucket.
- `B091297MW7` and `B091265WFP`: explicit 4 GB SSD wording; preserved and anomaly-flagged.
- `B09ZNK263F`: a damaged title states a 1 TB HDD and an unlabelled 256 GB fragment. The probe
  sees the labelled drive only. This is not a certified total-storage value for the later schema.
- `B08SF96WNN`: advertised combined storage includes eMMC and a microSD card. The internal-drive
  probe does not count the removable card as internal storage.
- `B09TPP34RY`: a truncated title with some usable capacity tokens but incomplete other details.

These checks exposed failure modes and informed synthetic regression tests. There is no
independent ground-truth label set, full-record manual verification, extraction-precision result,
or retrieval-quality metric. Do not describe the candidate counts as manually verified products.

## Reproduction and actual checks

Place the approved archive at the path above, then run from the repository root after the
development installation described in the README:

```powershell
python -X utf8 -m searchrank_ai.data_audit --archive data/raw/amazon_india_2023/source.zip --output-dir artifacts/amazon_india_audit/my_run
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

Use a new output directory for each run. Existing reports are never overwritten. A corrupt file,
wrong column schema, malformed record, multiple CSV members, or changed source hash raises an
error rather than producing a successful audit. A failed write can leave partial artifacts;
only use a run that exited successfully.

Local outputs:

- `report.json`: provenance, conditions, counts, candidate profile, and limitations.
- `categories.json`: the full category inventory.
- `laptop_review.jsonl`: 7,023 unchanged source records with separate derived audit findings.
- `sample.json`: 40 category records selected with seed `20260903`.
- `candidate_sample.json`: 30 core-field candidates selected with the same fixed seed.

Recorded final-rule runs: `artifacts/amazon_india_audit/run2` and `run3`, audit version 2.
They completed at 2026-09-03 14:27:31 UTC and 14:27:49 UTC, taking 14.421 and 14.828 seconds for
the measured audit work before output serialization. Conditions: Windows 11 build 26200,
Python 3.12.13, local archive, earlier exploratory reads already performed, no cold-cache control,
no model calls, and no audit-time network calls. CPU/RAM details were not obtained because the
system-information query was denied. Timings are run records, not a controlled performance claim.

Actual validation:

- 56 tests passed; fixtures are synthetic and require no network or credentials.
- Ruff lint and formatting checks passed; dependency consistency check passed.
- Full-source runs produced identical reports excluding run timestamps/durations, and byte-identical
  category, review, and sample files.
- Category counts reconcile to the full source; classification and numeric counts reconcile to
  the laptop category.
- Archive SHA-256 matched before/after; raw archive and generated outputs are ignored by Git.

## Remaining Phase 1 work

1. Select and approve a replacement source; Amazon India will not be adopted.
2. Finalize a product schema with source evidence, explicit unknowns, currency assumptions,
   condition/bundle handling, and precise storage semantics.
3. Build and validate the production cleaning pipeline; quarantine uncertain records rather than
   silently treating audit heuristics as verified facts.
4. Recount usable products and document any target-size trade-off after cleaning.

No final processed catalogue, retrieval, database, or later-phase functionality has been built.
