"""Test repository database isolation (AUD-34, AUD-38, RV3-09).

Verifies that the canonical file `data/proofreturn.db` is never modified, written to,
or touched during test suite execution, and that its SHA-256 hash remains identical
before and after tests.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest


def _compute_file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def test_data_proofreturn_db_hash_unmodified_before_and_after(initial_repo_db_hash: str | None) -> None:
    """Verifies data/proofreturn.db has not been modified since test session start (AUD-34, AUD-38)."""
    repo_db_path = Path("data/proofreturn.db")

    if initial_repo_db_hash is not None:
        assert repo_db_path.is_file(), "data/proofreturn.db must exist if it existed at session start."
        current_hash = _compute_file_sha256(repo_db_path)
        assert current_hash == initial_repo_db_hash, (
            f"Isolation violation (AUD-34): data/proofreturn.db was modified during tests! "
            f"Session initial hash: {initial_repo_db_hash}, Current hash: {current_hash}"
        )
    else:
        assert not repo_db_path.exists(), (
            "Isolation violation (AUD-34): data/proofreturn.db did not exist at session start but was created!"
        )


def test_database_url_environment_points_to_isolated_temp(session_temp_db_path: Path) -> None:
    """Verifies DATABASE_URL environment variables never point to data/proofreturn.db."""
    db_url = os.environ.get("DATABASE_URL", "")
    proofreturn_url = os.environ.get("PROOFRETURN_DATABASE_URL", "")

    assert "data/proofreturn.db" not in db_url.replace("\\", "/"), (
        f"DATABASE_URL must never point to data/proofreturn.db during tests, got: {db_url}"
    )
    assert "data/proofreturn.db" not in proofreturn_url.replace("\\", "/"), (
        f"PROOFRETURN_DATABASE_URL must never point to data/proofreturn.db during tests, got: {proofreturn_url}"
    )
    assert str(session_temp_db_path) in db_url or "proofreturn_test_session" in db_url


def test_active_repo_writes_do_not_mutate_repo_db(reset_db: Any) -> None:
    """Verifies that operations performed through DatabaseRepository mutate only isolated temp db."""
    repo_db_path = Path("data/proofreturn.db")
    hash_before = _compute_file_sha256(repo_db_path)

    # Perform mutations on reset_db
    from backend.db.models import Merchant
    with reset_db.get_session() as session:
        session.add(
            Merchant(
                merchant_id="merch_isolation_test",
                name="Isolation Corp",
                instant_exposure_cap_minor=100000,
                outstanding_instant_exposure_minor=0,
                currency="USD",
            )
        )
        session.commit()

    hash_after = _compute_file_sha256(repo_db_path)
    assert hash_after == hash_before, (
        "Writing to DatabaseRepository mutated data/proofreturn.db! Isolation failure."
    )
