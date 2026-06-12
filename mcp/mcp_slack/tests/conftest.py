import os

import pytest
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, ".env"))

# All tests/demos run against this channel (the bot must be invited to it).
TEST_CHANNEL = "qbiz_slackbot_testing"


def _have_slack_creds() -> bool:
    return bool(os.environ.get("SLACK_BOT_TOKEN"))


def _have_app_token() -> bool:
    return bool(os.environ.get("SLACK_APP_TOKEN"))


requires_slack = pytest.mark.skipif(
    not _have_slack_creds(),
    reason="SLACK_BOT_TOKEN not set — skipping live Slack tests",
)

requires_socket = pytest.mark.skipif(
    not _have_app_token(),
    reason="SLACK_APP_TOKEN not set — skipping Socket Mode tests",
)


@pytest.fixture
def channel() -> str:
    return TEST_CHANNEL


@pytest.fixture(autouse=True)
def _clear_channel_cache():
    """The channel name->ID cache is module-global; unit tests resolve against a
    fake client, so clear it around every test to prevent cross-test leakage."""
    from slack_mcp import slack_client

    slack_client._channel_cache.clear()
    yield
    slack_client._channel_cache.clear()
