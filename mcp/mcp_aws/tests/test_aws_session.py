"""Unit tests for aws_readonly_mcp.aws_session."""

from __future__ import annotations

import datetime
import threading
from unittest.mock import MagicMock, patch

import pytest

from aws_readonly_mcp.aws_session import ConfigError, SessionManager, _env, json_default


# ---------------------------------------------------------------------------
# _env() helper
# ---------------------------------------------------------------------------
class TestEnv:
    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "hello")
        assert _env("SOME_VAR") == "hello"

    def test_returns_default_when_missing(self, monkeypatch):
        monkeypatch.delenv("SOME_VAR", raising=False)
        assert _env("SOME_VAR", "fallback") == "fallback"

    def test_returns_default_when_empty_string(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "")
        assert _env("SOME_VAR", "fallback") == "fallback"

    def test_returns_none_when_missing_and_no_default(self, monkeypatch):
        monkeypatch.delenv("SOME_VAR", raising=False)
        assert _env("SOME_VAR") is None


# ---------------------------------------------------------------------------
# json_default() serialiser
# ---------------------------------------------------------------------------
class TestJsonDefault:
    def test_datetime_serialised_to_iso(self):
        dt = datetime.datetime(2024, 1, 15, 12, 0, 0)
        assert json_default(dt) == "2024-01-15T12:00:00"

    def test_date_serialised_to_iso(self):
        d = datetime.date(2024, 1, 15)
        assert json_default(d) == "2024-01-15"

    def test_bytes_decoded_as_utf8(self):
        assert json_default(b"hello") == "hello"

    def test_bytes_non_utf8_returned_as_hex(self):
        raw = b"\xff\xfe"
        assert json_default(raw) == raw.hex()

    def test_arbitrary_object_stringified(self):
        class Foo:
            def __str__(self):
                return "foo-str"

        assert json_default(Foo()) == "foo-str"


# ---------------------------------------------------------------------------
# SessionManager._load_config()
# ---------------------------------------------------------------------------
REQUIRED_ENV = {
    "AWS_READONLY_ROLE_ARN": "arn:aws:iam::123456789012:role/test-role",
}


class TestLoadConfig:
    def test_raises_when_role_arn_missing(self, monkeypatch):
        monkeypatch.delenv("AWS_READONLY_ROLE_ARN", raising=False)
        with pytest.raises(ConfigError, match="AWS_READONLY_ROLE_ARN"):
            SessionManager._load_config()

    def test_raises_when_role_arn_empty(self, monkeypatch):
        monkeypatch.setenv("AWS_READONLY_ROLE_ARN", "")
        with pytest.raises(ConfigError, match="AWS_READONLY_ROLE_ARN"):
            SessionManager._load_config()

    def test_minimal_config(self, monkeypatch):
        monkeypatch.setenv("AWS_READONLY_ROLE_ARN", "arn:aws:iam::123:role/r")
        for key in [
            "AWS_READONLY_REGION", "AWS_REGION", "AWS_DEFAULT_REGION",
            "AWS_READONLY_EXTERNAL_ID", "AWS_READONLY_SESSION_NAME",
            "AWS_READONLY_DURATION", "AWS_PROFILE",
        ]:
            monkeypatch.delenv(key, raising=False)

        cfg = SessionManager._load_config()

        assert cfg["role_arn"] == "arn:aws:iam::123:role/r"
        assert cfg["region"] is None
        assert cfg["external_id"] is None
        assert cfg["session_name"] == "aws-readonly-mcp"  # default
        assert cfg["duration"] == 3600                    # default
        assert cfg["profile"] is None

    def test_region_fallback_chain(self, monkeypatch):
        monkeypatch.setenv("AWS_READONLY_ROLE_ARN", "arn:aws:iam::123:role/r")
        monkeypatch.delenv("AWS_READONLY_REGION", raising=False)
        monkeypatch.setenv("AWS_REGION", "eu-west-1")
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

        cfg = SessionManager._load_config()
        assert cfg["region"] == "eu-west-1"

    def test_region_readonly_takes_priority(self, monkeypatch):
        monkeypatch.setenv("AWS_READONLY_ROLE_ARN", "arn:aws:iam::123:role/r")
        monkeypatch.setenv("AWS_READONLY_REGION", "us-west-2")
        monkeypatch.setenv("AWS_REGION", "eu-west-1")

        cfg = SessionManager._load_config()
        assert cfg["region"] == "us-west-2"

    def test_full_config(self, monkeypatch):
        monkeypatch.setenv("AWS_READONLY_ROLE_ARN", "arn:aws:iam::123:role/r")
        monkeypatch.setenv("AWS_READONLY_REGION", "us-east-1")
        monkeypatch.setenv("AWS_READONLY_EXTERNAL_ID", "ext-id-123")
        monkeypatch.setenv("AWS_READONLY_SESSION_NAME", "my-session")
        monkeypatch.setenv("AWS_READONLY_DURATION", "900")
        monkeypatch.setenv("AWS_PROFILE", "prod")

        cfg = SessionManager._load_config()

        assert cfg["role_arn"] == "arn:aws:iam::123:role/r"
        assert cfg["region"] == "us-east-1"
        assert cfg["external_id"] == "ext-id-123"
        assert cfg["session_name"] == "my-session"
        assert cfg["duration"] == 900
        assert cfg["profile"] == "prod"

    def test_invalid_duration_raises_config_error(self, monkeypatch):
        monkeypatch.setenv("AWS_READONLY_ROLE_ARN", "arn:aws:iam::123:role/r")
        monkeypatch.setenv("AWS_READONLY_DURATION", "not-a-number")
        with pytest.raises(ConfigError, match="AWS_READONLY_DURATION"):
            SessionManager._load_config()

    def test_external_id_absent_when_not_set(self, monkeypatch):
        monkeypatch.setenv("AWS_READONLY_ROLE_ARN", "arn:aws:iam::123:role/r")
        monkeypatch.delenv("AWS_READONLY_EXTERNAL_ID", raising=False)

        cfg = SessionManager._load_config()
        assert cfg["external_id"] is None


# ---------------------------------------------------------------------------
# SessionManager.session() — caching behaviour
# ---------------------------------------------------------------------------
class TestSessionCaching:
    def _make_manager(self):
        """Return a fresh SessionManager with _build_session stubbed out."""
        mgr = SessionManager()
        mock_session = MagicMock()
        mgr._build_session = MagicMock(return_value=mock_session)
        return mgr, mock_session

    def test_session_built_once(self):
        mgr, mock_session = self._make_manager()
        s1 = mgr.session()
        s2 = mgr.session()
        assert s1 is s2
        mgr._build_session.assert_called_once()

    def test_session_is_thread_safe(self):
        mgr, _ = self._make_manager()
        results = []

        def get_session():
            results.append(mgr.session())

        threads = [threading.Thread(target=get_session) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads must receive the same session object.
        assert len(set(id(s) for s in results)) == 1
        # _build_session must only have been called once.
        mgr._build_session.assert_called_once()


# ---------------------------------------------------------------------------
# SessionManager.client() — caching behaviour
# ---------------------------------------------------------------------------
class TestClientCaching:
    def _make_manager(self):
        mgr = SessionManager()
        mgr._default_region = "us-east-1"
        mock_session = MagicMock()
        mgr._session = mock_session          # skip _build_session
        return mgr, mock_session

    def test_client_cached_by_service_and_region(self):
        mgr, mock_session = self._make_manager()
        c1 = mgr.client("s3", "us-east-1")
        c2 = mgr.client("s3", "us-east-1")
        assert c1 is c2
        mock_session.client.assert_called_once()

    def test_different_regions_produce_different_clients(self):
        mgr, mock_session = self._make_manager()
        mgr.client("s3", "us-east-1")
        mgr.client("s3", "eu-west-1")
        assert mock_session.client.call_count == 2

    def test_different_services_produce_different_clients(self):
        mgr, mock_session = self._make_manager()
        mgr.client("s3")
        mgr.client("iam")
        assert mock_session.client.call_count == 2

    def test_falls_back_to_default_region(self):
        mgr, mock_session = self._make_manager()
        mgr._default_region = "ap-southeast-1"
        mgr.client("s3")
        mock_session.client.assert_called_once_with("s3", region_name="ap-southeast-1")

    def test_explicit_region_overrides_default(self):
        mgr, mock_session = self._make_manager()
        mgr._default_region = "us-east-1"
        mgr.client("s3", "eu-central-1")
        mock_session.client.assert_called_once_with("s3", region_name="eu-central-1")


# ---------------------------------------------------------------------------
# SessionManager.whoami()
# ---------------------------------------------------------------------------
class TestWhoami:
    def test_whoami_returns_expected_shape(self):
        mgr = SessionManager()
        mgr._default_region = "us-west-2"

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/test-role/session",
            "UserId": "AROA000000000000:session",
        }
        mgr.client = MagicMock(return_value=mock_sts)

        result = mgr.whoami()

        mgr.client.assert_called_once_with("sts")
        assert result == {
            "account": "123456789012",
            "arn": "arn:aws:sts::123456789012:assumed-role/test-role/session",
            "user_id": "AROA000000000000:session",
            "default_region": "us-west-2",
        }

    def test_whoami_handles_missing_fields_gracefully(self):
        mgr = SessionManager()
        mgr._default_region = None

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {}  # all fields absent
        mgr.client = MagicMock(return_value=mock_sts)

        result = mgr.whoami()

        assert result["account"] is None
        assert result["arn"] is None
        assert result["user_id"] is None
        assert result["default_region"] is None
