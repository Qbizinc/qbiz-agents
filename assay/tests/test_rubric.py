"""Test the scoring rubric — findings to dimension scores and overall score.

Tests the band boundaries, deduction logic, floor at 0, handling of assessed vs unclaimed
(and unregistered) dimensions, and the weighted overall score. Everything runs against the
shipped Qbiz baseline config — the rubric itself is generic arithmetic over that registry.
"""

import pytest

from qbiz_assay.config import (
    AssessmentConfig,
    DimensionSpec,
    RubricConfig,
    apply_overrides,
    baseline_config,
)
from qbiz_assay.findings import Finding, Severity
from qbiz_assay.rubric import (
    NOT_ASSESSED,
    DimensionScore,
    overall_score,
    score_dimensions,
)


@pytest.fixture(scope="module")
def rubric() -> RubricConfig:
    return baseline_config().rubric


def _finding(dimension: str, severity: Severity, title: str = "Issue") -> Finding:
    return Finding(
        dimension=dimension, severity=severity, title=title, detail="", remediation=""
    )


class TestBandFor:
    """band_for returns the correct band name for a given score."""

    def test_band_for_85_and_above_is_leading(self, rubric):
        assert rubric.band_for(100) == "Leading"
        assert rubric.band_for(90) == "Leading"
        assert rubric.band_for(85) == "Leading"

    def test_band_for_70_to_84_is_established(self, rubric):
        assert rubric.band_for(84) == "Established"
        assert rubric.band_for(75) == "Established"
        assert rubric.band_for(70) == "Established"

    def test_band_for_50_to_69_is_developing(self, rubric):
        assert rubric.band_for(69) == "Developing"
        assert rubric.band_for(60) == "Developing"
        assert rubric.band_for(50) == "Developing"

    def test_band_for_below_50_is_at_risk(self, rubric):
        assert rubric.band_for(49) == "At Risk"
        assert rubric.band_for(25) == "At Risk"
        assert rubric.band_for(0) == "At Risk"


class TestScoreDimensions:
    """score_dimensions produces correct scores, bands, and flags assessed status."""

    def test_dimension_with_no_findings_and_claimed_scores_clean_100(self, rubric):
        scores = score_dimensions(findings=[], assessed={"data_quality"}, rubric=rubric)
        assert scores["data_quality"].score == 100
        assert scores["data_quality"].band == "Leading"
        assert scores["data_quality"].assessed is True

    def test_dimension_with_no_findings_and_unclaimed_is_not_assessed(self, rubric):
        scores = score_dimensions(findings=[], assessed=set(), rubric=rubric)
        assert scores["data_quality"].score is None
        assert scores["data_quality"].band == NOT_ASSESSED
        assert scores["data_quality"].assessed is False

    def test_dimension_with_findings_gets_scored_even_if_unclaimed(self, rubric):
        finding = _finding("data_quality", Severity.HIGH)
        scores = score_dimensions([finding], assessed=set(), rubric=rubric)
        # HIGH severity = 25 point deduction
        assert scores["data_quality"].score == 75
        assert scores["data_quality"].assessed is True

    def test_unregistered_dimension_with_findings_is_scored(self, rubric):
        """Evidence trumps registration: a dimension the rubric doesn't know still scores."""
        finding = _finding("cloud_posture", Severity.HIGH)
        scores = score_dimensions([finding], assessed=set(), rubric=rubric)
        assert scores["cloud_posture"].score == 75
        assert scores["cloud_posture"].assessed is True
        # Registered dimensions come first; the unregistered one is appended.
        assert list(scores)[: len(rubric.dimensions)] == list(rubric.dimension_ids())

    def test_deductions_match_severity_weights(self, rubric):
        findings = [
            _finding("data_quality", severity, severity.value)
            for severity in Severity
        ]
        scores = score_dimensions(findings, {"data_quality"}, rubric=rubric)
        # 40 + 25 + 10 + 4 + 0 = 79 deducted
        assert scores["data_quality"].score == 100 - 79

    def test_score_floors_at_zero(self, rubric):
        findings = [
            _finding("data_quality", Severity.CRITICAL, f"C{i}") for i in range(3)
        ]
        scores = score_dimensions(findings, {"data_quality"}, rubric=rubric)
        # 40 * 3 = 120, but score floors at 0
        assert scores["data_quality"].score == 0
        assert scores["data_quality"].band == "At Risk"

    def test_all_registered_dimensions_are_included_in_output(self, rubric):
        scores = score_dimensions(findings=[], assessed=set(), rubric=rubric)
        assert set(scores) == set(rubric.dimension_ids())

    def test_findings_are_attached_to_dimension_score(self, rubric):
        f1 = _finding("data_quality", Severity.HIGH, "F1")
        f2 = _finding("data_quality", Severity.MEDIUM, "F2")
        f3 = _finding("documentation", Severity.HIGH, "F3")
        scores = score_dimensions([f1, f2, f3], {"data_quality"}, rubric=rubric)
        assert scores["data_quality"].findings == [f1, f2]
        assert scores["documentation"].findings == [f3]


class TestOverallScore:
    """overall_score computes the weighted mean of assessed dimensions."""

    def test_overall_score_is_mean_of_assessed_dimensions(self, rubric):
        """With baseline weights (all 1.0) the overall is the plain mean."""
        scores = {
            "data_quality": DimensionScore("data_quality", 100, "Leading"),
            "documentation": DimensionScore("documentation", 80, "Established"),
            "governance": DimensionScore("governance", 60, "Developing"),
            "operations": DimensionScore("operations", None, NOT_ASSESSED),
            "cost": DimensionScore("cost", 90, "Leading"),
            "ai_governance": DimensionScore("ai_governance", 70, "Established"),
        }
        # (100 + 80 + 60 + 90 + 70) / 5 = 80
        assert overall_score(scores, rubric) == 80

    def test_overall_score_ignores_unassessed_dimensions(self, rubric):
        scores = {
            "data_quality": DimensionScore("data_quality", 100, "Leading"),
            "documentation": DimensionScore("documentation", None, NOT_ASSESSED),
            "operations": DimensionScore("operations", 50, "Developing"),
            "ai_governance": DimensionScore("ai_governance", 80, "Established"),
        }
        # (100 + 50 + 80) / 3 ≈ 77
        assert overall_score(scores, rubric) == 77

    def test_overall_score_returns_none_when_nothing_assessed(self, rubric):
        scores = {
            dim: DimensionScore(dim, None, NOT_ASSESSED)
            for dim in rubric.dimension_ids()
        }
        assert overall_score(scores, rubric) is None

    def test_overall_score_rounds_to_int(self, rubric):
        scores = {
            "data_quality": DimensionScore("data_quality", 100, "Leading"),
            "documentation": DimensionScore("documentation", 81, "Established"),
        }
        # (100 + 81) / 2 = 90.5
        assert overall_score(scores, rubric) in (90, 91)

    def test_overall_score_honors_dimension_weights(self):
        """A reweighted rubric shifts the overall toward the heavier dimension."""
        config = apply_overrides(
            baseline_config(),
            {"rubric": {"dimensions": [{"id": "data_quality", "weight": 3.0}]}},
        )
        scores = {
            "data_quality": DimensionScore("data_quality", 100, "Leading"),
            "documentation": DimensionScore("documentation", 60, "Developing"),
        }
        # (100*3 + 60*1) / 4 = 90 — unweighted would be 80
        assert overall_score(scores, config.rubric) == 90

    def test_unregistered_dimension_defaults_to_weight_one(self, rubric):
        scores = {
            "data_quality": DimensionScore("data_quality", 100, "Leading"),
            "cloud_posture": DimensionScore("cloud_posture", 50, "Developing"),
        }
        assert overall_score(scores, rubric) == 75
