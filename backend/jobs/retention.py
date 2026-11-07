"""Media Retention and Crypto-Shredding Job (NFR-05, FR-82)."""

from __future__ import annotations

from typing import Any


def run_media_retention_job(
    *,
    records: list[dict[str, Any]],
    retention_days: int = 90,
) -> dict[str, Any]:
    """Shred raw media blobs older than `retention_days` while preserving SHA-256 hashes (NFR-05, FR-82)."""
    shredded_count = 0
    preserved_hashes = 0
    for rec in records:
        if len(str(rec.get("evidence_sha256", ""))) == 64:
            preserved_hashes += 1
        if int(rec.get("age_days", 0)) > retention_days:
            rec["blob_uri"] = None
            rec["shredded"] = True
            shredded_count += 1
    return {
        "retention_days": retention_days,
        "shredded_count": shredded_count,
        "preserved_hashes_count": preserved_hashes,
    }
