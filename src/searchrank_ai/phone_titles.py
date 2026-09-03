"""Conservative smartphone title probes for auditing, not catalogue facts.

Unlabelled RAM/storage pairs are reported separately as inferred evidence. Marketing
claims, model-name knowledge, and missing specifications never become invented facts.
"""

from __future__ import annotations

import re
import unicodedata

BRANDS = (
    "Samsung",
    "Redmi",
    "realme",
    "Motorola",
    "iQOO",
    "OnePlus",
    "Lava",
    "Vivo",
    "Apple",
    "OPPO",
    "POCO",
    "Nokia",
    "HMD",
    "itel",
    "Tecno",
    "Infinix",
    "Nothing",
    "Honor",
    "Xiaomi",
    "Google",
    "ZENO",
    "I KALL",
    "Jio",
    "BlackBerry",
    "ASUS",
)
_CAPACITY = r"(?<![\w.])(\d+(?:\.\d+)?)\s*(gb|tb)"
_LABELLED = re.compile(_CAPACITY + r"\s*(ram|rom|storage|internal memory)\b")
_PAIR = re.compile(_CAPACITY + r"\s*[,/+]\s*(\d+)\s*(gb|tb)\b")
_QUALIFIER = re.compile(r"up\s*to|upto|expand|extend|virtual|dynamic|boost")
_ACCESSORY = re.compile(
    r"\b(?:back\s+(?:cover|case)|flip\s+(?:cover|case)|screen\s+(?:protector|guard)"
    r"|tempered\s+glass|phone\s+(?:holder|stand|grip)|mobile\s+(?:holder|stand|pouch)"
    r"|case\s+(?:for|compatible)|cover\s+(?:for|compatible)|power\s*bank"
    r"|charging\s+(?:cable|station)|usb\s+cable|earbuds?|headphones?|earphones?"
    r"|wall\s+charger|travel\s+adapter|neckband|selfie\s+stick|micro\s*sd|pendrive"
    r"|otg\s+adapter|cleaning\s+kit|ring\s+holder|car\s+charger"
    r"|case|cover|cable|adaptor|adapter|holder|memory\s+card|mount|tripod)\b"
)
_KEYPAD = re.compile(r"\bkeypad\b|\bfeature\s*phone\b|\bnokia\s+2660\b")
_OTHER_DEVICE = re.compile(r"\b(?:tablet|smartwatch|laptop|ipad)\b")


def normalize(title: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", title).casefold()).strip()


def _finding(matches: list[dict], *, force_ambiguous: bool = False) -> dict:
    values = {item["value_gb"] for item in matches}
    status = "ambiguous" if force_ambiguous or len(values) > 1 else "found" if values else "missing"
    return {
        "status": status,
        "value_gb": next(iter(values)) if status == "found" else None,
        "evidence": matches,
    }


def probe_phone_title(title: str) -> dict:
    """Keep uncertain classification/specs explicit; preserve source separately.

    Brand matches are anchored at the start, optionally after a renewed label.
    GB/TB use decimal conversion; MB and unlabelled single capacities stay missing.
    Unlabelled pairs are hypotheses, never counted as explicit specification facts.
    """
    text = normalize(title)
    head = re.sub(r"^\(?\s*(?:renewed|refurbished)\s*\)?\s*", "", text)
    brand = next((b for b in BRANDS if re.match(rf"{re.escape(b.casefold())}(?!\w)", head)), None)
    if head.startswith("iphone "):
        brand = "Apple"
    ram, storage, inferred_ram, inferred_storage, ignored = [], [], [], [], []
    for match in _LABELLED.finditer(text):
        value = float(match[1]) * (1000 if match[2] == "tb" else 1)
        evidence = {"text": match[0], "value_gb": value, "offset": match.start()}
        preceding = text[max(0, match.start() - 25) : match.start()]
        # Only local qualifiers are applied here; later marketing RAM is not physical RAM.
        if value <= 0 or _QUALIFIER.search(preceding):
            ignored.append(evidence)
        elif match[3] == "ram":
            ram.append(evidence)
        else:
            storage.append(evidence)
    for match in _PAIR.finditer(text):
        first = float(match[1]) * (1000 if match[2] == "tb" else 1)
        second = float(match[3]) * (1000 if match[4] == "tb" else 1)
        surrounding = text[max(0, match.start() - 25) : match.end() + 18]
        if not (0 < first <= 32 and second >= 16 and second >= first * 2):
            continue
        if _QUALIFIER.search(surrounding):
            continue
        inferred_ram.append({"text": match[0], "value_gb": first, "offset": match.start()})
        inferred_storage.append({"text": match[0], "value_gb": second, "offset": match.start()})
    # Conservatively withhold a physical-RAM claim when the title advertises mixed RAM.
    mixed_ram = bool(re.search(r"virtual\s+ram|dynamic\s+ram|extended\s+ram|ram\s+expansion", text))
    ram_result = _finding(ram, force_ambiguous=bool(ram) and mixed_ram)
    storage_result = _finding(storage)
    pair_complete = bool(inferred_ram and inferred_storage)
    explicit_complete = ram_result["status"] == storage_result["status"] == "found"
    accessory_match = _ACCESSORY.search(text)
    if accessory_match:
        category = "accessory_or_bundle_review"
    elif _OTHER_DEVICE.search(text):
        category = "other_device_review"
    elif _KEYPAD.search(text):
        category = "keypad_review"
    elif brand and (
        explicit_complete
        or pair_complete
        or ram
        or storage
        or re.search(r"smart\s*phone|iphone|\b5g\b", text)
    ):
        category = "smartphone_candidate"
    else:
        category = "unresolved_review"
    return {
        "brand": brand,
        "classification": category,
        "classification_evidence": accessory_match[0] if accessory_match else None,
        "ram": ram_result,
        "storage": storage_result,
        "pair_ram": _finding(inferred_ram),
        "pair_storage": _finding(inferred_storage),
        "ignored_capacity_evidence": ignored,
        "mixed_ram_context": mixed_ram,
        "renewed_mentioned": bool(re.search(r"renewed|refurbished", text)),
        "has_devanagari": bool(re.search(r"[\u0900-\u097f]", title)),
    }
