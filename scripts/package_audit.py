"""Creates a clean, audit-compliant zip archive of the ProofReturn repository.
Excludes secrets (.env), dependencies (node_modules, .venv), caches, and runtime databases.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

# Directories to completely skip
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".hypothesis",
    ".ruff_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "storefront",  # root backup folder; source of truth is in apps/demo-storefront
}

# File extensions or specific files to exclude
EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".log",
    ".sqlite",
    ".db",
    ".db-shm",
    ".db-wal",
}

EXCLUDE_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".DS_Store",
    "Thumbs.db",
}


def should_exclude(rel_path: Path) -> bool:
    for part in rel_path.parts:
        if part in EXCLUDE_DIRS:
            return True

    name = rel_path.name
    if name in EXCLUDE_FILES and name != ".env.example":
        return True

    if rel_path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True

    return False


def create_zip(output_filename: str = "ProofReturn_Audit_Submission.zip") -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    output_path = repo_root / output_filename

    # Remove existing zip if any
    if output_path.exists():
        output_path.unlink()

    included_count = 0
    total_uncompressed_bytes = 0

    print(f"Creating clean audit bundle: {output_filename}")
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for root, dirs, files in os.walk(repo_root):
            # Prune excluded directories in-place so os.walk doesn't descend into them
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in files:
                abs_file = Path(root) / file
                rel_file = abs_file.relative_to(repo_root)

                # Skip the output zip itself
                if rel_file.name == output_filename:
                    continue

                if should_exclude(rel_file):
                    continue

                zipf.write(abs_file, arcname=str(rel_file))
                included_count += 1
                total_uncompressed_bytes += abs_file.stat().st_size

    zip_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Archived {included_count} files successfully.")
    print(f"Archive location: {output_path}")
    print(f"Final compressed size: {zip_size_mb:.2f} MB (uncompressed: {total_uncompressed_bytes / (1024 * 1024):.2f} MB)")
    return output_path


if __name__ == "__main__":
    create_zip()
