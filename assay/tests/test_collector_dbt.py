"""Test the dbt collector — manifest parsing and findings generation.

Tests collection statistics, expected findings, and graceful handling of errors
(bad paths, empty manifests, etc.).
"""

import json
from pathlib import Path

import pytest

from qbiz_assay.collectors.dbt import collect
from qbiz_assay.findings import Dimension, Severity


class TestDbtCollectorAgainstAcmeFixture:
    """Test against the acme dbt manifest fixture."""

    def test_acme_fixture_statistics(self, acme_manifest: Path):
        """Acme fixture should have correct model/test/source counts."""
        result = collect(acme_manifest)
        assert result.stats["models"] == 6
        assert result.stats["tests"] == 3
        assert result.stats["sources"] == 2

    def test_acme_fixture_test_coverage_is_33_percent(self, acme_manifest: Path):
        """Acme has 2 of 6 models tested (stg_orders and dim_customers)."""
        result = collect(acme_manifest)
        # 2 models tested out of 6 = 33%
        assert result.stats["test_coverage_pct"] == 33

    def test_acme_fixture_doc_coverage_is_33_percent(self, acme_manifest: Path):
        """Acme has 2 of 6 models with descriptions."""
        result = collect(acme_manifest)
        # stg_orders and dim_customers have descriptions = 2/6 = 33%
        assert result.stats["doc_coverage_pct"] == 33

    def test_acme_fixture_sensitivity_coverage_is_17_percent(self, acme_manifest: Path):
        """Acme has 1 of 6 models with sensitivity classification (dim_customers)."""
        result = collect(acme_manifest)
        # Only dim_customers is classified = 1/6 = 17%
        assert result.stats["sensitivity_coverage_pct"] == 17

    def test_acme_fixture_sources_without_freshness(self, acme_manifest: Path):
        """Acme has 1 source without freshness configured."""
        result = collect(acme_manifest)
        # customers source has freshness=null; orders has freshness rules
        assert result.stats["sources_without_freshness"] == 1

    def test_acme_fixture_expected_findings(self, acme_manifest: Path):
        """Acme fixture generates expected findings."""
        result = collect(acme_manifest)
        findings = result.findings

        # Should have 4 findings:
        # 1. Test coverage (HIGH since < 50%)
        # 2. Documentation coverage (HIGH since < 40%)
        # 3. Sensitivity classification (HIGH since < 50%)
        # 4. Source freshness (MEDIUM)
        assert len(findings) == 4

        # Extract findings by dimension and severity
        by_dim_severity = {
            (f.dimension, f.severity): f for f in findings
        }

        # Test coverage should be HIGH (33% < 50%)
        assert (Dimension.DATA_QUALITY, Severity.HIGH) in by_dim_severity
        tc_finding = by_dim_severity[(Dimension.DATA_QUALITY, Severity.HIGH)]
        assert "Test coverage" in tc_finding.title
        assert "33%" in tc_finding.title

        # Documentation should be HIGH (33% < 40%)
        assert (Dimension.DOCUMENTATION, Severity.HIGH) in by_dim_severity
        doc_finding = by_dim_severity[(Dimension.DOCUMENTATION, Severity.HIGH)]
        assert "Documentation coverage" in doc_finding.title

        # Sensitivity should be HIGH (17% < 50%)
        assert (Dimension.GOVERNANCE, Severity.HIGH) in by_dim_severity
        sens_finding = by_dim_severity[(Dimension.GOVERNANCE, Severity.HIGH)]
        assert "Sensitivity classification" in sens_finding.title

        # Freshness should be MEDIUM
        freshness_findings = [
            f for f in findings
            if "freshness" in f.title.lower()
        ]
        assert len(freshness_findings) == 1
        assert freshness_findings[0].severity == Severity.MEDIUM

    def test_acme_fixture_dimensions_assessed(self, acme_manifest: Path):
        """dbt collector claims it assessed the expected dimensions."""
        result = collect(acme_manifest)
        assert result.dimensions == {
            Dimension.DATA_QUALITY,
            Dimension.DOCUMENTATION,
            Dimension.GOVERNANCE,
        }


class TestDbtCollectorErrorHandling:
    """Test graceful error handling for bad inputs."""

    def test_nonexistent_path_yields_unreadable_finding(self, tmp_path: Path):
        """A nonexistent manifest path produces a single HIGH finding and no crash."""
        result = collect(tmp_path / "nonexistent" / "manifest.json")
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.severity == Severity.HIGH
        assert "unreadable" in finding.title.lower()
        assert finding.dimension == Dimension.DATA_QUALITY

    def test_invalid_json_yields_unreadable_finding(self, tmp_path: Path):
        """A manifest with invalid JSON produces a single HIGH finding."""
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("{ broken json ][")
        result = collect(manifest_path)
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.severity == Severity.HIGH
        assert "unreadable" in finding.title.lower()

    def test_empty_manifest_yields_no_models_finding(self, tmp_path: Path):
        """A manifest with zero models yields a MEDIUM finding."""
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"nodes": {}, "sources": {}}))
        result = collect(manifest_path)
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.severity == Severity.MEDIUM
        assert "No models" in finding.title

    def test_manifest_with_only_tests_no_models(self, tmp_path: Path):
        """A manifest with tests but no models still produces the 'No models' finding."""
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(
            json.dumps({
                "nodes": {
                    "test.acme.some_test": {
                        "resource_type": "test",
                        "depends_on": {"nodes": []},
                    }
                },
                "sources": {},
            })
        )
        result = collect(manifest_path)
        assert len(result.findings) == 1
        assert result.findings[0].title == "No models in the dbt manifest"

    def test_test_coverage_severity_transitions(self):
        """Test coverage is HIGH when < 50%, MEDIUM otherwise."""
        # This is an integration test of the threshold logic
        # HIGH < 50% is checked in the acme fixture test
        # Let's verify MEDIUM when >= 50%
        manifest_data = {
            "nodes": {
                "model.test.m1": {
                    "resource_type": "model",
                    "name": "m1",
                    "description": "",
                    "config": {"meta": {}},
                },
                "model.test.m2": {
                    "resource_type": "model",
                    "name": "m2",
                    "description": "",
                    "config": {"meta": {}},
                },
                "test.test.t1": {
                    "resource_type": "test",
                    "depends_on": {"nodes": ["model.test.m1"]},
                },
            },
            "sources": {},
        }
        # With 2 models and 1 test on m1: 50% coverage
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest_data))
            result = collect(manifest_path)
            # Find test coverage finding
            test_findings = [
                f for f in result.findings
                if "Test coverage" in f.title
            ]
            # At 50%, should be MEDIUM
            assert len(test_findings) == 1
            assert test_findings[0].severity == Severity.MEDIUM

    def test_doc_coverage_severity_transitions(self):
        """Documentation coverage is HIGH when < 40%, MEDIUM otherwise."""
        manifest_data = {
            "nodes": {
                "model.test.m1": {
                    "resource_type": "model",
                    "name": "m1",
                    "description": "Has docs",
                    "config": {"meta": {}},
                },
                "model.test.m2": {
                    "resource_type": "model",
                    "name": "m2",
                    "description": "",
                    "config": {"meta": {}},
                },
                "model.test.m3": {
                    "resource_type": "model",
                    "name": "m3",
                    "description": "",
                    "config": {"meta": {}},
                },
            },
            "sources": {},
        }
        # With 3 models and 1 documented: 33% < 40%, should be HIGH
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest_data))
            result = collect(manifest_path)
            doc_findings = [
                f for f in result.findings
                if "Documentation" in f.title
            ]
            assert len(doc_findings) == 1
            assert doc_findings[0].severity == Severity.HIGH

    def test_sensitivity_coverage_severity_transitions(self):
        """Sensitivity coverage is HIGH when < 50%, MEDIUM otherwise."""
        manifest_data = {
            "nodes": {
                "model.test.m1": {
                    "resource_type": "model",
                    "name": "m1",
                    "description": "",
                    "config": {"meta": {"sensitivity": "public"}},
                },
                "model.test.m2": {
                    "resource_type": "model",
                    "name": "m2",
                    "description": "",
                    "config": {"meta": {}},
                },
            },
            "sources": {},
        }
        # With 2 models and 1 classified: 50%, should be MEDIUM
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest_data))
            result = collect(manifest_path)
            sens_findings = [
                f for f in result.findings
                if "Sensitivity" in f.title
            ]
            assert len(sens_findings) == 1
            assert sens_findings[0].severity == Severity.MEDIUM

    def test_source_with_null_freshness_is_flagged(self):
        """A source with freshness=null is flagged."""
        manifest_data = {
            "nodes": {
                "model.test.m1": {
                    "resource_type": "model",
                    "name": "m1",
                    "description": "",
                    "config": {"meta": {"sensitivity": "public"}},
                },
            },
            "sources": {
                "source.test.raw.t1": {
                    "name": "t1",
                    "freshness": None,
                },
            },
        }
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest_data))
            result = collect(manifest_path)
            freshness_findings = [
                f for f in result.findings
                if "freshness" in f.title.lower()
            ]
            assert len(freshness_findings) == 1
            assert freshness_findings[0].severity == Severity.MEDIUM

    def test_source_with_proper_freshness_is_not_flagged(self):
        """A source with proper freshness config is not flagged."""
        manifest_data = {
            "nodes": {
                "model.test.m1": {
                    "resource_type": "model",
                    "name": "m1",
                    "description": "",
                    "config": {"meta": {"sensitivity": "public"}},
                },
            },
            "sources": {
                "source.test.raw.t1": {
                    "name": "t1",
                    "freshness": {
                        "warn_after": {"count": 12, "period": "hour"},
                        "error_after": {"count": 24, "period": "hour"},
                    },
                },
            },
        }
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest_data))
            result = collect(manifest_path)
            freshness_findings = [
                f for f in result.findings
                if "freshness" in f.title.lower()
            ]
            assert len(freshness_findings) == 0
