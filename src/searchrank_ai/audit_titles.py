"""Conservative title-only coverage probes, not a production product schema.

Every match is evidence from normalized source text. Unknown/ambiguous values stay
unset. Classification is a review aid, not a verified laptop ground-truth label.
"""

from __future__ import annotations

import re
import unicodedata

_TOKENS = {
    "सॉलिड स्टेट ड्राइव": "solid state drive",
    "फ्लैश मेमोरी": "flash memory",
    "हार्ड डिस्क": "hard disk",
    "एचडीडी": "hdd",
    "एसएसडी": "ssd",
    "ईएमएमसी": "emmc",
    "मेमोरी": "memory",
    "रैम": "ram",
    "जीबी": "gb",
    "टीबी": "tb",
}
_BRANDS = {
    "HP": ("hp", "एचपी", "एच पी"),
    "Lenovo": ("lenovo", "लेनोवो"),
    "Dell": ("dell", "डेल"),
    "ASUS": ("asus", "आसुस"),
    "Acer": ("acer", "एसर"),
    "Apple": ("apple", "एप्पल", "ऐप्पल"),
    "MSI": ("msi",),
    "Samsung": ("samsung", "सैमसंग"),
    "Microsoft": ("microsoft", "माइक्रोसॉफ्ट"),
    "Jio": ("jio", "जियो"),
    "AVITA": ("avita",),
    "Infinix": ("infinix",),
    "LG": ("lg",),
    "Fujitsu": ("fujitsu",),
    "GIGABYTE": ("gigabyte",),
    "Honor": ("honor",),
    "Huawei": ("huawei",),
    "Chuwi": ("chuwi",),
    "Toshiba": ("toshiba", "तोशिबा"),
}
_DDR = r"(?:lp)?ddr\s*-?\s*[345](?:x)?(?:\s*(?:ram|memory))?"
_RAM = re.compile(rf"(?<![\w.])(\d+)\s*gb\s*(?:{_DDR}|sdram|ram|memory)(?!\w)")
_DRIVE_TYPE = r"(?:ssd|hdd|emmc|flash memory|solid state(?: drive)?|hard (?:disk|drive))"
_DRIVE_MODIFIER = r"(?:(?:pcie(?:\s*\d(?:\.\d)?)?|nvme|m\.2|sata)\s+)*"
_STORAGE = re.compile(
    rf"(?<![\w.])(\d+(?:\.\d+)?)\s*(gb|tb)\s*{_DRIVE_MODIFIER}{_DRIVE_TYPE}(?!\w)"
)
_PAIR = re.compile(
    rf"(?<![\w.])(\d+)\s*gb\s*/\s*\d+(?:\.\d+)?\s*(?:gb|tb)"
    rf"\s*{_DRIVE_MODIFIER}{_DRIVE_TYPE}(?!\w)"
)
_RENEWED = re.compile(r"renewed|refurbished|नवीनीकृत|नवीकृत|पुनर्जीवित|रीन्यूड|रिन्यूड|फिर से नया")
_ACCESSORY = re.compile(
    r"skin|स्किन|स्टिकर|sticker|screen guard|स्क्रीन गार्ड|replacement|रिप्लेसमेंट"
    r"|adapter|एडाप्टर|एडेप्टर|charger|चार्जर|बैग|backpack|sleeve|लैपटॉप स्टैंड"
    r"|protector|प्रोटेक्टर|रक्षक|टचपैड|touchpad|कीबोर्ड कवर"
)
_DESKTOP = re.compile(
    r"desktop|डेस्कटॉप|\btower\b|मिनी पीसी|mini pc|thinkcentre|थिंकसेंटर"
    r"|elitedesk|elite desk|prodesk|optiplex|ऑप्टिप्लेक्स"
)
_TABLET = re.compile(r"tablet|टैबलेट")


def normalize_title(title: str) -> str:
    """Normalize for matching only; callers retain the unchanged original title."""
    text = unicodedata.normalize("NFKC", title).casefold()
    for original, replacement in _TOKENS.items():
        text = text.replace(original, replacement)
    return re.sub(r"\s+", " ", text).strip()


def _finding(values: set, matches: list[str]) -> dict:
    status = "found" if len(values) == 1 else "ambiguous" if values else "missing"
    return {
        "value": next(iter(values)) if status == "found" else None,
        "status": status,
        "normalized_matches": matches,
    }


def probe_title(title: str) -> dict:
    """Estimate recoverable fields without guessing from a model name or price.

    Slash-pair RAM (16GB/512GB SSD) is reported separately from explicit RAM.
    Multiple drive mentions are unresolved, even when they might be additive.
    TB uses a declared decimal GB-equivalent conversion (1 TB = 1,000 GB).
    """
    text = normalize_title(title)
    brands = {
        brand
        for brand, aliases in _BRANDS.items()
        if any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text) for alias in aliases)
    }
    brand = _finding(brands, sorted(brands))
    explicit = list(_RAM.finditer(text))
    pairs = list(_PAIR.finditer(text))
    ram_matches = explicit + pairs
    ram = _finding(
        {int(match[1]) for match in ram_matches if 0 < int(match[1]) <= 256},
        [match[0] for match in ram_matches],
    )
    ram["rule"] = "explicit" if explicit else "slash_pair" if pairs else None
    # Upgrade ceilings and accessory memory must not become installed-RAM facts.
    if ram_matches and re.search(r"up to|upto|expandable|upgrade|अपग्रेड|विस्तार", text):
        ram.update(value=None, status="ambiguous", rule="upgrade_context")

    drives = list(_STORAGE.finditer(text))
    storage = _finding(
        {float(match[1]) * (1000 if match[2] == "tb" else 1) for match in drives},
        [match[0] for match in drives],
    )
    if len(drives) > 1 or (drives and re.search(r"external|बाहरी|up to|expandable", text)):
        storage.update(value=None, status="ambiguous")
    if storage["value"] is not None and storage["value"] <= 0:
        storage.update(value=None, status="ambiguous")

    hardware_pair = ram["value"] is not None and storage["value"] is not None
    if _DESKTOP.search(text):
        classification = "desktop_keyword_review"
    elif _TABLET.search(text):
        classification = "tablet_keyword_review"
    elif _ACCESSORY.search(text):
        classification = (
            "bundle_or_accessory_review" if hardware_pair else "accessory_keyword_review"
        )
    elif brand["value"] is not None and hardware_pair:
        classification = "candidate_with_specs"
    else:
        classification = "unresolved_title_review"
    return {
        "brand": brand,
        "ram_gb": ram,
        "storage_gb_decimal": storage,
        "classification": classification,
        "condition": "renewed_mentioned" if _RENEWED.search(text) else "not_stated_as_renewed",
        "has_devanagari": bool(re.search(r"[\u0900-\u097f]", title)),
    }
