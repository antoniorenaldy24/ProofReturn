"""Global Pytest configuration and fixtures for backend test suite.

Isolation guarantee (AUD-34, AUD-38, RV3-09):
- conftest.py NEVER touches data/proofreturn.db.
- Uses a temporary database per test session (tmp_path_factory) and a reset per test that needs it.
- Database fixtures are NOT autouse so pure unit tests (state machine, policy engine, golden examples)
  run cleanly without importing or requiring database/SQLAlchemy packages.
- SHA-256 hash of data/proofreturn.db is recorded before tests run and verified to remain identical.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest

os.environ.setdefault("ENABLE_SCHEDULER", "false")

_REPO_DB_PATH = Path("data/proofreturn.db")
_INITIAL_DB_HASH: str | None = None
_DB_EXISTED_INITIALLY: bool = False


def _compute_db_hash() -> str | None:
    if not _REPO_DB_PATH.is_file():
        return None
    hasher = hashlib.sha256()
    with open(_REPO_DB_PATH, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def pytest_configure(config: pytest.Config) -> None:
    """Record initial hash of data/proofreturn.db before any test executes, and set fallback DATABASE_URL."""
    global _INITIAL_DB_HASH, _DB_EXISTED_INITIALLY
    _DB_EXISTED_INITIALLY = _REPO_DB_PATH.is_file()
    _INITIAL_DB_HASH = _compute_db_hash()

    # Safety shield: redirect default DATABASE_URL to a unique session temporary path immediately
    # so any code falling back to os.environ["DATABASE_URL"] never touches data/proofreturn.db
    if "DATABASE_URL" not in os.environ or "data/proofreturn.db" in os.environ.get("DATABASE_URL", ""):
        session_dir = tempfile.mkdtemp(prefix="proofreturn_pytest_")
        default_temp = Path(session_dir) / "proofreturn_isolated_session.db"
        isolated_url = f"sqlite:///{default_temp}"
        os.environ["DATABASE_URL"] = isolated_url
        os.environ["PROOFRETURN_DATABASE_URL"] = isolated_url


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Verify that data/proofreturn.db was never touched or modified during the test session."""
    final_hash = _compute_db_hash()
    if _DB_EXISTED_INITIALLY:
        assert final_hash == _INITIAL_DB_HASH, (
            f"Isolation violation (AUD-34/AUD-38): data/proofreturn.db was modified during the test suite! "
            f"Initial hash: {_INITIAL_DB_HASH}, Final hash: {final_hash}"
        )
    else:
        assert not _REPO_DB_PATH.exists(), (
            "Isolation violation (AUD-34/AUD-38): data/proofreturn.db was created during the test suite!"
        )


@pytest.fixture
def initial_repo_db_hash() -> str | None:
    """Return the SHA-256 hash of data/proofreturn.db captured at session start."""
    return _INITIAL_DB_HASH


def get_initial_db_hash() -> str | None:
    """Return the SHA-256 hash of data/proofreturn.db captured at session start."""
    return _INITIAL_DB_HASH


def did_db_exist_initially() -> bool:
    """Return whether data/proofreturn.db existed at session start."""
    return _DB_EXISTED_INITIALLY


@pytest.fixture(scope="session")
def session_temp_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped isolated temporary SQLite database path created via tmp_path_factory."""
    db_dir = tmp_path_factory.mktemp("proofreturn_session_db")
    db_file = db_dir / "proofreturn_test_session.db"
    url = f"sqlite:///{db_file}"
    os.environ["DATABASE_URL"] = url
    os.environ["PROOFRETURN_DATABASE_URL"] = url
    try:
        from backend.config import reset_settings_cache
        reset_settings_cache()
    except Exception:
        pass
    return db_file


@pytest.fixture(scope="session")
def session_db_url(session_temp_db_path: Path) -> str:
    """Session-scoped database URL for isolated testing."""
    return f"sqlite:///{session_temp_db_path}"


@pytest.fixture
def reset_db(session_temp_db_path: Path) -> Generator[Any, None, None]:
    """Non-autouse fixture that resets the isolated session database for tests that need it.

    Lazy imports DatabaseRepository so pure unit tests can run without SQLAlchemy/SQLModel.
    """
    from backend.config import reset_settings_cache
    from backend.db.repository import DatabaseRepository

    reset_settings_cache()
    repo = DatabaseRepository(database_url=f"sqlite:///{session_temp_db_path}", run_migrations_on_init=True)
    repo.reset_demo_database()
    yield repo
    reset_settings_cache()


@pytest.fixture
def db_repo(reset_db: Any) -> Any:
    """Alias for reset_db returning the isolated DatabaseRepository instance."""
    return reset_db
