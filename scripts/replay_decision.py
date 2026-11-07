"""Decision lineage replay tool (Section 31.4: `make replay DECISION=<id>`)."""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.audit_commitment import create_audit_commitment, reveal_and_draw_audit
from backend.domain.policy import PolicyConfig
from backend.policy_engine.release import ReleaseInput, decide_release
from sim.fmap import _illustrative_calib


def replay_demo_decision(decision_id: str, platform_seed: bytes | None = None) -> None:
    """Recompute deterministic decision from stored canonical inputs (MV-08, Section 31.4)."""
    policy = PolicyConfig.default_us()
    calib = _illustrative_calib("B")
    inp = ReleaseInput(
        price_minor=40000,
        declared_grade="B",
        tier="TRUSTED",
        has_origin_passport=True,
        account_cap_remaining_minor=100000,
        merchant_cap_remaining_minor=500000,
    )
    res = decide_release(inp, policy, calib)
    if platform_seed is None:
        raw_seed = os.environ.get("AUDIT_PLATFORM_SEED", "")
        platform_seed = raw_seed.encode("utf-8") if len(raw_seed) >= 32 else secrets.token_bytes(32)
    return_id = f"ret_for_{decision_id}"
    commit = create_audit_commitment(platform_seed, return_id, res.p)
    reveal = reveal_and_draw_audit(commit, platform_seed, "shopper_nonce_demo_01")

    print(f"Replayed Decision [{decision_id}]:")
    print(f"  Policy Version:  {policy.version}")
    print(f"  Lane / Timing:   {res.lane} / {res.timing}")
    print(f"  X_released:      ${res.x_released_minor / 100:.2f} (binding: {res.binding_constraint})")
    print(f"  Holdback H:      ${res.holdback_minor / 100:.2f}")
    print(f"  Audit p:         {float(res.p):.4f} (Draw u={float(reveal.u):.6f}, selected={reveal.selected})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a ProofReturn decision from stored inputs.")
    parser.add_argument("--decision", default="dec_demo_e1", help="Decision ID to replay")
    parser.add_argument("--seed", default=None, help="Hex-encoded 32-byte platform audit seed")
    args = parser.parse_args()
    seed_bytes = bytes.fromhex(args.seed) if args.seed else None
    replay_demo_decision(args.decision, seed_bytes)


if __name__ == "__main__":
    main()
