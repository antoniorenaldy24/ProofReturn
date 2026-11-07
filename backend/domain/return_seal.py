"""One-time return seal issuance and check-in weight/nonce verification (FR-64, F-06)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from backend.domain.nonce import SealNonce, generate_seal_nonce


@dataclass
class ReturnSealRecord:
    return_id: str
    nonce: SealNonce
    origin_weight_g: int
    dropoff_photo_sha256: str | None = None
    checkin_weight_g: int | None = None
    seal_intact: bool = False


def issue_return_seal(return_id: str, origin_weight_g: int) -> ReturnSealRecord:
    """FR-64: Issue a one-time return seal with a fresh nonce at approval."""
    nonce = generate_seal_nonce(prefix="RET")
    return ReturnSealRecord(
        return_id=return_id,
        nonce=nonce,
        origin_weight_g=origin_weight_g,
    )


def verify_return_seal_at_checkin(
    seal: ReturnSealRecord,
    *,
    observed_nonce_code: str,
    checkin_weight_g: int,
    seal_intact: bool,
    tolerance: Fraction = Fraction(10, 100),
) -> tuple[bool, list[str]]:
    """FR-64 & FR-73: Verify seal integrity, nonce match, and weight within tolerance (default +/-10%)."""
    reasons: list[str] = []
    if not seal_intact:
        reasons.append("BROKEN_SEAL")
    if observed_nonce_code.strip().upper() != seal.nonce.nonce_code:
        reasons.append("SEAL_NONCE_MISMATCH")
    if seal.origin_weight_g > 0:
        diff = abs(checkin_weight_g - seal.origin_weight_g)
        if Fraction(diff, seal.origin_weight_g) > tolerance:
            reasons.append("WEIGHT_OUT_OF_TOLERANCE")
    seal.checkin_weight_g = checkin_weight_g
    seal.seal_intact = seal_intact
    return (len(reasons) == 0), reasons
