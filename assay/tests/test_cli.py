"""Test the qba CLI — list-collectors output and profile-driven runs."""

from pathlib import Path

from qbiz_assay.cli import main


def _write_pulse_profile(tmp_path: Path, acme_root: Path) -> Path:
    path = tmp_path / "profile.yaml"
    path.write_text(
        f"""
client: CLI Test Co
mode: pulse
collectors:
  - name: dbt-manifest
    inputs:
      manifest_path: "{(acme_root / 'dbt' / 'manifest.json').as_posix()}"
""",
        encoding="utf-8",
    )
    return path


class TestListCollectors:
    def test_lists_every_builtin_with_mode_and_inputs(self, capsys):
        assert main(["assay", "list-collectors"]) == 0
        out = capsys.readouterr().out
        for name in ("dbt-manifest", "airflow-dags", "ai-usage", "aws-cloud-posture"):
            assert name in out
        assert "[artifact]" in out
        assert "[connected]" in out
        assert "requires MCP server(s): aws" in out
        assert "manifest_path" in out


class TestRun:
    def test_run_writes_report_and_audit(self, tmp_path, acme_root, capsys):
        profile = _write_pulse_profile(tmp_path, acme_root)
        report = tmp_path / "REPORT.md"
        audit = tmp_path / "audit.jsonl"
        code = main(
            ["assay", "run", str(profile), "--report", str(report), "--audit", str(audit)]
        )
        assert code == 0
        text = report.read_text(encoding="utf-8")
        assert "CLI Test Co" in text
        assert "## Scorecard" in text
        assert audit.exists() and audit.stat().st_size > 0

    def test_run_prints_report_to_stdout_by_default(self, tmp_path, acme_root, capsys):
        profile = _write_pulse_profile(tmp_path, acme_root)
        assert main(["assay", "run", str(profile)]) == 0
        out = capsys.readouterr().out
        assert "# Data & AI Readiness Assessment — CLI Test Co" in out

    def test_run_invalid_profile_exits_2_with_error(self, tmp_path, capsys):
        bad = tmp_path / "bad.yaml"
        bad.write_text("client: X\ncollectors: []\n", encoding="utf-8")
        assert main(["assay", "run", str(bad)]) == 2
        assert "error:" in capsys.readouterr().err

    def test_run_missing_file_exits_2(self, tmp_path, capsys):
        assert main(["assay", "run", str(tmp_path / "nope.yaml")]) == 2
        assert "error:" in capsys.readouterr().err
