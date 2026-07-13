"""qbiz_assay — Data & AI readiness assessment, governed by the Qbiz harness.

Assay scans a client's data estate (dbt project, Airflow DAGs, repo-wide AI usage) with
deterministic collectors, scores it against a six-dimension rubric, and renders a
client-facing report whose remediation roadmap maps to Qbiz offerings. The only LLM stage —
narrative — runs metered under `qbiz_harness`, making every report a live demonstration of
governed agent operation.

Dependency direction matches the repo rule: assay imports `qbiz_harness`; nothing imports back.
"""

from qbiz_assay.assessor import NarrationResult, Narrator, RuleBasedNarrator
from qbiz_assay.collectors import CollectorResult
from qbiz_assay.engine import (
    AGENT_ID,
    Assessment,
    AssessmentLimits,
    CollectorSpec,
    run_assessment,
)
from qbiz_assay.findings import (
    DIMENSION_TITLES,
    Dimension,
    Finding,
    Severity,
)
from qbiz_assay.report import render_markdown
from qbiz_assay.rubric import DimensionScore, band_for, overall_score, score_dimensions

__version__ = "0.1.0"

__all__ = [
    # Findings vocabulary
    "Dimension",
    "DIMENSION_TITLES",
    "Finding",
    "Severity",
    # Rubric
    "DimensionScore",
    "band_for",
    "score_dimensions",
    "overall_score",
    # Collectors
    "CollectorResult",
    # Narration
    "Narrator",
    "NarrationResult",
    "RuleBasedNarrator",
    # Engine
    "AGENT_ID",
    "Assessment",
    "AssessmentLimits",
    "CollectorSpec",
    "run_assessment",
    # Report
    "render_markdown",
    "__version__",
]
