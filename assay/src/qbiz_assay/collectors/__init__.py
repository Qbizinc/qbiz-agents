"""Collectors — deterministic scanners that turn a client artifact into findings.

Collectors are the free tier of the assessment: pure parsing, no LLM, no network. Each takes
a path, returns a `CollectorResult`, and never raises on messy input — a broken artifact is
itself a finding. The engine runs them under the harness's redundancy guard and records each
run in the audit log.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qbiz_assay.findings import Dimension, Finding


@dataclass(slots=True)
class CollectorResult:
    """What one collector saw: raw stats for the report, findings for the rubric.

    ``dimensions`` is the set of dimensions this run *assessed* — a claimed dimension with no
    findings scores clean, an unclaimed one stays "Not assessed" (see rubric).
    """

    name: str
    dimensions: set[Dimension] = field(default_factory=set)
    stats: dict[str, object] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)


__all__ = ["CollectorResult"]
