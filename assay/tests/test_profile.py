"""Test engagement profiles — loading, validation, the pulse-tier hard constraint, and
profile-driven runs end to end."""

from pathlib import Path

import pytest

from qbiz_assay.profile import (
    DeliveryMode,
    ProfileError,
    build_collector_specs,
    load_profile,
    run_profile,
)

PULSE_PROFILE = """
client: Acme Analytics
mode: pulse
collectors:
  - name: dbt-manifest
    inputs:
      manifest_path: "{acme}/dbt/manifest.json"
  - name: airflow-dags
    inputs:
      dags_dir: "{acme}/dags"
  - name: ai-usage
    inputs:
      repo_dir: "{acme}"
rubric:
  dimensions:
    - id: data_quality
      weight: 2.0
offerings:
  incident_agent:
    title: Managed Incident Response
limits:
  spend_limit_usd: 1.0
"""


def _write_profile(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "profile.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def pulse_profile_path(tmp_path: Path, acme_root: Path) -> Path:
    return _write_profile(
        tmp_path, PULSE_PROFILE.format(acme=acme_root.as_posix())
    )


class TestLoadProfile:
    def test_loads_client_mode_collectors_and_limits(self, pulse_profile_path):
        profile = load_profile(pulse_profile_path)
        assert profile.client == "Acme Analytics"
        assert profile.mode is DeliveryMode.PULSE
        assert [c.name for c in profile.collectors] == [
            "dbt-manifest",
            "airflow-dags",
            "ai-usage",
        ]
        assert profile.limits.spend_limit_usd == 1.0
        assert profile.limits.token_limit == 60_000  # unlisted fields keep defaults

    def test_rubric_and_offering_overrides_are_applied(self, pulse_profile_path):
        profile = load_profile(pulse_profile_path)
        assert profile.config.rubric.weight_for("data_quality") == 2.0
        assert profile.config.offering_title("incident_agent") == "Managed Incident Response"

    def test_relative_artifact_paths_resolve_against_profile_dir(self, tmp_path, acme_root):
        import shutil

        shutil.copy(acme_root / "dbt" / "manifest.json", tmp_path / "manifest.json")
        path = _write_profile(
            tmp_path,
            """
client: Rel Path Co
collectors:
  - name: dbt-manifest
    inputs:
      manifest_path: manifest.json
""",
        )
        profile = load_profile(path)
        resolved = profile.collectors[0].inputs["manifest_path"]
        assert Path(resolved).is_absolute()
        assert Path(resolved).exists()

    def test_unknown_collector_name_fails_with_known_list(self, tmp_path):
        path = _write_profile(
            tmp_path,
            """
client: X
collectors:
  - name: not-a-collector
    inputs: {}
""",
        )
        with pytest.raises(ProfileError, match="dbt-manifest"):
            load_profile(path)

    def test_missing_required_input_fails_at_load(self, tmp_path):
        path = _write_profile(
            tmp_path,
            """
client: X
collectors:
  - name: dbt-manifest
""",
        )
        with pytest.raises(ProfileError, match="manifest_path"):
            load_profile(path)

    def test_missing_client_fails(self, tmp_path):
        path = _write_profile(tmp_path, "collectors: [{name: dbt-manifest}]")
        with pytest.raises(ProfileError, match="client"):
            load_profile(path)

    def test_unknown_limits_field_fails(self, tmp_path, acme_root):
        path = _write_profile(
            tmp_path,
            f"""
client: X
collectors:
  - name: ai-usage
    inputs:
      repo_dir: "{acme_root.as_posix()}"
limits:
  spend_cap: 1.0
""",
        )
        with pytest.raises(ProfileError, match="spend_cap"):
            load_profile(path)


class TestPulseHardConstraint:
    def test_pulse_profile_rejects_connected_collector(self, tmp_path):
        """The zero-credential property of the pulse tier is enforced, not advisory."""
        path = _write_profile(
            tmp_path,
            """
client: X
mode: pulse
collectors:
  - name: aws-cloud-posture
    inputs:
      aws_call: "mcp:aws"
""",
        )
        with pytest.raises(ProfileError, match="pulse"):
            load_profile(path)

    def test_full_profile_accepts_connected_collector(self, tmp_path):
        path = _write_profile(
            tmp_path,
            """
client: X
mode: full
collectors:
  - name: aws-cloud-posture
    inputs:
      aws_call: "mcp:aws"
""",
        )
        profile = load_profile(path)
        assert profile.mode is DeliveryMode.FULL

    def test_connected_collector_without_tool_caller_fails_before_running(self, tmp_path):
        path = _write_profile(
            tmp_path,
            """
client: X
mode: full
collectors:
  - name: aws-cloud-posture
    inputs:
      aws_call: "mcp:aws"
""",
        )
        profile = load_profile(path)
        with pytest.raises(ProfileError, match="tool caller"):
            build_collector_specs(profile, tool_callers={})

    def test_connected_collector_binds_supplied_tool_caller(self, tmp_path):
        path = _write_profile(
            tmp_path,
            """
client: X
mode: full
collectors:
  - name: aws-cloud-posture
    inputs:
      aws_call: "mcp:aws"
""",
        )
        profile = load_profile(path)

        def fake_aws(tool: str, _args: dict) -> object:
            return [] if tool in ("s3_list_buckets", "iam_list_policies") else None

        assessment = run_profile(profile, tool_callers={"aws": fake_aws})
        assert assessment.scores["cloud_posture"].score == 100


class TestRunProfile:
    def test_pulse_run_end_to_end_uses_overridden_config(self, pulse_profile_path):
        assessment = run_profile(pulse_profile_path)
        assert assessment.client_name == "Acme Analytics"
        # All three artifact collectors ran…
        assert {r.name for r in assessment.collector_results} == {
            "dbt-manifest",
            "airflow-dags",
            "ai-usage",
        }
        # …the acme fixtures produce findings, and the overridden config travels with the
        # assessment (report rendering picks up the retitled offering from it).
        assert assessment.findings
        assert assessment.overall is not None
        assert assessment.config.offering_title("incident_agent") == "Managed Incident Response"
