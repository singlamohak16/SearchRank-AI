"""Synthetic tests for the approved 91mobiles catalogue pipeline."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest

from searchrank_ai.data_audit import sha256
from searchrank_ai.mobile_catalogue import (
    FINAL_FIELDS,
    OPTIONAL_SOURCE_FIELDS_EXCLUDED,
    SOURCE_FIELDS,
    audit_and_build,
    derive_brand,
    inspect_mobile,
    parse_battery,
    parse_display,
    parse_price,
    parse_ram_storage,
    parse_rating,
    parse_release,
    source_identity,
)


def row(**changes: str) -> dict[str, str]:
    values = dict(
        zip(
            SOURCE_FIELDS,
            (
                "Moto Test Phone 5G",
                "https://www.91mobiles.com/moto-test-phone-5g-price-in-india",
                "Release Date:01 Jan, 2025",
                "80%",
                "https://www.91-img.com/test.jpg",
                "Test Processor",
                "8 GB RAM | 256 GB Storage",
                "50 MP Rear Camera",
                "16 MP Front Camera",
                "5000 mAh | 45W Fast Charging",
                "6.5 inches (16.51 cm) | AMOLED",
                "AnTuTu Score 1,000,000",
                "Best Phones",
                "4.4/5",
                "8.1/10",
                "₹24,999",
                "Amazon",
            ),
            strict=True,
        )
    )
    values.update(changes)
    return values


def archive(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=SOURCE_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    path = tmp_path / "source.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("mobiles_data.csv", buffer.getvalue().encode("utf-8-sig"))
    return path


@pytest.mark.parametrize(
    "raw,status,value",
    [
        ("₹24,999", "valid", 24999),
        ("N/A", "missing", None),
        ("₹0", "invalid", None),
        ("24999", "invalid", None),
        ("₹2.5", "invalid", None),
        ("₹-1", "invalid", None),
    ],
)
def test_price_parser(raw, status, value):
    assert parse_price(raw) == {"status": status, "value": value}


@pytest.mark.parametrize(
    "raw,status,value,scale",
    [
        ("4.4/5", "valid", 4.4, 5),
        ("8.4/10", "valid", 4.2, 10),
        ("N/A", "missing", None, None),
        ("11/10", "invalid", None, 10),
        ("0/5", "invalid", None, 5),
        ("4.4", "invalid", None, None),
    ],
)
def test_rating_parser(raw, status, value, scale):
    assert parse_rating(raw) == {"status": status, "value": value, "source_scale": scale}


@pytest.mark.parametrize(
    "raw,status,ram,storage",
    [
        ("8 GB RAM | 256 GB Storage", "valid", 8, 256),
        ("12 GB RAM | 1 TB Storage", "valid", 12, 1000),
        ("12GB RAM + 256GB ROM", "valid", 12, 256),
        ("512 MB RAM | 4 GB Storage", "valid", 0.512, 4),
        ("N/A", "missing", None, None),
        ("8GB + 256GB", "invalid", None, None),
    ],
)
def test_capacity_parser(raw, status, ram, storage):
    assert parse_ram_storage(raw) == {"status": status, "ram_gb": ram, "storage_gb": storage}


def test_battery_display_and_release_parsers():
    assert parse_battery("5000 mAh | 45W Fast Charging") == {
        "status": "valid",
        "mah": 5000,
        "charging": "45W Fast Charging",
    }
    assert parse_battery("3000 mAh Fast Charging")["charging"] == "Fast Charging"
    assert parse_display("6.5 inches (16.51 cm) | AMOLED") == {
        "status": "valid",
        "inches": 6.5,
        "type": "AMOLED",
    }
    assert parse_release("Release Date:01 Jan, 2025") == {
        "status": "released",
        "date": "2025-01-01",
    }
    assert parse_release("Announced on:02 Jul, 2026")["status"] == "announced"
    assert parse_release("Release Date:To be announced on22 Jul, 2026")["status"] == "announced"
    assert parse_release("Release Date:Available for Sale on30 Jul, 2026")["status"] == "available"
    assert parse_release("N/A") == {"status": "unknown", "date": None}


def test_source_id_brand_and_untrusted_url_rules():
    valid = source_identity("https://www.91mobiles.com/test-phone-price-in-india")
    assert valid == {"status": "valid", "product_id": "91mobiles:test-phone"}
    for url in (
        "http://www.91mobiles.com/test-phone-price-in-india",
        "https://www.91mobiles.com.evil.example/test-phone-price-in-india",
        "https://www.91mobiles.com/test-phone-price-in-india?q=1",
        "https://[broken",
    ):
        assert source_identity(url)["status"] == "invalid"
    assert derive_brand("I KALL Test") == "I KALL"
    assert derive_brand("Black Shark Test") == "Black Shark"
    assert derive_brand("Moto Test") == "Motorola"


def test_eligibility_is_strict_and_missing_optional_core_values_stay_missing():
    source = row(processor="N/A", user_rating="N/A", front_camera="N/A")
    result = inspect_mobile(source)
    assert result["eligible"]
    assert result["rating"]["value"] is None
    assert source["processor"] == "N/A"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"price": "N/A"}, "price_missing"),
        ({"ram_storage": "N/A"}, "ram_storage_missing"),
        ({"ram_storage": "512 MB RAM | 4 GB Storage"}, "feature_phone_capacity"),
        ({"release_date": "Announced on:02 Jul, 2026"}, "announced_not_released"),
        ({"url": "https://evil.example/test-price-in-india"}, "invalid_source_url"),
    ],
)
def test_rejection_reasons_are_exposed(changes, reason):
    result = inspect_mobile(row(**changes))
    assert not result["eligible"]
    assert reason in result["rejection_reasons"]


def test_pipeline_preserves_raw_rows_and_writes_only_core_columns(tmp_path):
    source_rows = [
        row(),
        row(
            name="I KALL Feature",
            url="https://www.91mobiles.com/i-kall-feature-price-in-india",
            ram_storage="32 MB RAM | 32 MB Storage",
            spec_score="99%",
        ),
        row(
            name="vivo Missing Rating",
            url="https://www.91mobiles.com/vivo-missing-rating-price-in-india",
            user_rating="N/A",
            processor="N/A",
        ),
    ]
    source = archive(tmp_path, source_rows)
    before = sha256(source)
    audit_dir = tmp_path / "audit"
    catalogue = tmp_path / "processed" / "catalogue.csv"
    report = audit_and_build(source, audit_dir, catalogue)
    assert report["rows"] == 3
    assert report["catalogue"]["rows"] == 2
    assert report["counts"]["rejected_feature_phone_capacity"] == 1
    assert report["catalogue"]["optional_source_fields_excluded"] == list(
        OPTIONAL_SOURCE_FIELDS_EXCLUDED
    )
    with catalogue.open(encoding="utf-8", newline="") as stream:
        cleaned = list(csv.DictReader(stream))
    assert tuple(cleaned[0]) == FINAL_FIELDS
    assert all(field not in cleaned[0] for field in OPTIONAL_SOURCE_FIELDS_EXCLUDED)
    assert cleaned[1]["user_rating_5"] == ""
    assert cleaned[1]["processor"] == ""
    retained = [
        json.loads(line)["raw"]
        for line in (audit_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert retained == source_rows
    assert sha256(source) == before


def test_pipeline_is_reproducible_and_refuses_overwrite(tmp_path):
    source = archive(tmp_path, [row()])
    first = audit_and_build(source, tmp_path / "first", tmp_path / "first.csv")
    second = audit_and_build(source, tmp_path / "second", tmp_path / "second.csv")
    first.pop("run")
    second.pop("run")
    assert first == second
    assert (tmp_path / "first.csv").read_bytes() == (tmp_path / "second.csv").read_bytes()
    assert (tmp_path / "first" / "records.jsonl").read_bytes() == (
        tmp_path / "second" / "records.jsonl"
    ).read_bytes()
    with pytest.raises(FileExistsError):
        audit_and_build(source, tmp_path / "first", tmp_path / "new.csv")
    with pytest.raises(FileExistsError):
        audit_and_build(source, tmp_path / "third", tmp_path / "first.csv")


@pytest.mark.parametrize(
    "payload",
    [
        "wrong,header\n1,2\n",
        ",".join(SOURCE_FIELDS) + "\na,b,c\n",
        ",".join(SOURCE_FIELDS) + "\n",
    ],
)
def test_bad_sources_fail_before_outputs(tmp_path, payload):
    source = tmp_path / "bad.zip"
    with zipfile.ZipFile(source, "w") as bundle:
        bundle.writestr("source.csv", payload)
    with pytest.raises(ValueError):
        audit_and_build(source, tmp_path / "out", tmp_path / "catalogue.csv")
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "catalogue.csv").exists()


def test_duplicate_product_ids_are_not_silently_merged(tmp_path):
    source = archive(tmp_path, [row(), row(name="Different source name")])
    with pytest.raises(ValueError, match="duplicate product IDs"):
        audit_and_build(source, tmp_path / "out", tmp_path / "catalogue.csv")
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "catalogue.csv").exists()
