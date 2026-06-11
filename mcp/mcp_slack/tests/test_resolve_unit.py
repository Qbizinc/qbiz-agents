"""Unit tests for the pure resolution helpers — no network, fully mocked."""
from slack_mcp import slack_client


class _FakeClient:
    """Stands in for slack_sdk.WebClient: returns a fixed channel list."""

    def __init__(self, channels):
        self._channels = channels

    def conversations_list(self, **kwargs):
        return {"channels": self._channels, "response_metadata": {}}


def test_resolve_channel_by_name(monkeypatch):
    fake = _FakeClient([
        {"id": "C123", "name": "qbiz_slackbot_testing"},
        {"id": "C999", "name": "general"},
    ])
    monkeypatch.setattr(slack_client, "_client", fake)

    assert slack_client.resolve_channel("#qbiz_slackbot_testing") == "C123"
    assert slack_client.resolve_channel("qbiz_slackbot_testing") == "C123"


def test_resolve_channel_passes_through_id(monkeypatch):
    # A value that already looks like a channel ID should not trigger a lookup.
    monkeypatch.setattr(slack_client, "_client", _FakeClient([]))
    assert slack_client.resolve_channel("C0B8KNHG1QD") == "C0B8KNHG1QD"


def test_resolve_channel_unknown_raises(monkeypatch):
    monkeypatch.setattr(slack_client, "_client", _FakeClient([{"id": "C1", "name": "general"}]))
    try:
        slack_client.resolve_channel("does-not-exist")
    except ValueError as exc:
        assert "does-not-exist" in str(exc)
    else:
        raise AssertionError("expected ValueError for unknown channel")
