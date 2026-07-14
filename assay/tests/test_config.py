"""Test the config registries — baseline loading, parsing errors, and override merging."""

import pytest

from qbiz_assay.config import (
    ConfigError,
    apply_overrides,
    baseline_config,
    load_config,
    parse_config,
)
from qbiz_assay.findings import Severity


class TestBaseline:
    def test_baseline_loads_six_dimensions_in_order(self):
        config = baseline_config()
        assert config.rubric.dimension_ids() == (
            "data_quality",
            "documentation",
            "governance",
            "operations",
            "cost",
            "ai_governance",
        )

    def test_baseline_severity_weights_match_phase1_defaults(self):
        weights = baseline_config().rubric.severity_weights
        assert weights[Severity.CRITICAL] == 40
        assert weights[Severity.HIGH] == 25
        assert weights[Severity.MEDIUM] == 10
        assert weights[Severity.LOW] == 4
        assert weights[Severity.INFO] == 0

    def test_baseline_offering_titles_resolve(self):
        config = baseline_config()
        assert config.offering_title("dbt_startup_kit") == "Qbiz dbt Startup Kit"
        assert config.offering_title("agent_harness") == "Qbiz Agent Harness"

    def test_uncataloged_offering_id_displays_as_itself(self):
        assert baseline_config().offering_title("mystery_offering") == "mystery_offering"

    def test_unregistered_dimension_gets_placeholder_spec(self):
        rubric = baseline_config().rubric
        spec = rubric.spec_for("cloud_posture")
        assert spec.title == "cloud_posture"
        assert spec.weight == 1.0

    def test_load_config_reads_the_same_shape_from_a_path(self, tmp_path):
        yaml_text = """
rubric:
  severity_weights: {critical: 50, high: 20, medium: 5, low: 1, info: 0}
  bands:
    - {min: 60, name: Fine}
    - {min: 0, name: Not Fine}
  dimensions:
    - {id: only_dim, title: The Only Dimension}
offerings: {}
"""
        path = tmp_path / "custom.yaml"
        path.write_text(yaml_text, encoding="utf-8")
        config = load_config(path)
        assert config.rubric.dimension_ids() == ("only_dim",)
        assert config.rubric.band_for(59) == "Not Fine"


class TestParseErrors:
    def test_missing_rubric_section_raises(self):
        with pytest.raises(ConfigError, match="rubric"):
            parse_config({"offerings": {}})

    def test_unknown_severity_raises(self):
        with pytest.raises(ConfigError, match="unknown severity"):
            parse_config(
                {
                    "rubric": {
                        "severity_weights": {"catastrophic": 99},
                        "bands": [{"min": 0, "name": "X"}],
                        "dimensions": [{"id": "d"}],
                    }
                }
            )

    def test_bands_without_zero_floor_raise(self):
        with pytest.raises(ConfigError, match="min: 0"):
            parse_config(
                {
                    "rubric": {
                        "severity_weights": {},
                        "bands": [{"min": 50, "name": "Top Half Only"}],
                        "dimensions": [{"id": "d"}],
                    }
                }
            )

    def test_dimension_without_id_raises(self):
        with pytest.raises(ConfigError, match="id"):
            parse_config(
                {
                    "rubric": {
                        "severity_weights": {},
                        "bands": [{"min": 0, "name": "X"}],
                        "dimensions": [{"title": "No id here"}],
                    }
                }
            )


class TestOverrides:
    def test_dimension_field_override_keeps_unlisted_fields(self):
        config = apply_overrides(
            baseline_config(),
            {"rubric": {"dimensions": [{"id": "data_quality", "weight": 2.5}]}},
        )
        spec = config.rubric.spec_for("data_quality")
        assert spec.weight == 2.5
        assert spec.title == "Data Quality & Testing"  # kept from baseline

    def test_new_dimension_id_is_appended(self):
        config = apply_overrides(
            baseline_config(),
            {
                "rubric": {
                    "dimensions": [
                        {"id": "cloud_posture", "title": "Cloud Security Posture"}
                    ]
                }
            },
        )
        assert config.rubric.dimension_ids()[-1] == "cloud_posture"
        assert config.rubric.title_for("cloud_posture") == "Cloud Security Posture"

    def test_severity_weights_merge_per_severity(self):
        config = apply_overrides(
            baseline_config(), {"rubric": {"severity_weights": {"low": 8}}}
        )
        assert config.rubric.severity_weights[Severity.LOW] == 8
        assert config.rubric.severity_weights[Severity.CRITICAL] == 40  # untouched

    def test_bands_replace_wholesale(self):
        config = apply_overrides(
            baseline_config(),
            {"rubric": {"bands": [{"min": 90, "name": "Elite"}, {"min": 0, "name": "Rest"}]}},
        )
        assert config.rubric.band_for(89) == "Rest"
        assert config.rubric.band_for(95) == "Elite"

    def test_offering_retitle_and_addition(self):
        config = apply_overrides(
            baseline_config(),
            {
                "offerings": {
                    "incident_agent": {"title": "Managed Incident Response"},
                    "cloud_security_review": {"title": "Cloud Security Review"},
                }
            },
        )
        assert config.offering_title("incident_agent") == "Managed Incident Response"
        assert config.offering_title("cloud_security_review") == "Cloud Security Review"
        assert config.offering_title("dbt_startup_kit") == "Qbiz dbt Startup Kit"

    def test_empty_overrides_change_nothing(self):
        base = baseline_config()
        merged = apply_overrides(base, {})
        assert merged.rubric.dimension_ids() == base.rubric.dimension_ids()
        assert merged.rubric.bands == base.rubric.bands
        assert set(merged.offerings) == set(base.offerings)
