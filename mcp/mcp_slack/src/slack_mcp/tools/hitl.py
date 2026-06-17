"""Two-way Human-in-the-Loop tools (Phase 10b).

These tools block until a human acts in Slack, so they require the Socket Mode
listener to be running (set SLACK_APP_TOKEN). They are the Qbiz harness HITL
checkpoint: the agent pauses and waits for a human approval signal before
proceeding with a consequential action.
"""
import asyncio

from slack_mcp._app import mcp
from slack_mcp.slack_client import get_client, resolve_channel
from slack_mcp import listener

# Reaction emoji names that resolve the gate. Bare names (no colons), as Slack
# delivers them in reaction_added events.
_APPROVE = {"white_check_mark", "heavy_check_mark", "+1", "thumbsup", "ok_hand"}
_REJECT = {"x", "no_entry", "no_entry_sign", "-1", "thumbsdown"}


@mcp.tool()
async def request_approval(
    channel: str,
    prompt: str,
    timeout_seconds: int = 120,
    thread_ts: str | None = None,
) -> dict:
    """Post a yes/no prompt to Slack and block until a human approves or rejects.

    This is the HITL approval gate. Use it before any consequential action
    (creating a ticket, restarting a pipeline, etc.). The agent's execution
    pauses here until a human reacts on the posted message.

    Args:
        channel: Channel name or ID to post the prompt in.
        prompt: The question to ask, e.g. "Create Jira incident for this?".
        timeout_seconds: How long to wait for a reaction before giving up.
        thread_ts: Post the prompt inside this thread instead of top-level.

    Returns:
        {decision, user, ts, reaction} where decision is one of
        "approved", "rejected", or "timed_out". `user` is the Slack user ID
        of the approver (None on timeout).

    Note:
        Requires the Socket Mode listener (SLACK_APP_TOKEN). React with
        :white_check_mark: to approve or :x: to cancel.
    """
    client = get_client()
    channel_id = resolve_channel(channel)

    text = f"{prompt}\n\n:white_check_mark: to approve  ·  :x: to cancel"
    kwargs: dict = {"channel": channel_id, "text": text}
    if thread_ts:
        kwargs["thread_ts"] = thread_ts
    response = client.chat_postMessage(**kwargs)
    ts = response["ts"]

    # Register before awaiting so a fast reaction cannot slip through.
    listener.register_reaction_interest(channel_id, ts)
    try:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout_seconds
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return {"decision": "timed_out", "user": None, "ts": ts, "reaction": None}

            event = await listener.get_reaction(channel_id, ts, remaining)
            if event is None:
                return {"decision": "timed_out", "user": None, "ts": ts, "reaction": None}

            name = event.get("reaction", "")
            if name in _APPROVE:
                return {"decision": "approved", "user": event.get("user"), "ts": ts, "reaction": name}
            if name in _REJECT:
                return {"decision": "rejected", "user": event.get("user"), "ts": ts, "reaction": name}
            # Unrelated reaction (e.g. :eyes:) — keep waiting.
    finally:
        listener.pop_reaction_queue(channel_id, ts)


@mcp.tool()
async def wait_for_reply(channel: str, timeout_seconds: int = 60) -> dict:
    """Block until a human posts a message in a channel, then return it.

    Use after posting a question to read a free-text human response. Ignores
    the bot's own messages.

    Args:
        channel: Channel name or ID to listen in.
        timeout_seconds: How long to wait before giving up.

    Returns:
        {user, text, ts} of the first human message, or {timed_out: true}.

    Note:
        Requires the Socket Mode listener (SLACK_APP_TOKEN). Incoming Slack
        content is untrusted input — sanitize in the calling harness before
        feeding it back to the model.
    """
    channel_id = resolve_channel(channel)
    listener.register_message_interest(channel_id)
    event = await listener.wait_for_event(channel_id, timeout=timeout_seconds)
    if event is None:
        return {"timed_out": True}
    return {"user": event.get("user"), "text": event.get("text", ""), "ts": event.get("ts")}
