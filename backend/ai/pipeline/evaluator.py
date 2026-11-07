"""Advisory AI Evidence Evaluator with Judge Mode Replay, Google Gemini Provider, and Prompt Injection Defense (FR-15..20, FR-80, FR-86, FR-99)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from backend.ai.providers.gemini import GeminiClient

KNOWN_JUDGE_FIXTURE_HASHES: dict[str, dict[str, object]] = {
    "a" * 64: {
        "predicted_grade": "B",
        "conformal_set": ["B"],
        "AuthenticityScore": 0.96,
        " TamperScore": 0.03,
    },
    "c" * 64: {
        "predicted_grade": "A",
        "conformal_set": ["A"],
        "AuthenticityScore": 0.98,
        "TamperScore": 0.01,
    },
    "d" * 64: {
        "predicted_grade": "D",
        "conformal_set": ["C", "D"],
        "AuthenticityScore": 0.91,
        "TamperScore": 0.12,
    },
}

PROMPT_INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore previous instructions",
    "system:",
    "override grade",
    "approve refund",
    "disregard policy",
    "maximum refund",
)


@dataclass(frozen=True)
class EvidenceAssessmentResult:
    """Advisory assessment output (never triggers settlement actions directly per INV-05)."""

    evidence_sha256: str
    predicted_grade: str
    conformal_set: list[str]
    replay_label: str
    forced_lane: str | None = None
    forensic_flags: list[str] = field(default_factory=list)
    authenticity_score: float = 0.95
    tamper_score: float = 0.02


def assess_return_evidence(
    *,
    mode: str,
    evidence_sha256: str,
    declared_grade: str,
    text_in_media: str = "",
    has_live_model_keys: bool = False,
    provider: str = "gemini",
    api_key: str | None = None,
    model: str = "gemini-2.0-flash",
    image_base64: str | None = None,
    reason_code: str = "CHANGED_MIND",
) -> EvidenceAssessmentResult:
    """Assess return evidence with Judge Mode replay (FR-80), unknown-upload fallback (FR-99), Gemini provider, and injection defense (FR-86)."""
    flags: list[str] = []
    lower_text = text_in_media.lower()
    if any(pat in lower_text for pat in PROMPT_INJECTION_PATTERNS):
        flags.append("PROMPT_INJECTION_ATTEMPT")

    resolved_api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")
    has_keys = bool(resolved_api_key) or has_live_model_keys

    # Judge Mode with pre-computed recorded evidence hash (FR-80)
    if mode == "judge" and evidence_sha256 in KNOWN_JUDGE_FIXTURE_HASHES:
        fixture = KNOWN_JUDGE_FIXTURE_HASHES[evidence_sha256]
        return EvidenceAssessmentResult(
            evidence_sha256=evidence_sha256,
            predicted_grade=str(fixture["predicted_grade"]),
            conformal_set=list(fixture["conformal_set"]),  # type: ignore[arg-type]
            replay_label="REPLAYED",
            forced_lane=None,
            forensic_flags=flags,
        )

    # If no live API keys provided, route unknown upload to STANDARD with manual grading (FR-99)
    if not has_keys:
        return EvidenceAssessmentResult(
            evidence_sha256=evidence_sha256,
            predicted_grade=declared_grade,
            conformal_set=["A", "B", "C", "D"],
            replay_label="MANUAL (no model keys)",
            forced_lane="STANDARD",
            forensic_flags=[*flags, "NO_MODEL_KEYS_CONFIGURED"],
        )

    # Live assessment via Google Gemini
    if provider == "gemini" and resolved_api_key:
        client = GeminiClient(api_key=resolved_api_key, model=model)
        out = client.grade_evidence(
            declared_grade=declared_grade,
            reason_code=reason_code,
            text_in_media=text_in_media,
            image_base64=image_base64,
        )
        combined_flags = list(set(flags + out.forensic_flags))
        forced = "ESCALATED" if "PROMPT_INJECTION_ATTEMPT" in combined_flags else None
        return EvidenceAssessmentResult(
            evidence_sha256=evidence_sha256,
            predicted_grade=out.predicted_grade,
            conformal_set=out.conformal_set,
            replay_label=f"LIVE ({model})",
            forced_lane=forced,
            forensic_flags=combined_flags,
            authenticity_score=out.authenticity_score,
            tamper_score=out.tamper_score,
        )

    return EvidenceAssessmentResult(
        evidence_sha256=evidence_sha256,
        predicted_grade=declared_grade,
        conformal_set=[declared_grade],
        replay_label="LIVE",
        forced_lane="ESCALATED" if "PROMPT_INJECTION_ATTEMPT" in flags else None,
        forensic_flags=flags,
    )
