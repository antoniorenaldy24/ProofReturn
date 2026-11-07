"""Value- and risk-scaled evidence requirements and DEF functional self-test rules (FR-13, FR-68)."""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.policy import PolicyConfig


@dataclass(frozen=True)
class EvidenceRequirementSpec:
    value_band: str
    min_photos: int
    require_challenge_video: bool
    video_min_seconds: int
    video_max_seconds: int
    require_nonce_visible: bool
    require_functional_self_test: bool


def determine_evidence_requirements(
    *,
    price_minor: int,
    tier: str,
    declared_grade: str,
    category: str,
    policy: PolicyConfig,
) -> EvidenceRequirementSpec:
    """FR-13 & FR-68: Scale evidence requirements by item value, trust tier, and DEF electronics rule."""
    band = policy.value_band(price_minor)
    is_electronics = category in {"headphones", "camera_lens"}
    require_self_test = declared_grade == "DEF" and is_electronics

    if band == "LOW" and tier in {"TRUSTED", "ESTABLISHED"} and not require_self_test:
        return EvidenceRequirementSpec(
            value_band=band,
            min_photos=2,
            require_challenge_video=False,
            video_min_seconds=0,
            video_max_seconds=0,
            require_nonce_visible=True,
            require_functional_self_test=False,
        )
    if band == "MID":
        return EvidenceRequirementSpec(
            value_band=band,
            min_photos=4,
            require_challenge_video=True,
            video_min_seconds=10,
            video_max_seconds=25,
            require_nonce_visible=True,
            require_functional_self_test=require_self_test,
        )
    return EvidenceRequirementSpec(
        value_band=band,
        min_photos=4,
        require_challenge_video=True,
        video_min_seconds=20,
        video_max_seconds=40,
        require_nonce_visible=True,
        require_functional_self_test=require_self_test,
    )
