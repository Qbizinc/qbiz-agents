"""Shared vocabulary for assessment findings.

Assay's collectors emit `Finding`s — concrete, evidence-backed observations about a client's
data estate ("4 of 6 models have no tests"), each tagged with the readiness dimension it
affects, a severity, an evidence type (parsed, queried, or attested), and a remediation that
names the Qbiz offering that addresses it. The rubric turns findings into scores; the report
turns them into a roadmap.

Findings are deterministic facts, not LLM output. The narrative layer may *explain* them, but
it can never add, remove, or reword one — that separation is what makes the assessment
defensible in front of a client.

Per the framework's core design rule, dimensions and offerings are **registry entries, not
enums**: a dimension is a string id defined in the rubric config (see ``qbiz_assay.config``),
an offering is a string id defined in the offering catalog. The framework never compiles in
the list of things it can assess.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

#: A readiness dimension id — a key into the rubric config's dimension registry, e.g.
#: ``"data_quality"``. Plain strings (not an enum) so that adding an assessment domain is a
#: config change, never a core-code change.
DimensionId = str

#: An offering id — a key into the offering catalog, e.g. ``"dbt_startup_kit"``. The report
#: resolves ids to display titles; collectors never embed display text.
OfferingId = str


class Severity(str, Enum):
    """The severity ladder is framework vocabulary and stays closed; the *weight* each
    severity carries is rubric config (see ``RubricConfig.severity_weights``)."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


#: Sort order for reports — most severe first.
SEVERITY_ORDER: dict[Severity, int] = {s: i for i, s in enumerate(Severity)}


class EvidenceType(str, Enum):
    """How a finding knows what it claims.

    The report distinguishes these — a score built on attestations says so. Each acquisition
    mode has a natural evidence type (artifact→artifact, connected→system_of_record,
    interview→attestation), and collectors default accordingly.
    """

    ARTIFACT = "artifact"  # we parsed it
    SYSTEM_OF_RECORD = "system-of-record"  # we queried it
    ATTESTATION = "attestation"  # someone told us


@dataclass(slots=True)
class Finding:
    """One evidence-backed observation about the client's estate.

    ``subject`` is the artifact the finding is about (a model, DAG, or file path) so the client
    can go look; ``offering`` is the id of the Qbiz engagement that addresses it, used by the
    roadmap; ``evidence`` says whether we parsed, queried, or were told this.
    """

    dimension: DimensionId
    severity: Severity
    title: str
    detail: str
    remediation: str
    offering: OfferingId | None = None
    subject: str | None = None
    evidence: EvidenceType = EvidenceType.ARTIFACT
