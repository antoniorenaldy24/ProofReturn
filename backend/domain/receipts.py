"""Tamper-evident Shopper Receipts signed by the platform key (FR-76)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.domain.signing import (
    canonical_json_bytes,
    sha256_hex,
    sign_message_ed25519,
    verify_message_ed25519,
)

ALLOWED_RECEIPT_KINDS = {"INTAKE", "CHECKIN", "SETTLEMENT", "DELIVERY"}


@dataclass(frozen=True)
class SignedReceipt:
    receipt_id: str
    return_id: str
    kind: str
    payload: dict[str, Any]
    payload_hash: str
    signature: str
    key_id: str
    sent_at: str


def issue_signed_receipt(
    *,
    receipt_id: str,
    return_id: str,
    kind: str,
    payload: dict[str, Any],
    signing_private_key: bytes,
    key_id: str,
) -> SignedReceipt:
    if kind not in ALLOWED_RECEIPT_KINDS:
        raise ValueError(f"Unsupported receipt kind: {kind}")
    envelope = {
        "receipt_id": receipt_id,
        "return_id": return_id,
        "kind": kind,
        "payload": payload,
    }
    p_hash = sha256_hex(canonical_json_bytes(envelope))
    sig = sign_message_ed25519(signing_private_key, p_hash)
    return SignedReceipt(
        receipt_id=receipt_id,
        return_id=return_id,
        kind=kind,
        payload=payload,
        payload_hash=p_hash,
        signature=sig,
        key_id=key_id,
        sent_at=datetime.now(UTC).isoformat(),
    )


def verify_signed_receipt(receipt: SignedReceipt, public_key_bytes: bytes) -> bool:
    envelope = {
        "receipt_id": receipt.receipt_id,
        "return_id": receipt.return_id,
        "kind": receipt.kind,
        "payload": receipt.payload,
    }
    expected_hash = sha256_hex(canonical_json_bytes(envelope))
    if expected_hash != receipt.payload_hash:
        return False
    return verify_message_ed25519(public_key_bytes, receipt.payload_hash, receipt.signature)
