"""Test the Airflow DAG collector — AST parsing of DAG files for operational hygiene.

Tests collection against the acme fixture, specific finding patterns, and error handling
for unparseable Python files.
"""

from pathlib import Path

import pytest

from qbiz_assay.collectors.airflow import collect
from qbiz_assay.findings import Dimension, Severity


class TestAirflowCollectorAgainstAcmeFixture:
    """Test against the acme Airflow DAGs fixture."""

    def test_acme_fixture_statistics(self, acme_dags_dir: Path):
        """Acme fixture should have correct DAG and file counts."""
        result = collect(acme_dags_dir)
        assert result.stats["files_scanned"] == 2
        assert result.stats["dags"] == 2
        assert result.stats["dags_without_failure_callback"] == 2

    def test_acme_orders_pipeline_findings(self, acme_dags_dir: Path):
        """orders_pipeline should produce findings for: no retries, no callback, bad owner, catchup."""
        result = collect(acme_dags_dir)
        # Filter to only orders_pipeline findings
        orders_findings = [f for f in result.findings if "orders_pipeline" in f.subject or "orders" in f.title.lower()]

        # Should have 4 findings: no retries, no callback, no meaningful owner, catchup
        assert len(orders_findings) == 4

        by_severity = {f.severity: f for f in orders_findings}

        # HIGH: no callback
        high_findings = [f for f in orders_findings if f.severity == Severity.HIGH]
        assert len(high_findings) == 1
        assert "failure callback" in high_findings[0].title.lower()
        assert high_findings[0].dimension == Dimension.OPERATIONS

        # MEDIUM: no retries and catchup
        medium_findings = [f for f in orders_findings if f.severity == Severity.MEDIUM]
        assert len(medium_findings) == 2
        medium_titles = [f.title for f in medium_findings]
        assert any("retries" in t.lower() for t in medium_titles)
        assert any("catchup" in t.lower() for t in medium_titles)
        # Both should be in OPERATIONS or COST
        for f in medium_findings:
            assert f.dimension in {Dimension.OPERATIONS, Dimension.COST}

        # LOW: no meaningful owner
        low_findings = [f for f in orders_findings if f.severity == Severity.LOW]
        assert len(low_findings) == 1
        assert "owner" in low_findings[0].title.lower()

    def test_acme_customer_export_findings(self, acme_dags_dir: Path):
        """customer_export should produce ONLY a no-callback finding."""
        result = collect(acme_dags_dir)
        # Filter to only customer_export findings
        export_findings = [f for f in result.findings if "customer_export" in f.subject or "customer_export" in f.title.lower()]

        # Should have exactly 1 finding: no callback
        assert len(export_findings) == 1
        assert "failure callback" in export_findings[0].title.lower()
        assert export_findings[0].severity == Severity.HIGH
        assert export_findings[0].dimension == Dimension.OPERATIONS

    def test_acme_retries_do_not_produce_finding_when_set(self, acme_dags_dir: Path):
        """customer_export has retries=3, so no retries finding should be present."""
        result = collect(acme_dags_dir)
        retries_findings = [f for f in result.findings if "retries" in f.title.lower()]
        # customer_export with retries=3 should not appear
        export_retry_findings = [
            f for f in retries_findings if "customer_export" in f.subject or "customer_export" in f.title.lower()
        ]
        assert len(export_retry_findings) == 0

    def test_acme_owner_set_does_not_produce_finding(self, acme_dags_dir: Path):
        """customer_export has owner='data-eng', so no owner finding should be present."""
        result = collect(acme_dags_dir)
        owner_findings = [f for f in result.findings if "owner" in f.title.lower()]
        export_owner_findings = [
            f for f in owner_findings if "customer_export" in f.subject or "customer_export" in f.title.lower()
        ]
        assert len(export_owner_findings) == 0

    def test_airflow_dimensions_assessed(self, acme_dags_dir: Path):
        """Airflow collector claims it assessed OPERATIONS and COST."""
        result = collect(acme_dags_dir)
        assert result.dimensions == {Dimension.OPERATIONS, Dimension.COST}


class TestAirflowCollectorErrorHandling:
    """Test graceful error handling for broken Python files."""

    def test_syntactically_broken_py_file_yields_low_unparseable_finding(self, tmp_path: Path):
        """A DAG file with syntax errors produces a LOW finding and does not crash."""
        broken_py = tmp_path / "broken.py"
        broken_py.write_text("if True\n  print('missing colon')")

        result = collect(tmp_path)
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.severity == Severity.LOW
        assert "Unparseable" in finding.title
        assert finding.dimension == Dimension.OPERATIONS
        assert "broken.py" in finding.subject

    def test_empty_dags_directory(self, tmp_path: Path):
        """An empty DAGs directory yields no findings."""
        result = collect(tmp_path)
        assert result.stats["files_scanned"] == 0
        assert result.stats["dags"] == 0
        assert result.stats["dags_without_failure_callback"] == 0
        assert len(result.findings) == 0

    def test_multiple_broken_files(self, tmp_path: Path):
        """Multiple broken files each produce a finding."""
        (tmp_path / "broken1.py").write_text("if True\n  syntax error")
        (tmp_path / "broken2.py").write_text("def incomplete(")

        result = collect(tmp_path)
        assert len(result.findings) == 2
        assert all(f.severity == Severity.LOW for f in result.findings)

    def test_classic_dag_style_parsing(self, tmp_path: Path):
        """DAG in classic style DAG(...) constructor is parsed."""
        dag_file = tmp_path / "classic_dag.py"
        dag_file.write_text("""
from airflow import DAG
from datetime import datetime

dag = DAG(
    "my_dag",
    default_args={"owner": "airflow"},
    start_date=datetime(2024, 1, 1),
)
""")
        result = collect(tmp_path)
        assert result.stats["dags"] == 1
        # Should have findings for no retries, no callback, no meaningful owner
        assert len(result.findings) >= 2

    def test_retries_not_configured_produces_finding(self, tmp_path: Path):
        """A DAG with no retries (or retries=0) produces a MEDIUM finding."""
        dag_file = tmp_path / "no_retries.py"
        dag_file.write_text("""
from airflow import DAG
from datetime import datetime

def dummy_callback(context):
    pass

default_args = {"owner": "data-eng", "on_failure_callback": dummy_callback}

dag = DAG(
    "no_retries_dag",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
)
""")
        result = collect(tmp_path)
        retry_findings = [f for f in result.findings if "retries" in f.title.lower()]
        assert len(retry_findings) == 1
        assert retry_findings[0].severity == Severity.MEDIUM

    def test_retries_explicitly_zero_produces_finding(self, tmp_path: Path):
        """A DAG with retries=0 still produces a finding."""
        dag_file = tmp_path / "zero_retries.py"
        dag_file.write_text("""
from airflow import DAG
from datetime import datetime

def dummy_callback(context):
    pass

default_args = {"retries": 0, "owner": "data-eng", "on_failure_callback": dummy_callback}

dag = DAG(
    "zero_retries_dag",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
)
""")
        result = collect(tmp_path)
        retry_findings = [f for f in result.findings if "retries" in f.title.lower()]
        assert len(retry_findings) == 1
        assert retry_findings[0].severity == Severity.MEDIUM

    def test_retries_positive_does_not_produce_finding(self, tmp_path: Path):
        """A DAG with retries > 0 does not produce a retries finding."""
        dag_file = tmp_path / "good_retries.py"
        dag_file.write_text("""
from airflow import DAG
from datetime import datetime

def dummy_callback(context):
    pass

default_args = {"retries": 3, "owner": "data-eng", "on_failure_callback": dummy_callback}

dag = DAG(
    "good_retries_dag",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
)
""")
        result = collect(tmp_path)
        retry_findings = [f for f in result.findings if "retries" in f.title.lower()]
        assert len(retry_findings) == 0

    def test_callback_in_dag_kwargs_prevents_finding(self, tmp_path: Path):
        """on_failure_callback in DAG kwargs prevents the no-callback finding."""
        dag_file = tmp_path / "has_callback.py"
        dag_file.write_text("""
from airflow import DAG
from datetime import datetime

def my_callback(context):
    pass

default_args = {"owner": "data-eng", "retries": 1}

dag = DAG(
    "callback_dag",
    default_args=default_args,
    on_failure_callback=my_callback,
    start_date=datetime(2024, 1, 1),
)
""")
        result = collect(tmp_path)
        callback_findings = [f for f in result.findings if "callback" in f.title.lower()]
        assert len(callback_findings) == 0

    def test_callback_in_default_args_prevents_finding(self, tmp_path: Path):
        """on_failure_callback in default_args prevents the no-callback finding."""
        dag_file = tmp_path / "callback_in_defaults.py"
        dag_file.write_text("""
from airflow import DAG
from datetime import datetime

def my_callback(context):
    pass

default_args = {"on_failure_callback": my_callback, "owner": "data-eng", "retries": 1}

dag = DAG(
    "callback_dag",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
)
""")
        result = collect(tmp_path)
        callback_findings = [f for f in result.findings if "callback" in f.title.lower()]
        assert len(callback_findings) == 0

    def test_catchup_true_produces_cost_finding(self, tmp_path: Path):
        """catchup=True produces a MEDIUM COST finding."""
        dag_file = tmp_path / "catchup_dag.py"
        dag_file.write_text("""
from airflow import DAG
from datetime import datetime

def dummy_callback(context):
    pass

default_args = {"owner": "data-eng", "retries": 1, "on_failure_callback": dummy_callback}

dag = DAG(
    "catchup_dag",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    catchup=True,
)
""")
        result = collect(tmp_path)
        catchup_findings = [f for f in result.findings if "catchup" in f.title.lower()]
        assert len(catchup_findings) == 1
        assert catchup_findings[0].severity == Severity.MEDIUM
        assert catchup_findings[0].dimension == Dimension.COST

    def test_catchup_false_does_not_produce_finding(self, tmp_path: Path):
        """catchup=False does not produce a finding."""
        dag_file = tmp_path / "no_catchup.py"
        dag_file.write_text("""
from airflow import DAG
from datetime import datetime

def dummy_callback(context):
    pass

default_args = {"owner": "data-eng", "retries": 1, "on_failure_callback": dummy_callback}

dag = DAG(
    "no_catchup_dag",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    catchup=False,
)
""")
        result = collect(tmp_path)
        catchup_findings = [f for f in result.findings if "catchup" in f.title.lower()]
        assert len(catchup_findings) == 0

    def test_meaningful_owner_does_not_produce_finding(self, tmp_path: Path):
        """A DAG with a real owner string does not produce an owner finding."""
        dag_file = tmp_path / "good_owner.py"
        dag_file.write_text("""
from airflow import DAG
from datetime import datetime

def dummy_callback(context):
    pass

default_args = {"owner": "data-team", "retries": 1, "on_failure_callback": dummy_callback}

dag = DAG(
    "good_owner_dag",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
)
""")
        result = collect(tmp_path)
        owner_findings = [f for f in result.findings if "owner" in f.title.lower()]
        assert len(owner_findings) == 0

    def test_owner_default_airflow_produces_finding(self, tmp_path: Path):
        """Default owner 'airflow' is flagged."""
        dag_file = tmp_path / "airflow_owner.py"
        dag_file.write_text("""
from airflow import DAG
from datetime import datetime

def dummy_callback(context):
    pass

default_args = {"owner": "airflow", "retries": 1, "on_failure_callback": dummy_callback}

dag = DAG(
    "airflow_owner_dag",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
)
""")
        result = collect(tmp_path)
        owner_findings = [f for f in result.findings if "owner" in f.title.lower()]
        assert len(owner_findings) == 1
        assert owner_findings[0].severity == Severity.LOW
