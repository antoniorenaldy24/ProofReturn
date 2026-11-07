"""Deterministic, hash-chained Decision Record and lineage builder (FR-27, INV-06, INV-09, Section 31.4)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from backend.domain.signing import canonical_json_bytes, sha256_hex


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    return_id: str
    policy_version_id: str
    inputs_hash: str
    lane: str
    timing: str
    x_max_minor: int
    x_released_minor: int
    holdback_minor: int
    binding_constraint: str
    p: Fraction
    audit_commitment: str
    nonce_shopper: str
    explanation: str
    prev_hash: str | None
    hash: str


def build_decision_record(
    *,
    decision_id: str,
    return_id: str,
    policy_version_id: str,
    inputs_payload: dict[str, Any],
    lane: str,
    timing: str,
    x_max_minor: int,
    x_released_minor: int,
    holdback_minor: int,
    binding_constraint: str,
    p: Fraction,
    audit_commitment: str,
    nonce_shopper: str,
    explanation: str,
    prev_hash: str | None,
) -> DecisionRecord:
    """FR-27 & INV-06: Every money decision stores inputs_hash, non-empty explanation, and hash-chain link."""
    if not explanation or not explanation.strip():
        raise ValueError("INV-06 violation: Decision explanation must be non-empty.")

    inputs_hash = sha256_hex(canonical_json_bytes(inputs_payload))
    chain_body = {
        "decision_id": decision_id,
        "return_id": return_id,
        "policy_version_id": policy_version_id,
        "inputs_hash": inputs_hash,
        "lane": lane,
        "timing": timing,
        "x_max_minor": x_max_minor,
        "x_released_minor": x_released_minor,
        "holdback_minor": holdback_minor,
        "binding_constraint": binding_constraint,
        "p": f"{p.numerator}/{p.denominator}",
        "audit_commitment": audit_commitment,
        "nonce_shopper": nonce_shopper,
        "explanation": explanation,
        "prev_hash": prev_hash,
    }
    record_hash = sha256_hex(canonical_json_bytes(chain_body))
    return DecisionRecord(
        decision_id=decision_id,
        return_id=return_id,
        policy_version_id=policy_version_id,
        inputs_hash=inputs_hash,
        lane=lane,
        timing=timing,
        x_max_minor=x_max_minor,
        x_released_minor=x_released_minor,
        holdback_minor=holdback_minor,
        binding_constraint=binding_constraint,
        p=p,
        audit_commitment=audit_commitment,
        nonce_shopper=nonce_shopper,
        explanation=explanation,
        prev_hash=prev_hash,
        hash=record_hash,
    )


def verify_decision_chain(records: list[DecisionRecord]) -> bool:
    """INV-09: Verify append-only hash chain across decisions."""
    prev: str | None = None
    for rec in records:
        if rec.prev_hash != prev:
            return False
        chain_body = {
            "decision_id": rec.decision_id,
            "return_id": rec.return_id,
            "policy_version_id": rec.policy_version_id,
            "inputs_hash": rec.inputs_hash,
            "lane": rec.lane,
            "timing": rec.timing,
            "x_max_minor": rec.x_max_minor,
            "x_released_minor": rec.x_released_minor,
            "holdback_minor": rec.holdback_minor,
            "binding_constraint": rec.binding_constraint,
            "p": f"{rec.p.numerator}/{rec.p.denominator}",
            "audit_commitment": rec.audit_commitment,
            "nonce_shopper": rec.nonce_shopper,
            "explanation": rec.explanation,
            "prev_hash": rec.prev_hash,
        }
        expected = sha256_hex(canonical_json_bytes(chain_body))
        if rec.hash != expected:
            return False
        prev = rec.hash
    return True
