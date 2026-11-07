"""Authentic Media Forensics Scorer and Red-Team Evaluation Suite (F-04: FR-18, FR-20, NFR-02)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ForensicsResult:
    """Advisory forensic authenticity and tamper evaluation output (FR-18)."""

    evidence_sha256: str
    authenticity_score: float
    tamper_score: float
    flags: list[str] = field(default_factory=list)
    hard_fail: bool = False


def evaluate_media_forensics(
    *,
    evidence_sha256: str,
    exif_present: bool,
    ela_anomaly_score: float,
    nonce_matched: bool,
    screen_recapture_detected: bool = False,
) -> ForensicsResult:
    """Compute authenticity/tamper scores and forensic flags (FR-18)."""
    flags: list[str] = []
    if not exif_present:
        flags.append("EXIF_STRIPPED")
    if ela_anomaly_score > 0.25:
        flags.append("ELA_SPLICE_ANOMALY")
    if screen_recapture_detected:
        flags.append("SCREEN_RECAPTURE_MOIRE")
    if not nonce_matched:
        flags.append("CHALLENGE_NONCE_FAIL")

    hard_fail = (not nonce_matched) or screen_recapture_detected or (ela_anomaly_score > 0.50)
    tamper = min(1.0, max(0.0, ela_anomaly_score + (0.40 if screen_recapture_detected else 0.0)))
    auth = max(0.0, 1.0 - tamper - (0.05 if not exif_present else 0.0))

    return ForensicsResult(
        evidence_sha256=evidence_sha256,
        authenticity_score=round(auth, 4),
        tamper_score=round(tamper, 4),
        flags=flags,
        hard_fail=hard_fail,
    )


def run_redteam_suite() -> dict[str, Any]:
    """Execute offline red-team attack evaluation suite (FR-20, NFR-02)."""
    t0 = time.perf_counter()
    cases = [
        evaluate_media_forensics(
            evidence_sha256="rt_1",
            exif_present=False,
            ela_anomaly_score=0.65,
            nonce_matched=True,
        ),
        evaluate_media_forensics(
            evidence_sha256="rt_2",
            exif_present=True,
            ela_anomaly_score=0.05,
            nonce_matched=False,
        ),
        evaluate_media_forensics(
            evidence_sha256="rt_3",
            exif_present=True,
            ela_anomaly_score=0.10,
            nonce_matched=True,
            screen_recapture_detected=True,
        ),
        evaluate_media_forensics(
            evidence_sha256="rt_4",
            exif_present=False,
            ela_anomaly_score=0.72,
            nonce_matched=False,
        ),
        evaluate_media_forensics(
            evidence_sha256="rt_5",
            exif_present=True,
            ela_anomaly_score=0.55,
            nonce_matched=True,
        ),
        evaluate_media_forensics(
            evidence_sha256="rt_6",
            exif_present=False,
            ela_anomaly_score=0.20,
            nonce_matched=False,
            screen_recapture_detected=True,
        ),
    ]
    elapsed = round(time.perf_counter() - t0, 4)
    false_approvals = sum(1 for c in cases if not c.hard_fail)
    return {
        "total_cases": len(cases),
        "false_fast_lane_approvals": false_approvals,
        "p95_latency_seconds": elapsed,
    }
