"""Application-owned labels and comparison rules, independent of model output."""

FIELD_LABELS = {
    "product_name": "product name",
    "brand": "brand",
    "price_inr": "price",
    "ram_gb": "RAM",
    "storage_gb": "storage",
    "user_rating_5": "user rating",
    "processor": "processor",
    "battery_mah": "battery capacity",
    "charging": "charging",
    "display_inches": "display size",
    "display_type": "display type",
    "rear_camera": "rear camera",
    "front_camera": "front camera",
    "release_date": "release date",
    "release_status": "release status",
}

# These attributes are not collected by the adopted catalogue schema.
UNCOLLECTED_FIELD_LABELS = {
    "weight_g": "weight",
    "rating_count": "rating count",
    "live_price_inr": "live price",
    "stock_availability": "current stock availability",
    "warranty": "warranty",
}

# A neutral criterion permits either factual direction, but cannot imply a winner
# for a preference. Directional criteria have exactly one allowed direction.
COMPARISON_RULES: dict[str, tuple[str, str | None]] = {
    "price": ("price_inr", None),
    "lowest price": ("price_inr", "lower"),
    "highest price": ("price_inr", "higher"),
    "ram": ("ram_gb", None),
    "most ram": ("ram_gb", "higher"),
    "least ram": ("ram_gb", "lower"),
    "storage": ("storage_gb", None),
    "most storage": ("storage_gb", "higher"),
    "least storage": ("storage_gb", "lower"),
    "rating": ("user_rating_5", None),
    "highest rating": ("user_rating_5", "higher"),
    "lowest rating": ("user_rating_5", "lower"),
    "battery capacity": ("battery_mah", None),
    "largest battery capacity": ("battery_mah", "higher"),
    "smallest battery capacity": ("battery_mah", "lower"),
    "display size": ("display_inches", None),
    "largest display": ("display_inches", "higher"),
    "smallest display": ("display_inches", "lower"),
}

NUMERIC_COMPARISON_FIELDS = frozenset(rule[0] for rule in COMPARISON_RULES.values())
