"""Cryptographic nonce generation for origin and return package seals (FR-04, FR-64)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from backend.domain.signing import sha256_hex


@dataclass(frozen=True)
class SealNonce:
    nonce_code: str
    nonce_hash: str
    qr_payload: str


def generate_seal_nonce(prefix: str = "PR") -> SealNonce:
    """Generate an unpredictable seal nonce with human-readable code and SHA-256 hash (FR-04)."""
    raw_token = secrets.token_hex(8).upper()
    short_code = f"{prefix}-{raw_token[:4]}-{raw_token[4:8]}"
    full_nonce = f"{short_code}:{raw_token}"
    return SealNonce(
        nonce_code=short_code,
        nonce_hash=sha256_hex(full_nonce),
        qr_payload=full_nonce,
    )
