"""Shared vocabulary for assessment findings.

Assay's collectors emit `Finding`s — concrete, evidence-backed observations about a client's
data estate ("4 of 6 models have no tests"), each tagged with the readiness dimension it
affects, a severity, and a remediation that names the Qbiz offering that addresses it. The
rubric turns findings into scores; the report turns them into a roadmap.

Findings are deterministic facts, not LLM output. The narrative layer may *explain* them, but
it can never add, remove, or reword one — that separation is what makes the assessment
defensible in front of a client.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Dimension(str, Enum):
    """The six readiness dimensions Assay scores.

    A ``str`` enum so it serializes cleanly into the audit log and report JSON.
    """

    DATA_QUALITY = "data_quality"
    DOCUMENTATION = "documentation"
    GOVERNANCE = "governance"
    OPERATIONS = "operations"
    COST = "cost"
    AI_GOVERNANCE = "ai_governance"


DIMENSION_TITLES: dict[Dimension, str] = {
    Dimension.DATA_QUALITY: "Data Quality & Testing",
    Dimension.DOCUMENTATION: "Documentation & Discoverability",
    Dimension.GOVERNANCE: "Governance & Data Sensitivity",
    Dimension.OPERATIONS: "Operational Maturity",
    Dimension.COST: "Cost Efficiency",
    Dimension.AI_GOVERNANCE: "AI Readiness & Governance",
}


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


#: Points deducted from a dimension's score (out of 100) per finding of each severity.
SEVERITY_WEIGHTS: dict[Severity, int] = {
    Severity.CRITICAL: 40,
    Severity.HIGH: 25,
    Severity.MEDIUM: 10,
    Severity.LOW: 4,
    Severity.INFO: 0,
}

#: Sort order for reports — most severe first.
SEVERITY_ORDER: dict[Severity, int] = {s: i for i, s in enumerate(Severity)}


# --- Qbiz offerings a remediation can point at -------------------------------------------------
# The roadmap section of the report groups findings by these. Keeping them as constants (rather
# than free text in each collector) is what lets the report say "these five findings are all
# solved by the same engagement".

OFFERING_STARTUP_KIT = "Qbiz dbt Startup Kit"
OFFERING_SENSITIVITY = "Data Sensitivity Classification"
OFFERING_INCIDENT_AGENT = "Agentic Incident Response"
OFFERING_HARNESS = "Qbiz Agent Harness"
OFFERING_ADVISORY = "AI Readiness Advisory"


@dataclass(slots=True)
class Finding:
    """One evidence-backed observation about the client's estate.

    ``subject`` is the artifact the finding is about (a model, DAG, or file path) so the client
    can go look; ``offering`` is the Qbiz engagement that addresses it, used by the roadmap.
    """

    dimension: Dimension
    severity: Severity
    title: str
    detail: str
    remediation: str
    offering: str | None = None
    subject: str | None = None
