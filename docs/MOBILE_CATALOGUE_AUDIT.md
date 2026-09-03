# 91mobiles catalogue audit and cleaning report

Date: 2026-09-04. Phase 1 dataset decision and measured full-file results.

## Verdict

**Adopted as the Phase 1 smartphone catalogue after deterministic filtering.** The approved source
contains 4,000 unique mobile-phone records. The cleaning rule retains **3,062** price- and
capacity-filter-ready smartphone records, which meets the project's 2,000–5,000 target. The
processed catalogue is generated locally and remains ignored by Git.

This is a historical catalogue for search evaluation, not live inventory. Adoption means the file
is suitable for this portfolio project's controlled experiments; it does not independently certify
every scraped specification, rating, release claim, price, or image.

## Source and provenance

- Publisher page: [Mobile Phones Specs & Prices Dataset (2008–2026)](https://www.kaggle.com/datasets/suresh2837/mobile-phones-specs-and-prices-dataset-20082026)
- Publisher: Suresh Khadka (`suresh2837`)
- Stated origin: publicly available 91mobiles listings
- Listed licence: CC0: Public Domain
- Publisher usage note: shared for learning/practice, not commercial use
- Downloaded: 2026-09-04
- Archive: 210,165 bytes
- Archive SHA-256: `98604a14020c9e7e45bcf0b578540d7a20f8dad4be8ad31686a05720b438c297`
- CSV member: `mobiles_data.csv`, 1,657,763 bytes

The CC0 label and the publisher's narrower usage note are in tension. The project therefore keeps
the raw archive, processed catalogue, and generated audit artifacts out of Git and documents the
source instead of redistributing the data.

## Complete source inventory

The source has exactly 4,000 rows and 17 columns. Names, source URLs, and derived URL-slug product
IDs are all unique; there are no exact duplicate rows. All 4,000 source URLs are query-free HTTPS
URLs on `www.91mobiles.com` and match the expected product-page path. The source has no explicit
product-ID column, so the pipeline creates `91mobiles:<url-slug>` while retaining the complete URL.

| Source field | Missing rows |
|---|---:|
| `name` | 0 |
| `url` | 0 |
| `release_date` | 55 |
| `spec_score` | 1,116 |
| `image_url` | 9 |
| `processor` | 883 |
| `ram_storage` | 669 |
| `rear_camera` | 104 |
| `front_camera` | 788 |
| `battery` | 11 |
| `display` | 3 |
| `antutu_score` | 2,423 |
| `awards` | 2,369 |
| `user_rating` | 264 |
| `expert_rating` | 2,373 |
| `price` | 53 |
| `store` | 53 |

## Deterministic eligibility rule

A source row enters the catalogue only when it has:

1. a non-empty name and deterministic title-prefix brand;
2. a valid, unique HTTPS 91mobiles source URL;
3. a positive integer INR price;
4. explicitly parseable RAM and storage text;
5. at least 1 GB RAM and at least 8 GB storage; and
6. no `Announced on` or `To be announced` source marker.

These thresholds separate filter-ready smartphones from the sampled feature-phone rows without
using model-name knowledge. Examples excluded by the capacity rule include Nokia 3210 2024,
Nokia 105 Classic, Snexian Guru GT, and Itel Ace 3 Shine. Low prices alone are not rejection
evidence: older Android phones such as Lyf Flame 7S and Panasonic T44 remain because their explicit
capacity and price fields satisfy the rule.

Rejection counts overlap when a row has more than one reason:

| Reason | Source rows |
|---|---:|
| Missing RAM/storage | 669 |
| Feature-phone capacity below the threshold | 216 |
| Missing price | 53 |
| Announced or to be announced | 7 |

No row is repaired, guessed, or silently merged. All 4,000 original rows and values remain in the
ignored audit JSONL alongside their derived parsing results and rejection reasons.

## Final core-only schema

The generated catalogue has 3,062 rows and exactly these 18 fields:

| Field | Meaning |
|---|---|
| `product_id` | Stable ID derived from the source URL slug |
| `product_name` | Original source name with surrounding whitespace removed |
| `brand` | Deterministic title-prefix brand; `Moto` is normalized to `Motorola` |
| `price_inr` | Positive integer price in Indian rupees |
| `ram_gb` | Explicit physical RAM converted to decimal GB |
| `storage_gb` | Explicit storage converted to decimal GB; 1 TB = 1,000 GB |
| `user_rating_5` | User rating normalized to a five-point scale when the source scale is explicit |
| `processor` | Source processor text or empty when unavailable |
| `battery_mah` | Parsed battery capacity |
| `charging` | Source charging text or empty when unavailable |
| `display_inches` | Parsed diagonal display size |
| `display_type` | Source panel-type text |
| `rear_camera` | Source rear-camera text |
| `front_camera` | Source front-camera text |
| `release_date` | ISO date when parseable |
| `release_status` | `released`, `available`, or `unknown` |
| `source_url` | Original 91mobiles product URL |
| `image_url` | Original image URL or empty when unavailable |

Per the user's instruction, `spec_score`, `antutu_score`, `awards`, `expert_rating`, and `store`
are excluded from the final dataset. They remain only in the preserved raw audit evidence.

## Catalogue profile

- Brands represented: 70 after capacity/price/release filtering
- INR price minimum / median / maximum: 2,499 / 16,999 / 219,900
- RAM minimum / median / maximum: 1 / 6 / 18 GB
- Storage minimum / median / maximum: 8 / 128 / 2,000 GB
- User ratings: 2,983 present and 79 missing
- Rating normalization: 2,927 source values were `/5`; 56 source values were `/10`
- Processor: 2,983 present and 79 missing
- Battery and rear/front camera evidence: present for all retained rows
- Charging detail: 2,339 present and 723 missing
- Display: 3 missing or unparseable
- Release date: 4 missing
- Image URL: 7 missing
- Release-year coverage: 2013–2026, plus four unknown dates

The catalogue SHA-256 is
`c3428dd04e5d02c6a66ce00f5961f6b1f6ba9dcc30d86a37ffde84523619c7ea`.

## Reproduction

After placing the approved archive at the ignored raw-data path, run:

```powershell
.venv\Scripts\python.exe -X utf8 -m searchrank_ai.mobile_catalogue `
  --archive data\raw\suresh_91mobiles_2008_2026\source.zip `
  --audit-dir artifacts\suresh_91mobiles_audit\new-run `
  --catalogue data\processed\suresh_91mobiles_2008_2026\catalogue-new.csv
```

The command refuses to overwrite either output. Two full-source runs matched on every report field
outside run metadata and produced byte-identical catalogues, records, and fixed-seed samples. The
source hash was unchanged before and after each audit.

## Limitations

- There is no rating/review count, so a rating cannot be weighted by feedback volume.
- `/10` user ratings can be mathematically normalized but their collection semantics were not
  independently verified.
- Prices and availability are source observations, not live offers or guarantees.
- Product variants remain separate because the source supplies distinct names and URLs.
- Derived brand and capacity-based device classification are deterministic heuristics, not manual
  ground truth for all 4,000 rows.
- Some 2026 models may have been announced or expected when scraped. Explicit announcement markers
  are excluded, but standard release-date claims were not checked against live manufacturer pages.
- Processor, charging, display, release date, rating, and image gaps remain empty rather than being
  filled from outside knowledge.
- No image was downloaded, no retailer was scraped, and catalogue text was never executed or sent
  to an LLM.
