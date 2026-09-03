"""Read-only Amazon India CSV audit; output is a review artifact, not a catalogue.

Run with ``python -m searchrank_ai.data_audit --archive ... --output-dir ...``.
No network calls, model calls, data correction, deduplication, or image downloads.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import platform
import random
import re
import statistics
import time
import zipfile
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from searchrank_ai.audit_titles import probe_title

SOURCE_URL = "https://www.kaggle.com/datasets/asaniczka/amazon-india-products-2023-1-5m-products"
LICENSE_URL = "https://opendatacommons.org/licenses/by/1-0/index.html"
CATEGORY = "लैपटॉप"
SEED = 20260903
FIELDS = (
    "asin",
    "title",
    "imgUrl",
    "productURL",
    "stars",
    "reviews",
    "price",
    "listPrice",
    "categoryName",
    "isBestSeller",
    "boughtInLastMonth",
)


def numeric_status(raw: str, *, rating: bool = False) -> str:
    """Distinguish missing zero sentinels from invalid/out-of-range numbers."""
    if not raw.strip():
        return "blank"
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return "invalid"
    if not value.is_finite():
        return "invalid"
    if value == 0:
        return "zero_missing"
    if value < 0 or (rating and not Decimal(1) <= value <= Decimal(5)):
        return "invalid"
    return "valid"


def valid_source_url(url: str, asin: str) -> bool:
    """Check source syntax/ID agreement only, not live listing availability."""
    try:
        parts = urlsplit(url)
        return (
            parts.scheme == "https"
            and parts.netloc in {"amazon.in", "www.amazon.in"}
            and parts.path.rstrip("/") in {f"/dp/{asin}", f"/gp/product/{asin}"}
            and re.fullmatch(r"[A-Z0-9]{10}", asin) is not None
        )
    except ValueError:
        return False


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect_row(row: dict[str, str]) -> dict:
    result = probe_title(row["title"])
    result.update(
        valid_asin=re.fullmatch(r"[A-Z0-9]{10}", row["asin"]) is not None,
        valid_source_url=valid_source_url(row["productURL"], row["asin"]),
        price_status=numeric_status(row["price"]),
        rating_status=numeric_status(row["stars"], rating=True),
    )
    result["core_fields_present"] = all(
        (
            result["valid_asin"],
            result["valid_source_url"],
            bool(row["title"].strip()),
            result["price_status"] == "valid",
            result["brand"]["status"] == "found",
            result["ram_gb"]["status"] == "found",
            result["storage_gb_decimal"]["status"] == "found",
        )
    )
    flags = []
    if result["price_status"] == "valid" and Decimal(row["price"]) < 5000:
        flags.append("price_below_5000_review")
    storage = result["storage_gb_decimal"]["value"]
    if storage is not None and storage < 16:
        flags.append("storage_below_16gb_review")
    result["anomaly_flags"] = flags
    return result


def candidate_profile(records: list[dict]) -> dict:
    """Summarize tentative candidates; review thresholds are not data corrections."""
    core = [
        record
        for record in records
        if record["audit"]["classification"] == "candidate_with_specs"
        and record["audit"]["core_fields_present"]
    ]
    prices = [Decimal(record["raw"]["price"]) for record in core]
    unflagged = [record for record in core if not record["audit"]["anomaly_flags"]]
    return {
        "unique_exact_titles": len({record["raw"]["title"] for record in core}),
        "without_anomaly_flags": len(unflagged),
        "without_anomaly_flags_and_rated": sum(
            record["audit"]["rating_status"] == "valid" for record in unflagged
        ),
        "price_min_median_max": [str(min(prices)), str(statistics.median(prices)), str(max(prices))]
        if prices
        else [],
        "brand_counts": dict(
            sorted(Counter(record["audit"]["brand"]["value"] for record in core).items())
        ),
        "review_thresholds": {"positive_price_below": 5000, "storage_gb_below": 16},
        "threshold_note": "Heuristic review triggers only; absence of a flag is not validation.",
    }


def audit_archive(archive: Path, output_dir: Path) -> dict:
    """Stream the full source and retain laptop-category rows locally for review.

    A new output directory is required: reruns never overwrite existing reports.
    Failure raises an exception; partial outputs must not be treated as success.
    """
    started = time.perf_counter()
    digest_before = sha256(archive)
    categories: Counter = Counter()
    all_ids: Counter = Counter()
    ids: Counter = Counter()
    titles: Counter = Counter()
    counts: Counter = Counter()
    source_counts: Counter = Counter()
    records = []
    with zipfile.ZipFile(archive) as bundle:
        members = [info for info in bundle.infolist() if info.filename.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError("Expected exactly one CSV member in the source archive")
        member = members[0]
        with bundle.open(member) as stream:
            reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig"), strict=True)
            if reader.fieldnames != list(FIELDS):
                raise ValueError(f"Unexpected CSV schema: {reader.fieldnames!r}")
            for row_number, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"Malformed CSV record at record number {row_number}")
                categories[row["categoryName"]] += 1
                all_ids[row["asin"]] += 1
                source_counts[f"price_{numeric_status(row['price'])}"] += 1
                source_counts[f"rating_{numeric_status(row['stars'], rating=True)}"] += 1
                if row["categoryName"] != CATEGORY:
                    continue
                ids[row["asin"]] += 1
                titles[row["title"]] += 1
                findings = inspect_row(row)
                records.append({"csv_record_number": row_number, "raw": row, "audit": findings})
                counts["category_rows"] += 1
                counts[findings["classification"]] += 1
                counts[findings["condition"]] += 1
                for field in ("price_status", "rating_status"):
                    counts[f"{field}_{findings[field]}"] += 1
                for field in ("brand", "ram_gb", "storage_gb_decimal"):
                    counts[f"{field}_{findings[field]['status']}"] += 1
                counts[f"ram_rule_{findings['ram_gb']['rule']}"] += 1
                for field in ("valid_asin", "valid_source_url", "has_devanagari"):
                    counts[field] += int(findings[field])
                candidate = findings["classification"] == "candidate_with_specs"
                core = candidate and findings["core_fields_present"]
                rated = core and findings["rating_status"] == "valid"
                counts["candidate_core_complete"] += int(core)
                counts["candidate_core_and_rating_complete"] += int(rated)
                counts["candidate_core_renewed_mentioned"] += int(
                    core and findings["condition"] == "renewed_mentioned"
                )
                counts["candidate_core_rating_renewed_mentioned"] += int(
                    rated and findings["condition"] == "renewed_mentioned"
                )
    digest_after = sha256(archive)
    if digest_before != digest_after:
        raise RuntimeError("Source archive changed during the audit")
    report = {
        "audit_version": 2,
        "source": {
            "url": SOURCE_URL,
            "listed_license": "ODC-By 1.0",
            "license_url": LICENSE_URL,
            "archive_name": archive.name,
            "archive_bytes": archive.stat().st_size,
            "sha256": digest_before,
            "unchanged_after_audit": True,
            "csv_member": member.filename,
            "csv_bytes": member.file_size,
            "csv_crc32": member.CRC,
            "fields": list(FIELDS),
        },
        "run": {
            "completed_at_utc": datetime.now(UTC).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "sample_seed": SEED,
            "models_or_network_used": False,
        },
        "inventory": {
            "rows": categories.total(),
            "categories": len(categories),
            "unique_asins": len(all_ids),
            "repeated_asin_rows": all_ids.total() - len(all_ids),
            "blank_asin_rows": all_ids[""],
            "numeric_counts": dict(sorted(source_counts.items())),
        },
        "scope": {
            "category": CATEGORY,
            "unique_asins": len(ids),
            "repeated_asin_rows": ids.total() - len(ids),
            "repeated_exact_title_rows": titles.total() - len(titles),
            "counts": dict(sorted(counts.items())),
        },
        "candidate_profile": candidate_profile(records),
        "caveats": [
            "Coverage probes are not validated production extraction or laptop labels.",
            "Only the exact laptop category is reviewed; other categories may contain laptops.",
            "Distinct ASINs can describe the same model, configuration, or bundle.",
            "A zero price or rating is unavailable evidence, not a valid zero-valued fact.",
            "Brand/spec matching uses title tokens only, including explicit Hindi aliases.",
            "Slash pairs are structural RAM interpretations; multi-drive storage is unresolved.",
            "Storage uses decimal GB-equivalents; no missing capacity or condition is invented.",
            "No live price, availability, URL reachability, translation, or image checks.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    with (output_dir / "laptop_review.jsonl").open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    sample = random.Random(SEED).sample(records, min(40, len(records)))
    core = [
        record
        for record in records
        if record["audit"]["classification"] == "candidate_with_specs"
        and record["audit"]["core_fields_present"]
    ]
    core_sample = random.Random(SEED).sample(core, min(30, len(core)))
    artifacts = {
        "report.json": report,
        "categories.json": dict(sorted(categories.items())),
        "sample.json": sample,
        "candidate_sample.json": core_sample,
    }
    for name, content in artifacts.items():
        (output_dir / name).write_text(
            json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = audit_archive(args.archive, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
