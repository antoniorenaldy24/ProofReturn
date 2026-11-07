"""Sensitive data scrubber for structured JSON logs and OTel spans (INV-13, NFR-08)."""

from __future__ import annotations

from typing import Any

SENSITIVE_KEYS: set[str] = {
    "serial_raw",
    "buyer_email",
    "payer_id",
    "shopper_email",
    "card_number",
    "shipping_address",
    "phone_number",
}


def scrub_sensitive_log(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `payload` with all plaintext serials and PII keys redacted (INV-13)."""
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if key in SENSITIVE_KEYS:
            cleaned[key] = "[REDACTED]"
        elif isinstance(value, dict):
            cleaned[key] = scrub_sensitive_log(value)
        else:
            cleaned[key] = value
    return cleaned
