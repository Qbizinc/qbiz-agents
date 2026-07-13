"""Scoring rubric — deterministic findings in, dimension scores out.

Scores are arithmetic over findings (start at 100, deduct per severity), never model output.
An unassessed dimension is reported as exactly that — "Not assessed" — rather than silently
scoring 100; an assessment that awards points for missing evidence would teach clients to
hide artifacts from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qbiz_assay.findings import SEVERITY_WEIGHTS, Dimension, Finding

#: (minimum score, band name), checked top-down.
BANDS: tuple[tuple[int, str], ...] = (
    (85, "Leading"),
    (70, "Established"),
    (50, "Developing"),
    (0, "At Risk"),
)

NOT_ASSESSED = "Not assessed"


def band_for(score: int) -> str:
    for minimum, name in BANDS:
        if score >= minimum:
            return name
    return BANDS[-1][1]  # pragma: no cover — the 0 band catches everything


@dataclass(slots=True)
class DimensionScore:
    """Score for one dimension. ``score`` is ``None`` when nothing assessed it."""

    dimension: Dimension
    score: int | None
    band: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def assessed(self) -> bool:
        return self.score is not None


def score_dimensions(
    findings: list[Finding],
    assessed: set[Dimension],
) -> dict[Dimension, DimensionScore]:
    """Score every dimension.

    ``assessed`` is the set of dimensions the collectors that ran claim to cover. A dimension
    with findings is scored even when unclaimed (evidence trumps declarations); a claimed
    dimension with no findings scores a clean 100.
    """
    by_dim: dict[Dimension, list[Finding]] = {d: [] for d in Dimension}
    for finding in findings:
        by_dim[finding.dimension].append(finding)

    scores: dict[Dimension, DimensionScore] = {}
    for dim in Dimension:
        dim_findings = by_dim[dim]
        if not dim_findings and dim not in assessed:
            scores[dim] = DimensionScore(dim, None, NOT_ASSESSED)
            continue
        deducted = sum(SEVERITY_WEIGHTS[f.severity] for f in dim_findings)
        value = max(0, 100 - deducted)
        scores[dim] = DimensionScore(dim, value, band_for(value), dim_findings)
    return scores


def overall_score(scores: dict[Dimension, DimensionScore]) -> int | None:
    """Unweighted mean of assessed dimensions; ``None`` if nothing was assessed."""
    values = [s.score for s in scores.values() if s.score is not None]
    if not values:
        return None
    return round(sum(values) / len(values))
