"""Global Pytest fixtures for backend test suite."""

import os
os.environ.setdefault("ENABLE_SCHEDULER", "false")

import pytest
from backend.db.repository import DatabaseRepository


@pytest.fixture(autouse=True)
def reset_default_demo_db() -> None:
    """Reset shared default demo database before each test to eliminate cross-test state leakage."""
    repo = DatabaseRepository()
    repo.reset_demo_database()
