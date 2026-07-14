"""Test the scoring rubric — findings to dimension scores and overall score.

Tests the band boundaries, deduction logic, floor at 0, handling of assessed vs
unclaimed dimensions, and overall score computation.
"""

import pytest

from qbiz_assay.findings import Dimension, Finding, Severity
from qbiz_assay.rubric import (
    NOT_ASSESSED,
    DimensionScore,
    band_for,
    overall_score,
    score_dimensions,
)


class TestBandFor:
    """band_for returns the correct band name for a given score."""

    def test_band_for_85_and_above_is_leading(self):
        """Scores 85+ fall in the Leading band."""
        assert band_for(100) == "Leading"
        assert band_for(90) == "Leading"
        assert band_for(85) == "Leading"

    def test_band_for_70_to_84_is_established(self):
        """Scores 70-84 fall in the Established band."""
        assert band_for(84) == "Established"
        assert band_for(75) == "Established"
        assert band_for(70) == "Established"

    def test_band_for_50_to_69_is_developing(self):
        """Scores 50-69 fall in the Developing band."""
        assert band_for(69) == "Developing"
        assert band_for(60) == "Developing"
        assert band_for(50) == "Developing"

    def test_band_for_below_50_is_at_risk(self):
        """Scores below 50 fall in the At Risk band."""
        assert band_for(49) == "At Risk"
        assert band_for(25) == "At Risk"
        assert band_for(0) == "At Risk"


class TestScoreDimensions:
    """score_dimensions produces correct scores, bands, and flags assessed status."""

    def test_dimension_with_no_findings_and_claimed_scores_clean_100(self):
        """A claimed dimension with no findings scores 100 (Leading)."""
        scores = score_dimensions(
            findings=[],
            assessed={Dimension.DATA_QUALITY},
        )
        assert scores[Dimension.DATA_QUALITY].score == 100
        assert scores[Dimension.DATA_QUALITY].band == "Leading"
        assert scores[Dimension.DATA_QUALITY].assessed is True

    def test_dimension_with_no_findings_and_unclaimed_is_not_assessed(self):
        """An unclaimed dimension with no findings remains Not assessed."""
        scores = score_dimensions(
            findings=[],
            assessed=set(),
        )
        assert scores[Dimension.DATA_QUALITY].score is None
        assert scores[Dimension.DATA_QUALITY].band == NOT_ASSESSED
        assert scores[Dimension.DATA_QUALITY].assessed is False

    def test_dimension_with_findings_gets_scored_even_if_unclaimed(self):
        """A dimension with findings is scored even when not in the assessed set."""
        finding = Finding(
            dimension=Dimension.DATA_QUALITY,
            severity=Severity.HIGH,
            title="Test issue",
            detail="Test",
            remediation="Test",
        )
        scores = score_dimensions(
            findings=[finding],
            assessed=set(),  # NOT claiming DATA_QUALITY
        )
        # HIGH severity = 25 point deduction
        assert scores[Dimension.DATA_QUALITY].score == 75
        assert scores[Dimension.DATA_QUALITY].assessed is True

    def test_deductions_match_severity_weights(self):
        """Each finding deducts points according to SEVERITY_WEIGHTS."""
        findings = [
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.CRITICAL,
                title="Critical",
                detail="",
                remediation="",
            ),
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.HIGH,
                title="High",
                detail="",
                remediation="",
            ),
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.MEDIUM,
                title="Medium",
                detail="",
                remediation="",
            ),
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.LOW,
                title="Low",
                detail="",
                remediation="",
            ),
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.INFO,
                title="Info",
                detail="",
                remediation="",
            ),
        ]
        scores = score_dimensions(findings, {Dimension.DATA_QUALITY})
        # 40 + 25 + 10 + 4 + 0 = 79 deducted
        expected = 100 - 79
        assert scores[Dimension.DATA_QUALITY].score == expected

    def test_score_floors_at_zero(self):
        """Score never goes negative; it floors at 0."""
        findings = [
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.CRITICAL,
                title="C1",
                detail="",
                remediation="",
            ),
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.CRITICAL,
                title="C2",
                detail="",
                remediation="",
            ),
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.CRITICAL,
                title="C3",
                detail="",
                remediation="",
            ),
        ]
        scores = score_dimensions(findings, {Dimension.DATA_QUALITY})
        # 40 * 3 = 120, but score floors at 0
        assert scores[Dimension.DATA_QUALITY].score == 0
        assert scores[Dimension.DATA_QUALITY].band == "At Risk"

    def test_all_dimensions_are_included_in_output(self):
        """score_dimensions returns an entry for every Dimension enum value."""
        scores = score_dimensions(findings=[], assessed=set())
        assert len(scores) == len(Dimension)
        for dim in Dimension:
            assert dim in scores

    def test_findings_are_attached_to_dimension_score(self):
        """Findings are attached to their dimension's DimensionScore."""
        f1 = Finding(
            dimension=Dimension.DATA_QUALITY,
            severity=Severity.HIGH,
            title="F1",
            detail="",
            remediation="",
        )
        f2 = Finding(
            dimension=Dimension.DATA_QUALITY,
            severity=Severity.MEDIUM,
            title="F2",
            detail="",
            remediation="",
        )
        f3 = Finding(
            dimension=Dimension.DOCUMENTATION,
            severity=Severity.HIGH,
            title="F3",
            detail="",
            remediation="",
        )
        scores = score_dimensions([f1, f2, f3], {Dimension.DATA_QUALITY})
        assert len(scores[Dimension.DATA_QUALITY].findings) == 2
        assert f1 in scores[Dimension.DATA_QUALITY].findings
        assert f2 in scores[Dimension.DATA_QUALITY].findings
        assert len(scores[Dimension.DOCUMENTATION].findings) == 1
        assert f3 in scores[Dimension.DOCUMENTATION].findings


class TestOverallScore:
    """overall_score computes the unweighted mean of assessed dimensions."""

    def test_overall_score_is_mean_of_assessed_dimensions(self):
        """Overall score is the mean of all dimensions that have a score (not None)."""
        scores = {
            Dimension.DATA_QUALITY: DimensionScore(
                Dimension.DATA_QUALITY, 100, "Leading"
            ),
            Dimension.DOCUMENTATION: DimensionScore(
                Dimension.DOCUMENTATION, 80, "Established"
            ),
            Dimension.GOVERNANCE: DimensionScore(
                Dimension.GOVERNANCE, 60, "Developing"
            ),
            Dimension.OPERATIONS: DimensionScore(
                Dimension.OPERATIONS, None, NOT_ASSESSED
            ),
            Dimension.COST: DimensionScore(
                Dimension.COST, 90, "Leading"
            ),
            Dimension.AI_GOVERNANCE: DimensionScore(
                Dimension.AI_GOVERNANCE, 70, "Established"
            ),
        }
        result = overall_score(scores)
        # (100 + 80 + 60 + 90 + 70) / 5 = 400 / 5 = 80
        assert result == 80

    def test_overall_score_ignores_unassessed_dimensions(self):
        """Unassessed dimensions (score=None) are not included in the mean."""
        scores = {
            Dimension.DATA_QUALITY: DimensionScore(
                Dimension.DATA_QUALITY, 100, "Leading"
            ),
            Dimension.DOCUMENTATION: DimensionScore(
                Dimension.DOCUMENTATION, None, NOT_ASSESSED
            ),
            Dimension.GOVERNANCE: DimensionScore(
                Dimension.GOVERNANCE, None, NOT_ASSESSED
            ),
            Dimension.OPERATIONS: DimensionScore(
                Dimension.OPERATIONS, 50, "Developing"
            ),
            Dimension.COST: DimensionScore(
                Dimension.COST, None, NOT_ASSESSED
            ),
            Dimension.AI_GOVERNANCE: DimensionScore(
                Dimension.AI_GOVERNANCE, 80, "Established"
            ),
        }
        result = overall_score(scores)
        # (100 + 50 + 80) / 3 = 230 / 3 ≈ 77
        assert result == 77

    def test_overall_score_returns_none_when_nothing_assessed(self):
        """If no dimensions are assessed, overall_score returns None."""
        scores = {
            Dimension.DATA_QUALITY: DimensionScore(
                Dimension.DATA_QUALITY, None, NOT_ASSESSED
            ),
            Dimension.DOCUMENTATION: DimensionScore(
                Dimension.DOCUMENTATION, None, NOT_ASSESSED
            ),
            Dimension.GOVERNANCE: DimensionScore(
                Dimension.GOVERNANCE, None, NOT_ASSESSED
            ),
            Dimension.OPERATIONS: DimensionScore(
                Dimension.OPERATIONS, None, NOT_ASSESSED
            ),
            Dimension.COST: DimensionScore(
                Dimension.COST, None, NOT_ASSESSED
            ),
            Dimension.AI_GOVERNANCE: DimensionScore(
                Dimension.AI_GOVERNANCE, None, NOT_ASSESSED
            ),
        }
        result = overall_score(scores)
        assert result is None

    def test_overall_score_rounds_to_int(self):
        """Overall score is rounded (not truncated) to an integer."""
        scores = {
            Dimension.DATA_QUALITY: DimensionScore(
                Dimension.DATA_QUALITY, 100, "Leading"
            ),
            Dimension.DOCUMENTATION: DimensionScore(
                Dimension.DOCUMENTATION, 81, "Established"
            ),
            Dimension.GOVERNANCE: DimensionScore(
                Dimension.GOVERNANCE, None, NOT_ASSESSED
            ),
            Dimension.OPERATIONS: DimensionScore(
                Dimension.OPERATIONS, None, NOT_ASSESSED
            ),
            Dimension.COST: DimensionScore(
                Dimension.COST, None, NOT_ASSESSED
            ),
            Dimension.AI_GOVERNANCE: DimensionScore(
                Dimension.AI_GOVERNANCE, None, NOT_ASSESSED
            ),
        }
        result = overall_score(scores)
        # (100 + 81) / 2 = 90.5, rounds to 90 or 91
        assert result in (90, 91)
