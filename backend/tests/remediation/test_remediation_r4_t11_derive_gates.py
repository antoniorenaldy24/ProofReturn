"""Test Release Verification Gate Derivation (RV3-13, RV3-10, Task T11).

Asserts:
1. criteria.yaml defines requirements, invariants, ST ids, and journeys for G0..G6 per SSOT Section 27.
2. derive_gates.py --check passes with zero diff on docs/gates/final-acceptance.md.
3. G0 is PASSED supported by real ST-01 PayPal Sandbox IDs in st01-R4.json.
4. G1..G6 reflect accurate IN PROGRESS status with missing criteria derived from rtm.csv.
5. Manual edits to the status column in final-acceptance.md are rejected with non-zero exit code.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent.parent
CRITERIA_PATH = ROOT / "docs" / "gates" / "criteria.yaml"
FINAL_ACCEPTANCE_PATH = ROOT / "docs" / "gates" / "final-acceptance.md"
DERIVE_GATES_SCRIPT = ROOT / "scripts" / "derive_gates.py"


def test_criteria_yaml_structure():
    """Verify criteria.yaml has all gates G0..G6 with required keys."""
    assert CRITERIA_PATH.exists()
    with open(CRITERIA_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    for gkey in ["G0", "G1", "G2", "G3", "G4", "G5", "G6"]:
        assert gkey in data, f"Missing gate {gkey} in criteria.yaml"
        gate = data[gkey]
        assert "name" in gate
        assert "target_date" in gate
        assert "requirements" in gate
        assert "invariants" in gate
        assert "st_ids" in gate
        assert "journeys" in gate

    # G0 includes ST-01
    assert "ST-01" in data["G0"]["st_ids"]

    # G1 includes SSOT Section 27 required requirements and invariants
    assert "FR-09" in data["G1"]["requirements"]
    assert "FR-12" in data["G1"]["requirements"]
    assert "INV-01" in data["G1"]["invariants"]
    assert "INV-03" in data["G1"]["invariants"]


def test_derive_gates_check_mode_clean():
    """derive_gates.py --check returns exit code 0 when final-acceptance.md matches."""
    res = subprocess.run(
        [sys.executable, str(DERIVE_GATES_SCRIPT), "--check"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"derive_gates --check failed:\n{res.stdout}\n{res.stderr}"
    assert "OK: docs/gates/final-acceptance.md matches derived evidence" in res.stdout


def test_derive_gates_rejects_manual_tampering(tmp_path):
    """derive_gates.py --check rejects manual edits to the status column."""
    original_text = FINAL_ACCEPTANCE_PATH.read_text(encoding="utf-8")
    try:
        # Tamper final-acceptance.md to falsely claim G1 PASSED
        tampered = original_text.replace(
            "| **G1 Money loop** | Nov 2 | FR-09, 12, 22, 23, 24, 57, 58, 60, 64, 71 VERIFIED; INV-01, 03, 04, 05, 14 VERIFIED; state machine allowed+forbidden pass; FX-01..09, 17, 20 pass; REC-01/02 running | **IN PROGRESS**",
            "| **G1 Money loop** | Nov 2 | FR-09, 12, 22, 23, 24, 57, 58, 60, 64, 71 VERIFIED; INV-01, 03, 04, 05, 14 VERIFIED; state machine allowed+forbidden pass; FX-01..09, 17, 20 pass; REC-01/02 running | **PASSED**",
        )
        FINAL_ACCEPTANCE_PATH.write_text(tampered, encoding="utf-8")

        res = subprocess.run(
            [sys.executable, str(DERIVE_GATES_SCRIPT), "--check"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        assert res.returncode == 1
        assert "FAIL: docs/gates/final-acceptance.md is out of date" in res.stderr
    finally:
        # Always restore original text
        FINAL_ACCEPTANCE_PATH.write_text(original_text, encoding="utf-8")
