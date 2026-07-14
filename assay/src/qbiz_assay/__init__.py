"""qbiz_assay — Data & AI discovery assessment framework, governed by the Qbiz harness.

Assay scans a client's data estate with deterministic collectors, scores it against a
config-driven rubric, and renders a client-facing report whose remediation roadmap maps to
Qbiz offerings. The only LLM stage — narrative — runs metered under `qbiz_harness`, making
every report a live demonstration of governed agent operation.

The framework's core design rule: core pieces iterate registries, never enums. Dimensions,
rubric weights and bands, and offerings live in config (``qbiz_assay.config``); collectors
self-register with declared metadata (``qbiz_assay.collectors``); an engagement profile
(``qbiz_assay.profile``) is the per-client entry point. See ``docs/EXTENDING.md`` for the
extension ladder.

Dependency direction matches the repo rule: assay imports `qbiz_harness`; nothing imports back.
"""

from qbiz_assay.assessor import NarrationResult, Narrator, RuleBasedNarrator
from qbiz_assay.collectors import (
    AcquisitionMode,
    CollectorInfo,
    CollectorResult,
    RegisteredCollector,
    all_collectors,
    collector,
    get_collector,
)
from qbiz_assay.config import (
    AssessmentConfig,
    ConfigError,
    DimensionSpec,
    OfferingSpec,
    RubricConfig,
    apply_overrides,
    baseline_config,
    load_config,
)
from qbiz_assay.engine import (
    AGENT_ID,
    Assessment,
    AssessmentLimits,
    CollectorSpec,
    run_assessment,
)
from qbiz_assay.findings import (
    DimensionId,
    EvidenceType,
    Finding,
    OfferingId,
    Severity,
)
from qbiz_assay.profile import (
    DeliveryMode,
    EngagementProfile,
    ProfileError,
    build_collector_specs,
    load_profile,
    run_profile,
)
from qbiz_assay.report import render_markdown
from qbiz_assay.rubric import DimensionScore, overall_score, score_dimensions

__version__ = "0.2.0"

__all__ = [
    # Findings vocabulary
    "DimensionId",
    "EvidenceType",
    "Finding",
    "OfferingId",
    "Severity",
    # Config registries
    "AssessmentConfig",
    "ConfigError",
    "DimensionSpec",
    "OfferingSpec",
    "RubricConfig",
    "apply_overrides",
    "baseline_config",
    "load_config",
    # Rubric
    "DimensionScore",
    "score_dimensions",
    "overall_score",
    # Collectors
    "AcquisitionMode",
    "CollectorInfo",
    "CollectorResult",
    "RegisteredCollector",
    "all_collectors",
    "collector",
    "get_collector",
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
    # Profiles
    "DeliveryMode",
    "EngagementProfile",
    "ProfileError",
    "build_collector_specs",
    "load_profile",
    "run_profile",
    # Report
    "render_markdown",
    "__version__",
]
