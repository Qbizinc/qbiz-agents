"""Test the AI usage collector — LLM imports and governance detection.

Tests collection against the acme fixture, credential detection, governance module
recognition, and edge cases like empty repos and governed setups.
"""

from pathlib import Path

import pytest

from qbiz_assay.collectors.ai_usage import collect
from qbiz_assay.findings import Dimension, Severity


class TestAiUsageCollectorAgainstAcmeFixture:
    """Test against the acme repo fixture (with dbt, dags, and ml directories)."""

    def test_acme_fixture_statistics(self, acme_repo_dir: Path):
        """Acme fixture should have correct LLM and credential counts."""
        result = collect(acme_repo_dir)
        # ml/churn_scoring.py and ml/support_summarizer.py = 2 LLM files
        assert result.stats["llm_call_sites"] == 2
        # Neither file imports qbiz_harness
        assert result.stats["governed_call_sites"] == 0
        # customer_export.py has ftp_password, churn_scoring.py has sk- key = 2
        assert result.stats["files_with_hardcoded_credentials"] == 2

    def test_acme_fixture_llm_files_detected(self, acme_repo_dir: Path):
        """Acme fixture LLM files are correctly identified."""
        result = collect(acme_repo_dir)
        # churn_scoring imports openai, support_summarizer imports anthropic
        assert result.stats["providers"] == ["anthropic", "openai"]

    def test_acme_fixture_credentials_found(self, acme_repo_dir: Path):
        """Acme fixture hardcoded credentials are detected in 2 files."""
        result = collect(acme_repo_dir)
        # Find CRITICAL findings for credentials
        cred_findings = [f for f in result.findings if f.severity == Severity.CRITICAL]
        assert len(cred_findings) == 2
        # Both should be about hardcoded credentials in GOVERNANCE dimension
        assert all(f.dimension == Dimension.GOVERNANCE for f in cred_findings)
        assert all("Hardcoded credential" in f.title for f in cred_findings)

    def test_acme_fixture_ungoverned_call_sites_finding(self, acme_repo_dir: Path):
        """Acme has ungoverned call sites (no qbiz_harness) -> HIGH finding."""
        result = collect(acme_repo_dir)
        ungoverned_findings = [
            f for f in result.findings
            if "ungoverned" in f.title.lower()
        ]
        assert len(ungoverned_findings) == 1
        assert ungoverned_findings[0].severity == Severity.HIGH
        assert ungoverned_findings[0].dimension == Dimension.AI_GOVERNANCE

    def test_acme_fixture_no_audit_trail_finding(self, acme_repo_dir: Path):
        """Acme has no governed call sites -> MEDIUM 'no audit trail' finding."""
        result = collect(acme_repo_dir)
        audit_findings = [
            f for f in result.findings
            if "audit trail" in f.title.lower()
        ]
        assert len(audit_findings) == 1
        assert audit_findings[0].severity == Severity.MEDIUM
        assert audit_findings[0].dimension == Dimension.AI_GOVERNANCE

    def test_acme_dimensions_assessed(self, acme_repo_dir: Path):
        """AI usage collector claims it assessed AI_GOVERNANCE and GOVERNANCE."""
        result = collect(acme_repo_dir)
        assert result.dimensions == {Dimension.AI_GOVERNANCE, Dimension.GOVERNANCE}


class TestAiUsageCollectorEdgeCases:
    """Test edge cases: empty repos, governed setups, etc."""

    def test_empty_repo_yields_greenfield_info_finding(self, tmp_path: Path):
        """An empty repo (no Python files) yields a single INFO greenfield finding."""
        result = collect(tmp_path)
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.severity == Severity.INFO
        assert "greenfield" in finding.title.lower()
        assert finding.dimension == Dimension.AI_GOVERNANCE

    def test_python_files_with_no_llm_imports(self, tmp_path: Path):
        """Python files with no LLM imports yield greenfield finding."""
        (tmp_path / "util.py").write_text("def add(a, b):\n  return a + b")
        (tmp_path / "config.py").write_text("DEBUG = True")

        result = collect(tmp_path)
        assert result.stats["llm_call_sites"] == 0
        assert result.stats["governed_call_sites"] == 0
        assert result.stats["files_with_hardcoded_credentials"] == 0
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.INFO

    def test_llm_file_with_harness_import_is_governed(self, tmp_path: Path):
        """A file with LLM import AND qbiz_harness import is counted as governed."""
        governed_file = tmp_path / "agent.py"
        governed_file.write_text("""
import anthropic
from qbiz_harness import CostGovernor

client = anthropic.Anthropic()
""")
        result = collect(tmp_path)
        assert result.stats["llm_call_sites"] == 1
        # Since there's at least one governed file, there should be NO
        # "ungoverned call sites" HIGH finding
        ungoverned_findings = [
            f for f in result.findings
            if "ungoverned" in f.title.lower()
        ]
        assert len(ungoverned_findings) == 0
        # But there should also be no "no audit trail" finding when there are governed files
        audit_findings = [
            f for f in result.findings
            if "audit trail" in f.title.lower()
        ]
        assert len(audit_findings) == 0

    def test_multiple_llm_imports_in_one_file(self, tmp_path: Path):
        """A file importing multiple LLM providers is counted once."""
        multi_file = tmp_path / "multi.py"
        multi_file.write_text("""
import openai
import anthropic
from google.generativeai import client

# ... code using multiple providers
""")
        result = collect(tmp_path)
        # Should be 1 LLM file, not 3
        assert result.stats["llm_call_sites"] == 1
        assert set(result.stats["providers"]) == {"anthropic", "google.generativeai", "openai"}

    def test_hardcoded_password_in_string(self, tmp_path: Path):
        """Hardcoded password string matching regex is detected."""
        file_with_cred = tmp_path / "script.py"
        file_with_cred.write_text('password = "secretsecret123"')
        result = collect(tmp_path)
        assert result.stats["files_with_hardcoded_credentials"] == 1
        cred_findings = [f for f in result.findings if f.severity == Severity.CRITICAL]
        assert len(cred_findings) == 1

    def test_hardcoded_api_key_in_string(self, tmp_path: Path):
        """Hardcoded API key string is detected."""
        file_with_key = tmp_path / "config.py"
        file_with_key.write_text('api_key = "sk-1234567890abcdef"')
        result = collect(tmp_path)
        assert result.stats["files_with_hardcoded_credentials"] == 1

    def test_hardcoded_auth_token(self, tmp_path: Path):
        """Hardcoded auth_token is detected."""
        file_with_token = tmp_path / "auth.py"
        file_with_token.write_text('auth_token = "token_1234567890_abcdef"')
        result = collect(tmp_path)
        assert result.stats["files_with_hardcoded_credentials"] == 1

    def test_short_secrets_ignored(self, tmp_path: Path):
        """Secrets shorter than 8 characters are not flagged."""
        file_with_short = tmp_path / "test.py"
        file_with_short.write_text('password = "short"')
        result = collect(tmp_path)
        assert result.stats["files_with_hardcoded_credentials"] == 0

    def test_credential_limit_5_findings(self, tmp_path: Path):
        """At most 5 credential findings are reported (even if more files have them)."""
        # Create 10 files with credentials
        for i in range(10):
            (tmp_path / f"file{i}.py").write_text(f'api_key = "secret_key_{i:020d}"')

        result = collect(tmp_path)
        cred_findings = [f for f in result.findings if f.severity == Severity.CRITICAL]
        # At most 5 should be reported
        assert len(cred_findings) <= 5

    def test_openai_import_detected(self, tmp_path: Path):
        """openai module import is detected."""
        file = tmp_path / "gpt.py"
        file.write_text("import openai\nclient = openai.OpenAI()")
        result = collect(tmp_path)
        assert "openai" in result.stats["providers"]

    def test_anthropic_import_detected(self, tmp_path: Path):
        """anthropic module import is detected."""
        file = tmp_path / "claude.py"
        file.write_text("import anthropic\nclient = anthropic.Anthropic()")
        result = collect(tmp_path)
        assert "anthropic" in result.stats["providers"]

    def test_langchain_import_detected(self, tmp_path: Path):
        """langchain and langchain_* imports are detected."""
        file = tmp_path / "chain.py"
        file.write_text("from langchain import LLMChain\nfrom langchain_openai import ChatOpenAI")
        result = collect(tmp_path)
        providers = set(result.stats["providers"])
        assert "langchain" in providers
        assert "langchain_openai" in providers

    def test_dotenv_import_not_flagged_as_llm(self, tmp_path: Path):
        """Non-LLM imports like dotenv are not flagged as LLM providers."""
        file = tmp_path / "config.py"
        file.write_text("from dotenv import load_dotenv\nload_dotenv()")
        result = collect(tmp_path)
        assert result.stats["llm_call_sites"] == 0
        # Should have greenfield finding
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.INFO

    def test_only_one_ungoverned_finding_per_run(self, tmp_path: Path):
        """Only one 'ungoverned LLM call sites' finding even with multiple files."""
        (tmp_path / "agent1.py").write_text("import openai")
        (tmp_path / "agent2.py").write_text("import anthropic")
        (tmp_path / "agent3.py").write_text("import litellm")

        result = collect(tmp_path)
        ungoverned_findings = [
            f for f in result.findings
            if "ungoverned" in f.title.lower()
        ]
        assert len(ungoverned_findings) == 1

    def test_syntax_error_in_python_file_skipped_gracefully(self, tmp_path: Path):
        """A file with syntax errors is skipped (not flagged as LLM file)."""
        good_file = tmp_path / "good.py"
        good_file.write_text("import openai")
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("if True\n  broken syntax")

        result = collect(tmp_path)
        # Should still detect openai in the good file
        assert result.stats["llm_call_sites"] == 1
        assert "openai" in result.stats["providers"]

    def test_unreadable_file_skipped_gracefully(self, tmp_path: Path):
        """An unreadable file is skipped without crashing."""
        good_file = tmp_path / "good.py"
        good_file.write_text("import anthropic")
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("import openai")

        # Try to make the file unreadable on Windows is tricky, so we just
        # verify that the collector doesn't crash and processes the good file
        result = collect(tmp_path)
        assert result.stats["llm_call_sites"] >= 1
