"""Test the collector registry — registration, discovery, and mode constraints."""

import pytest

from qbiz_assay.collectors import (
    AcquisitionMode,
    CollectorResult,
    all_collectors,
    collector,
    get_collector,
)


class TestBuiltinDiscovery:
    def test_builtin_collectors_are_discoverable(self):
        names = {c.name for c in all_collectors()}
        assert {"dbt-manifest", "airflow-dags", "ai-usage", "aws-cloud-posture"} <= names

    def test_registry_is_name_sorted(self):
        names = [c.name for c in all_collectors()]
        assert names == sorted(names)

    def test_get_collector_returns_metadata_and_callable(self):
        registered = get_collector("dbt-manifest")
        assert registered.info.mode is AcquisitionMode.ARTIFACT
        assert "manifest_path" in registered.info.inputs
        assert callable(registered.fn)

    def test_get_collector_unknown_name_lists_known(self):
        with pytest.raises(KeyError, match="dbt-manifest"):
            get_collector("no-such-collector")

    def test_phase1_collectors_are_artifact_mode_with_no_mcp(self):
        for name in ("dbt-manifest", "airflow-dags", "ai-usage"):
            info = get_collector(name).info
            assert info.mode is AcquisitionMode.ARTIFACT
            assert info.requires_mcp == ()

    def test_cloud_posture_is_connected_and_declares_aws(self):
        info = get_collector("aws-cloud-posture").info
        assert info.mode is AcquisitionMode.CONNECTED
        assert info.requires_mcp == ("aws",)
        assert info.dimensions == {"cloud_posture"}


class TestRegistrationConstraints:
    def test_duplicate_name_raises(self):
        @collector(
            name="registry-test-duplicate",
            dimensions={"data_quality"},
            mode=AcquisitionMode.ARTIFACT,
            inputs={},
        )
        def first(**_kw) -> CollectorResult:
            return CollectorResult(name="registry-test-duplicate")

        with pytest.raises(ValueError, match="already registered"):
            @collector(
                name="registry-test-duplicate",
                dimensions={"data_quality"},
                mode=AcquisitionMode.ARTIFACT,
                inputs={},
            )
            def second(**_kw) -> CollectorResult:
                return CollectorResult(name="registry-test-duplicate")

    def test_re_registering_the_same_function_is_idempotent(self):
        def fn(**_kw) -> CollectorResult:
            return CollectorResult(name="registry-test-idempotent")

        decorate = collector(
            name="registry-test-idempotent",
            dimensions={"data_quality"},
            mode=AcquisitionMode.ARTIFACT,
            inputs={},
        )
        assert decorate(fn) is fn
        assert decorate(fn) is fn  # e.g. a module imported twice under two names

    def test_artifact_mode_rejects_requires_mcp(self):
        with pytest.raises(ValueError, match="artifact mode"):
            collector(
                name="registry-test-artifact-mcp",
                dimensions={"data_quality"},
                mode=AcquisitionMode.ARTIFACT,
                inputs={},
                requires_mcp=("aws",),
            )

    def test_connected_mode_requires_mcp_declaration(self):
        with pytest.raises(ValueError, match="reuse-over-duplication"):
            collector(
                name="registry-test-connected-bare",
                dimensions={"cloud_posture"},
                mode=AcquisitionMode.CONNECTED,
                inputs={},
            )

    def test_decorator_returns_function_unchanged(self):
        def fn(**_kw) -> CollectorResult:
            return CollectorResult(name="registry-test-unchanged")

        decorated = collector(
            name="registry-test-unchanged",
            dimensions=set(),
            mode=AcquisitionMode.ARTIFACT,
            inputs={},
        )(fn)
        assert decorated is fn
