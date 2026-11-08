#!/usr/bin/env python3
"""Derive Release Verification Gate statuses from evidence.

Governed strictly by Section 27 (Release Verification Gates G0-G6) and Section 49 (FA-01..FA-11).
Adheres to Audit Finding RV3-13 (MEDIUM) and Task T11:
- Reads criteria from docs/gates/criteria.yaml
- Validates verification status against docs/rtm.csv, docs/sandbox-tests.md, and docs/evidence/st01-R4.json
- A row is VERIFIED only if:
    * In rtm.csv: status is VERIFIED, test_ids exist, and required evidence files exist.
    * In sandbox-tests.md: status is VERIFIED and real PayPal IDs exist in docs/evidence/st01-R4.json.
- Updates the Status column of docs/gates/final-acceptance.md:
    * PASSED only if every criterion is VERIFIED.
    * otherwise IN PROGRESS with the list of missing ids.
- Supports --check mode for CI: exits non-zero if final-acceptance.md differs from script output.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CRITERIA_PATH = ROOT / "docs" / "gates" / "criteria.yaml"
RTM_CSV_PATH = ROOT / "docs" / "rtm.csv"
SANDBOX_TESTS_PATH = ROOT / "docs" / "sandbox-tests.md"
ST01_EVIDENCE_PATH = ROOT / "docs" / "evidence" / "st01-R4.json"
FINAL_ACCEPTANCE_PATH = ROOT / "docs" / "gates" / "final-acceptance.md"


def load_rtm_verified(rtm_path: Path) -> dict[str, bool]:
    """Return map of RTM ID -> is_verified."""
    verified_map: dict[str, bool] = {}
    if not rtm_path.exists():
        return verified_map

    with open(rtm_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = row.get("id", "").strip()
            status = row.get("status", "").strip().upper()
            evidence = row.get("evidence", "").strip()
            test_ids = row.get("test_ids", "").strip()
            ev_links = [l.strip() for l in row.get("evidence_links", "").split(";") if l.strip()]

            # Condition: Status must be VERIFIED
            # and test evidence / test_ids must exist
            # and referenced evidence links must exist
            if status == "VERIFIED":
                has_test = bool(evidence and evidence != "-") or bool(test_ids and test_ids != "-")
                links_exist = all((ROOT / el).exists() for el in ev_links)
                verified_map[rid] = has_test and links_exist
            else:
                verified_map[rid] = False

    return verified_map


def load_sandbox_verified(sandbox_path: Path, st01_path: Path) -> dict[str, bool]:
    """Return map of ST ID -> is_verified."""
    verified_map: dict[str, bool] = {}
    if not sandbox_path.exists():
        return verified_map

    # Load real PayPal IDs from st01-R4.json
    has_real_st01_ids = False
    if st01_path.exists():
        try:
            with open(st01_path, encoding="utf-8") as f:
                data = json.load(f)
                order1 = data.get("order_1_happy_path", {})
                order2 = data.get("order_2_dispute_scenario", {})
                if order1.get("paypal_order_id") and order1.get("capture_id"):
                    has_real_st01_ids = True
        except Exception:
            has_real_st01_ids = False

    table_pattern = re.compile(r"^\|\s*(ST-\d+)\s*\|.*?\|\s*`?([A-Z_]+)`?\s*\|", re.MULTILINE)
    content = sandbox_path.read_text(encoding="utf-8")
    for match in table_pattern.finditer(content):
        stid, status = match.group(1), match.group(2)
        if stid == "ST-01":
            verified_map[stid] = (status == "VERIFIED" and has_real_st01_ids)
        else:
            # Per task requirement 3: ST rows are VERIFIED only with real ids in st01-R4.json
            verified_map[stid] = False

    return verified_map


def evaluate_gate(
    gate_key: str,
    gate_cfg: dict[str, Any],
    rtm_verified: dict[str, bool],
    st_verified: dict[str, bool],
) -> tuple[str, list[str]]:
    """Evaluate whether gate passes or is in progress with missing criteria."""
    missing: list[str] = []

    reqs = gate_cfg.get("requirements") or []
    for req in reqs:
        if not rtm_verified.get(req, False):
            missing.append(req)

    invs = gate_cfg.get("invariants") or []
    for inv in invs:
        if not rtm_verified.get(inv, False):
            missing.append(inv)

    st_ids = gate_cfg.get("st_ids") or []
    for stid in st_ids:
        if not st_verified.get(stid, False):
            missing.append(stid)

    journeys = gate_cfg.get("journeys") or []
    for j in journeys:
        # Journeys are not tracked in rtm.csv and require deployed 3x verification
        missing.append(j)

    if not missing:
        return "**PASSED**", []
    return f"**IN PROGRESS** (missing: {', '.join(missing)})", missing


def update_final_acceptance_markdown(
    markdown_path: Path,
    gate_statuses: dict[str, str],
) -> str:
    """Update status column in final-acceptance.md table and return new text."""
    content = markdown_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    new_lines: list[str] = []

    # Matches table rows like:
    # | **G0 Feasibility** | Oct 29 | ... | **PASSED** | ... |
    row_pattern = re.compile(r"^\|\s*(\*\*G\d[^\*]*\*\*)\s*\|([^\|]*)\|([^\|]*)\|(.*?)\|(.*)$")

    for line in lines:
        m = row_pattern.match(line)
        if m:
            gate_label = m.group(1).strip()
            target_date = m.group(2)
            criteria_col = m.group(3)
            evidence_col = m.group(5)

            # Extract gate key like 'G0', 'G1'
            key_m = re.search(r"G\d", gate_label)
            if key_m and key_m.group(0) in gate_statuses:
                gkey = key_m.group(0)
                new_status = gate_statuses[gkey]
                new_line = f"| {gate_label} |{target_date}|{criteria_col}| {new_status} |{evidence_col}"
                new_lines.append(new_line)
                continue

        new_lines.append(line)

    return "\n".join(new_lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive gate statuses from evidence.")
    parser.add_argument("--check", action="store_true", help="Check without modifying; exit 1 if diff exists.")
    args = parser.parse_args()

    if not CRITERIA_PATH.exists():
        print(f"ERROR: {CRITERIA_PATH} not found.", file=sys.stderr)
        return 1

    with open(CRITERIA_PATH, encoding="utf-8") as f:
        criteria = yaml.safe_load(f)

    rtm_verified = load_rtm_verified(RTM_CSV_PATH)
    st_verified = load_sandbox_verified(SANDBOX_TESTS_PATH, ST01_EVIDENCE_PATH)

    gate_statuses: dict[str, str] = {}
    print("=" * 80)
    print("Release Verification Gate Derivation (scripts/derive_gates.py)")
    print("=" * 80)

    for gkey, gcfg in criteria.items():
        status_str, missing = evaluate_gate(gkey, gcfg, rtm_verified, st_verified)
        gate_statuses[gkey] = status_str
        print(f"[{gkey}] {gcfg.get('name', gkey)}: {status_str}")
        if missing:
            print(f"      Missing criteria count: {len(missing)}")

    print("-" * 80)

    if not FINAL_ACCEPTANCE_PATH.exists():
        print(f"ERROR: {FINAL_ACCEPTANCE_PATH} not found.", file=sys.stderr)
        return 1

    old_content = FINAL_ACCEPTANCE_PATH.read_text(encoding="utf-8")
    new_content = update_final_acceptance_markdown(FINAL_ACCEPTANCE_PATH, gate_statuses)

    if args.check:
        if old_content != new_content:
            diff = difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile="docs/gates/final-acceptance.md (current)",
                tofile="docs/gates/final-acceptance.md (derived)",
            )
            print("FAIL: docs/gates/final-acceptance.md is out of date with criteria/evidence!", file=sys.stderr)
            print("Run 'python scripts/derive_gates.py' to update it.\n", file=sys.stderr)
            sys.stderr.writelines(diff)
            return 1
        print("OK: docs/gates/final-acceptance.md matches derived evidence (0 diff).")
        return 0

    FINAL_ACCEPTANCE_PATH.write_text(new_content, encoding="utf-8")
    print(f"SUCCESS: Updated {FINAL_ACCEPTANCE_PATH.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
