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
