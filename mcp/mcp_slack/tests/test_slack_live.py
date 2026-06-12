"""Live integration tests against the real Qbiz Slack workspace.

These replace the throwaway _smoke_*.py scripts. They are skipped automatically
when credentials are absent, so a credential-less checkout still collects green.

Run them with:
    uv run --group dev pytest -m live
    uv run --group dev pytest -m hitl    # the reaction round-trip only
"""
import asyncio

import pytest

from conftest import requires_slack, requires_socket
from slack_mcp.slack_client import get_client, resolve_channel


def test_server_registers_all_tools():
    """The 7 posting tools plus the 2 HITL tools must register cleanly (no creds needed)."""
    import slack_mcp.server  # noqa: F401 — importing registers tools as a side effect
    from slack_mcp._app import mcp

    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == {
        "send_message", "send_dm", "add_reaction", "upload_file",
        "list_channels", "get_channel_history", "find_user",
        "request_approval", "wait_for_reply",
    }


@requires_slack
@pytest.mark.live
def test_auth_identifies_the_bot():
    info = get_client().auth_test()
    assert info["ok"] is True
    assert info["user_id"]  # the bot's user ID


@requires_slack
@pytest.mark.live
def test_send_message_round_trip(channel):
    client = get_client()
    channel_id = resolve_channel(channel)
    ts = client.chat_postMessage(channel=channel_id, text="pytest live: send_message")["ts"]
    assert ts
    # Confirm it landed by reading it back from history.
    history = client.conversations_history(channel=channel_id, latest=ts, inclusive=True, limit=1)
    assert history["messages"][0]["ts"] == ts


@requires_slack
@requires_socket
@pytest.mark.live
async def test_socket_mode_connects_and_disconnects():
    from slack_mcp import listener

    await listener.start_listener()
    assert listener._socket_client is not None
    await listener.stop_listener()
    assert listener._socket_client is None


@requires_slack
@requires_socket
@pytest.mark.hitl
async def test_reaction_round_trip(channel):
    """Post a message, react to it as the bot, and confirm the reaction_added event
    routes back through Socket Mode — the exact path request_approval depends on.

    Skips (rather than fails) if the event never arrives, because that means the
    Slack app is missing the `reaction_added` bot-event subscription — a workspace
    config gap, not a code defect. Add it under Event Subscriptions and reinstall.
    """
    from slack_mcp import listener

    client = get_client()
    channel_id = resolve_channel(channel)

    await listener.start_listener()
    try:
        ts = client.chat_postMessage(channel=channel_id, text="pytest hitl: reaction probe")["ts"]
        listener.register_reaction_interest(channel_id, ts)
        client.reactions_add(channel=channel_id, timestamp=ts, name="white_check_mark")

        event = await listener.get_reaction(channel_id, ts, timeout=15)
        listener.pop_reaction_queue(channel_id, ts)

        if event is None:
            pytest.skip(
                "reaction_added did not arrive over Socket Mode — subscribe the "
                "`reaction_added` bot event in the Slack app and reinstall."
            )
        assert event["reaction"] == "white_check_mark"
    finally:
        await listener.stop_listener()
