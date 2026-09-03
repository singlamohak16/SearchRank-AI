"""Audit and build the approved 91mobiles smartphone catalogue.

The source ZIP is immutable input. Every source row and field is retained in the
audit JSONL, while the generated CSV contains only the approved core attributes.
Parsing is deterministic and never fills missing specifications from model knowledge.
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
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from searchrank_ai.data_audit import sha256

SOURCE_URL = (
    "https://www.kaggle.com/datasets/suresh2837/mobile-phones-specs-and-prices-dataset-20082026"
)
SOURCE_FIELDS = (
    "name",
    "url",
    "release_date",
    "spec_score",
    "image_url",
    "processor",
    "ram_storage",
    "rear_camera",
    "front_camera",
    "battery",
    "display",
    "antutu_score",
    "awards",
    "user_rating",
    "expert_rating",
    "price",
    "store",
)
FINAL_FIELDS = (
    "product_id",
    "product_name",
    "brand",
    "price_inr",
    "ram_gb",
    "storage_gb",
    "user_rating_5",
    "processor",
    "battery_mah",
    "charging",
    "display_inches",
    "display_type",
    "rear_camera",
    "front_camera",
    "release_date",
    "release_status",
    "source_url",
    "image_url",
)
OPTIONAL_SOURCE_FIELDS_EXCLUDED = (
    "spec_score",
    "antutu_score",
    "awards",
    "expert_rating",
    "store",
)
SEED = 20260904
_MISSING = {"", "n/a", "na", "null", "none"}
_CAPACITY = re.compile(
    r"^(\d+(?:\.\d+)?)\s*(GB|MB)\s*RAM\s*(?:\||\+)\s*"
    r"(\d+(?:\.\d+)?)\s*(GB|MB|TB)\s*(?:Storage|ROM)$",
    re.IGNORECASE,
)
_PRICE = re.compile(r"^₹\s*([\d,]+)$")
_RATING = re.compile(r"^(\d+(?:\.\d+)?)\s*/\s*(5|10)$")
_BATTERY = re.compile(r"^(\d+(?:\.\d+)?)\s*mAh(?:\s*\|\s*|\s+)?(.*)$", re.IGNORECASE)
_DISPLAY = re.compile(r"^(\d+(?:\.\d+)?)\s*inches\b.*?\|\s*(.+)$", re.IGNORECASE)
_RELEASE_DATE = re.compile(r"(\d{2} [A-Z][a-z]{2}, \d{4})$")
_URL_PATH = re.compile(r"^/([a-z0-9-]+)-price-in-india/?$")
_MULTIWORD_BRANDS = ("I KALL", "Black Shark", "Good One", "MU Phone")
_BRAND_ALIASES = {"Moto": "Motorola", "Blackberry": "BlackBerry", "Asus": "ASUS"}


def text_or_none(raw: str) -> str | None:
    """Return source text unchanged apart from surrounding whitespace."""
    value = raw.strip()
    return None if value.casefold() in _MISSING else value


def _decimal(raw: str) -> Decimal | None:
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def parse_price(raw: str) -> dict:
    value = text_or_none(raw)
    if value is None:
        return {"status": "missing", "value": None}
    match = _PRICE.fullmatch(value)
    parsed = _decimal(match[1].replace(",", "")) if match else None
    if parsed is None or parsed <= 0 or parsed != parsed.to_integral_value():
        return {"status": "invalid", "value": None}
    return {"status": "valid", "value": int(parsed)}


def parse_rating(raw: str) -> dict:
    value = text_or_none(raw)
    if value is None:
        return {"status": "missing", "value": None, "source_scale": None}
    match = _RATING.fullmatch(value)
    parsed = _decimal(match[1]) if match else None
    scale = int(match[2]) if match else None
    if parsed is None or scale is None or not 0 < parsed <= scale:
        return {"status": "invalid", "value": None, "source_scale": scale}
    normalized = (parsed * Decimal(5) / Decimal(scale)).quantize(Decimal("0.01"))
    return {"status": "valid", "value": float(normalized), "source_scale": scale}


def _to_gb(value: Decimal, unit: str) -> Decimal:
    return value * {"MB": Decimal("0.001"), "GB": Decimal(1), "TB": Decimal(1000)}[unit]


def parse_ram_storage(raw: str) -> dict:
    value = text_or_none(raw)
    if value is None:
        return {"status": "missing", "ram_gb": None, "storage_gb": None}
    match = _CAPACITY.fullmatch(value)
    if not match:
        return {"status": "invalid", "ram_gb": None, "storage_gb": None}
    ram = _to_gb(Decimal(match[1]), match[2].upper())
    storage = _to_gb(Decimal(match[3]), match[4].upper())
    if ram <= 0 or storage <= 0:
        return {"status": "invalid", "ram_gb": None, "storage_gb": None}
    return {"status": "valid", "ram_gb": float(ram), "storage_gb": float(storage)}


def parse_battery(raw: str) -> dict:
    value = text_or_none(raw)
    if value is None:
        return {"status": "missing", "mah": None, "charging": None}
    match = _BATTERY.fullmatch(value)
    parsed = _decimal(match[1]) if match else None
    if parsed is None or parsed <= 0 or parsed != parsed.to_integral_value():
        return {"status": "invalid", "mah": None, "charging": None}
    charging = match[2].strip() or None
    return {"status": "valid", "mah": int(parsed), "charging": charging}


def parse_display(raw: str) -> dict:
    value = text_or_none(raw)
    if value is None:
        return {"status": "missing", "inches": None, "type": None}
    match = _DISPLAY.fullmatch(value)
    parsed = _decimal(match[1]) if match else None
    if parsed is None or parsed <= 0:
        return {"status": "invalid", "inches": None, "type": None}
    return {"status": "valid", "inches": float(parsed), "type": match[2].strip()}


def parse_release(raw: str) -> dict:
    value = text_or_none(raw)
    if value is None:
        return {"status": "unknown", "date": None}
    match = _RELEASE_DATE.search(value)
    if not match:
        return {"status": "invalid", "date": None}
    try:
        parsed = datetime.strptime(match[1], "%d %b, %Y").date()
    except ValueError:
        return {"status": "invalid", "date": None}
    folded = value.casefold()
    if "to be announced" in folded or folded.startswith("announced on:"):
        status = "announced"
    elif "available for sale" in folded:
        status = "available"
    else:
        status = "released"
    return {"status": status, "date": parsed.isoformat()}


def source_identity(raw: str) -> dict:
    value = text_or_none(raw)
    if value is None:
        return {"status": "missing", "product_id": None}
    try:
        parts = urlsplit(value)
    except ValueError:
        return {"status": "invalid", "product_id": None}
    match = _URL_PATH.fullmatch(parts.path)
    valid = (
        parts.scheme == "https"
        and parts.netloc == "www.91mobiles.com"
        and not parts.query
        and not parts.fragment
        and match is not None
    )
    return {
        "status": "valid" if valid else "invalid",
        "product_id": f"91mobiles:{match[1]}" if valid else None,
    }


def derive_brand(name: str) -> str | None:
    value = text_or_none(name)
    if value is None:
        return None
    folded = value.casefold()
    for brand in _MULTIWORD_BRANDS:
        if folded == brand.casefold() or folded.startswith(f"{brand.casefold()} "):
            return brand
    token = value.split(maxsplit=1)[0]
    return _BRAND_ALIASES.get(token, token)


def inspect_mobile(row: dict[str, str]) -> dict:
    """Parse only explicit source evidence and list every exclusion reason."""
    identity = source_identity(row["url"])
    price = parse_price(row["price"])
    rating = parse_rating(row["user_rating"])
    capacity = parse_ram_storage(row["ram_storage"])
    battery = parse_battery(row["battery"])
    display = parse_display(row["display"])
    release = parse_release(row["release_date"])
    name = text_or_none(row["name"])
    brand = derive_brand(row["name"])
    reasons = []
    if name is None:
        reasons.append("missing_name")
    if brand is None:
        reasons.append("missing_brand")
    if identity["status"] != "valid":
        reasons.append("invalid_source_url")
    if price["status"] != "valid":
        reasons.append(f"price_{price['status']}")
    if capacity["status"] != "valid":
        reasons.append(f"ram_storage_{capacity['status']}")
    elif capacity["ram_gb"] < 1 or capacity["storage_gb"] < 8:
        reasons.append("feature_phone_capacity")
    if release["status"] == "announced":
        reasons.append("announced_not_released")
    return {
        "identity": identity,
        "brand": brand,
        "price": price,
        "rating": rating,
        "capacity": capacity,
        "battery": battery,
        "display": display,
        "release": release,
        "eligible": not reasons,
        "rejection_reasons": reasons,
    }


def _csv_number(value: float | int | None) -> str | float | int:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def final_record(row: dict[str, str], audit: dict) -> dict[str, str | float | int]:
    """Return only the approved core catalogue attributes."""
    return {
        "product_id": audit["identity"]["product_id"],
        "product_name": row["name"].strip(),
        "brand": audit["brand"],
        "price_inr": audit["price"]["value"],
        "ram_gb": _csv_number(audit["capacity"]["ram_gb"]),
        "storage_gb": _csv_number(audit["capacity"]["storage_gb"]),
        "user_rating_5": _csv_number(audit["rating"]["value"]),
        "processor": text_or_none(row["processor"]) or "",
        "battery_mah": _csv_number(audit["battery"]["mah"]),
        "charging": audit["battery"]["charging"] or "",
        "display_inches": _csv_number(audit["display"]["inches"]),
        "display_type": audit["display"]["type"] or "",
        "rear_camera": text_or_none(row["rear_camera"]) or "",
        "front_camera": text_or_none(row["front_camera"]) or "",
        "release_date": audit["release"]["date"] or "",
        "release_status": audit["release"]["status"],
        "source_url": row["url"].strip(),
        "image_url": text_or_none(row["image_url"]) or "",
    }


def _summary(values: list[float | int]) -> list[float | int]:
    return [min(values), statistics.median(values), max(values)] if values else []


def audit_and_build(archive: Path, audit_dir: Path, catalogue_path: Path) -> dict:
    """Audit every row, write reproducible evidence, and create the core-only CSV."""
    if audit_dir.exists():
        raise FileExistsError("Choose a new audit directory; existing outputs are preserved")
    if catalogue_path.exists():
        raise FileExistsError("Choose a new catalogue path; existing output is preserved")
    started = time.perf_counter()
    digest_before = sha256(archive)
    records = []
    with zipfile.ZipFile(archive) as bundle:
        members = [
            member for member in bundle.infolist() if member.filename.lower().endswith(".csv")
        ]
        if len(members) != 1 or members[0].file_size > 20_000_000:
            raise ValueError("Expected one CSV smaller than 20 MB")
        member = members[0]
        with bundle.open(member) as stream:
            reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig"), strict=True)
            if reader.fieldnames != list(SOURCE_FIELDS):
                raise ValueError(f"Unexpected CSV schema: {reader.fieldnames!r}")
            for record_number, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"Malformed CSV record at {record_number}")
                records.append(
                    {"csv_record_number": record_number, "raw": row, "audit": inspect_mobile(row)}
                )
    if not records:
        raise ValueError("Empty dataset")
    if sha256(archive) != digest_before:
        raise RuntimeError("Source changed while auditing")

    product_ids = [record["audit"]["identity"]["product_id"] for record in records]
    valid_ids = [value for value in product_ids if value is not None]
    duplicate_product_ids = [item for item, count in Counter(valid_ids).items() if count > 1]
    eligible = [record for record in records if record["audit"]["eligible"]]
    final_rows = [final_record(record["raw"], record["audit"]) for record in eligible]
    final_ids = [row["product_id"] for row in final_rows]
    if len(final_ids) != len(set(final_ids)):
        raise ValueError("Eligible source rows contain duplicate product IDs; no rows were merged")

    counts = Counter()
    missing_by_field = Counter()
    for record in records:
        row = record["raw"]
        audit = record["audit"]
        for field in SOURCE_FIELDS:
            missing_by_field[field] += text_or_none(row[field]) is None
        for field in ("price", "rating", "capacity", "battery", "display"):
            counts[f"{field}_{audit[field]['status']}"] += 1
        counts[f"release_{audit['release']['status']}"] += 1
        counts[f"source_url_{audit['identity']['status']}"] += 1
        for reason in audit["rejection_reasons"]:
            counts[f"rejected_{reason}"] += 1

    final_missing = {
        field: sum(row[field] == "" for row in final_rows)
        for field in FINAL_FIELDS
        if field not in {"product_id", "product_name", "brand", "price_inr", "ram_gb", "storage_gb"}
    }
    prices = [row["price_inr"] for row in final_rows]
    ram_values = [float(row["ram_gb"]) for row in final_rows]
    storage_values = [float(row["storage_gb"]) for row in final_rows]
    years = Counter(
        row["release_date"][:4] if row["release_date"] else "unknown" for row in final_rows
    )
    rating_scales = Counter(
        record["audit"]["rating"]["source_scale"]
        for record in eligible
        if record["audit"]["rating"]["status"] == "valid"
    )
    exact_rows = {tuple(record["raw"][field] for field in SOURCE_FIELDS) for record in records}

    rng = random.Random(SEED)
    subsets = {"eligible": eligible}
    for reason in sorted(
        {reason for record in records for reason in record["audit"]["rejection_reasons"]}
    ):
        subsets[reason] = [
            record for record in records if reason in record["audit"]["rejection_reasons"]
        ]
    samples = {
        name: sorted(
            rng.sample(group, min(20, len(group))), key=lambda item: item["csv_record_number"]
        )
        for name, group in subsets.items()
    }

    catalogue_path.parent.mkdir(parents=True, exist_ok=True)
    with catalogue_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FINAL_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(final_rows)
    catalogue_digest = sha256(catalogue_path)

    report = {
        "source": {
            "url": SOURCE_URL,
            "listed_license": "CC0: Public Domain",
            "publisher_usage_note": "Learning/practice purposes; not for commercial use",
            "archive_sha256": digest_before,
            "archive_bytes": archive.stat().st_size,
            "member": member.filename,
            "csv_bytes": member.file_size,
            "csv_fields": list(SOURCE_FIELDS),
        },
        "run": {
            "utc": datetime.now(UTC).isoformat(),
            "seconds": round(time.perf_counter() - started, 4),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "seed": SEED,
        "rows": len(records),
        "unique_names": len({record["raw"]["name"] for record in records}),
        "unique_urls": len({record["raw"]["url"] for record in records}),
        "unique_valid_product_ids": len(set(valid_ids)),
        "duplicate_product_ids": sorted(duplicate_product_ids),
        "exact_duplicate_rows": len(records) - len(exact_rows),
        "missing_by_source_field": dict(missing_by_field),
        "counts": dict(sorted(counts.items())),
        "catalogue": {
            "rows": len(final_rows),
            "fields": list(FINAL_FIELDS),
            "optional_source_fields_excluded": list(OPTIONAL_SOURCE_FIELDS_EXCLUDED),
            "sha256": catalogue_digest,
            "missing_by_field": final_missing,
            "rating_source_scales": {
                str(key): value for key, value in sorted(rating_scales.items())
            },
            "release_years": dict(sorted(years.items())),
            "price_inr_min_median_max": _summary(prices),
            "ram_gb_min_median_max": _summary(ram_values),
            "storage_gb_min_median_max": _summary(storage_values),
        },
        "eligibility_rule": [
            "Non-empty product name and derived brand",
            "Valid unique HTTPS 91mobiles source URL",
            "Positive integer INR price",
            "Explicit parseable RAM and storage",
            "At least 1 GB RAM and 8 GB storage",
            "No announced or to-be-announced source marker",
        ],
        "limits": [
            "Source content and derived brand/device classification were not independently "
            "verified",
            "Prices and availability are historical source observations, not live offers",
            "No rating/review count exists, so rating confidence cannot be weighted",
            "Some core comparison attributes remain explicitly missing",
            "CC0 listing and publisher non-commercial usage note are in tension",
            "Variants remain separate because the source supplies unique names and URLs",
        ],
    }

    audit_dir.mkdir(parents=True, exist_ok=False)
    (audit_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (audit_dir / "samples.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (audit_dir / "records.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--catalogue", type=Path, required=True)
    args = parser.parse_args()
    report = audit_and_build(args.archive, args.audit_dir, args.catalogue)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
