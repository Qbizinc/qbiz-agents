"""Test scaffold for a new collector — copy this file alongside your copy of
collectors/TEMPLATE.py and adapt. The shape to keep:

- build a minimal fixture in ``tmp_path`` (artifact mode) or a fake tool caller (connected),
- call ``collect()`` directly — the decorator returns the function unchanged,
- assert on ``stats``, finding titles/severities/dimensions,
- and always cover the messy-input path: findings, never exceptions.

Keep fixtures free of secret-shaped literals (see conftest.planted_secret_line / SECURITY.md).

These tests also keep TEMPLATE.py honest: the example consultants copy from always compiles,
registers, and passes.
"""

from qbiz_assay.collectors import AcquisitionMode, get_collector
from qbiz_assay.collectors.TEMPLATE import NAME, collect
from qbiz_assay.findings import Severity


class TestTemplateCollector:
    def test_registers_with_declared_metadata(self):
        info = get_collector(NAME).info
        assert info.mode is AcquisitionMode.ARTIFACT
        assert set(info.inputs) == {"file_path"}
        assert info.dimensions == {"documentation"}

    def test_counts_lines_in_a_readable_file(self, tmp_path):
        f = tmp_path / "notes.txt"
        f.write_text("one\ntwo\nthree\n", encoding="utf-8")
        result = collect(file_path=f)
        assert result.stats == {"lines": 3}
        assert result.findings == []

    def test_empty_file_yields_info_finding(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = collect(file_path=f)
        [finding] = result.findings
        assert finding.severity is Severity.INFO
        assert result.stats == {"lines": 0}

    def test_unreadable_input_is_a_finding_not_an_exception(self, tmp_path):
        result = collect(file_path=tmp_path / "does-not-exist.txt")
        [finding] = result.findings
        assert finding.severity is Severity.LOW
        assert "unreadable" in finding.title.lower()
