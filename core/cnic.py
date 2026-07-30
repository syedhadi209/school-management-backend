import re

from rest_framework import serializers


CNIC_DIGITS = 13


def normalize_cnic(value: str | None) -> str:
    """Strip separators and return digits only. Empty input stays empty."""
    if not value:
        return ""
    return re.sub(r"\D", "", str(value).strip())


def format_cnic(value: str | None) -> str:
    """Display a 13-digit CNIC as 00000-0000000-0 when possible."""
    digits = normalize_cnic(value)
    if len(digits) != CNIC_DIGITS:
        return digits
    return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"


def validate_cnic(value: str | None) -> str:
    """
    Validate an optional CNIC.

    Returns the normalised 13-digit string, or "" when blank.
    Raises a DRF ValidationError for malformed values.
    """
    digits = normalize_cnic(value)
    if not digits:
        return ""
    if len(digits) != CNIC_DIGITS:
        raise serializers.ValidationError(
            "Enter a valid 13-digit CNIC (e.g. 00000-0000000-0)."
        )
    return digits
