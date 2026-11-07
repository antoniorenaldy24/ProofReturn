"""Commit-reveal audit draw with shopper nonce contribution (FR-61, FR-95, INV-16)."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class AuditCommitment:
    return_id: str
    commitment: str
    p: Fraction


@dataclass(frozen=True)
class AuditReveal:
    return_id: str
    commitment: str
    p: Fraction
    seed_platform_hex: str
    nonce_shopper: str
    beacon_value: str | None
    seed_final_hex: str
    u: Fraction
    selected: bool

    def verify_commitment(self, expected_return_id: str) -> bool:
        """INV-16 & MV-16: Verify revealed seed_platform hashes to commitment c."""
        if self.return_id != expected_return_id:
            return False
        seed_bytes = bytes.fromhex(self.seed_platform_hex)
        recomputed_c = hashlib.sha256(seed_bytes + b"||" + self.return_id.encode("utf-8")).hexdigest()
        return recomputed_c == self.commitment


def create_audit_commitment(
    seed_platform: bytes,
    return_id: str,
    p: Fraction,
) -> AuditCommitment:
    """FR-95: At approval, commit c = SHA-256(seed_platform || return_id) and record p."""
    c = hashlib.sha256(seed_platform + b"||" + return_id.encode("utf-8")).hexdigest()
    return AuditCommitment(return_id=return_id, commitment=c, p=p)


def reveal_and_draw_audit(
    commitment_record: AuditCommitment,
    seed_platform: bytes,
    nonce_shopper: str,
    beacon_value: str | None = None,
) -> AuditReveal:
    """FR-95: seed_final = SHA-256(seed_platform || nonce_shopper || beacon? || return_id); u = HMAC(seed_final, 'audit')."""
    # ASSUMPTION(A-27): Public randomness beacon is optional; shopper nonce is mandatory
    expected_c = hashlib.sha256(seed_platform + b"||" + commitment_record.return_id.encode("utf-8")).hexdigest()
    if expected_c != commitment_record.commitment:
        raise ValueError("Seed reveal does not match pre-committed hash c.")

    parts = [
        seed_platform,
        nonce_shopper.encode("utf-8"),
    ]
    if beacon_value is not None:
        parts.append(beacon_value.encode("utf-8"))
    parts.append(commitment_record.return_id.encode("utf-8"))

    seed_final = hashlib.sha256(b"||".join(parts)).digest()
    digest = hmac.new(seed_final, b"audit", hashlib.sha256).digest()
    # Map 64-bit integer prefix of HMAC digest to exact rational in [0, 1)
    int_val = int.from_bytes(digest[:8], "big")
    u = Fraction(int_val, 1 << 64)
    selected = u < commitment_record.p

    return AuditReveal(
        return_id=commitment_record.return_id,
        commitment=commitment_record.commitment,
        p=commitment_record.p,
        seed_platform_hex=seed_platform.hex(),
        nonce_shopper=nonce_shopper,
        beacon_value=beacon_value,
        seed_final_hex=seed_final.hex(),
        u=u,
        selected=selected,
    )
