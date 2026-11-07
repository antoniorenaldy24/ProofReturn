"""Cross-Reference, Schema, and Phrase Integrity Checker (Section 47: XR-01..XR-10)."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSOT_PATH = ROOT / "docs" / "SSOT.md"
RTM_CSV_PATH = ROOT / "docs" / "rtm.csv"
SANDBOX_TESTS_PATH = ROOT / "docs" / "sandbox-tests.md"
POLICY_DEFAULTS_PATH = ROOT / "config" / "policy_defaults.json"
POLICY_DOMAIN_PATH = ROOT / "backend" / "domain" / "policy.py"

REQUIRED_POLICY_FIELDS = {
    "curve_json",
    "phi",
    "return_shipping_minor",
    "mu",
    "p_min",
    "p_max",
    "p_std",
    "rho_stress",
    "beta_leak",
    "alpha_route",
    "alpha_accuse",
    "value_bands_json",
    "timing_matrix_json",
    "tier_L_json",
    "tier_caps_json",
    "kappa",
    "aggregate_cap_minor",
    "velocity_json",
    "theta_h",
    "promotion_rules_json",
}

FORBIDDEN_PHRASES = [
    "bounds hint",
    "between $",
    "T1 refund",
]


def check_xr01_xr02(ssot_text: str, errors: list[str]) -> tuple[set[str], set[str], set[str]]:
    """XR-01 & XR-02: Verify FR, NFR, INV, ST, A definitions and RTM coverage."""
    defined_reqs: set[str] = set()
    for m in re.finditer(r"^\|\s*((?:FR|NFR|INV)-\d+)\s*\|", ssot_text, re.MULTILINE):
        defined_reqs.add(m.group(1))

    if not RTM_CSV_PATH.exists():
        errors.append("XR-02: docs/rtm.csv does not exist.")
        return defined_reqs, set(), set()

    rtm_ids: list[str] = []
    with RTM_CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rtm_ids.append(row["id"])

    rtm_set = set(rtm_ids)
    if len(rtm_ids) != len(rtm_set):
        errors.append("XR-02: Duplicate IDs found in docs/rtm.csv.")

    missing_in_rtm = defined_reqs - rtm_set
    if missing_in_rtm:
        errors.append(f"XR-02: Requirements missing from docs/rtm.csv: {sorted(missing_in_rtm)}")

    extra_in_rtm = rtm_set - defined_reqs
    if extra_in_rtm:
        errors.append(f"XR-02: Unknown IDs in docs/rtm.csv: {sorted(extra_in_rtm)}")

    defined_sts = set(re.findall(r"^\|\s*(ST-\d+)\s*\|", ssot_text, re.MULTILINE))
    defined_assumptions = set(re.findall(r"^\|\s*(A-\d+)\s*\|", ssot_text, re.MULTILINE))
    return defined_reqs, defined_sts, defined_assumptions


def check_xr03(errors: list[str]) -> None:
    """XR-03: Every test ID recorded in docs/rtm.csv exists in test files."""
    if not RTM_CSV_PATH.exists():
        return
    test_files = list((ROOT / "backend" / "tests").rglob("*.py")) if (ROOT / "backend" / "tests").exists() else []
    test_files += list((ROOT / "sim").rglob("*.py")) if (ROOT / "sim").exists() else []
    combined_code = "\n".join(p.read_text(encoding="utf-8") for p in test_files)

    with RTM_CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t_ids_raw = (row.get("test_ids") or "").strip()
            if not t_ids_raw:
                continue
            for tid in [x.strip() for x in t_ids_raw.split(";") if x.strip()]:
                if tid not in combined_code:
                    errors.append(f"XR-03: Test ID '{tid}' for {row['id']} not found in test suite.")


def check_xr04_xr05(ssot_text: str, defined_sts: set[str], errors: list[str]) -> None:
    """XR-04 & XR-05: Every ST-xx in docs/sandbox-tests.md and every [VERIFY ST-xx] valid."""
    if not SANDBOX_TESTS_PATH.exists():
        errors.append("XR-04: docs/sandbox-tests.md is missing.")
    else:
        st_doc = SANDBOX_TESTS_PATH.read_text(encoding="utf-8")
        logged_sts = set(re.findall(r"^\|\s*(ST-\d+)\s*\|", st_doc, re.MULTILINE))
        missing_st = defined_sts - logged_sts
        if missing_st:
            errors.append(f"XR-04: ST IDs missing from docs/sandbox-tests.md: {sorted(missing_st)}")

    for m in re.finditer(r"\[VERIFY\s+(ST-\d+)\]", ssot_text):
        st_id = m.group(1)
        if st_id not in defined_sts:
            errors.append(f"XR-05: [VERIFY {st_id}] references undefined Sandbox test.")


def check_xr06(defined_assumptions: set[str], errors: list[str]) -> None:
    """XR-06: Every ASSUMPTION(A-xx) in code exists in the register."""
    py_files = list((ROOT / "backend").rglob("*.py")) if (ROOT / "backend").exists() else []
    py_files += list((ROOT / "sim").rglob("*.py")) if (ROOT / "sim").exists() else []
    for p in py_files:
        text = p.read_text(encoding="utf-8")
        for m in re.finditer(r"ASSUMPTION\((A-\d+)\)", text):
            a_id = m.group(1)
            if a_id not in defined_assumptions:
                errors.append(f"XR-06: {p.relative_to(ROOT)} references unknown {a_id}.")


def check_xr07_xr08(ssot_text: str, errors: list[str]) -> None:
    """XR-07 & XR-08: Section numbers and GAP coverage map."""
    headings: set[str] = set()
    for m in re.finditer(r"^#{2,3}\s+(\d+(?:\.\d+)?)\b", ssot_text, re.MULTILINE):
        headings.add(m.group(1))
        headings.add(m.group(1).split(".")[0])

    for m in re.finditer(r"\bSection\s+(\d+(?:\.\d+)?)\b", ssot_text):
        sec = m.group(1)
        if sec not in headings:
            errors.append(f"XR-07: Reference to non-existent Section {sec}.")

    gap_rows = re.findall(r"^\|\s*(GAP-\d+)\s*\|[^|]+\|[^|]+\|\s*([^|]+)\|", ssot_text, re.MULTILINE)
    if len(gap_rows) < 37:
        errors.append(f"XR-08: Expected 37 GAP rows in Appendix D, found {len(gap_rows)}.")
    for gap_id, secs in gap_rows:
        for s in re.findall(r"\d+(?:\.\d+)?", secs):
            if s not in headings:
                errors.append(f"XR-08: {gap_id} maps to missing section {s}.")


def check_xr09(ssot_text: str, errors: list[str]) -> None:
    """XR-09: Schema linter for policies table and typed policy config."""
    for field in REQUIRED_POLICY_FIELDS:
        if f"`{field}`" not in ssot_text:
            errors.append(f"XR-09: Policy field `{field}` missing from SSOT Section 10.4.")

    if POLICY_DEFAULTS_PATH.exists():
        data = json.loads(POLICY_DEFAULTS_PATH.read_text(encoding="utf-8"))
        missing_cfg = REQUIRED_POLICY_FIELDS - set(data.keys())
        if missing_cfg:
            errors.append(f"XR-09: Fields missing from config/policy_defaults.json: {sorted(missing_cfg)}")

    if POLICY_DOMAIN_PATH.exists():
        code = POLICY_DOMAIN_PATH.read_text(encoding="utf-8")
        for field in REQUIRED_POLICY_FIELDS:
            if field not in code:
                errors.append(f"XR-09: Policy field '{field}' missing from backend/domain/policy.py.")


def check_xr10(errors: list[str]) -> None:
    """XR-10: Phrase linter on public docs and code (excluding Changelog & Appendices E-F)."""
    targets: list[Path] = [ROOT / "README.md"]
    if (ROOT / "backend").exists():
        targets.extend((ROOT / "backend").rglob("*.py"))
    if (ROOT / "sim").exists():
        targets.extend((ROOT / "sim").rglob("*.py"))
    for p in targets:
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8")
        for phrase in FORBIDDEN_PHRASES:
            if phrase.lower() in content.lower():
                errors.append(f"XR-10: Forbidden stale phrase '{phrase}' found in {p.relative_to(ROOT)}.")


def main() -> int:
    errors: list[str] = []
    if not SSOT_PATH.exists():
        print("FATAL: docs/SSOT.md not found.", file=sys.stderr)
        return 1

    ssot_text = SSOT_PATH.read_text(encoding="utf-8")
    _, defined_sts, defined_assumptions = check_xr01_xr02(ssot_text, errors)
    check_xr03(errors)
    check_xr04_xr05(ssot_text, defined_sts, errors)
    check_xr06(defined_assumptions, errors)
    check_xr07_xr08(ssot_text, errors)
    check_xr09(ssot_text, errors)
    check_xr10(errors)

    if errors:
        print("check-refs FAILED with errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("check-refs PASSED (XR-01..XR-10 verified).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
