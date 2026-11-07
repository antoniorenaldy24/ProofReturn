"""Keyed HMAC-SHA256 Serial & Lifecycle Registry (F-12: FR-53, INV-13)."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any


def normalize_serial(raw_serial: str) -> str:
    """Normalize serial string by stripping whitespace/hyphens and upper-casing."""
    return "".join(ch for ch in raw_serial.strip().upper() if ch.isalnum())


def compute_serial_commitment(merchant_secret: bytes, merchant_id: str, raw_serial: str) -> str:
    """Compute keyed HMAC-SHA256(merchant_secret, merchant_id + ':' + normalize(serial)) per INV-13."""
    norm = normalize_serial(raw_serial)
    msg = f"{merchant_id}:{norm}".encode()
    return hmac.new(merchant_secret, msg, hashlib.sha256).hexdigest()


@dataclass
class SerialRegistryEntry:
    """Stored serial commitment record (never stores plaintext serial per INV-13)."""

    merchant_id: str
    order_id: str
    passport_id: str
    serial_Commitment: str
    status: str = "ACTIVE"


class SerialRegistry:
    """Detects cross-order serial swaps and repeat-refund attempts using keyed HMAC commitments."""

    def __init__(self, merchant_secret: bytes) -> None:
        self._secret = merchant_secret
        self._by_order: dict[tuple[str, str], SerialRegistryEntry] = {}

    def register_origin_serial(
        self,
        *,
        merchant_id: str,
        order_id: str,
        passport_id: str,
        raw_serial: str,
    ) -> SerialRegistryEntry:
        commitment = compute_serial_commitment(self._secret, merchant_id, raw_serial)
        entry = SerialRegistryEntry(
            merchant_id=merchant_id,
            order_id=order_id,
            passport_id=passport_id,
            serial_Commitment=commitment,
            status="ACTIVE",
        )
        self._by_order[(merchant_id, order_id)] = entry
        return entry

    def mark_serial_refunded(self, *, merchant_id: str, order_id: str) -> None:
        entry = self._by_order[(merchant_id, order_id)]
        entry.status = "REFUNDED"

    def verify_return_serial(
        self,
        *,
        merchant_id: str,
        order_id: str,
        raw_serial: str,
    ) -> dict[str, Any]:
        entry = self._by_order.get((merchant_id, order_id))
        if not entry:
            return {"matched": False, "flag": "ORDER_SERIAL_NOT_REGISTERED"}
        candidate = compute_serial_commitment(self._secret, merchant_id, raw_serial)
        if not hmac.compare_digest(entry.serial_Commitment, candidate):
            return {"matched": False, "flag": "SERIAL_MISMATCH"}
        if entry.status == "REFUNDED":
            return {"matched": False, "flag": "SERIAL_ALREADY_REFUNDED"}
        return {"matched": True, "status": "MATCHED_ACTIVE", "serial_commitment": candidate}
