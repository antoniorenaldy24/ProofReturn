"""Automated Repository Secret and Credential Scanner (Section 12.1, Section 35.2, TM-12, AUD-38).

Scans all tracked and codebase files (excluding .env and virtualenvs) to prevent
unintentional credential exposure, live API keys, and hardcoded secrets from entering CI.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# High-entropy token and live credential patterns
SUSPICIOUS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Live Google API Key", re.compile(r"AIzaSy[A-Za-z0-9_-]{33}")),
    ("OpenAI / Anthropic Secret Key", re.compile(r"(?:sk-[A-Za-z0-9]{32,}|sk-ant-[A-Za-z0-9_-]{32,})")),
    ("GitHub Personal Access Token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("AWS Secret Access Key", re.compile(r"(?i)aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]")),
    ("Live PayPal Access Token", re.compile(r"A21AA[A-Za-z0-9_-]{60,}")),
    ("Unencrypted RSA / EC Private Key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]

EXCLUDE_DIRS: set[str] = {".git", ".venv", "venv", "node_modules", ".hypothesis", "__pycache__"}
EXCLUDE_FILES: set[str] = {".env", "uv.lock", "package-lock.json"}


def scan_file(file_path: Path) -> list[str]:
    """Scan a single file for known secret patterns."""
    findings: list[str] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Allow placeholder comments or example values
        if "replace_with" in line or "dummy" in line or "fake" in line or "example" in line:
            continue
        for name, pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(line):
                findings.append(f"{file_path}:{line_num}: Found pattern [{name}]")
    return findings


def check_git_ignored_secrets() -> list[str]:
    """Ensure .env and credential files are strictly ignored by git and never tracked (RV-05, TM-12)."""
    findings: list[str] = []
    try:
        proc = subprocess.run(
            ["git", "ls-files"], cwd=str(ROOT), capture_output=True, text=True, check=False
        )
        if proc.returncode == 0:
            tracked_files = proc.stdout.splitlines()
            for tf in tracked_files:
                if tf == ".env" or (tf.startswith(".env.") and not tf.endswith(".example")):
                    findings.append(f"CRITICAL: Secret environment file '{tf}' is tracked by git! Remove immediately.")
        else:
            findings.append(f"WARNING: 'git ls-files' returned non-zero code {proc.returncode}: {proc.stderr.strip()}")
    except FileNotFoundError:
        findings.append("WARNING: git executable not found on system PATH; skipping git tracking check.")
    except Exception as exc:
        findings.append(f"WARNING: git tracking check encountered unexpected error: {exc}")

    gitignore_path = ROOT / ".gitignore"
    if gitignore_path.exists():
        gi_content = gitignore_path.read_text(encoding="utf-8")
        if ".env" not in gi_content:
            findings.append("WARNING: .env is not explicitly ignored in .gitignore!")
    else:
        findings.append("ERROR: .gitignore not found at repository root.")

    return findings


def main() -> int:
    print("=" * 60)
    print("Running ProofReturn Secret & Credential Scanner (AUD-38, TM-12)")
    print("=" * 60)

    all_findings: list[str] = []

    # 1. Check git tracking hygiene
    git_findings = check_git_ignored_secrets()
    all_findings.extend(git_findings)

    # 2. Walk directory and scan files
    scanned_count = 0
    for path in ROOT.rglob("*"):
        if path.is_file():
            # Skip excluded dirs
            if any(part in EXCLUDE_DIRS for part in path.parts):
                continue
            if path.name in EXCLUDE_FILES:
                continue
            if path.suffix in {".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".webp", ".db", ".sqlite", ".bin"}:
                continue

            findings = scan_file(path)
            if findings:
                all_findings.extend(findings)
            scanned_count += 1

    print(f"Scanned {scanned_count} files across repository.")

    if all_findings:
        print("\n[!] SECRETS / SENSITIVE CREDENTIALS DETECTED:")
        for f in all_findings:
            print(f"  - {f}")
        return 1

    print("[OK] Secret scan passed: 0 credentials or leaked keys detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
