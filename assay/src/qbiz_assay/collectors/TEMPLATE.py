"""TEMPLATE — copy this file to write a new collector. Full guide: docs/EXTENDING.md.

The short version of the contract:

1. Copy this file to ``collectors/<your_check>.py`` (or your engagement repo — see the
   "Where collectors live" section of the guide).
2. Fill in the ``@collector`` declaration — that metadata is what ``qba assay
   list-collectors`` shows a consultant, and what the profile loader validates against.
3. Turn what you observe into ``Finding``s. Findings are deterministic facts: parse, query,
   or record — never guess, never call an LLM.
4. Never raise on messy input: a broken artifact is itself a finding (see the except branch
   below). A collector that crashes takes the whole engagement run with it.
5. Copy ``tests/test_collector_TEMPLATE.py`` alongside and adapt it.

Before writing a collector that talks to a live system, run the reuse checklist in
ASSAY_PLAN.md ("Reuse over duplication") — live access goes through a shared MCP server
(``requires_mcp``), never through client code private to Assay. The registry enforces the
declaration; the checklist is on you.

This template is itself registered and tested (``tests/test_collector_TEMPLATE.py``), so it
can never rot into an example that no longer compiles. It counts lines in one text file —
the smallest honest artifact check.
"""

from __future__ import annotations

from pathlib import Path

from qbiz_assay.collectors import AcquisitionMode, CollectorResult, collector
from qbiz_assay.findings import Finding, Severity

# The dimension id(s) your findings are tagged with. Use ids from the baseline rubric
# (config/qbiz_baseline.yaml) or add a new one in the engagement profile (Tier 0).
_DIMENSIONS = {"documentation"}

# Unique across the registry; shown by list-collectors and used in the audit trail.
NAME = "template-line-count"

# An id from the offering catalog (baseline or profile-added); the roadmap groups by it.
_OFFERING = "ai_advisory"


@collector(
    name=NAME,
    dimensions=_DIMENSIONS,
    mode=AcquisitionMode.ARTIFACT,  # artifact | connected | interview — exactly one
    inputs={"file_path": "path to any text file (this is a template, it just counts lines)"},
    # requires_mcp=("<server>",),   # connected mode only: the MCP server(s) you call
    description="Template collector — copy me. Counts lines in a text file.",
)
def collect(file_path: Path | str) -> CollectorResult:
    # Parameter names must match the `inputs` keys above: profiles bind them by keyword.
    result = CollectorResult(name=NAME, dimensions=set(_DIMENSIONS))

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except OSError as exc:
        # Rule 4: unreadable input is a finding, not an exception.
        result.findings.append(
            Finding(
                dimension="documentation",
                severity=Severity.LOW,
                title="Template input unreadable",
                detail=f"Could not read {file_path}: {exc}",
                remediation="Share a readable file.",
                subject=str(file_path),
            )
        )
        return result

    lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)

    # `stats` feeds the audit trail and ad-hoc inspection; findings feed the rubric.
    result.stats = {"lines": lines}

    if lines == 0:
        result.findings.append(
            Finding(
                dimension="documentation",
                severity=Severity.INFO,
                title="File is empty",
                detail=f"{file_path} contains no lines.",
                remediation="Probably nothing — this is a template finding.",
                offering=_OFFERING,
                subject=str(file_path),
            )
        )

    return result
