# Replacement dataset screening

Date: 2026-09-03. Phase 1 remains active.

**Final Phase 1 update:** The user approved and the project adopted the subsequently proposed
4,000-row Suresh Khadka/91mobiles dataset after a complete
[audit and reproducible cleaning run](MOBILE_CATALOGUE_AUDIT.md). The final core-only catalogue has
3,062 records. The remainder of this document preserves the earlier screening history.

The user rejected the audited Amazon India 2023 source. The audit and raw archive are retained
for traceability, not adopted as the catalogue. The later approved smartphone scope retained the
2,000–5,000 target, original identifier/source-reference rule, INR prices, meaningful rating
coverage, and evidenced specifications.

## Selected replacement — 91mobiles specifications and prices

[Publisher and preview](https://www.kaggle.com/datasets/suresh2837/mobile-phones-specs-and-prices-dataset-20082026).
The source has 4,000 unique names and URLs, structured specifications, INR prices, and user ratings.
Its listed licence is CC0, although the publisher also gives a learning/non-commercial usage note.
The full-file audit found 3,062 price/capacity-ready smartphones after excluding missing core
evidence, feature-phone capacities, and announced records. The final dataset intentionally omits
specification score, AnTuTu score, awards, expert rating, and store. This measured result supersedes
the candidate-only conclusions below.

## Initial screening result (superseded by the audit above)

**No laptop replacement was verified to satisfy all requirements simultaneously.** Smartphone
screening found a substantially stronger audit candidate: Prathamesh Mistry's 2025 Amazon India
phone listings. Its public preview meets the desired scale and evidence requirements, but title
parsing, duplicate handling, rating coverage, low-price anomalies, and smartphone-only purity still
need a complete audit. This is a recommendation to investigate, not a guarantee of clean records.
Do not change domains, lower the target size, remove rating support, merge sources, or adopt a
dataset automatically.

These findings come from publisher documentation and public browser previews, not full-file
downloads or our own complete missing-value audits. Displayed profile percentages are rounded.

## Smartphone scope alternative — strongest next audit candidate

### Amazon Great Indian Sale 2025 mobile listings

[Publisher and preview](https://www.kaggle.com/datasets/prothomeshmistry/amazon-big-billion-sale-22-2025-mobile-phones).
Listed licence: MIT. File: `Amazon Big Billion Sale 2025 -Oct Mobile Phones.csv`, displayed size
2.56 MB and six columns.

The preview contains 3,529 rows by its numeric profile, 2,805 unique ASINs, 2,792 unique product
names, and 3,529 displayed unique source URLs. Fields include an English product title, INR price,
average customer rating, review count, ASIN, and Amazon India URL. Many sampled titles explicitly
contain RAM, storage, processor, battery, display, and camera evidence. After ASIN deduplication,
the apparent 2,805-product ceiling remains inside the preferred 2,000–5,000 range.

This is not yet an approved clean catalogue. RAM/storage and most other specifications are embedded
in untrusted titles rather than separate source columns. The preview also shows 724 more rows than
unique ASINs, `N/A` ratings in samples, and unusually common prices of INR 299 and INR 284. Those
low values could indicate accessories, instalment amounts, or extraction errors and must not be
treated as phone prices without evidence. URLs contain search/referral parameters and would need
canonicalization while preserving the original string.

### Smartphone alternatives not preferred

- [Shahriar Kabir's detailed smartphone dataset](https://www.kaggle.com/datasets/shahriarkabir/smartphone-dataset/versions/1):
  approximately 1,149 variant rows and 17 useful fields, including INR prices, customer ratings,
  rating/review counts, RAM, storage, display, cameras, battery, and processor. Public profiles show
  1,069 numeric ratings. It lacks a source product ID/URL and is below the preferred scale.
- [Devashree Madhugiri's Flipkart mobiles](https://www.kaggle.com/datasets/devsubhash/flipkart-mobiles-dataset):
  3,114 older variant rows, CC0, structured RAM/storage, INR prices, and 2,970 numeric ratings in
  the preview. It has only eight fields, no source ID/URL, no descriptions or richer phone specs,
  and is marked as never updated.
- [Vik369's 2026 Flipkart phones](https://www.kaggle.com/datasets/vik369/flipkart-mobile-phones-dataset-2026):
  33,000+ claimed rows and structured fields, but no source ID/URL. Previewed rows contain impossible
  values such as 32 GB RAM for basic keypad phones, and some review counts exceed their rating counts.
  Repeated profile clusters further weaken confidence. Not recommended as-is.
- [Shavilya Rajput's cleaned 2025 Amazon phones](https://www.kaggle.com/datasets/shavilyarajput/amazon-great-indian-sale-phone-dataset-2025):
  only 701 unique ASINs/800 URLs in the preview and a minimum displayed price of INR 53 despite a
  claimed smartphone-only cleaning step. It is smaller and does not remove the anomaly concern.

## 1. Flipkart Laptop Dataset (2022) — closest functional match

[Publisher and preview](https://www.kaggle.com/datasets/dhanushbommavaram/laptop-dataset).
Listed licence: CC BY-SA 4.0. File: `complete laptop data0.csv`, displayed size 1.64 MB.

The card reports 984 entries from June 2022; the preview shows 98 columns, 984 unique product
links, English titles, INR prices, model/part numbers, user ratings, RAM, SSD/HDD capacity, and
processor fields. Rating histogram counts sum to 690, leaving 294 without numeric ratings
(29.88%). Optional model-name/series fields also have gaps. Missing HDD values need not imply
missing storage. Exact usable counts and specification consistency still require an audit.

Trade-off: below the original size target and still historical. It addresses structure/language,
not freshness. Do not invent extra rows or assume every displayed specification is correct.

## 2. Vibish Joe's 2026 India dataset — scale, but ratings and consistency blockers

[Publisher and preview](https://www.kaggle.com/datasets/vibishjoe/2026-laptop-prices-and-specifications-in16k-items).
Listed licence: MIT. Two displayed files: `laptops_cleaned.csv` (5.55 MB, 21 columns) and
`laptops_uncleaned.csv` (18.23 MB, 272 columns); 16,905 unique source URLs.

Includes English names, brand, price, source URL, RAM/storage, CPU/GPU, and other fields. The
cleaned schema has no customer rating. The uncleaned `Customer Reviews` preview is effectively
all null, with a "Be the first to review this item" placeholder. CPU/GPU fields have missing values.

A checked row's title states 2GB RAM/500GB storage, while cleaned fields contain 8/512. Both files
include engineered columns, so an "uncleaned" filename is not proof of untouched source evidence.
Not suitable as-is; publication year also does not establish that every model or price is recent.

## 3. Abhinav's India 2025 specifications — smaller, different rating semantics

[Publisher repository](https://github.com/abhinavflac/laptops-specs-dataset).
Reported size: 992 cleaned records and 27 fields; raw/processed files are listed. English examples
include brand/model, INR price, RAM/storage, CPU/GPU, and display fields.

The documented `rating` is a 0–100 user/expert score, not established 1–5 customer feedback.
Do not divide it by 20 and call it customer stars. Missingness/IDs need further inspection.
The repository displays MIT licensing while its README says CC0; clarify before adopting.
Below the size target and not a direct replacement for the required rating evidence.

## Other candidates screened out

- [Elvin Rustamov's eBay source](https://www.kaggle.com/datasets/elvinrustam/ebay-laptops-and-netbooks-sales):
  CC0 listed; raw preview 4.15 MB/23 columns, cleaned preview 2.03 MB/24 columns. Dollar prices,
  used/refurbished/parts-only listings, approximately 96% missing raw ratings and 39% missing brands.
  Structured RAM/storage alone do not make it a stronger fit. Not recommended.
- [Gaming Laptops 2026](https://www.kaggle.com/datasets/kanchana1990/gaming-laptops-2026/data):
  publisher reports 614 records/10 columns, primarily USD, CC BY-NC 4.0. Specs require title or
  description parsing, and the listed schema has no product ID/URL. Does not meet scope needs.
- [Flipkart laptop reviews](https://www.kaggle.com/datasets/gitadityamaddali/flipkart-laptop-reviews):
  24,000 review rows cover about 600 laptop models according to the MIT-licensed data card.
  Review rows must not be counted as unique catalogue products; listed fields lack prices/URLs.

## Approval history

The user subsequently approved changing the catalogue domain to smartphones and downloading/auditing
the 3,529-row Amazon India candidate. That dataset failed the suitability review. On 2026-09-04,
the user separately approved auditing the Suresh Khadka/91mobiles replacement and directed that
optional attributes be omitted from the final dataset. That audit and cleaning pipeline are complete.

No live retail scraping, commit, push, or later-phase implementation was performed.
