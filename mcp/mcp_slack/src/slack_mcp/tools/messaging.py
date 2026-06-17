from slack_mcp._app import mcp
from slack_mcp.slack_client import get_client, resolve_channel, resolve_user_id


@mcp.tool()
def send_message(channel: str, text: str, thread_ts: str | None = None) -> str:
    """Post a message to a Slack channel or append to an existing thread.

    Args:
        channel: Channel name (e.g. #data-incidents) or channel ID.
        text: Message text. Supports Slack mrkdwn formatting.
        thread_ts: Timestamp of the parent message to reply in its thread.
            Omit to start a new top-level message.

    Returns:
        The message timestamp (ts). Pass this as thread_ts in follow-up calls
        to append further messages to the same thread.
    """
    client = get_client()
    channel_id = resolve_channel(channel)
    kwargs: dict = {"channel": channel_id, "text": text}
    if thread_ts:
        kwargs["thread_ts"] = thread_ts
    response = client.chat_postMessage(**kwargs)
    return response["ts"]


@mcp.tool()
def send_dm(user: str, text: str) -> str:
    """Send a direct message to a Slack user.

    Args:
        user: User's display name, real name, or email address.
        text: Message text.

    Returns:
        The message timestamp (ts).
    """
    client = get_client()
    user_id = resolve_user_id(user)
    dm = client.conversations_open(users=user_id)
    channel_id = dm["channel"]["id"]
    response = client.chat_postMessage(channel=channel_id, text=text)
    return response["ts"]


@mcp.tool()
def add_reaction(channel: str, timestamp: str, emoji: str) -> str:
    """Add an emoji reaction to a Slack message.

    Args:
        channel: Channel name or ID where the message lives.
        timestamp: The message timestamp (ts) returned by send_message.
        emoji: Emoji name without colons (e.g. "white_check_mark", "thumbsup").

    Returns:
        "ok" on success.
    """
    client = get_client()
    channel_id = resolve_channel(channel)
    client.reactions_add(channel=channel_id, timestamp=timestamp, name=emoji)
    return "ok"
