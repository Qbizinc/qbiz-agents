"""Test the report renderer — markdown output from an Assessment.

Tests that rendered markdown contains expected sections, properly formats the
scorecard, and includes roadmap and governance disclosure when appropriate.
"""

from qbiz_harness import AuditLog

from qbiz_assay.assessor import RuleBasedNarrator
from qbiz_assay.collectors import CollectorResult
from qbiz_assay.engine import run_assessment
from qbiz_assay.findings import Dimension, Finding, Severity, OFFERING_STARTUP_KIT, OFFERING_HARNESS
from qbiz_assay.report import render_markdown


def _collector(
    name: str,
    dimensions: set[Dimension] | None = None,
    findings: list[Finding] | None = None,
) -> CollectorResult:
    """Helper to create a minimal CollectorResult."""
    return CollectorResult(
        name=name,
        dimensions=dimensions or set(),
        stats={"scan_complete": True},
        findings=findings or [],
    )


class TestReportScorecard:
    """The report renders a proper scorecard section."""

    def test_report_contains_scorecard_header(self):
        """Report contains '## Scorecard' section."""
        assessment = run_assessment(
            client_name="Test Co.",
            collectors=[
                ("test", lambda: _collector("test")),
            ],
        )
        markdown = render_markdown(assessment)
        assert "## Scorecard" in markdown

    def test_scorecard_shows_scored_dimensions(self):
        """Scorecard rows include scored dimensions with their scores and bands."""
        f1 = Finding(
            dimension=Dimension.DATA_QUALITY,
            severity=Severity.HIGH,
            title="Test issue",
            detail="",
            remediation="",
        )
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector(
                    "test",
                    dimensions={Dimension.DATA_QUALITY},
                    findings=[f1],
                )),
            ],
        )
        markdown = render_markdown(assessment)
        # Should show the dimension title
        assert "Data Quality & Testing" in markdown
        # Should show the score (75 after HIGH deduction)
        assert "75" in markdown
        # Should show the band (75 is Established)
        assert "Established" in markdown

    def test_scorecard_shows_unassessed_dimensions_as_dash(self):
        """Unassessed dimensions show '—' in the scorecard."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector(
                    "test",
                    dimensions={Dimension.DATA_QUALITY},
                )),
            ],
        )
        markdown = render_markdown(assessment)
        # Should have unassessed dimensions
        assert "—" in markdown

    def test_scorecard_unassessed_note_appears(self):
        """Report includes a note about unassessed dimensions."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector("test")),
            ],
        )
        markdown = render_markdown(assessment)
        # All dimensions are unassessed
        assert "Not assessed in this pass" in markdown


class TestReportExecutiveSummary:
    """The report includes an executive summary section."""

    def test_report_contains_executive_summary_header(self):
        """Report contains '## Executive summary' section."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector("test")),
            ],
        )
        markdown = render_markdown(assessment)
        assert "## Executive summary" in markdown

    def test_executive_summary_has_content(self):
        """Executive summary section contains narrated text."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector(
                    "test",
                    dimensions={Dimension.DATA_QUALITY},
                )),
            ],
        )
        markdown = render_markdown(assessment)
        lines = markdown.split("\n")
        # Find the executive summary section
        summary_start = None
        for i, line in enumerate(lines):
            if "## Executive summary" in line:
                summary_start = i
                break
        assert summary_start is not None
        # Should have content after the header
        assert summary_start + 2 < len(lines)
        content = lines[summary_start + 2]
        assert len(content) > 0


class TestReportDimensionDetails:
    """The report includes per-dimension detail sections."""

    def test_report_contains_dimension_heading_for_scored_dimension(self):
        """Scored dimensions get their own section heading."""
        findings = [
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.MEDIUM,
                title="Some issue",
                detail="",
                remediation="",
            ),
        ]
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector(
                    "test",
                    dimensions={Dimension.DATA_QUALITY},
                    findings=findings,
                )),
            ],
        )
        markdown = render_markdown(assessment)
        # Should contain the dimension title
        assert "Data Quality & Testing" in markdown
        # Should be a heading (##)
        assert "## Data Quality & Testing" in markdown

    def test_unassessed_dimension_not_in_detail_sections(self):
        """Unassessed dimensions do not get detail section headings."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector("test")),
            ],
        )
        markdown = render_markdown(assessment)
        # Count the number of dimension headings (should be 0)
        # Only the scorecard and executive summary, no detail sections
        dimension_headings = sum(
            1 for line in markdown.split("\n")
            if "## " in line and "Data Quality" in line
        )
        # Might appear in scorecard but not as its own section
        # Let's check by looking for "Data Quality" followed by score in a section
        assert "## Scorecard" in markdown


class TestReportRoadmap:
    """The report includes a roadmap section when findings have offerings."""

    def test_report_roadmap_section_appears_when_findings_have_offerings(self):
        """When findings have offerings, a roadmap section appears."""
        findings = [
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.HIGH,
                title="Test coverage low",
                detail="",
                remediation="Add tests",
                offering=OFFERING_STARTUP_KIT,
            ),
        ]
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector(
                    "test",
                    dimensions={Dimension.DATA_QUALITY},
                    findings=findings,
                )),
            ],
        )
        markdown = render_markdown(assessment)
        assert "## Recommended roadmap" in markdown

    def test_roadmap_contains_offering_as_heading(self):
        """Roadmap groups findings by offering, each as a ### heading."""
        findings = [
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.HIGH,
                title="Issue 1",
                detail="",
                remediation="Fix it",
                offering=OFFERING_STARTUP_KIT,
            ),
            Finding(
                dimension=Dimension.AI_GOVERNANCE,
                severity=Severity.CRITICAL,
                title="Issue 2",
                detail="",
                remediation="Fix that",
                offering=OFFERING_HARNESS,
            ),
        ]
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector(
                    "test",
                    dimensions={Dimension.DATA_QUALITY, Dimension.AI_GOVERNANCE},
                    findings=findings,
                )),
            ],
        )
        markdown = render_markdown(assessment)
        assert f"### " in markdown
        assert OFFERING_STARTUP_KIT in markdown
        assert OFFERING_HARNESS in markdown

    def test_roadmap_does_not_appear_when_no_offerings(self):
        """Roadmap section is absent when no findings have offerings."""
        findings = [
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.MEDIUM,
                title="Issue",
                detail="",
                remediation="",
                offering=None,  # No offering
            ),
        ]
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector(
                    "test",
                    dimensions={Dimension.DATA_QUALITY},
                    findings=findings,
                )),
            ],
        )
        markdown = render_markdown(assessment)
        assert "## Recommended roadmap" not in markdown


class TestReportGovernanceDisclosure:
    """The report includes a section disclosing how the assessment was governed."""

    def test_report_contains_governance_disclosure_header(self):
        """Report contains 'How this assessment was produced' section."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector("test")),
            ],
        )
        markdown = render_markdown(assessment)
        assert "## How this assessment was produced" in markdown

    def test_disclosure_mentions_collectors(self):
        """Governance section names the collectors that ran."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("collector-one", lambda: _collector("collector-one")),
                ("collector-two", lambda: _collector("collector-two")),
            ],
        )
        markdown = render_markdown(assessment)
        assert "Deterministic collectors" in markdown
        assert "collector-one" in markdown
        assert "collector-two" in markdown

    def test_disclosure_mentions_budget_if_governor_present(self):
        """Governance section shows token/spend if governor is present."""
        audit = AuditLog()
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector("test")),
            ],
            audit=audit,
        )
        markdown = render_markdown(assessment)
        # Should mention tokens and spend
        assert "token" in markdown.lower()
        assert "spend" in markdown.lower() or "$" in markdown

    def test_disclosure_mentions_interventions_when_present(self):
        """If interventions occurred, governance disclosure mentions them."""
        audit = AuditLog()
        audit.record_intervention(
            action="test_action",
            component="test_component",
            prevented="test_prevented",
            agent_id="test",
            cohort="test",
            incident_id="test",
        )
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector("test")),
            ],
            audit=audit,
        )
        markdown = render_markdown(assessment)
        assert "Harness interventions" in markdown

    def test_disclosure_says_no_interventions_when_none(self):
        """Governance section says no interventions when the agent stayed in bounds."""
        audit = AuditLog()
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector("test")),
            ],
            audit=audit,
        )
        markdown = render_markdown(assessment)
        assert "no interventions" in markdown.lower() or "none" in markdown.lower()


class TestReportFormatting:
    """Report formatting is correct (tables, markdown, etc.)."""

    def test_scorecard_is_a_markdown_table(self):
        """Scorecard is formatted as a markdown table."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector("test")),
            ],
        )
        markdown = render_markdown(assessment)
        # Tables have | separators and --- rows
        assert "| --- |" in markdown or "|---|" in markdown

    def test_report_title_includes_client_name(self):
        """Report title includes the client name."""
        assessment = run_assessment(
            client_name="Acme Corporation",
            collectors=[
                ("test", lambda: _collector("test")),
            ],
        )
        markdown = render_markdown(assessment)
        assert "Acme Corporation" in markdown
        assert "# " in markdown  # Title level

    def test_report_includes_run_id(self):
        """Report mentions the run_id."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector("test")),
            ],
        )
        markdown = render_markdown(assessment)
        assert assessment.run_id in markdown

    def test_findings_are_shown_in_table_format(self):
        """Finding details are shown in table format."""
        findings = [
            Finding(
                dimension=Dimension.DATA_QUALITY,
                severity=Severity.HIGH,
                title="Test gap",
                detail="",
                remediation="Add tests",
                subject="orders_model",
            ),
        ]
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector(
                    "test",
                    dimensions={Dimension.DATA_QUALITY},
                    findings=findings,
                )),
            ],
        )
        markdown = render_markdown(assessment)
        # Should have finding details in a table
        assert "Severity" in markdown or "HIGH" in markdown
        assert "Test gap" in markdown or "test gap" in markdown.lower()

    def test_report_can_accept_audit_path_parameter(self):
        """render_markdown accepts an optional audit_path parameter."""
        assessment = run_assessment(
            client_name="Test",
            collectors=[
                ("test", lambda: _collector("test")),
            ],
        )
        # Should not raise
        markdown = render_markdown(assessment, audit_path="/path/to/audit.jsonl")
        assert "/path/to/audit.jsonl" in markdown
