"""Shared pytest fixtures for the qbiz-assay test suite."""

from pathlib import Path

import pytest


def planted_secret_line(kind: str = "password", value: str | None = None) -> str:
    """A Python source line ``<kind> = "<fake value>"`` for credential-detector tests.

    Assembled at runtime so the committed test source never contains a secret-shaped
    literal — secret scanners (GitGuardian on PRs, ggshield pre-commit) would rightly
    flag one, and teaching people to dismiss scanner findings is worse than the finding.
    The assembled line only ever exists inside a pytest ``tmp_path``. Real-secret policy:
    SECURITY.md at the repo root.
    """
    if value is None:
        value = "-".join(("fake", "assay", "fixture", "credential"))
    return kind + ' = "' + value + '"'


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
