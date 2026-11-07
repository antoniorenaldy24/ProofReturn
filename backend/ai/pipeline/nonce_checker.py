"""Challenge Nonce Verification and Retake Limit Enforcer (F-04: FR-65, FR-66)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NonceVerificationResult:
    """Distinguishes NONCE_UNREADABLE (retake allowed) vs NONCE_MISMATCH (escalate immediately) per FR-65."""

    status: str
    allow_retake: bool
    escalate_immediately: bool
    generic_feedback: str


def verify_challenge_nonce(
    *,
    expected_nonce: str,
    observed_text: str,
    blur_score: float = 0.0,
) -> NonceVerificationResult:
    """Compare observed challenge code against expected nonce (FR-65)."""
    clean_exp = expected_nonce.strip().upper()
    clean_obs = observed_text.strip().upper()

    if not clean_obs or blur_score >= 0.70:
        return NonceVerificationResult(
            status="NONCE_UNREADABLE",
            allow_retake=True,
            escalate_immediately=False,
            generic_feedback="We could not clearly read the challenge code. Please steady the camera in good lighting and retake the photo.",
        )

    if clean_obs != clean_exp:
        return NonceVerificationResult(
            status="NONCE_MISMATCH",
            allow_retake=False,
            escalate_immediately=True,
            generic_feedback="The submitted verification code did not match this return session. Your return has been routed for specialist review.",
        )

    return NonceVerificationResult(
        status="NONCE_MATCHED",
        allow_retake=False,
        escalate_immediately=False,
        generic_feedback="Verification code confirmed.",
    )


@dataclass
class RetakeTracker:
    """Enforces retake limits (3 per step, 8 per return) with generic non-leaking feedback (FR-66)."""

    max_per_step: int = 3
    max_per_return: int = 8
    total_retakes: int = 0
    step_counts: dict[str, int] = field(default_factory=dict)

    def record_retake(self, *, step: str) -> dict[str, Any]:
        current_step = self.step_counts.get(step, 0) + 1
        self.step_counts[step] = current_step
        self.total_retakes += 1

        if current_step > self.max_per_step or self.total_retakes > self.max_per_return:
            return {
                "allowed": False,
                "step": step,
                "route_to": "STANDARD",
                "user_message": "Maximum photo attempts reached. Your return will proceed via standard warehouse check-in.",
            }

        return {
            "allowed": True,
            "step": step,
            "attempt": current_step,
            "user_message": "Please center the item in bright lighting and capture the photo again.",
        }
