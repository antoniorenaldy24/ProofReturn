"""Daily Hash-Chain Merkle Anchor Token Generator (F-01: FR-83)."""

from __future__ import annotations

from typing import Any

from backend.domain.signing import sha256_hex, sign_message_ed25519


def create_daily_anchor_token(
    *,
    date_str: str,
    head_hashes: list[str],
    signing_seed: bytes,
) -> dict[str, Any]:
    """Compute a daily Merkle/digest root over Passport and Decision chain heads and sign it (FR-83)."""
    if not signing_seed or len(signing_seed) < 32:
        raise ValueError("INV-13 violation: signing_seed must be at least 32 bytes.")
    combined = f"{date_str}:{'|'.join(sorted(head_hashes))}".encode()
    merkle_root = sha256_hex(combined)
    sig = sign_message_ed25519(signing_seed, combined)
    return {
        "date": date_str,
        "chains_anchored": len(head_hashes),
        "merkle_root": merkle_root,
        "signature": sig,
    }
