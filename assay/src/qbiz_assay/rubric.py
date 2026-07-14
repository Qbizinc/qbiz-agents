"""Scoring rubric — deterministic findings in, dimension scores out.

Scores are arithmetic over findings (start at 100, deduct per severity), never model output.
An unassessed dimension is reported as exactly that — "Not assessed" — rather than silently
scoring 100; an assessment that awards points for missing evidence would teach clients to
hide artifacts from it.

Which dimensions exist, what each severity deducts, where the bands sit, and how dimensions
weigh into the overall score all come from the ``RubricConfig`` registry — this module is
generic arithmetic over that registry, per the framework's core design rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qbiz_assay.config import RubricConfig
from qbiz_assay.findings import DimensionId, Finding

NOT_ASSESSED = "Not assessed"


@dataclass(slots=True)
class DimensionScore:
    """Score for one dimension. ``score`` is ``None`` when nothing assessed it."""

    dimension: DimensionId
    score: int | None
    band: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def assessed(self) -> bool:
        return self.score is not None


def score_dimensions(
    findings: list[Finding],
    assessed: set[DimensionId],
    rubric: RubricConfig,
) -> dict[DimensionId, DimensionScore]:
    """Score every dimension the rubric registers, in registry order.

    ``assessed`` is the set of dimensions the collectors that ran claim to cover. A dimension
    with findings is scored even when unclaimed — and even when *unregistered* in the rubric
    (evidence trumps registration; it lands after the registered ones). A claimed dimension
    with no findings scores a clean 100.
    """
    ordered: list[DimensionId] = list(rubric.dimension_ids())
    for dim in sorted({f.dimension for f in findings} | assessed):
        if dim not in ordered:
            ordered.append(dim)

    by_dim: dict[DimensionId, list[Finding]] = {d: [] for d in ordered}
    for finding in findings:
        by_dim[finding.dimension].append(finding)

    scores: dict[DimensionId, DimensionScore] = {}
    for dim in ordered:
        dim_findings = by_dim[dim]
        if not dim_findings and dim not in assessed:
            scores[dim] = DimensionScore(dim, None, NOT_ASSESSED)
            continue
        deducted = sum(rubric.deduction_for(f.severity) for f in dim_findings)
        value = max(0, 100 - deducted)
        scores[dim] = DimensionScore(dim, value, rubric.band_for(value), dim_findings)
    return scores


def overall_score(
    scores: dict[DimensionId, DimensionScore],
    rubric: RubricConfig,
) -> int | None:
    """Weighted mean of assessed dimensions (weights from the rubric registry); ``None`` if
    nothing was assessed."""
    weighted = [
        (s.score, rubric.weight_for(dim))
        for dim, s in scores.items()
        if s.score is not None
    ]
    total_weight = sum(w for _, w in weighted)
    if not weighted or total_weight == 0:
        return None
    return round(sum(score * w for score, w in weighted) / total_weight)
