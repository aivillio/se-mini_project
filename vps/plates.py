"""Indian registration-plate normalisation and validation."""

from __future__ import annotations

import re

from vps.errors import InvalidPlate

# Standard series (e.g. KA01AB1234, DL3CAF0001) and Bharat series (e.g. 22BH1234AA)
_STANDARD = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$")
_BHARAT = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$")

CATEGORIES = ("2W", "4W", "EV", "HANDICAP")


def normalize_plate(raw: str) -> str:
    return re.sub(r"[\s\-.]", "", (raw or "")).upper()


def is_valid_plate(plate: str) -> bool:
    return bool(_STANDARD.match(plate) or _BHARAT.match(plate))


def validate_plate(raw: str) -> str:
    plate = normalize_plate(raw)
    if not is_valid_plate(plate):
        raise InvalidPlate(f"'{raw}' is not a valid registration number", details={"plate": raw})
    return plate


def validate_category(category: str) -> str:
    cat = (category or "").upper()
    if cat not in CATEGORIES:
        raise InvalidPlate(  # surfaced as 400 to the client
            f"Unknown vehicle category '{category}'", code="INVALID_CATEGORY", details={"allowed": CATEGORIES}
        )
    return cat


def mask_plate(plate: str) -> str:
    """For logs/receipts: KA01AB1234 -> KA01****34."""
    return plate[:4] + "*" * max(0, len(plate) - 6) + plate[-2:] if len(plate) > 6 else plate
