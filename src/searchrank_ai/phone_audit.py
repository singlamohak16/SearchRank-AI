"""Offline, evidence-preserving suitability audit of the approved phone ZIP.

Outputs JSON/JSONL review artifacts, not a cleaned catalogue. No network/model calls,
data repair, source deletion, or deduplication. Existing output directories are refused.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import platform
import random
import re
import statistics
import time
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from searchrank_ai.data_audit import sha256
from searchrank_ai.phone_titles import probe_phone_title

SOURCE_URL = (
    "https://www.kaggle.com/datasets/prothomeshmistry/amazon-big-billion-sale-22-2025-mobile-phones"
)
FIELDS = ("Product_Name", "Price", "Rating", "Review_Count", "ASIN", "Product_URL")
SEED = 20260903


def number(raw: str, kind: str) -> dict:
    """Parse explicit values only. Zero reviews is valid; zero price/rating is unavailable."""
    value = raw.strip()
    if value.casefold() in {"", "n/a", "na", "null", "none"}:
        return {"status": "missing", "value": None}
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return {"status": "invalid", "value": None}
    if not parsed.is_finite() or parsed < 0:
        return {"status": "invalid", "value": None}
    if kind != "reviews" and parsed == 0:
        return {"status": "zero_unavailable", "value": None}
    if kind == "rating" and not 1 <= parsed <= 5:
        return {"status": "invalid", "value": None}
    if kind == "reviews" and parsed != parsed.to_integral_value():
        return {"status": "invalid", "value": None}
    return {"status": "valid", "value": float(parsed) if kind != "reviews" else int(parsed)}


def canonical_url(raw: str, asin: str) -> str | None:
    """Validate direct or single relative sponsored destinations without fetching URLs."""
    if not re.fullmatch(r"[A-Z0-9]{10}", asin):
        return None
    try:
        parts = urlsplit(raw)
        if parts.scheme != "https" or parts.netloc not in {"www.amazon.in", "amazon.in"}:
            return None
        path = parts.path
        if path == "/sspa/click":
            destinations = parse_qs(parts.query).get("url", [])
            if len(destinations) != 1:
                return None
            destination = urlsplit(destinations[0])
            if destination.netloc or destination.scheme or not destination.path.startswith("/"):
                return None
            path = destination.path
        match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)", path)
        valid = match is not None and match[1] == asin
        return f"https://www.amazon.in/dp/{asin}" if valid else None
    except ValueError:
        return None


def inspect_phone(row: dict[str, str]) -> dict:
    result = probe_phone_title(row["Product_Name"])
    result.update(
        valid_asin=bool(re.fullmatch(r"[A-Z0-9]{10}", row["ASIN"])),
        canonical_url=canonical_url(row["Product_URL"], row["ASIN"]),
        price=number(row["Price"], "price"),
        rating=number(row["Rating"], "rating"),
        reviews=number(row["Review_Count"], "reviews"),
    )
    price = result["price"]["value"]
    flags = []
    if price is not None and price < 3000:
        flags.append("price_below_3000_review")
    if result["renewed_mentioned"]:
        flags.append("renewed_review")
    if any(result[field]["status"] == "ambiguous" for field in ("ram", "storage")):
        flags.append("ambiguous_specs")
    pair_conflict = any(
        result[field]["status"] == result[f"pair_{field}"]["status"] == "found"
        and result[field]["value_gb"] != result[f"pair_{field}"]["value_gb"]
        for field in ("ram", "storage")
    )
    if pair_conflict:
        flags.append("explicit_pair_conflict")
    result["flags"] = flags
    base = (
        result["classification"] == "smartphone_candidate"
        and result["canonical_url"] is not None
        and price is not None
    )
    result["explicit_core"] = bool(
        base and result["ram"]["status"] == result["storage"]["status"] == "found"
    )
    # Inference is counted only as possible future recovery, not strict-filter-ready data.
    result["recoverable_core"] = bool(
        base
        and not pair_conflict
        and all(
            result[field]["status"] == "found"
            or (
                result[field]["status"] == "missing"
                and result[f"pair_{field}"]["status"] == "found"
            )
            for field in ("ram", "storage")
        )
    )
    return result


def profile(records: list[dict]) -> dict:
    rows = [r["raw"] for r in records]
    prices = [
        r["audit"]["price"]["value"] for r in records if r["audit"]["price"]["value"] is not None
    ]
    return {
        "rows": len(records),
        "unique_asins": len({r["ASIN"] for r in rows}),
        "rated_rows": sum(r["audit"]["rating"]["status"] == "valid" for r in records),
        "rated_unique_asins": len(
            {r["raw"]["ASIN"] for r in records if r["audit"]["rating"]["status"] == "valid"}
        ),
        "brand_rows": dict(
            sorted(Counter(r["audit"]["brand"] or "unknown" for r in records).items())
        ),
        "price_min_median_max": [min(prices), statistics.median(prices), max(prices)]
        if prices
        else [],
    }


def audit_phone_archive(archive: Path, output_dir: Path) -> dict:
    """Read every row; inventory duplicate conflicts and retain reproducible samples."""
    if output_dir.exists():
        raise FileExistsError("Choose a new output directory; existing audit outputs are preserved")
    started = time.perf_counter()
    digest_before = sha256(archive)
    records = []
    with zipfile.ZipFile(archive) as bundle:
        members = [m for m in bundle.infolist() if m.filename.lower().endswith(".csv")]
        if len(members) != 1 or members[0].file_size > 50_000_000:
            raise ValueError("Expected one CSV smaller than 50 MB")
        member = members[0]
        with bundle.open(member) as stream:
            reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig"), strict=True)
            if reader.fieldnames != list(FIELDS):
                raise ValueError(f"Unexpected CSV schema: {reader.fieldnames!r}")
            for record_number, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"Malformed CSV record at {record_number}")
                records.append(
                    {"csv_record_number": record_number, "raw": row, "audit": inspect_phone(row)}
                )
    if not records:
        raise ValueError("Empty dataset")
    digest_after = sha256(archive)
    if digest_before != digest_after:
        raise RuntimeError("Source changed while auditing")
    groups = defaultdict(list)
    for record in records:
        groups[record["raw"]["ASIN"]].append(record)
    duplicate_groups = []
    for asin, group in sorted(groups.items()):
        if len(group) > 1:
            conflicts = [f for f in FIELDS if f != "ASIN" and len({r["raw"][f] for r in group}) > 1]
            duplicate_groups.append(
                {
                    "asin": asin,
                    "record_numbers": [r["csv_record_number"] for r in group],
                    "differing_fields": conflicts,
                }
            )
    subsets = {
        category: [r for r in records if r["audit"]["classification"] == category]
        for category in sorted({r["audit"]["classification"] for r in records})
    }
    for name in ("explicit_core", "recoverable_core"):
        subsets[name] = [r for r in records if r["audit"][name]]
        subsets[f"{name}_unflagged"] = [r for r in subsets[name] if not r["audit"]["flags"]]
    rng = random.Random(SEED)
    samples = {
        name: sorted(rng.sample(group, min(20, len(group))), key=lambda r: r["csv_record_number"])
        for name, group in sorted(subsets.items())
    }
    counts = Counter()
    for record in records:
        findings = record["audit"]
        for field in ("price", "rating", "reviews", "ram", "storage", "pair_ram", "pair_storage"):
            counts[f"{field}_{findings[field]['status']}"] += 1
        for flag in findings["flags"]:
            counts[flag] += 1
        counts["invalid_asin"] += not findings["valid_asin"]
        counts["invalid_or_mismatched_url"] += findings["canonical_url"] is None
        counts["sponsored_source_urls"] += "/sspa/click?" in record["raw"]["Product_URL"]
        counts["has_devanagari"] += findings["has_devanagari"]
    report = {
        "source": {
            "url": SOURCE_URL,
            "listed_license": "MIT",
            "archive_sha256": digest_before,
            "archive_bytes": archive.stat().st_size,
            "member": member.filename,
            "csv_bytes": member.file_size,
            "csv_fields": list(FIELDS),
        },
        "run": {
            "utc": datetime.now(UTC).isoformat(),
            "seconds": round(time.perf_counter() - started, 4),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "seed": SEED,
        "all": profile(records),
        "counts": dict(sorted(counts.items())),
        "unique_titles": len({r["raw"]["Product_Name"] for r in records}),
        "unique_raw_urls": len({r["raw"]["Product_URL"] for r in records}),
        "exact_duplicate_rows": len(records)
        - len({tuple(r["raw"][f] for f in FIELDS) for r in records}),
        "duplicate_asin_groups": len(duplicate_groups),
        "duplicate_asin_excess_rows": sum(len(g) - 1 for g in groups.values()),
        "duplicate_conflict_groups_by_field": dict(
            sorted(Counter(f for g in duplicate_groups for f in g["differing_fields"]).items())
        ),
        "subsets": {name: profile(group) for name, group in sorted(subsets.items())},
        "limits": [
            "Heuristic categories, not verified product labels",
            "No live price/spec verification",
            "Unlabelled pairs are inferred, not explicit RAM/storage evidence",
            "No data adopted or removed",
            "Brand is title-prefix evidence only",
            "Price below INR 3000 is only a review flag",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, value in (
        ("report", report),
        ("samples", samples),
        ("duplicate_groups", duplicate_groups),
    ):
        (output_dir / f"{name}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    with (output_dir / "records.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = audit_phone_archive(args.archive, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
