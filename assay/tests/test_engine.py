"""Test the assessment engine — orchestration of collectors, scoring, and narration.

Tests redundancy guard, cost governor integration, intervention recording, and
the fallback narrator path when budgets are exceeded.
"""

import pytest

from qbiz_harness import AuditLog

from qbiz_assay.assessor import Narrator, NarrationResult, RuleBasedNarrator
from qbiz_assay.collectors import CollectorResult
from qbiz_assay.engine import Assessment, AssessmentLimits, run_assessment
from qbiz_assay.config import baseline_config
from qbiz_assay.findings import Finding, Severity


def _dummy_collector(
    name: str,
    dimensions: set[str] | None = None,
    findings: list[Finding] | None = None,
) -> CollectorResult:
    """Helper to create a CollectorResult with minimal setup."""
    return CollectorResult(
        name=name,
        dimensions=dimensions or set(),
        stats={"dummy": True},
        findings=findings or [],
    )


class TestEngineRedundancyGuard:
    """The engine's redundancy guard prevents re-collecting the same artifact."""

    def test_duplicate_collector_name_skipped_second_time(self):
        """Registering the same collector twice: second is skipped by redundancy guard."""
        call_count = {"count": 0}

        def collector_that_tracks_calls() -> CollectorResult:
            call_count["count"] += 1
            return _dummy_collector("tracked-collector")

        audit = AuditLog()
        assessment = run_assessment(
            client_name="Test Client",
            collectors=[
                ("tracked-collector", collector_that_tracks_calls),
                ("tracked-collector", collector_that_tracks_calls),  # Same name!
            ],
            audit=audit,
        )

        # Collector should only be called once
        assert call_count["count"] == 1
        # Only one result should be in the assessment
        assert len(assessment.collector_results) == 1
        # An intervention should be recorded
        interventions = audit.interventions()
        assert len(interventions) == 1
        intervention = interventions[0]
        assert "Redundant" in intervention.intervention.prevented
        assert intervention.intervention.component == "cost_governor"

    def test_intervention_recorded_with_component_and_prevented_text(self):
        """Redundancy intervention includes 'Redundant' and component='cost_governor'."""
        audit = AuditLog()
        run_assessment(
            client_name="Test",
            collectors=[
                ("col1", lambda: _dummy_collector("col1")),
                ("col1", lambda: _dummy_collector("col1")),
            ],
            audit=audit,
        )
        interventions = audit.interventions()
        assert len(interventions) == 1
        assert interventions[0].intervention.component == "cost_governor"
        assert "Redundant" in interventions[0].intervention.prevented


class TestEngineCostGovernor:
    """The engine metering when the narrator breaches budget."""

    def test_narrator_breach_on_second_call_degrades_to_fallback(self):
        """When narrator exceeds budget, remaining sections use fallback narrator."""

        class HighCostNarrator:
            """Narrator that reports huge cost on call 2."""

            def __init__(self):
                self.call_count = 0

            def narrate(
                self, section: str, context: dict[str, object]
            ) -> NarrationResult:
                self.call_count += 1
                if self.call_count == 2:
                    # Breach the budget
                    return NarrationResult(text=f"{section} text", cost_usd=1.00)
                return NarrationResult(text=f"{section} text", cost_usd=0.01)

        audit = AuditLog()
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _dummy_collector(
                    "test",
                    dimensions={"data_quality", "documentation", "governance"},
                    findings=[],
                )),
            ],
            narrator=HighCostNarrator(),
            audit=audit,
            limits=AssessmentLimits(spend_limit_usd=0.5),
        )

        # Some sections should be in fallback_sections (at least the ones after the breach)
        assert len(assessment.fallback_sections) > 0
        # But narratives should still contain all expected sections
        expected_sections = {"executive_summary", "data_quality", "documentation", "governance"}
        assert set(assessment.narratives.keys()) == expected_sections
        # All narratives should have content
        assert all(
            len(text) > 0 for text in assessment.narratives.values()
        )

    def test_fallback_sections_list_tracks_degraded_narration(self):
        """fallback_sections contains the sections that degraded to rule-based."""

        class BudgetBreakerNarrator:
            """Narrator that breaches on the first real section (not executive_summary)."""

            def narrate(
                self, section: str, context: dict[str, object]
            ) -> NarrationResult:
                if section != "executive_summary":
                    # Breach immediately
                    return NarrationResult(text=section, cost_usd=10.00)
                return NarrationResult(text=section, cost_usd=0.01)

        audit = AuditLog()
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _dummy_collector(
                    "test",
                    dimensions={"data_quality", "documentation"},
                    findings=[],
                )),
            ],
            narrator=BudgetBreakerNarrator(),
            audit=audit,
            limits=AssessmentLimits(spend_limit_usd=0.5),
        )

        # Fallback sections should include dimension narratives (not executive_summary)
        assert len(assessment.fallback_sections) > 0
        assert "executive_summary" not in assessment.fallback_sections


class TestEngineNarrationCoverage:
    """All expected sections are narrated, even under degradation."""

    def test_default_narrator_produces_no_interventions(self):
        """Using the default RuleBasedNarrator incurs no interventions."""
        audit = AuditLog()
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _dummy_collector(
                    "test",
                    dimensions={"data_quality", "operations"},
                    findings=[],
                )),
            ],
            narrator=RuleBasedNarrator(),
            audit=audit,
        )
        assert len(audit.interventions()) == 0

    def test_audit_log_tags_all_actions_with_cohort_and_incident_id(self):
        """Every audit entry is tagged with cohort='assay' and a common incident_id."""
        audit = AuditLog()
        assessment = run_assessment(
            client_name="Test Client",
            collectors=[
                ("col1", lambda: _dummy_collector("col1", dimensions={"data_quality"})),
            ],
            audit=audit,
        )

        # Get all audit entries
        all_entries = audit.events
        assert len(all_entries) > 0

        # All should have cohort='assay'
        for entry in all_entries:
            assert entry.cohort == "assay"

        # All should have the same incident_id
        incident_ids = {e.incident_id for e in all_entries}
        assert len(incident_ids) == 1
        assert incident_ids.pop() == assessment.run_id

    def test_audit_includes_collect_and_narrate_actions(self):
        """Audit log includes 'collect:*' and 'narrate:*' actions."""
        audit = AuditLog()
        run_assessment(
            client_name="Test",
            collectors=[
                ("test-collector", lambda: _dummy_collector(
                    "test-collector",
                    dimensions={"data_quality"},
                )),
            ],
            audit=audit,
        )

        actions = [e.action for e in audit.events]
        collect_actions = [a for a in actions if a.startswith("collect:")]
        narrate_actions = [a for a in actions if a.startswith("narrate:")]

        assert len(collect_actions) > 0
        assert len(narrate_actions) > 0

    def test_max_narrative_sections_limit_enforces_action_cap(self):
        """AssessmentLimits.max_narrative_sections limits the number of sections narrated."""
        call_count = {"count": 0}

        class CountingNarrator:
            def narrate(self, section: str, context: dict[str, object]) -> NarrationResult:
                call_count["count"] += 1
                return NarrationResult(text=f"{section}: {call_count['count']}", cost_usd=0.01)

        audit = AuditLog()
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _dummy_collector(
                    "test",
                    dimensions={
                        "data_quality",
                        "documentation",
                        "governance",
                    },
                )),
            ],
            narrator=CountingNarrator(),
            audit=audit,
            limits=AssessmentLimits(max_narrative_sections=1),
        )

        # Only 1 section should be metered (executive_summary)
        # The rest should degrade to fallback
        assert call_count["count"] == 1
        assert len(assessment.fallback_sections) >= 1


class TestEngineAssessment:
    """Assessment object correctly assembles results."""

    def test_assessment_run_id_is_present(self):
        """Each assessment gets a unique run_id."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _dummy_collector("test")),
            ],
        )
        assert assessment.run_id
        assert len(assessment.run_id) > 0

    def test_assessment_client_name_preserved(self):
        """The client_name is preserved in the assessment."""
        assessment = run_assessment(
            client_name="Acme Inc.",
            collectors=[
                ("test", lambda: _dummy_collector("test")),
            ],
        )
        assert assessment.client_name == "Acme Inc."

    def test_assessment_collects_all_findings(self):
        """All findings from all collectors are in assessment.findings."""
        f1 = Finding(
            dimension="data_quality",
            severity=Severity.HIGH,
            title="F1",
            detail="",
            remediation="",
        )
        f2 = Finding(
            dimension="governance",
            severity=Severity.CRITICAL,
            title="F2",
            detail="",
            remediation="",
        )
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _dummy_collector(
                    "test",
                    dimensions={"data_quality", "governance"},
                    findings=[f1, f2],
                )),
            ],
        )
        assert len(assessment.findings) == 2
        assert f1 in assessment.findings
        assert f2 in assessment.findings

    def test_assessment_scores_all_dimensions(self):
        """assessment.scores has entries for all dimensions."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _dummy_collector("test")),
            ],
        )
        baseline_dims = baseline_config().rubric.dimension_ids()
        assert len(assessment.scores) == len(baseline_dims)
        for dim in baseline_dims:
            assert dim in assessment.scores

    def test_assessment_with_findings_computes_overall_score(self):
        """With findings, overall score is computed from assessed dimensions."""
        findings = [
            Finding(
                dimension="data_quality",
                severity=Severity.HIGH,
                title="Issue",
                detail="",
                remediation="",
            ),
        ]
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _dummy_collector(
                    "test",
                    dimensions={"data_quality"},
                    findings=findings,
                )),
            ],
        )
        # DATA_QUALITY has 1 HIGH finding (25-point deduction) = 75
        assert assessment.overall == 75

    def test_assessment_with_no_findings_has_no_overall_score(self):
        """With no findings and no claimed dimensions, overall_score is None."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _dummy_collector("test")),
            ],
        )
        assert assessment.overall is None
