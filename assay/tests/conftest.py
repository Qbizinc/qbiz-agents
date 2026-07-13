"""Shared pytest fixtures for the qbiz-assay test suite."""

from pathlib import Path

import pytest


@pytest.fixture
def acme_root() -> Path:
    """Path to the demo acme fixture root."""
    return Path(__file__).parent.parent / "demo" / "fixtures" / "acme"


@pytest.fixture
def acme_manifest(acme_root: Path) -> Path:
    """Path to the acme dbt manifest.json."""
    return acme_root / "dbt" / "manifest.json"


@pytest.fixture
def acme_dags_dir(acme_root: Path) -> Path:
    """Path to the acme Airflow dags directory."""
    return acme_root / "dags"


@pytest.fixture
def acme_repo_dir(acme_root: Path) -> Path:
    """Path to the acme repo root (for AI usage collector)."""
    return acme_root
