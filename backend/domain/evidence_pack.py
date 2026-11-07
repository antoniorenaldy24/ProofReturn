"""Dispute Evidence Pack Generator (F-07: FR-32, FR-33, FR-34, FR-35)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class EvidencePack:
    """Structured and printable Evidence Pack for PayPal disputes and shopper downloads."""

    pack_id: str
    return_id: str
    order_id: str
    passport_id: str
    decision_id: str
    dispute_id: str | None
    refund_request_ids: list[str]
    custody_intervals: list[str]
    canonical_sha256: str
    summary_markdown: str
    buyer_downloadable: bool = True


def generate_evidence_pack(
    *,
    return_id: str,
    order_id: str,
    passport_id: str,
    decision_id: str,
    refund_request_ids: list[str],
    custody_intervals: list[str],
    dispute_id: str | None = None,
) -> EvidencePack:
    """Generate a canonical Evidence Pack with SHA-256 integrity hash (FR-33, FR-35)."""
    payload = {
        "return_id": return_id,
        "order_id": order_id,
        "passport_id": passport_id,
        "decision_id": decision_id,
        "dispute_id": dispute_id,
        "refund_request_ids": refund_request_ids,
        "custody_intervals": custody_intervals,
    }
    canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    summary = (
        f"# ProofReturn Evidence Pack — {return_id}\n\n"
        f"- **Order ID**: `{order_id}`\n"
        f"- **Passport ID**: `{passport_id}`\n"
        f"- **Decision ID**: `{decision_id}`\n"
        f"- **Dispute Reference**: `{dispute_id or 'N/A'}`\n"
        f"- **Custody Chain**: `{' -> '.join(custody_intervals)}`\n"
        f"- **Canonical SHA-256**: `{digest}`\n"
    )
    return EvidencePack(
        pack_id=f"ep_{return_id}",
        return_id=return_id,
        order_id=order_id,
        passport_id=passport_id,
        decision_id=decision_id,
        dispute_id=dispute_id,
        refund_request_ids=list(refund_request_ids),
        custody_intervals=list(custody_intervals),
        canonical_sha256=digest,
        summary_markdown=summary,
        buyer_downloadable=True,
    )
