"""dbt collector — reads a compiled ``manifest.json`` and measures project hygiene.

The manifest is used (rather than parsing ``.sql`` files) because it is dbt's own compiled
truth: every model, column, test edge, and meta tag, independent of adapter or project layout.
Ask the client for ``target/manifest.json`` — no warehouse access is needed for this pass.

Measures three things:
- **Test coverage** (data quality) — models with at least one test attached.
- **Documentation coverage** — models with a non-empty description.
- **Sensitivity classification coverage** (governance) — models carrying a ``sensitivity`` meta
  tag, per the Qbiz data-sensitivity scheme. Zero coverage is the single biggest blocker to
  pointing AI agents at a warehouse safely.
"""

from __future__ import annotations

import json
from pathlib import Path

from qbiz_assay.collectors import AcquisitionMode, CollectorResult, collector
from qbiz_assay.findings import Finding, Severity

_DIMENSIONS = {"data_quality", "documentation", "governance"}

NAME = "dbt-manifest"

_OFFERING_STARTUP_KIT = "dbt_startup_kit"
_OFFERING_SENSITIVITY = "sensitivity_classification"


def _pct(part: int, total: int) -> int:
    return round(100 * part / total) if total else 0


def _sample(names: list[str], cap: int = 5) -> str:
    shown = ", ".join(sorted(names)[:cap])
    extra = len(names) - cap
    return f"{shown} (+{extra} more)" if extra > 0 else shown


def _meta(node: dict) -> dict:
    """Model meta can live at the node root or under config; merge both (config wins)."""
    merged = dict(node.get("meta") or {})
    merged.update((node.get("config") or {}).get("meta") or {})
    return merged


def _freshness_configured(source: dict) -> bool:
    freshness = source.get("freshness")
    if not isinstance(freshness, dict):
        return False
    return any(
        isinstance(rule, dict) and rule.get("count") is not None
        for rule in freshness.values()
    )


@collector(
    name=NAME,
    dimensions=_DIMENSIONS,
    mode=AcquisitionMode.ARTIFACT,
    inputs={"manifest_path": "path to the project's compiled target/manifest.json"},
    description="dbt project hygiene: test, documentation, and sensitivity-tag coverage, "
    "plus source freshness SLAs — from the compiled manifest alone.",
)
def collect(manifest_path: Path | str) -> CollectorResult:
    result = CollectorResult(name=NAME, dimensions=set(_DIMENSIONS))
    try:
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result.findings.append(
            Finding(
                dimension="data_quality",
                severity=Severity.HIGH,
                title="dbt manifest unreadable",
                detail=f"Could not parse {manifest_path}: {exc}. The project may not compile.",
                remediation=(
                    "Get `dbt parse` passing first — a project that does not compile cannot "
                    "be tested, documented, or safely handed to an agent."
                ),
                offering=_OFFERING_STARTUP_KIT,
                subject=str(manifest_path),
            )
        )
        return result

    # Defensive: a hand-edited or corrupted manifest can have a non-dict node/source value
    # (e.g. `"nodes": {"model.x": null}`) even though the outer JSON parses fine. Skip those
    # rather than crash on the chained .get() calls below.
    nodes: dict = {
        uid: n for uid, n in (data.get("nodes") or {}).items() if isinstance(n, dict)
    }
    models = {uid: n for uid, n in nodes.items() if n.get("resource_type") == "model"}
    tests = [n for n in nodes.values() if n.get("resource_type") == "test"]
    sources: dict = {
        uid: s for uid, s in (data.get("sources") or {}).items() if isinstance(s, dict)
    }

    tested: set[str] = set()
    for test in tests:
        tested.update(test.get("depends_on", {}).get("nodes", []))

    untested = [n.get("name", uid) for uid, n in models.items() if uid not in tested]
    undocumented = [
        n.get("name", uid) for uid, n in models.items() if not (n.get("description") or "").strip()
    ]
    unclassified = [
        n.get("name", uid) for uid, n in models.items() if "sensitivity" not in _meta(n)
    ]
    stale_sources = [
        s.get("name", uid) for uid, s in sources.items() if not _freshness_configured(s)
    ]

    total = len(models)
    test_cov = _pct(total - len(untested), total)
    doc_cov = _pct(total - len(undocumented), total)
    sens_cov = _pct(total - len(unclassified), total)

    result.stats = {
        "models": total,
        "tests": len(tests),
        "test_coverage_pct": test_cov,
        "doc_coverage_pct": doc_cov,
        "sensitivity_coverage_pct": sens_cov,
        "sources": len(sources),
        "sources_without_freshness": len(stale_sources),
    }

    if total == 0:
        result.findings.append(
            Finding(
                dimension="data_quality",
                severity=Severity.MEDIUM,
                title="No models in the dbt manifest",
                detail="The manifest compiled but contains zero models — nothing to assess.",
                remediation="Confirm the right manifest was shared, or start from a working template.",
                offering=_OFFERING_STARTUP_KIT,
            )
        )
        return result

    if untested:
        result.findings.append(
            Finding(
                dimension="data_quality",
                severity=Severity.HIGH if test_cov < 50 else Severity.MEDIUM,
                title=f"Test coverage is {test_cov}% ({len(untested)} of {total} models untested)",
                detail=f"Untested models: {_sample(untested)}. Breakage in these ships silently.",
                remediation=(
                    "Add uniqueness/not-null tests to primary keys first, then relationship "
                    "tests between layers — the startup kit's conventions make this mechanical."
                ),
                offering=_OFFERING_STARTUP_KIT,
            )
        )

    if undocumented:
        result.findings.append(
            Finding(
                dimension="documentation",
                severity=Severity.HIGH if doc_cov < 40 else Severity.MEDIUM,
                title=f"Documentation coverage is {doc_cov}% ({len(undocumented)} models undescribed)",
                detail=(
                    f"Undocumented models: {_sample(undocumented)}. Every consumer — human or "
                    "agent — has to reverse-engineer intent from SQL."
                ),
                remediation="Backfill model descriptions; enforce docs-on-new-models in CI.",
                offering=_OFFERING_STARTUP_KIT,
            )
        )

    if unclassified:
        result.findings.append(
            Finding(
                dimension="governance",
                severity=Severity.HIGH if sens_cov < 50 else Severity.MEDIUM,
                title=(
                    f"Sensitivity classification coverage is {sens_cov}% "
                    f"({len(unclassified)} models unclassified)"
                ),
                detail=(
                    f"Models without a `sensitivity` meta tag: {_sample(unclassified)}. "
                    "Unclassified data cannot be safely exposed to AI agents — an agent has no "
                    "way to know what it must not read or return."
                ),
                remediation=(
                    "Adopt a sensitivity scheme (public/internal/confidential/restricted) as "
                    "model- and column-level meta; treat unclassified as restricted."
                ),
                offering=_OFFERING_SENSITIVITY,
            )
        )

    if stale_sources:
        result.findings.append(
            Finding(
                dimension="data_quality",
                severity=Severity.MEDIUM,
                title=f"{len(stale_sources)} source(s) have no freshness checks",
                detail=(
                    f"Sources without freshness SLAs: {_sample(stale_sources)}. Upstream delays "
                    "surface as wrong numbers, not alerts."
                ),
                remediation="Declare `freshness` on raw sources so staleness pages someone.",
                offering=_OFFERING_STARTUP_KIT,
            )
        )

    return result
